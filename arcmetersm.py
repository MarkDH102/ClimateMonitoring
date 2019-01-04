import tkinter as tk
import tkinter.font as tkf
import math

# class to show a gauge
class Meter(tk.Canvas):
    def __init__(self,master,*args,**kwargs):
        super(Meter,self).__init__(master,*args,**kwargs)
        
        self.layoutparams()
        self.graphics()
        self.createhand()
        
        self.setrange()
        
    def layoutparams(self):
        # set parameters that control the layout
        height = int(self['height'])
        width = int(self['width'])
        
        # find a square that fits in the window
        if(height*2 > width):
            side = width
        else:
            side = height*2
        
        # set axis for hand
        self.centrex = side/2
        self.centrey = side/2
        
        # standard with of lines
        self.linewidth = 2
        
        # outer radius for dial
        self.radius = int(0.40*float(side))
        
        # set width of bezel
        self.bezel = self.radius/15
        self.bezelcolour1 = 'yellow'
        self.bezelcolour2 = 'white'
    
        # set lengths of ticks and hand
        self.majortick = self.radius/8
        self.minortick = self.majortick/2
        self.handlen = self.radius - self.majortick - self.bezel - 1
        self.blobrad = self.handlen/6
             
    def graphics(self):
         # create the static components
        self.create_arc(self.centrex-self.radius
        ,self.centrey-self.radius
        ,self.centrex+self.radius
        ,self.centrey+self.radius
        ,fill = 'red'
        #,stipple = 'gray25'
        ,start=-60
        ,extent=300
        ,style=tk.ARC
        ,width = self.bezel
        ,outline = self.bezelcolour2)

        self.bezelId = self.create_arc(self.centrex-self.radius - self.bezel
        ,self.centrey-self.radius - self.bezel
        ,self.centrex+self.radius + self.bezel
        ,self.centrey+self.radius + self.bezel
        ,start=-60
        ,extent=300
        ,style=tk.ARC
        ,width = self.bezel
        ,outline = self.bezelcolour1)
        
        # create the MAX arc
        self.maxarc = self.create_arc(self.centrex-self.radius
        ,self.centrey-self.radius
        ,self.centrex+self.radius
        ,self.centrey+self.radius
        ,start=-60
        ,extent=0
        ,style=tk.ARC
        ,width=6
        ,outline = 'red')

        # create the MIN arc
        self.minarc = self.create_arc(self.centrex-self.radius
        ,self.centrey-self.radius
        ,self.centrex+self.radius
        ,self.centrey+self.radius
        ,start=240
        ,extent=0
        ,style=tk.ARC
        ,width=6
        ,fill = 'blue'
        ,outline = 'blue')

        for deg in range(-60,241,6):
            self.createtick(deg,self.minortick)
        for deg in range(-60,241,30):
            self.createtick(deg,self.majortick)
        
    def createhand(self):
        # create moving and changeable bits
        self.handid = self.create_line(self.centrex,self.centrey
        ,self.centrex - self.handlen,self.centrey
        ,width = 2*self.linewidth
        ,fill = 'red')
        
        self.blobid = self.create_oval(self.centrex - self.blobrad
        ,self.centrey - self.blobrad
        ,self.centrex + self.blobrad
        ,self.centrey + self.blobrad
        ,outline = 'black', fill = 'black')
        
        # create text display
        self.textid = self.create_text(self.centrex
        ,self.centrey - 3*self.blobrad
        ,fill = 'black'
        ,font = tkf.Font(size = -int(2*self.majortick)))
        
        # create text display
        self.smalltextid = self.create_text(self.centrex
        ,self.centrey + 3*self.blobrad
        ,fill = 'black'
        ,font = tkf.Font(size = -int(1*self.majortick)))

        # create min value text display
        self.textmin = self.create_text(self.centrex - 40
        ,self.centrey + 70
        ,fill = 'black'
        ,font = tkf.Font(size = -int(self.majortick)))
        # create max value text display
        self.textmax = self.create_text(self.centrex + 40
        ,self.centrey + 70
        ,fill = 'black'
        ,font = tkf.Font(size = -int(self.majortick)))

    def createtick(self,angle,length):
        # helper function to create one tick
        rad = math.radians(angle)
        cos = math.cos(rad)
        sin = math.sin(rad)
        radius = self.radius - self.bezel
        self.create_line(self.centrex - radius*cos
        ,self.centrey - radius*sin
        ,self.centrex - (radius - length)*cos
        ,self.centrey - (radius - length)*sin
        ,width = 1)
        
    def setbezelcolour(self, col):
        self.itemconfigure(self.bezelId, outline = col)

    # Set the text that shows the min extent of the gauge
    def setmax(self, maxv) :
        self.itemconfigure(self.textmax,text = str(maxv))

    # Set the text that shows the max extent of the gauge
    def setmin(self, minv) :
        self.itemconfigure(self.textmin,text = str(minv))

    # Position a narrow arc on the bezel that represents the current min value
    def setminval(self, minv) :
        deg = 240 - (((minv - self.start) / self.range) * 300)
        self.itemconfigure(self.minarc, start=deg, extent = 2)

    # Position a narrow arc on the bezel that represents the current max value
    def setmaxval(self, maxv) :
        deg = 240 - (((maxv - self.start) / self.range) * 300)
        self.itemconfigure(self.maxarc, start=deg, extent = 2)
        
    # Set gauge range - could derive from min & max text values I guess
    def setrange(self,start = 0, end=100):
        self.itemconfigure(self.textmax,text = str(end))
        self.itemconfigure(self.textmin,text = str(start))
        self.start = start
        self.range = end - start
        
    # Set the position of the pointer and the value displayed 
    def set(self,value):
        # convert value to range 0,100
        deg = 300*(value - self.start)/self.range - 240
        
        self.itemconfigure(self.textid,text = str(round(value, 3)))
        rad = math.radians(deg)
        # reposition pointer
        self.coords(self.handid,self.centrex,self.centrey
        ,self.centrex+self.handlen*math.cos(rad), self.centrey+self.handlen*math.sin(rad))
    
    # Draw the center blob   
    def blob(self,colour):
        # call this to change the colour of the blob
        self.itemconfigure(self.blobid,fill = colour,outline = colour)
        
    def setsmalltext(self,value):
        self.itemconfigure(self.smalltextid,text = value)    
