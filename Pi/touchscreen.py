# ============================================================================
# The start of the code that deals with the serial touchscreen LCD.
# This needs to go into a different module eventually
# screen is set to run at 9600 by default, but I ramp it up to 115200
# ============================================================================

import serial
import time
import constants as const

class screen:

    def __init__(self):

        self._screenSerialPort = 0 
        self._screenReplyBuffer = []
        self._screenDetected = False    
        self._replyFromScreen = False 
        self._touchCount = 0
        self._screenIsAsleep = False
        # Get some common constants from the imported file
        self.CONST = const._Const()
       
    def LCDdispose(self):

        if self._screenDetected == True :
            self._screenSerialPort.close()


    # ============================================================================
    # GPIO serial port is always connected to the serial LCD touchscreen
    # ============================================================================
    def LCDgetSerialPort(self, rate, flush):

        try:
            # This worked on the old Pi - bloody typical
            #self._screenSerialPort = serial.Serial('/dev/ttyAMA0', rate, timeout = 0.5, rtscts = 0)
            self._screenSerialPort = serial.Serial('/dev/serial0', rate, timeout = 0.5, rtscts = 0)

            if flush == True :
                # Clear any display startup junk from the input serial buffers
                self._screenSerialPort.flushInput()

            self._screenDetected = True

            return 1

        except (OSError, serial.SerialException):
            pass        

        return 0

    # ============================================================================
    # Set serial touch screen baud rate to 115200
    # ============================================================================
    def LCDsetBaudRate(self) :

        if self._screenDetected == False :
            print("No Screen")
            return

        self._screenSerialPort.write(b'\x00')
        self._screenSerialPort.write(b'\x26')
        self._screenSerialPort.write(b'\x00')
        self._screenSerialPort.write(b'\x0D')

        # Give it time to send the characters out before closing the port!!!
        time.sleep(0.2)
        # Unit will change and reply with an ACK at the new baud rate after 100mS

        self._screenSerialPort.close()

        self.LCDgetSerialPort(115200, False)
        self.LCDcheckResponse(1)

    # ============================================================================
    # Read an expected count of bytes from the serial touch screen
    # ============================================================================
    def LCDcheckResponse(self, count):

        if self._screenDetected == False :
            return

        self._replyFromScreen = False
        self._screenReplyBuffer = []
        x = '0'
        r = 0
        # allow at least 100mS for the baud rate change message ACK to arrive...
        t = time.time() + 0.15

        f = count

        if count == 99 :
            count = 1
        while (self._screenSerialPort.inWaiting() != count) and (time.time() < t) :
            time.sleep(0.001)
            # print time.time() ,
            # print t
            c = 0

        c = 0
        d = self._screenSerialPort.inWaiting()
        # Allow 5 seconds for display to respond
        t = time.time() + 5.0
        while (c < d) and (time.time() < t) :
            self._replyFromScreen = True
            #print ("Got data")
            x = self._screenSerialPort.read()
            self._screenReplyBuffer.append(ord(x))
            if ord(x) == 6 :
                if f == 99 :
                    print ("ACK") ,
                r = 1
            elif ord(x) == 21 :
                y = 0
                if f == 99 :
                    print ("NAK") ,
            else :
                y = 0
                if f == 99 :
                    print (ord(x)) ,
            c = c + 1

        if f == 99 :
            #print (t) ,
            #print ("    ") ,
            #print (time.time())
            f = 0

        return x

    # ============================================================================
    # Draw a raised button at x,y with text t and fixed colours, font
    # ============================================================================
    def LCDdrawButton(self, x, y, t) :

        if self._screenDetected == False :
            return
 
        xL = int(x) % 256
        xH = int(x / 256)
        yL = int(y) % 256
        yH = int(y / 256)

        # Send the command to draw button
        self._screenSerialPort.write(b'\x00')
        self._screenSerialPort.write(b'\x11')
        # State 0 = pressed 1 = raised
        self._screenSerialPort.write(b'\x00')
        self._screenSerialPort.write(b'\x01')
        # x coord
        self._screenSerialPort.write(bytes([xH]))
        self._screenSerialPort.write(bytes([xL]))
        # y coord
        self._screenSerialPort.write(bytes([yH]))
        self._screenSerialPort.write(bytes([yL]))
        # button colour (fix at white FFFF for now...)
        self._screenSerialPort.write(b'\xFF')
        self._screenSerialPort.write(b'\xFF')
        # text colour (fix at black 0000 for now...)
        self._screenSerialPort.write(b'\x00')
        self._screenSerialPort.write(b'\x00')
        # font (fix at 0-system for now...)
        self._screenSerialPort.write(b'\x00')
        self._screenSerialPort.write(b'\x00')
        # font text width multiplier (fix at 1 for now...)
        self._screenSerialPort.write(b'\x00')
        self._screenSerialPort.write(b'\x01')
        # font text height multiplier  (fix at 1 for now...)
        self._screenSerialPort.write(b'\x00')
        self._screenSerialPort.write(b'\x01')
        # the text
        for c in t:
            self._screenSerialPort.write(bytes(c, 'UTF-8'))

        # And terminate with a NUL
        self._screenSerialPort.write(b'\x00')

        # ACK
        self.LCDcheckResponse(1)

    # ============================================================================
    # Send the two bytes down to set a colour - use from other LCD commands only
    # ============================================================================
    def p_LCDwriteColourBytes(self, colour) :

        if self._screenDetected == False :
            return
 
        if colour == self.CONST.BLUE :
            self._screenSerialPort.write(b'\x00')
            self._screenSerialPort.write(b'\x1F')
        elif colour == self.CONST.RED :
            self._screenSerialPort.write(b'\xF8')
            self._screenSerialPort.write(b'\x00')
        elif colour == self.CONST.YELLOW :
            self._screenSerialPort.write(b'\xFF')
            self._screenSerialPort.write(b'\xE0')
        elif colour == self.CONST.GREEN :
            self._screenSerialPort.write(b'\x04')
            self._screenSerialPort.write(b'\x00')
        elif colour == self.CONST.ORANGE :
            self._screenSerialPort.write(b'\xFD')
            self._screenSerialPort.write(b'\x20')
        elif colour == self.CONST.WHITE :
            self._screenSerialPort.write(b'\xFF')
            self._screenSerialPort.write(b'\xFF')
        elif colour == self.CONST.BLACK :
            self._screenSerialPort.write(b'\x00')
            self._screenSerialPort.write(b'\x00')
        
    # ============================================================================
    # Set a pixel at the x,y coordinates with colour
    # ============================================================================
    def LCDsetPixel(self, x, y, colour) :

        if self._screenDetected == False :
            return
 
        xL = int(x) % 256
        xH = int(x / 256)
        yL = int(y) % 256
        yH = int(y / 256)

        if xL < 0 :
            xL = 0
        if xL > 255 :
            xL = 255
        if xH < 0 :
            xH = 0
        if xH > 255 :
            xH = 255
        if yL < 0 :
            yL = 0
        if yL > 255 :
            yL = 255
        if yH < 0 :
            yH = 0
        if yH > 255 :
            yH = 255
        
        # Send the command to set pixel
        self._screenSerialPort.write(b'\xFF')
        self._screenSerialPort.write(b'\xC1')
        # x coord
        self._screenSerialPort.write(bytes([xH]))
        self._screenSerialPort.write(bytes([xL]))
        # y coord
        self._screenSerialPort.write(bytes([yH]))
        self._screenSerialPort.write(bytes([yL]))

        # colour (fix at red for now...)
        self.p_LCDwriteColourBytes(colour)
        # ACK
        self.LCDcheckResponse(1)

    # ============================================================================
    # Draw a line from xS,yS to xE, yE coordinates with colour
    # ============================================================================
    def LCDdrawLine(self, xS, yS, xE, yE, colour) :

        if self._screenDetected == False :
            return
 
        xsL = int(xS) % 256
        xsH = int(xS / 256)
        ysL = int(yS) % 256
        ysH = int(yS / 256)
        xeL = int(xE) % 256
        xeH = int(xE / 256)
        yeL = int(yE) % 256
        yeH = int(yE / 256)

        # Send the command to set pixel
        self._screenSerialPort.write(b'\xFF')
        self._screenSerialPort.write(b'\xC8')
        # x start coord
        self._screenSerialPort.write(bytes([xsH]))
        self._screenSerialPort.write(bytes([xsL]))
        # y start coord
        self._screenSerialPort.write(bytes([ysH]))
        self._screenSerialPort.write(bytes([ysL]))
        # x end coord
        self._screenSerialPort.write(bytes([xeH]))
        self._screenSerialPort.write(bytes([xeL]))
        # y end coord
        self._screenSerialPort.write(bytes([yeH]))
        self._screenSerialPort.write(bytes([yeL]))

        self.p_LCDwriteColourBytes(colour)    
        # ACK
        self.LCDcheckResponse(1)

    # ============================================================================
    # Turn the serial touch screen backlight on or off to conserve power
    # Note screen goes completely blank when the backlight is off
    # ============================================================================
    def LCDbacklight(self, onoff) :

        if self._screenDetected == False :
            return

        if onoff == 0 :
            # Send the command to clear the string
            self._screenSerialPort.write(b'\xFF')
            self._screenSerialPort.write(b'\xD5')
            self._screenSerialPort.write(b'\x00')
            self._screenSerialPort.write(b'\x06')
        else :
            self._screenSerialPort.write(b'\xFF')
            self._screenSerialPort.write(b'\xD6')
            self._screenSerialPort.write(b'\x00')
            self._screenSerialPort.write(b'\x06')

        # ACK + pin number (word)
        self.LCDcheckResponse(3)

    # ============================================================================
    # Clear the serial touchscreen display - make sure it is ACK'd
    # ============================================================================
    def LCDclear(self):

        if self._screenDetected == False :
            return
 
        c = 0
        r = '0'
        
        while (c < 10) and (ord(r) != 6) :    
            # Send the command to clear the string
            self._screenSerialPort.write(b'\xFF')
            self._screenSerialPort.write(b'\xCD')

            # Just an ACK
            r = self.LCDcheckResponse(1)
            c += 1
            
    # ============================================================================
    # Move writing cursor to Row, Column on serial touch screen
    # ============================================================================
    def LCDmoveToRowColumn(self, intRow, intColumn) :

        if self._screenDetected == False :
            return
 
        # Send the command to clear the string
        self._screenSerialPort.write(b'\xFF')
        self._screenSerialPort.write(b'\xE9')
        self._screenSerialPort.write(b'\x00')
        self._screenSerialPort.write(bytes(chr(intRow), 'UTF-8'))
        self._screenSerialPort.write(b'\x00')
        self._screenSerialPort.write(bytes(chr(intColumn), 'UTF-8'))

        # Just an ACK
        self.LCDcheckResponse(1)

    # ============================================================================
    # Write string of given colour at current writing cursor position
    # ============================================================================
    def LCDwriteString(self, strText, colour) :

        if self._screenDetected == False :
            return
 
        self.LCDsetTextForegroundColour(colour)

        # Send the command to write the string
        self._screenSerialPort.write(b'\x00')
        self._screenSerialPort.write(b'\x18')

        for c in strText:
            self._screenSerialPort.write(bytes(c, 'UTF-8'))

        # And terminate with a NUL
        self._screenSerialPort.write(b'\x00')

        # and ACK followed by the length of string written (word)
        self.LCDcheckResponse(3)

    # ============================================================================
    # Change the current forecolour on the serial touch screen
    # ============================================================================
    def LCDsetTextForegroundColour(self, colour) :
        
        if self._screenDetected == False :
            return
 
        # Send the command to change the forecolour
        self._screenSerialPort.write(b'\xFF')
        self._screenSerialPort.write(b'\xE7')

        self.p_LCDwriteColourBytes(colour)

        # An ACK followed by the Colour (word)
        self.LCDcheckResponse(3)

    # ============================================================================
    # Set the touch enabled area to the whole screen
    # ============================================================================
    def LCDsetTouchRegion(self) :
        
        if self._screenDetected == False :
            return
 
        # Send the command to enable touch
        self._screenSerialPort.write(b'\xFF')
        self._screenSerialPort.write(b'\x38')
        self._screenSerialPort.write(b'\x00')
        self._screenSerialPort.write(b'\x00')

        # An ACK
        self.LCDcheckResponse(1)

        self._screenSerialPort.write(b'\xFF')
        self._screenSerialPort.write(b'\x38')
        self._screenSerialPort.write(b'\x00')
        self._screenSerialPort.write(b'\x02')

        # An ACK
        self.LCDcheckResponse(1)


    # ============================================================================
    # See if the screen has been touched and if so, where
    # ============================================================================
    def LCDgetTouchState(self) :

        if self._screenDetected == False :
            return 0, 0, 0

        self._touchCount += 1
        xCoord = 0
        yCoord = 0

        if self._screenIsAsleep == True :
            #print ("Waiting...{}".format(xcount))
            touched = self.LCDcheckResponse(3)
            if self._replyFromScreen == True :
                # Should be ACK, timeH, timeL
                timeLeft = self._screenReplyBuffer[1] * 256 + self._screenReplyBuffer[2] 
                #print ("Time left {}".format(timeLeft))
                if timeLeft == 0 :
                    #print("Timed out again")
                    self.LCDputToSleep(3600)
                    self._screenIsAsleep = True
                else :
                    self._screenIsAsleep = False
                    #print("Touched")
            # Indicate no response
            touched = '0'
        else :
            # Send the command to get the touch status
            self._screenSerialPort.write(b'\xFF')
            self._screenSerialPort.write(b'\x37')
            self._screenSerialPort.write(b'\x00')
            self._screenSerialPort.write(b'\x00')

            # An ACK followed by 0 no touch, 1 touch, 2 release, 3 moving
            touched = ord(self.LCDcheckResponse(3))

            #print ("Check touch {}  {}".format(ord(x), self._touchCount))

            if touched == 1 :

                # Get the X coord
                self._screenSerialPort.write(b'\xFF')
                self._screenSerialPort.write(b'\x37')
                self._screenSerialPort.write(b'\x00')
                self._screenSerialPort.write(b'\x01')

                y = self.LCDcheckResponse(3)
                xCoord = self._screenReplyBuffer[1] * 256 + self._screenReplyBuffer[2] 
        
                # Get the X coord
                self._screenSerialPort.write(b'\xFF')
                self._screenSerialPort.write(b'\x37')
                self._screenSerialPort.write(b'\x00')
                self._screenSerialPort.write(b'\x02')

                y = self.LCDcheckResponse(3)
                yCoord = self._screenReplyBuffer[1] * 256 + self._screenReplyBuffer[2] 

                # addLogMessage("Touch={},{}".format(_xTouchCoord, _yTouchCoord))

        return touched, xCoord, yCoord

    
    def LCDputToSleep(self, timeToSleep) :

        xL = int(timeToSleep) % 256
        xH = int(timeToSleep / 256)

        if xL < 0 :
            xL = 0
        if xL > 255 :
            xL = 255
        if xH < 0 :
            xH = 0
        if xH > 255 :
            xH = 255
        
        # Send the command to sleep
        self._screenSerialPort.write(b'\xFF')
        self._screenSerialPort.write(b'\x3B')
        # time to sleep
        self._screenSerialPort.write(bytes([xH]))
        self._screenSerialPort.write(bytes([xL]))

        self._screenIsAsleep = True
        
        # NO RESPONSE UNTIL IT WAKES UP
        # ACK
        self.LCDcheckResponse(99)


    def LCDisScreenAsleep(self) :
        
        return self._screenIsAsleep

