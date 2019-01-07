# climatetest16b.py
# M Hollingworth
# 21-Nov-2018
#
# RUN WITH PYTHON3
#
# 1 Arduino unit is plugged in. 
# This gathers all the RF data from the other Arduinos and presents a single message to the Pi over a proprietary 3 wire interface
# All temperatures are transmitted in Deg C. All humiditys are RH%. All pressures are mB
# Arduino is the slave. Pi toggles reset, then clocks data in looking for three commas to terminate.
# At startup a day change is detected and a filename with that days timestamp is created and an array created that will store records
# at approx 1 minute intervals.
# At midnight the contents of the array are written to the filename,a new filename is generated and the array cleared.
# At midnight, gnuplot is run externally to produce two graphs (PNG files) (temperatures and humiditys)
# At midnight a timer is invoked such that at 6:30AM an email containing the two png files and all the previous days' data is sent
# At 6:30AM, if the data fails to send then keep retrying at half hour intervals
# If the temperature in the shed reaches level1 (25C) or level2 (35C) send a single email per day

# The internal Pi serial port is connected to a touch screen LCD
# This normally displays all the current temperatures
# Touch the screen in the lower half to show min/max/badCRC and time since last message
# While in this screen, touching the display again resets all of the above values and changes back to displaying the temperatures
# If no touch is detected on the screen for 60s then its backlight is turned off to conserve power. Touch it to get display on again

import math

import sys

if sys.version_info[0] < 3 :
    from Tkinter import *
else :
    from tkinter import *

import glob
import serial
import os
import time
from time import strftime, localtime
from datetime import date
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.image import MIMEImage
from subprocess import call
import arcmetersm as m
import shutil
import RPi.GPIO as GPIO
import touchscreen
import signal

import constants as const

NO_TARGET = True

# Setup some global variables

_shutDown = False

_showDebug = False

_sampleCountLounge = 0
_sampleCountBedroom = 0
_sampleCountGardenroom = 0
_sampleCountSummerhouse = 0
_sampleCountAttic = 0
_minsSinceBedroom = 0
_minsSinceGardenroom = 0
_minsSinceSummerhouse = 0
_minsSinceAttic = 0
_crcCountSummerhouse = 0
_crcCountBedroom = 0
_crcCountGardenroom = 0
_crcCountAttic = 0

# Previous temperatures/humidity for working out the 15 minute trend
_houseTemperature = 0
_housePressure = 0
_houseHumidity = 0
_oldGardenroomT = 0
_oldGardenroomH = 0
_oldBedroomT = 0
_oldBedroomH = 0
_oldSummerhouseT = 0
_oldHouseT = 0
_oldHouseH = 0
_oldHouseP = 0

_minTemperatureGardenroom = 100
_maxTemperatureGardenroom = -100
_minHumidityGardenroom = 150
_maxHumidityGardenroom = -150
_maxVoltGardenroom = -100
_minVoltGardenroom = 100

_minTemperatureBedroom = 100
_maxTemperatureBedroom = -100
_minHumidityBedroom = 150
_maxHumidityBedroom = -150
_maxVoltBedroom = -100
_minVoltBedroom = 100

_minTemperatureSummerhouse = 100
_maxTemperatureSummerhouse = -100
_minHumiditySummerhouse = 150
_maxHumiditySummerhouse = -150
_maxVoltSummerhouse = -100
_minVoltSummerhouse = 100

_minTemperatureAttic = 100
_maxTemperatureAttic = -100
_minHumidityAttic = 150
_maxHumidityAttic = -150
_maxVoltAttic = -100
_minVoltAttic = 100

_minTemperatureLounge = 100
_maxTemperatureLounge = -100
_minPressureLounge = 10000
_maxPressureLounge = -10000
_minHumidityLounge = 100
_maxHumidityLounge = -100

_minCpuTemp = 100
_maxCpuTemp = -100

_allMinMaxValues = ""

_currentSummerhouseTemperature = 0
_currentBedroomTemperature = 0
_currentGardenroomTemperature = 0
_currentAtticTemperature = 0
_currentBedroomHumidity = 0
_currentGardenroomHumidity = 0
_currentAtticHumidity = 0
_currentSummerhouseHumidity = 0
_currentSummerhouseVolt = 0
_currentBedroomVolt = 0
_currentGardenroomVolt = 0
_currentAtticVolt = 0
_currentLightLevel = 0

_fixCount = 0
_resetCount = 0

_houseFile = ""
_houseData = []

_logMessages = []

_fileNamesToEmail = []
_firstEmailRetry = 0

_shedAtLevel1messageSent = False
_shedAtLevel2messageSent = False

# Serial touch screen
_timeToBlank = 0
_screenIsBlank = False
_screenIsTemperatures = True

# Get some common constants from the imported file
CONST = const._Const()

class TimeoutException(Exception) :
    pass

def _timeout(signum, frame) :
    raise TimeoutException()


# ============================================================================
# Add log message to the buffer and print to the terminal
# ============================================================================
def addLogMessage(s) :
    global _logMessages

    ss = s
    ss = ss + " " + strftime("%d/%m %H:%M", localtime())
    print(ss)
    if len(_logMessages) == 25 :
        _logMessages.pop(0)
    _logMessages.append(ss)

# ============================================================================
# Retry sending the email as it didn't go first time
# ============================================================================
def tryToSendEmail():

    global _firstEmailRetry
    global _fileNamesToEmail

    sentOk = 0
    if _firstEmailRetry == 0 :
 
        signal.signal(signal.SIGALRM, _timeout)
        signal.alarm(12)

        try :

            server=smtplib.SMTP('smtp-mail.outlook.com', 587)
            server.ehlo()
            server.starttls()
            server.ehlo()
            server.login(CONST.EMAIL_ADDRESS_TO_SEND_FROM, "PWD")
            msg = MIMEMultipart()
            msg['Subject'] = "Data from Pi (RETRY)"
            msg['From'] = CONST.EMAIL_ADDRESS_TO_SEND_FROM
            msg['To'] = CONST.EMAIL_ADDRESS_TO_SEND_TO
            msg.preamble = "Data from Pi (RETRY)"

            #if len(_fileNamesToEmail) :
            #    for item in _fileNamesToEmail :
            #        fp = open(item, 'r')
            #        data = MIMEText(fp.read())
            #        msg.attach(data)            
            #else :
            #    msg['Subject'] = "Data from Pi (RETRY - NONE)"
            #    msg.preamble = "Data from Pi (RETRY - NONE)"
               
            # Add a short text message listing the minimum and maximum values for the previous 24hour period
            msg.attach(MIMEText(_allMinMaxValues))
            
            if os.path.exists("file.png") :
                img_data = open("file.png", 'rb').read()
                image = MIMEImage(img_data, name=os.path.basename("file.png"))
                msg.attach(image)

            if os.path.exists("file1.png") :
                img_data1 = open("file1.png", 'rb').read()
                image1 = MIMEImage(img_data1, name=os.path.basename("file1.png"))
                msg.attach(image1)

            if os.path.exists("file2.png") :
                img_data2 = open("file2.png", 'rb').read()
                image2 = MIMEImage(img_data2, name=os.path.basename("file2.png"))
                msg.attach(image2)

            server.sendmail(CONST.EMAIL_ADDRESS_TO_SEND_FROM, CONST.EMAIL_ADDRESS_TO_SEND_TO, msg.as_string())
            server.quit()

            # Only clear these if everything has gone to plan
            _fileNamesToEmail = []
    
            sentOk = 1
            addLogMessage("Retry data OK")

        except (TimeoutException) :
            addLogMessage("Retry data timeout")            

        except :
            addLogMessage("Retry data FAIL")            

        finally :
            signal.alarm(0)

    # Keep trying every half hour if we didn't succeed
    if sentOk == 0 :
        if _firstEmailRetry == 1 :
            # Reset the timer for the FIRST retry event - 6.5 hours time...
            # it's midnight, so we won't be up until at least 7
            root.after(23400000 , tryToSendEmail)
        else :
            # Reset the timer for the next event - just check every 30 minutes
            root.after(1800000 , tryToSendEmail)

    _firstEmailRetry = 0

# ============================================================================
# Send an email with the latest data files attached
# ============================================================================
def sendEmail():
    
    global _fileNamesToEmail
    global _firstEmailRetry

    signal.signal(signal.SIGALRM, _timeout)
    signal.alarm(12)

    try :
        server=smtplib.SMTP('smtp-mail.outlook.com', 587)
        server.ehlo()
        server.starttls()
        server.ehlo()
        server.login(CONST.EMAIL_ADDRESS_TO_SEND_FROM, "PWD")
        msg = MIMEMultipart()
        msg['Subject'] = "Data from Pi"
        msg['From'] = CONST.EMAIL_ADDRESS_TO_SEND_FROM
        msg['To'] = CONST.EMAIL_ADDRESS_TO_SEND_TO
        msg.preamble = "Data from Pi"

        #if len(_fileNamesToEmail) :
        #    for item in _fileNamesToEmail :
        #        fp = open(item, 'r')
        #        data = MIMEText(fp.read())
        #        msg.attach(data)            
        #else :
        #    fp = open(_houseFile, 'r')
        #    data = MIMEText(fp.read())
        #    msg.attach(data)

        # Add a short text message listing the minimum and maximum values for the previous 24hour period
        msg.attach(MIMEText(_allMinMaxValues))

        if os.path.exists("file.png") :
            img_data = open("file.png", 'rb').read()
            image = MIMEImage(img_data, name=os.path.basename("file.png"))
            msg.attach(image)

        if os.path.exists("file1.png") :
            img_data1 = open("file1.png", 'rb').read()
            image1 = MIMEImage(img_data1, name=os.path.basename("file1.png"))
            msg.attach(image1)

        if os.path.exists("file2.png") :
            img_data2 = open("file2.png", 'rb').read()
            image2 = MIMEImage(img_data2, name=os.path.basename("file2.png"))
            msg.attach(image2)

        server.sendmail(CONST.EMAIL_ADDRESS_TO_SEND_FROM, CONST.EMAIL_ADDRESS_TO_SEND_TO, msg.as_string())
        server.quit()

        # Only clear these if everything has gone to plan
        _fileNamesToEmail = []

        addLogMessage("Data OK")

    except (TimeoutException) :
        addLogMessage("Data timeout")

        _fileNamesToEmail.append(_houseFile)

        # And start a timed event running to retry email again every half hour
        _firstEmailRetry = 1
        tryToSendEmail()

    except :

        addLogMessage("Data fail")

        _fileNamesToEmail.append(_houseFile)

        # And start a timed event running to retry email again every half hour
        _firstEmailRetry = 1
        tryToSendEmail()        

    finally :
        signal.alarm(0)

# ============================================================================
# Send an email with just a header detailing temperature in the shed.
# Only sent once when the threshold is reached. Flags are reset at midnight.
# ============================================================================
def sendAlarmEmail(alarmtype):
    
    signal.signal(signal.SIGALRM, _timeout)
    signal.alarm(12)

    try :
        server=smtplib.SMTP('smtp-mail.outlook.com', 587)
        server.ehlo()
        server.starttls()
        server.ehlo()
        server.login(CONST.EMAIL_ADDRESS_TO_SEND_FROM, "PWD")
        msg = MIMEMultipart()

        v = "unknown"
        if alarmtype == CONST.FIRST_LEVEL_SHED_ALARM_VAL :
            v = str(CONST.FIRST_LEVEL_SHED_ALARM_VAL)
        if alarmtype == CONST.SECOND_LEVEL_SHED_ALARM_VAL :
            v = str(CONST.SECOND_LEVEL_SHED_ALARM_VAL)

        msg.preamble = "Shed just reached " + v + " deg C"
        msg['Subject'] = msg.preamble
        msg['From'] = CONST.EMAIL_ADDRESS_TO_SEND_FROM
        msg['To'] = CONST.EMAIL_ADDRESS_TO_SEND_TO

        server.sendmail(CONST.EMAIL_ADDRESS_TO_SEND_FROM, CONST.EMAIL_ADDRESS_TO_SEND_TO, msg.as_string())
        server.quit()

        addLogMessage("Alm [{}]-Ok".format(alarmtype))
		
    except (TimeoutException) :
        addLogMessage("Alarm timeout")

    except :

        # Don't bother retrying - the message is only informational anyway
        addLogMessage("Alm [{}]-Fail".format(alarmtype))

    finally :
        signal.alarm(0)

# ============================================================================
# Convert a string to a float with error handling
# ============================================================================
def getNum(s):

    try:
        return float(s)
    except ValueError:
        return 0

# ============================================================================
# Check for a new day and update filenames accordingly
# ============================================================================
def checkForNewDay() :

    global _houseFile
    global _houseData
    global _shedAtLevel1messageSent	
    global _shedAtLevel2messageSent	

    # 'today' will be 0 Mon to 6 Sun
    today = date.today()
    if today.weekday() != checkForNewDay.thisDay :
	
        checkForNewDay.thisDay = today.weekday()

        _shedAtLevel1messageSent = False
        _shedAtLevel2messageSent = False

        # Very first time we call this _sampleCountLounge will be 12
        if _sampleCountLounge > 12 :
            # SO, we are here because of a genuine new day midnight roll over
            # and therefore we already have a filename
            
            # Write all the data out before renaming the files

            if _intResetAtMidnight.get() == 1:
                resetAllMinMax(0)

            fileobj = open(_houseFile, 'a')
            for item in _houseData :
                fileobj.write(item)               
            fileobj.close()

            # delete any existing data
            if os.path.exists("data.txt") :
                os.remove("data.txt")

            # make a copy of our existing data ready for gnuplot to do its work
            shutil.copy(_houseFile, "data.txt")

            # delete any existing image
            if os.path.exists("file.png") :
                os.remove("file.png")

            # delete any existing image
            if os.path.exists("file1.png") :
                os.remove("file1.png")

            # delete any existing image
            if os.path.exists("file2.png") :
                os.remove("file2.png")

            # Now graph the data to file.png
            os.system('gnuplot temp.gp')

            # And graph the humidity data to file1.png
            os.system('gnuplot temp1.gp')

            # And graph the voltage and pressure data to file2.png
            os.system('gnuplot temp2.gp')

            sendEmail()

            # Clear all the arrays to start loading them again
            _houseData = []

        _houseFile = "House_" + today.isoformat() + ".txt"
	
    if _houseFile == "" :
        _houseFile = "TestHouse.txt"


# ============================================================================
# Show house values and save all values to file
# ============================================================================
def updateHouse(houseT, houseH, houseP) :

    global _houseTemperature
    global _housePressure
    global _houseHumidity
    global _sampleCountLounge
    global _minTemperatureLounge
    global _maxTemperatureLounge
    global _minHumidityLounge
    global _maxHumidityLounge
    global _minPressureLounge
    global _maxPressureLounge
    global _houseData
    global _maxCpuTemp
    global _minCpuTemp

    global _oldHouseH
    global _oldHouseT
    global _oldHouseP
    
    _houseTemperature = getNum(houseT)
    # Correct for mB
    _housePressure = getNum(houseP)
    _houseHumidity = getNum(houseH)
    
    _sampleCountLounge += 1

    if _houseTemperature > _maxTemperatureLounge :
        _maxTemperatureLounge = _houseTemperature
    if _houseTemperature < _minTemperatureLounge :
        _minTemperatureLounge = _houseTemperature
    if _houseHumidity > _maxHumidityLounge :
        _maxHumidityLounge = _houseHumidity
    if _houseHumidity < _minHumidityLounge :
        _minHumidityLounge = _houseHumidity
    if _housePressure > _maxPressureLounge :
        _maxPressureLounge = _housePressure
    if _housePressure < _minPressureLounge :
        _minPressureLounge = _housePressure

    # Check if approx 15 minutes have elasped
    updateHouse.trendCount += 1
    if updateHouse.trendCount ==  180 :
        _oldHouseT = _houseTemperature
        _oldHouseH = _houseHumidity
        _oldHouseP = _housePressure
        updateHouse.trendCount = 0
            
    labelLoungeTempMax.configure(text = "Mx=" + "{:4.1f}".format(_maxTemperatureLounge))
    labelLoungePresMax.configure(text = "Mx=" + "{:7.2f}".format(_maxPressureLounge))
    labelLoungeHumMax.configure(text = "Mx=" + "{:4.1f}".format(_maxHumidityLounge))
    labelLoungeTempMin.configure(text = "Mn=" + "{:4.1f}".format(_minTemperatureLounge))
    labelLoungePresMin.configure(text = "Mn=" + "{:7.2f}".format(_minPressureLounge))
    labelLoungeHumMin.configure(text = "Mn=" + "{:4.1f}".format(_minHumidityLounge))

    labelSlounge.configure(text="Lounge (" + str(_sampleCountLounge) +")")
    labelSattic.configure(text="Attic (" + str(_sampleCountAttic) + ")")
            
    # cpuTemp will always be returned as temp=x.x'C<cr>, so strip 1st five and last three characters
    cpuTemp = os.popen('vcgencmd measure_temp').readline()[5:-3]

    ct = getNum(cpuTemp)
    if ct > _maxCpuTemp :
        _maxCpuTemp= ct
    if ct < _minCpuTemp :
        _minCpuTemp = ct
    labelCpuTemp.configure(text = "CPU Temp={:4.1f} (Mn={:4.1f} , Mx={:4.1f})".format(ct, _minCpuTemp, _maxCpuTemp))

    loungeTempMeter.setminval(_minTemperatureLounge)
    loungeTempMeter.setmaxval(_maxTemperatureLounge)
    loungeTempMeter.set(_houseTemperature)

    loungeHumMeter.set(_houseHumidity)
    loungeHumMeter.setmaxval(_maxHumidityLounge)
    loungeHumMeter.setminval(_minHumidityLounge)

    loungePresMeter.set(_housePressure)
    loungePresMeter.setminval(_minPressureLounge)
    loungePresMeter.setmaxval(_maxPressureLounge)
    
    if _screenIsTemperatures == True :
        if tscreen.LCDisScreenAsleep() == False :
            TouchScreenUpdateValues()

    updateHouse.recordCountFromLounge += 1
    # We get 1 record approx every 5 seconds, but we only want to store approx once a minute
    if updateHouse.recordCountFromLounge >= 11 :
        updateHouse.recordCountFromLounge = 0
        strV = str(_currentSummerhouseTemperature) + " " + str(_houseTemperature) + " " + str(_houseHumidity) + " " + str(_housePressure) + " " + str(ct) + " "
        strW = str(_currentBedroomTemperature) + " " + str(_currentBedroomHumidity) + " "
        strX = str(_currentGardenroomTemperature) + " " + str(_currentGardenroomHumidity) + " "
        strY = str(_crcCountSummerhouse) + " " + str(_crcCountBedroom) + " " + str(_crcCountGardenroom) + " "
        strYY = str(_currentSummerhouseVolt) + " " + str(_currentBedroomVolt) + " " + str(_currentGardenroomVolt) + " "
        strYYY = str(_currentAtticVolt) + " " + str(_currentAtticTemperature) + " " + str(_crcCountAttic) + " "
        strYYYY = str(_currentAtticHumidity) + " " + str(_currentSummerhouseHumidity) + " "
        strZ = strV + strW + strX + strY + strYY + strYYY + strYYYY + str(_fixCount) + " " + str(_resetCount) + " " + str(_currentLightLevel) + "\r\n"
        _houseData.append(strZ)
        checkForNewDay()            	


# ============================================================================
# Read the string from the Arduino using my proprietary 3 wire interface
# ============================================================================

def readArduino3wire() :
    #              s=summerhouse, b=bedroom, g=gardenroom, a=attic, h=house
    #              Ts    Tb    Tg    Ta   Hb    Hg    Ha    Hs    Vs    Vb    Vg    Va    Cs Cb Cg Ca Bs  Bb  Bg  Ba  Corrected  Reset  Th    Hh    Ph      Light
    #            0 1     2     3     4    5     6     7     8     9     10    11    12    13 14 15 16 17  18  19  20  21         22     23    24    25      26
    #response = "V,12.10,22.10,25.50,9.30,67.40,56.60,72.20,66.44,5.610,4.950,5.200,4.900,15,16,17,18,100,200,300,400,2222200000,170000,32.50,51.23,1001.54,22,,,"

    bitcount = 0
    data = 0
    bytes = 0
    strData = ""
    badCount = 0
    endOfData = False

    GPIO.output(CONST.WIRERESET, 1)
    while (endOfData == False) :
        bitcount = 0
        data = 0
  
        while ( (bitcount < 8) and (bytes < 256) ) :
            GPIO.output(CONST.WIRECLK, 1)
            time.sleep(0.000001)
            if GPIO.input(CONST.WIREDATA) == 1 :
                data = data | (1 << bitcount)
            bitcount += 1
            if bitcount == 8 :
                if data != 0 :
                    strData += chr(data)
                    if (strData[-3:] == ",,,") :
                        endOfData = True
                bytes +=1 
                # Too much data
                if bytes == 256 :
                    endOfData = True;
                    badCount = 1
            GPIO.output(CONST.WIRECLK, 0)

    GPIO.output(CONST.WIRERESET, 0)

    if badCount != 0:
        print ("BAD: {}".format(strData));
        strData = ""
    
    return strData

    
# ============================================================================
# Get any available data from Arduino unit and display it
# ============================================================================
def updateRadioUnits():

    #              s=summerhouse, b=bedroom, g=gardenroom, a=attic, h=house
    #              Ts    Tb    Tg    Ta   Hb    Hg    Ha    Hs    Vs    Vb    Vg    Va    Cs Cb Cg Ca Bs  Bb  Bg  Ba  Corrected  Reset  Th    Hh    Ph      Light
    #            0 1     2     3     4    5     6     7     8     9     10    11    12    13 14 15 16 17  18  19  20  21         22     23    24    25      26
    #response = "V,12.10,22.10,25.50,9.30,67.40,56.60,72.20,66.44,5.610,4.950,5.200,4.900,15,16,17,18,100,200,300,400,2222200000,170000,32.50,51.23,1001.54,22,,,"

    global _sampleCountSummerhouse
    global _sampleCountBedroom
    global _sampleCountGardenroom
    global _sampleCountAttic
    global _minTemperatureSummerhouse
    global _maxTemperatureSummerhouse
    global _minTemperatureBedroom
    global _maxTemperatureBedroom
    global _minTemperatureGardenroom
    global _maxTemperatureGardenroom
    global _minTemperatureAttic
    global _maxTemperatureAttic
    global _minHumidityBedroom
    global _maxHumidityBedroom
    global _minHumidityGardenroom
    global _maxHumidityGardenroom
    global _minHumidityAttic
    global _maxHumidityAttic
    global _minHumiditySummerhouse
    global _maxHumiditySummerhouse
    global _minVoltSummerhouse
    global _maxVoltSummerhouse
    global _minVoltBedroom
    global _maxVoltBedroom
    global _minVoltGardenroom
    global _maxVoltGardenroom    
    global _minVoltAttic
    global _maxVoltAttic
    global _currentSummerhouseVolt
    global _currentBedroomVolt
    global _currentGardenroomVolt
    global _currentAtticVolt
    global _currentSummerhouseTemperature
    global _currentBedroomTemperature
    global _currentGardenroomTemperature
    global _currentAtticTemperature
    global _currentAtticHumidity
    global _currentBedroomHumidity
    global _currentGardenroomHumidity
    global _currentSummerhouseHumidity
    global _currentLightLevel
    global _crcCountSummerhouse
    global _crcCountBedroom
    global _crcCountGardenroom
    global _crcCountAttic
    global _shedAtLevel1messageSent	
    global _shedAtLevel2messageSent	

    global _minsSinceBedroom
    global _minsSinceGardenroom
    global _minsSinceSummerhouse
    global _minsSinceAttic

    global _oldGardenroomT
    global _oldGardenroomH
    global _oldBedroomT
    global _oldBedroomH
    global _oldSummerhouseT

    global _fixCount
    global _resetCount

    strX = readArduino3wire()

    if len(strX) :
        try :
            p1 = strX.split(",")
        except :
            p1 = []
            addLogMessage("Bad Msg")

        if len(p1) > 27 :

            _currentLightLevel = getNum(p1[26]) / 10.0
            labelLightLevel.configure(text="Light Level = " + str(_currentLightLevel))

            t = getNum(p1[1])
            _currentSummerhouseTemperature = t
            if t > _maxTemperatureSummerhouse :
                _maxTemperatureSummerhouse = t
            if t < _minTemperatureSummerhouse :
                _minTemperatureSummerhouse = t
            summerhouseTempMeter.set(t)
            summerhouseTempMeter.setminval(_minTemperatureSummerhouse)
            summerhouseTempMeter.setmaxval(_maxTemperatureSummerhouse)
			
            t = getNum(p1[8])
            _currentSummerhouseHumidity = t
            if t > _maxHumiditySummerhouse :
                _maxHumiditySummerhouse = t
            if t < _minHumiditySummerhouse :
                _minHumiditySummerhouse = t
            summerhouseHumMeter.set(t)
            summerhouseHumMeter.setminval(_minHumiditySummerhouse)
            summerhouseHumMeter.setmaxval(_maxHumiditySummerhouse)

            if t >= CONST.FIRST_LEVEL_SHED_ALARM_VAL :
                if _shedAtLevel1messageSent == False :
                    _shedAtLevel1messageSent = True
                    sendAlarmEmail(CONST.FIRST_LEVEL_SHED_ALARM_VAL)
            if t >= CONST.SECOND_LEVEL_SHED_ALARM_VAL :
                if _shedAtLevel2messageSent == False :
                    _shedAtLevel2messageSent = True
                    sendAlarmEmail(CONST.SECOND_LEVEL_SHED_ALARM_VAL)

            if _sampleCountSummerhouse != getNum(p1[13]) :
                _minsSinceSummerhouse = 0
                _oldSummerhouseT = getNum(p1[1])
            if _sampleCountBedroom != getNum(p1[14]) :
                _minsSinceBedroom = 0
                _oldBedroomT = getNum(p1[2])
                _oldBedroomH = getNum(p1[5])
            if _sampleCountGardenroom != getNum(p1[15]) :
                _minsSinceGardenroom = 0
                _oldGardenroomT = getNum(p1[3])
                _oldGardenroomH = getNum(p1[6])
            if _sampleCountAttic != getNum(p1[16]) :
                _minsSinceAttic = 0

            _sampleCountSummerhouse = getNum(p1[13])
            _sampleCountBedroom = getNum(p1[14])
            _sampleCountGardenroom = getNum(p1[15])
            _sampleCountAttic = getNum(p1[16])
            
            t = getNum(p1[2])
            _currentBedroomTemperature = t
            # We may not have any samples to start with...
            if _sampleCountBedroom > 0 :
                if t > _maxTemperatureBedroom :
                    _maxTemperatureBedroom = t
                if t < _minTemperatureBedroom :
                    _minTemperatureBedroom = t
            bedroomTempMeter.set(t)
            bedroomTempMeter.setminval(_minTemperatureBedroom)
            bedroomTempMeter.setmaxval(_maxTemperatureBedroom)

            t = getNum(p1[5])
            _currentBedroomHumidity = t
            # We may not have any samples to start with...
            if _sampleCountBedroom > 0 :
                if t > _maxHumidityBedroom :
                    _maxHumidityBedroom = t
                if t < _minHumidityBedroom :
                    _minHumidityBedroom = t
            bedroomHumMeter.set(t)
            bedroomHumMeter.setminval(_minHumidityBedroom)
            bedroomHumMeter.setmaxval(_maxHumidityBedroom)

            t = getNum(p1[3])
            _currentGardenroomTemperature = t
            # We may not have any samples to start with...
            if _sampleCountGardenroom > 0 :
                if t > _maxTemperatureGardenroom :
                    _maxTemperatureGardenroom = t
                if t < _minTemperatureGardenroom :
                    _minTemperatureGardenroom = t
            gardenroomTempMeter.set(t)
            gardenroomTempMeter.setminval(_minTemperatureGardenroom)
            gardenroomTempMeter.setmaxval(_maxTemperatureGardenroom)

            t = getNum(p1[6])
            _currentGardenroomHumidity = t
            # We may not have any samples to start with...
            if _sampleCountGardenroom > 0 :
                if t > _maxHumidityGardenroom :
                    _maxHumidityGardenroom = t
                if t < _minHumidityGardenroom :
                    _minHumidityGardenroom = t
            gardenroomHumMeter.set(t)
            gardenroomHumMeter.setminval(_minHumidityGardenroom)
            gardenroomHumMeter.setmaxval(_maxHumidityGardenroom)

            _crcCountSummerhouse = getNum(p1[17])
            _crcCountBedroom = getNum(p1[18])
            _crcCountGardenroom = getNum(p1[19])
            _crcCountAttic = getNum(p1[20])

            t = getNum(p1[9])
            # Correct as Arduino is 10 times less sometimes...???
            if (t < 1.0) :
                t = t * 10.0
            _currentSummerhouseVolt = t
            if t > _maxVoltSummerhouse :
                _maxVoltSummerhouse = t
            if t < _minVoltSummerhouse :
                _minVoltSummerhouse = t
            summerhouseVoltMeter.set(_currentSummerhouseVolt)
            summerhouseVoltMeter.setminval(_minVoltSummerhouse)
            summerhouseVoltMeter.setmaxval(_maxVoltSummerhouse)
            
            t = getNum(p1[10])
            # Correct as Arduino is 10 times less sometimes...???
            if (t < 1.0) :
                t = t * 10.0
            _currentBedroomVolt = t
            if t > _maxVoltBedroom :
                _maxVoltBedroom = t
            if t < _minVoltBedroom :
                _minVoltBedroom = t
            bedroomVoltMeter.set(_currentBedroomVolt)
            bedroomVoltMeter.setminval(_minVoltBedroom)
            bedroomVoltMeter.setmaxval(_maxVoltBedroom)

            t = getNum(p1[11])
            # Correct as Arduino is 10 times less sometimes...???
            if (t < 1.0) :
                t = t * 10.0
            _currentGardenroomVolt = t
            if t > _maxVoltGardenroom :
                _maxVoltGardenroom = t
            if t < _minVoltGardenroom :
                _minVoltGardenroom = t
            gardenroomVoltMeter.set(_currentGardenroomVolt)
            gardenroomVoltMeter.setminval(_minVoltGardenroom)
            gardenroomVoltMeter.setmaxval(_maxVoltGardenroom)

            t = getNum(p1[12])
            # Correct as Arduino is 10 times less sometimes...???
            if (t < 1.0) :
                t = t * 10.0
            _currentAtticVolt = t
            if t > _maxVoltAttic :
                _maxVoltAttic = t
            if t < _minVoltAttic :
                _minVoltAttic = t
            atticVoltMeter.set(_currentAtticVolt)
            atticVoltMeter.setminval(_minVoltAttic)
            atticVoltMeter.setmaxval(_maxVoltAttic)

            t = getNum(p1[4])
            _currentAtticTemperature = t
            if t > _maxTemperatureAttic :
                _maxTemperatureAttic = t
            if t < _minTemperatureAttic :
                _minTemperatureAttic = t
            atticTempMeter.set(t)
            atticTempMeter.setminval(_minTemperatureAttic)
            atticTempMeter.setmaxval(_maxTemperatureAttic)

            t = getNum(p1[7])
            _currentAtticHumidity = t
            if t > _maxHumidityAttic :
                _maxHumidityAttic = t
            if t < _minHumidityAttic :
                _minHumidityAttic = t
            atticHumMeter.set(t)
            atticHumMeter.setminval(_minHumidityAttic)
            atticHumMeter.setmaxval(_maxHumidityAttic)

            labelSbedroom.configure(text="BEDROOM (" + str(_sampleCountBedroom) + ")")
            labelBedroomTempMin.configure(text = "Mn=" + "{:4.1f}".format(_minTemperatureBedroom))
            labelBedroomTempMax.configure(text = "Mx=" + "{:4.1f}".format(_maxTemperatureBedroom))
            labelBedroomHumMin.configure(text = "Mn=" + "{:4.1f}".format(_minHumidityBedroom))
            labelBedroomHumMax.configure(text = "Mx=" + "{:4.1f}".format(_maxHumidityBedroom))
            labelBedroomVoltMin.configure(text = "Mn=" + "{:4.2f}".format(_minVoltBedroom))
            labelBedroomVoltMax.configure(text = "Mx=" + "{:4.2f}".format(_maxVoltBedroom))

            labelSgardenroom.configure(text="GARDEN ROOM (" + str(_sampleCountGardenroom) + ")")
            labelGardenroomTempMin.configure(text = "Mn=" + "{:4.1f}".format(_minTemperatureGardenroom))
            labelGardenroomTempMax.configure(text = "Mx=" + "{:4.1f}".format(_maxTemperatureGardenroom))
            labelGardenroomHumMin.configure(text = "Mn=" + "{:4.1f}".format(_minHumidityGardenroom))
            labelGardenroomHumMax.configure(text = "Mx=" + "{:4.1f}".format(_maxHumidityGardenroom))
            labelGardenroomVoltMin.configure(text = "Mn=" + "{:4.2f}".format(_minVoltGardenroom))
            labelGardenroomVoltMax.configure(text = "Mx=" + "{:4.1f}".format(_maxVoltGardenroom))

            labelSsummerhouse.configure(text="SUMMERHOUSE (" + str(_sampleCountSummerhouse) + ")")
            labelSummerhouseTempMin.configure(text = "Mn=" + "{:4.1f}".format(_minTemperatureSummerhouse))
            labelSummerhouseTempMax.configure(text = "Mx=" + "{:4.1f}".format(_maxTemperatureSummerhouse))
            labelSummerhouseHumMin.configure(text = "Mn=" + "{:4.1f}".format(_minHumiditySummerhouse))
            labelSummerhouseHumMax.configure(text = "Mx=" + "{:4.1f}".format(_maxHumiditySummerhouse))
            labelSummerhouseVoltMin.configure(text = "Mn=" + "{:4.2f}".format(_minVoltSummerhouse))
            labelSummerhouseVoltMax.configure(text = "Mx=" + "{:4.2f}".format(_maxVoltSummerhouse))

            labelSattic.configure(text="Attic (" + str(_sampleCountAttic) + ")")
            labelAtticTempMin.configure(text = "Mn=" + "{:4.1f}".format(_minTemperatureAttic))
            labelAtticTempMax.configure(text = "Mx=" + "{:4.1f}".format(_maxTemperatureAttic))
            labelAtticHumMin.configure(text = "Mn=" + "{:4.1f}".format(_minHumidityAttic))
            labelAtticHumMax.configure(text = "Mx=" + "{:4.1f}".format(_maxHumidityAttic))
            labelAtticVoltMin.configure(text = "Mn=" + "{:4.2f}".format(_minVoltAttic))
            labelAtticVoltMax.configure(text = "Mx=" + "{:4.2f}".format(_maxVoltAttic))

            _fixCount = getNum(p1[21])
            _resetCount = getNum(p1[22])

            # This call writes the file, so leave it until last...
            updateHouse(p1[23], p1[24], p1[25])

    # Reset the timer for the next event - just check every 5 seconds
    root.after(5000, updateRadioUnits)

# ============================================================================
# Update minutes since a message was received for the 3 RF transmitted values
# ============================================================================
def updateMinutesSinceCounters() :

    global _minsSinceBedroom
    global _minsSinceGardenroom
    global _minsSinceSummerhouse
    global _minsSinceAttic

    _minsSinceSummerhouse += 1
    _minsSinceBedroom += 1
    _minsSinceGardenroom += 1
    _minsSinceAttic += 1
    
    # Reset the timer for the next event - every minute
    root.after(1000 * 60, updateMinutesSinceCounters)

# ============================================================================
# User has clicked the EXIT button
# ============================================================================
def stopProg(e):

    # Useful for testing...
    #checkForNewDay.thisDay = -1
    #checkForNewDay()

    if _houseFile != "" :
        fileobj = open(_houseFile, 'a')
        for item in _houseData :
            fileobj.write(item)               
        fileobj.close()

    fileobj = open("tempvals.txt", 'w')
    fileobj.write(str(_currentSummerhouseTemperature) + "\r\n")               
    fileobj.write(str(_currentSummerhouseHumidity) + "\r\n")               
    fileobj.write(str(_currentSummerhouseVolt) + "\r\n")               
    fileobj.write(str(_currentBedroomTemperature) + "\r\n")               
    fileobj.write(str(_currentGardenroomTemperature) + "\r\n")               
    fileobj.write(str(_currentBedroomHumidity) + "\r\n")               
    fileobj.write(str(_currentGardenroomHumidity) + "\r\n")               
    fileobj.write(str(_currentBedroomVolt) + "\r\n")               
    fileobj.write(str(_currentGardenroomVolt) + "\r\n")               
    fileobj.write(str(_currentAtticVolt) + "\r\n")               
    fileobj.write(str(_currentAtticTemperature) + "\r\n")               
    fileobj.write(str(_currentAtticHumidity) + "\r\n")               
    fileobj.write(str(_currentLightLevel) + "\r\n")               
    fileobj.close()

    tscreen.LCDdispose()

    GPIO.cleanup()

    root.destroy()

# ============================================================================
# User has clicked the RESET MIN?MAX button
# ============================================================================
def resetLoungeMinMax(e):
    global _minTemperatureLounge
    global _maxTemperatureLounge
    global _minPressureLounge
    global _maxPressureLounge
    global _minHumidityLounge
    global _maxHumidityLounge
    global _allMinMaxValues

    _allMinMaxValues = _allMinMaxValues + "Lounge Temperature Minimum = {:2.1f}".format(_minTemperatureLounge) + "  Maximum = {:2.1f}".format(_maxTemperatureLounge) +"\r\n"
    _allMinMaxValues = _allMinMaxValues + "Lounge Humidity Minimum = {:2.1f}".format(_minHumidityLounge) + "  Maximum = {:2.1f}".format(_maxHumidityLounge) +"\r\n"
    _allMinMaxValues = _allMinMaxValues + "Lounge Pressure Minimum = {:2.1f}".format(_minPressureLounge) + "  Maximum = {:2.1f}".format(_maxPressureLounge) +"\r\n"

    _minTemperatureLounge = 100
    _maxTemperatureLounge = -100
    _minPressureLounge = 10000
    _maxPressureLounge = -10000

    _minHumidityLounge = 100
    _maxHumidityLounge = -100

    loungeTempMeter.setminval(0)
    loungeTempMeter.setmaxval(0)
    loungePresMeter.setminval(950)
    loungePresMeter.setmaxval(950)
    loungeHumMeter.setmaxval(0)
    loungeHumMeter.setminval(0)

    labelLoungeTempMax.configure(text = "Mx=0")
    labelLoungePresMax.configure(text = "Mx=950")
    labelLoungeHumMax.configure(text = "Mx=0")
    labelLoungeTempMin.configure(text = "Mn=0")
    labelLoungePresMin.configure(text = "Mn=950")
    labelLoungeHumMin.configure(text = "Mn=0")

def resetBedroomMinMax(e):
    global _minTemperatureBedroom
    global _maxTemperatureBedroom
    global _minHumidityBedroom
    global _maxHumidityBedroom
    global _minVoltBedroom
    global _maxVoltBedroom
    global _allMinMaxValues

    _allMinMaxValues = _allMinMaxValues + "Bedroom Temperature Minimum = {:2.1f}".format(_minTemperatureBedroom) + "  Maximum = {:2.1f}".format(_maxTemperatureBedroom) +"\r\n"
    _allMinMaxValues = _allMinMaxValues + "Bedroom Humidity Minimum = {:2.1f}".format(_minHumidityBedroom) + "  Maximum = {:2.1f}".format(_maxHumidityBedroom) +"\r\n"

    _minHumidityBedroom = 100
    _maxHumidityBedroom = -100
    _minTemperatureBedroom = 100
    _maxTemperatureBedroom = -100
    _minVoltBedroom = 100
    _maxVoltBedroom = -100

    bedroomHumMeter.setminval(0)
    bedroomHumMeter.setmaxval(0)
    bedroomTempMeter.setminval(0)
    bedroomTempMeter.setmaxval(0)
    bedroomVoltMeter.setminval(0)
    bedroomVoltMeter.setmaxval(0)

    labelBedroomTempMin.configure(text = "Mn=0")
    labelBedroomTempMax.configure(text = "Mx=0")
    labelBedroomHumMin.configure(text = "Mn=0")
    labelBedroomHumMax.configure(text = "Mx=0")
    labelBedroomVoltMin.configure(text = "Mn=0")
    labelBedroomVoltMax.configure(text = "Mx=0")

def resetGardenroomMinMax(e):
    global _minTemperatureGardenroom
    global _maxTemperatureGardenroom
    global _minHumidityGardenroom
    global _maxHumidityGardenroom
    global _minVoltGardenroom
    global _maxVoltGardenroom
    global _allMinMaxValues

    _allMinMaxValues = _allMinMaxValues + "Gardenroom Temperature Minimum = {:2.1f}".format(_minTemperatureGardenroom) + "  Maximum = {:2.1f}".format(_maxTemperatureGardenroom) +"\r\n"
    _allMinMaxValues = _allMinMaxValues + "Gardenroom Humidity Minimum = {:2.1f}".format(_minHumidityGardenroom) + "  Maximum = {:2.1f}".format(_maxHumidityGardenroom) +"\r\n"

    _minHumidityGardenroom = 100
    _minHumidityGardenroom = 100
    _maxHumidityGardenroom = -100
    _minTemperatureGardenroom = 100
    _maxTemperatureGardenroom = -100
    _maxTemperatureGardenroom = -100
    _minVoltGardenroom = 100
    _maxVoltGardenroom = -100

    gardenroomHumMeter.setminval(0)
    gardenroomHumMeter.setmaxval(0)
    gardenroomTempMeter.setminval(0)
    gardenroomTempMeter.setmaxval(0)
    gardenroomVoltMeter.setminval(0)
    gardenroomVoltMeter.setmaxval(0)

    labelGardenroomTempMin.configure(text = "Mn=0")
    labelGardenroomTempMax.configure(text = "Mx=0")
    labelGardenroomHumMin.configure(text = "Mn=0")
    labelGardenroomHumMax.configure(text = "Mx=0")
    labelGardenroomVoltMin.configure(text = "Mn=0")
    labelGardenroomVoltMax.configure(text = "Mx=0")

def resetSummerhouseMinMax(e):
    global _minTemperatureSummerhouse
    global _maxTemperatureSummerhouse
    global _minHumiditySummerhouse
    global _maxHumiditySummerhouse
    global _minVoltSummerhouse
    global _maxVoltSummerhouse
    global _allMinMaxValues

    _allMinMaxValues = _allMinMaxValues + "Summerhouse Temperature Minimum = {:3.1f}".format(_minTemperatureSummerhouse) + "  Maximum = {:3.1f}".format(_maxTemperatureSummerhouse) +"\r\n"
    _allMinMaxValues = _allMinMaxValues + "Summerhouse Humidity Minimum = {:2}".format(_minHumiditySummerhouse) + "  Maximum = {:2}".format(_maxHumiditySummerhouse) +"\r\n"

    _minTemperatureSummerhouse = 100
    _maxTemperatureSummerhouse = -100
    _minHumiditySummerhouse = 100
    _maxHumiditySummerhouse = -100
    _minVoltSummerhouse = 100
    _maxVoltSummerhouse = -100

    summerhouseTempMeter.setminval(0)
    summerhouseTempMeter.setmaxval(0)

    summerhouseVoltMeter.setminval(0)
    summerhouseVoltMeter.setmaxval(0)

    summerhouseHumMeter.setminval(0)
    summerhouseHumMeter.setmaxval(0)

    labelSummerhouseTempMin.configure(text = "Mn=0")
    labelSummerhouseTempMax.configure(text = "Mx=0")

    labelSummerhouseVoltMin.configure(text = "Mn=0")
    labelSummerhouseVoltMax.configure(text = "Mx=0")

    labelSummerhouseHumMin.configure(text = "Mn=0")
    labelSummerhouseHumMax.configure(text = "Mx=0")
	
def resetCpuMinMax(e):
    global _minCpuTemp
    global _maxCpuTemp
    global _allMinMaxValues

    _allMinMaxValues = _allMinMaxValues + "CPU Temperature Minimum = {:2}".format(_minCpuTemp) + "  Maximum = {:2}".format(_maxCpuTemp) +"\r\n"

    _minCpuTemp = 100
    _maxCpuTemp = -100

    labelCpuTemp.configure(text = "CPU Temp=0 (Mn=0 , Mx=0)")

def resetAtticMinMax(e):
    global _minTemperatureAttic
    global _maxTemperatureAttic
    global _minHumidityAttic
    global _maxHumidityAttic
    global _minVoltAttic
    global _maxVoltAttic
    global _allMinMaxValues

    _allMinMaxValues = _allMinMaxValues + "Attic Temperature Minimum = {:2}".format(_minTemperatureAttic) + "  Maximum = {:2}".format(_maxTemperatureAttic) +"\r\n"
    _allMinMaxValues = _allMinMaxValues + "Attic Humidity Minimum = {:2}".format(_minHumidityAttic) + "  Maximum = {:2}".format(_maxHumidityAttic) +"\r\n"

    _minTemperatureAttic = 100
    _maxTemperatureAttic = -100
    _minHumidityAttic = 100
    _maxHumidityAttic = -100
    _minVoltAttic = 100
    _maxVoltAttic = -100

    atticTempMeter.setminval(0)
    atticTempMeter.setmaxval(0)

    atticVoltMeter.setminval(0)
    atticVoltMeter.setmaxval(0)

    atticHumMeter.setminval(0)
    atticHumMeter.setmaxval(0)

    labelAtticTempMin.configure(text = "Mn=0")
    labelAtticTempMax.configure(text = "Mx=0")
	
    labelAtticVoltMin.configure(text = "Mn=0")
    labelAtticVoltMax.configure(text = "Mx=0")

    labelAtticHumMin.configure(text = "Mn=0")
    labelAtticHumMax.configure(text = "Mx=0")

def resetAllMinMax(e):

    global _allMinMaxValues

    # Make up the string to send as the text in the email
    _allMinMaxValues = "Minimum and Maximum values for the last 24 hours\r\n"

    resetCpuMinMax(e)
    resetAtticMinMax(e)
    resetSummerhouseMinMax(e)
    resetGardenroomMinMax(e)
    resetBedroomMinMax(e)
    resetLoungeMinMax(e)

def checkForSavedValues():

    global _currentSummerhouseTemperature
    global _currentSummerhouseHumidity
    global _currentBedroomTemperature
    global _currentGardenroomTemperature
    global _currentBedroomHumidity
    global _currentGardenroomHumidity
    global _currentSummerhouseVolt
    global _currentBedroomVolt
    global _currentGardenroomVolt
    global _currentAtticVolt
    global _currentAtticTemperature
    global _currentAtticHumidity
    global _currentLightLevel

    if os.path.exists("tempvals.txt") :
        fileobj = open("tempvals.txt", 'r')
        _currentSummerhouseTemperature = getNum((fileobj.readline()[:-1]))
        _currentSummerhouseHumidity = getNum((fileobj.readline()[:-1]))
        _currentSummerhouseVolt = getNum((fileobj.readline()[:-1]))
        _currentBedroomTemperature = getNum((fileobj.readline()[:-1]))
        _currentGardenroomTemperature = getNum((fileobj.readline()[:-1]))
        _currentBedroomHumidity = getNum((fileobj.readline()[:-1]))
        _currentGardenroomHumidity = getNum((fileobj.readline()[:-1]))
        _currentBedroomVolt = getNum((fileobj.readline()[:-1]))
        _currentGardenroomVolt = getNum((fileobj.readline()[:-1]))
        _currentAtticVolt = getNum((fileobj.readline()[:-1]))
        _currentAtticTemperature = getNum((fileobj.readline()[:-1]))
        _currentAtticHumidity = getNum((fileobj.readline()[:-1]))
        _currentLightLevel = getNum((fileobj.readline()[:-1]))
        fileobj.close()

# ============================================================================
# Which way has new reading gone since the last reading
# ============================================================================
def getTrend(newV, oldV) :
    if newV > oldV :
        return ' (>)'
    if newV < oldV :
        return ' (<)'
    return ' (=)'
    
# ============================================================================
# Write the current sensor values to the serial touch screen
# ============================================================================
def TouchScreenUpdateValues() :

    # House sensors
    # Temperature
    tscreen.LCDmoveToRowColumn(7,16)
    strX = "{:7.2f}".format(_houseTemperature) + getTrend(_houseTemperature, _oldHouseT)
    tscreen.LCDwriteString(strX, CONST.YELLOW)
    # Humidity
    tscreen.LCDmoveToRowColumn(8,16)
    strX = "{:7.2f}".format(_houseHumidity) + getTrend(_houseHumidity, _oldHouseH)
    tscreen.LCDwriteString(strX, CONST.YELLOW)
    # Pressure
    tscreen.LCDmoveToRowColumn(9,16)
    strX = "{:7.2f}".format(_housePressure) + getTrend(_housePressure, _oldHouseP)
    tscreen.LCDwriteString(strX, CONST.YELLOW)

    # Gardenroom sensors
    # Temperature
    tscreen.LCDmoveToRowColumn(17,16)
    strX = "{:7.2f}".format(_currentGardenroomTemperature) + getTrend(_currentGardenroomTemperature, _oldGardenroomT)
    tscreen.LCDwriteString(strX, CONST.GREEN)
    # Humidity
    tscreen.LCDmoveToRowColumn(18,16)
    strX = "{:7.2f}".format(_currentGardenroomHumidity) + getTrend(_currentGardenroomHumidity, _oldGardenroomH)
    tscreen.LCDwriteString(strX, CONST.GREEN)
    # Volts
    tscreen.LCDmoveToRowColumn(19,16)
    strX = "{:7.2f}".format(_currentGardenroomVolt)
    tscreen.LCDwriteString(strX, CONST.GREEN)

    # Bedroom sensors
    # Temperature
    tscreen.LCDmoveToRowColumn(12,16)
    strX = "{:7.2f}".format(_currentBedroomTemperature) + getTrend(_currentBedroomTemperature, _oldBedroomT)
    tscreen.LCDwriteString(strX, CONST.RED)
    # Humidity
    tscreen.LCDmoveToRowColumn(13,16)
    strX = "{:7.2f}".format(_currentBedroomHumidity) + getTrend(_currentBedroomHumidity, _oldBedroomH)
    tscreen.LCDwriteString(strX, CONST.RED)
    # Volts
    tscreen.LCDmoveToRowColumn(14,16)
    strX = "{:7.2f}".format(_currentBedroomVolt)
    tscreen.LCDwriteString(strX, CONST.RED)

    # Summerhouse sensors
    # Temperature
    tscreen.LCDmoveToRowColumn(3,16)
    strX = "{:7.2f}".format(_currentSummerhouseTemperature) + getTrend(_currentSummerhouseTemperature, _oldSummerhouseT)
    tscreen.LCDwriteString(strX, CONST.BLUE)
    # Volts
    tscreen.LCDmoveToRowColumn(4,16)
    strX = "{:7.2f}".format(_currentSummerhouseVolt)
    tscreen.LCDwriteString(strX, CONST.BLUE)
    
    # Attic sensors
    # Temperature
    tscreen.LCDmoveToRowColumn(22,16)
    strX = "{:7.2f}".format(_currentAtticTemperature)
    tscreen.LCDwriteString(strX, CONST.ORANGE)
    # Volts
    tscreen.LCDmoveToRowColumn(23,16)
    strX = "{:7.2f}".format(_currentAtticVolt)
    tscreen.LCDwriteString(strX, CONST.ORANGE)

    # ============================================================================
# Draw the initial display of the serial touchscreen
# ============================================================================
def TouchScreenSetupInitialLayout() :

    tscreen.LCDclear()

    # Turn backlight on (anything other than 0 to turn it on)
    tscreen.LCDbacklight(1)

    tscreen.LCDmoveToRowColumn(0,9)
    tscreen.LCDwriteString("Climate Unit", CONST.WHITE)

    tscreen.LCDmoveToRowColumn(2,0)
    tscreen.LCDwriteString("Summerhouse", CONST.BLUE)
    tscreen.LCDmoveToRowColumn(3,0)
    tscreen.LCDwriteString("    Temperature", CONST.BLUE)
    tscreen.LCDmoveToRowColumn(4,0)
    tscreen.LCDwriteString("    Volt", CONST.BLUE)

    tscreen.LCDmoveToRowColumn(6,0)
    tscreen.LCDwriteString("Lounge", CONST.YELLOW)
    tscreen.LCDmoveToRowColumn(7,0)
    tscreen.LCDwriteString("    Temperature", CONST.YELLOW)
    tscreen.LCDmoveToRowColumn(8,0)
    tscreen.LCDwriteString("    Humidity", CONST.YELLOW)
    tscreen.LCDmoveToRowColumn(9,0)
    tscreen.LCDwriteString("    Pressure", CONST.YELLOW)

    tscreen.LCDmoveToRowColumn(11,0)
    tscreen.LCDwriteString("Bedroom", CONST.RED)
    tscreen.LCDmoveToRowColumn(12,0)
    tscreen.LCDwriteString("    Temperature", CONST.RED)
    tscreen.LCDmoveToRowColumn(13,0)
    tscreen.LCDwriteString("    Humidity", CONST.RED)
    tscreen.LCDmoveToRowColumn(14,0)
    tscreen.LCDwriteString("    Volt", CONST.RED)

    tscreen.LCDmoveToRowColumn(16,0)
    tscreen.LCDwriteString("Gardenroom", CONST.GREEN)
    tscreen.LCDmoveToRowColumn(17,0)
    tscreen.LCDwriteString("    Temperature", CONST.GREEN)
    tscreen.LCDmoveToRowColumn(18,0)
    tscreen.LCDwriteString("    Humidity", CONST.GREEN)
    tscreen.LCDmoveToRowColumn(19,0)
    tscreen.LCDwriteString("    Volt", CONST.GREEN)

    tscreen.LCDmoveToRowColumn(21,0)
    tscreen.LCDwriteString("Attic", CONST.ORANGE)
    tscreen.LCDmoveToRowColumn(22,0)
    tscreen.LCDwriteString("    Temperature", CONST.ORANGE)
    tscreen.LCDmoveToRowColumn(23,0)
    tscreen.LCDwriteString("    Volt", CONST.ORANGE)

    tscreen.LCDsetTouchRegion()


# ============================================================================
# Draw the min/max/crc screen
# ============================================================================
def TouchScreenMinMaxCrcLayout() :

    tscreen.LCDclear()

    tscreen.LCDmoveToRowColumn(0,9)
    tscreen.LCDwriteString("Climate Unit", CONST.WHITE)

    tscreen.LCDmoveToRowColumn(2,8)
    tscreen.LCDwriteString("Min", CONST.WHITE)
    tscreen.LCDmoveToRowColumn(2,13)
    tscreen.LCDwriteString("Max", CONST.WHITE)
    tscreen.LCDmoveToRowColumn(2,18)
    tscreen.LCDwriteString("Crc", CONST.WHITE)
    tscreen.LCDmoveToRowColumn(2,23)
    tscreen.LCDwriteString("Minutes", CONST.WHITE)

    tscreen.LCDmoveToRowColumn(4,0)
    tscreen.LCDwriteString("Summerhouse", CONST.BLUE)
    tscreen.LCDmoveToRowColumn(5,2)
    tscreen.LCDwriteString("Temp", CONST.BLUE)
    tscreen.LCDmoveToRowColumn(5,8)
    tscreen.LCDwriteString("{:2.0f}".format(_minTemperatureSummerhouse), CONST.BLUE)
    tscreen.LCDmoveToRowColumn(5,13)
    tscreen.LCDwriteString("{:2.0f}".format(_maxTemperatureSummerhouse), CONST.BLUE)
    tscreen.LCDmoveToRowColumn(5,18)
    tscreen.LCDwriteString("{:3.0f}".format(_crcCountSummerhouse), CONST.BLUE)
    tscreen.LCDmoveToRowColumn(5,23)
    tscreen.LCDwriteString("{:3.0f}".format(_minsSinceSummerhouse), CONST.BLUE)

    tscreen.LCDmoveToRowColumn(7,0)
    tscreen.LCDwriteString("Lounge", CONST.YELLOW)
    tscreen.LCDmoveToRowColumn(8,2)
    tscreen.LCDwriteString("Temp", CONST.YELLOW)
    tscreen.LCDmoveToRowColumn(9,2)
    tscreen.LCDwriteString("Hum", CONST.YELLOW)
    tscreen.LCDmoveToRowColumn(10,2)
    tscreen.LCDwriteString("Pres", CONST.YELLOW)
    tscreen.LCDmoveToRowColumn(8,8)
    tscreen.LCDwriteString("{:2.0f}".format(_minTemperatureLounge), CONST.YELLOW)
    tscreen.LCDmoveToRowColumn(8,13)
    tscreen.LCDwriteString("{:2.0f}".format(_maxTemperatureLounge), CONST.YELLOW)
    tscreen.LCDmoveToRowColumn(9,8)
    tscreen.LCDwriteString("{:2.0f}".format(_minHumidityLounge), CONST.YELLOW)
    tscreen.LCDmoveToRowColumn(9,13)
    tscreen.LCDwriteString("{:2.0f}".format(_maxHumidityLounge), CONST.YELLOW)
    tscreen.LCDmoveToRowColumn(10,8)
    tscreen.LCDwriteString("{:2.0f}".format(_minPressureLounge), CONST.YELLOW)
    tscreen.LCDmoveToRowColumn(10,13)
    tscreen.LCDwriteString("{:2.0f}".format(_maxPressureLounge), CONST.YELLOW)

    tscreen.LCDmoveToRowColumn(12,0)
    tscreen.LCDwriteString("Bedroom", CONST.RED)
    tscreen.LCDmoveToRowColumn(13,2)
    tscreen.LCDwriteString("Temp", CONST.RED)
    tscreen.LCDmoveToRowColumn(14,2)
    tscreen.LCDwriteString("Hum", CONST.RED)
    tscreen.LCDmoveToRowColumn(13,8)
    tscreen.LCDwriteString("{:2.0f}".format(_minTemperatureBedroom), CONST.RED)
    tscreen.LCDmoveToRowColumn(13,13)
    tscreen.LCDwriteString("{:2.0f}".format(_maxTemperatureBedroom), CONST.RED)
    tscreen.LCDmoveToRowColumn(14,8)
    tscreen.LCDwriteString("{:2.0f}".format(_minHumidityBedroom), CONST.RED)
    tscreen.LCDmoveToRowColumn(14,13)
    tscreen.LCDwriteString("{:2.0f}".format(_maxHumidityBedroom), CONST.RED)
    tscreen.LCDmoveToRowColumn(13,18)
    tscreen.LCDwriteString("{:3.0f}".format(_crcCountBedroom), CONST.RED)
    tscreen.LCDmoveToRowColumn(13,23)
    tscreen.LCDwriteString("{:3.0f}".format(_minsSinceBedroom), CONST.RED)

    tscreen.LCDmoveToRowColumn(16,0)
    tscreen.LCDwriteString("Gardenroom", CONST.GREEN)
    tscreen.LCDmoveToRowColumn(17,2)
    tscreen.LCDwriteString("Temp", CONST.GREEN)
    tscreen.LCDmoveToRowColumn(18,2)
    tscreen.LCDwriteString("Hum", CONST.GREEN)
    tscreen.LCDmoveToRowColumn(17,8)
    tscreen.LCDwriteString("{:2.0f}".format(_minTemperatureGardenroom), CONST.GREEN)
    tscreen.LCDmoveToRowColumn(17,13)
    tscreen.LCDwriteString("{:2.0f}".format(_maxTemperatureGardenroom), CONST.GREEN)
    tscreen.LCDmoveToRowColumn(18,8)
    tscreen.LCDwriteString("{:2.0f}".format(_minHumidityGardenroom), CONST.GREEN)
    tscreen.LCDmoveToRowColumn(18,13)
    tscreen.LCDwriteString("{:2.0f}".format(_maxHumidityGardenroom), CONST.GREEN)
    tscreen.LCDmoveToRowColumn(17,18)
    tscreen.LCDwriteString("{:3.0f}".format(_crcCountGardenroom), CONST.GREEN)
    tscreen.LCDmoveToRowColumn(17,23)
    tscreen.LCDwriteString("{:3.0f}".format(_minsSinceGardenroom), CONST.GREEN)
    
    tscreen.LCDmoveToRowColumn(20,0)
    tscreen.LCDwriteString("CPU", CONST.ORANGE)
    tscreen.LCDmoveToRowColumn(21,2)
    tscreen.LCDwriteString("Temp", CONST.ORANGE)
    tscreen.LCDmoveToRowColumn(21,8)
    tscreen.LCDwriteString("{:2.0f}".format(_minCpuTemp), CONST.ORANGE)
    tscreen.LCDmoveToRowColumn(21,13)
    tscreen.LCDwriteString("{:2.0f}".format(_maxCpuTemp), CONST.ORANGE)

    tscreen.LCDmoveToRowColumn(22,0)
    tscreen.LCDwriteString("Attic", CONST.ORANGE)
    tscreen.LCDmoveToRowColumn(23,2)
    tscreen.LCDwriteString("Temp", CONST.ORANGE)
    tscreen.LCDmoveToRowColumn(23,8)
    tscreen.LCDwriteString("{:2.0f}".format(_minTemperatureAttic), CONST.ORANGE)
    tscreen.LCDmoveToRowColumn(23,13)
    tscreen.LCDwriteString("{:2.0f}".format(_maxTemperatureAttic), CONST.ORANGE)
    tscreen.LCDmoveToRowColumn(23,18)
    tscreen.LCDwriteString("{:3.0f}".format(_crcCountAttic), CONST.ORANGE)
    tscreen.LCDmoveToRowColumn(23,23)
    tscreen.LCDwriteString("{:3.0f}".format(_minsSinceAttic), CONST.ORANGE)

    tscreen.LCDdrawButton(10, 300, "KIL")
    tscreen.LCDdrawButton(70, 300, "LOG")
    tscreen.LCDdrawButton(130, 300, "GPH")
    tscreen.LCDdrawButton(190, 300, "GPT")
    
def drawGraph(intType) :

    # 0..4   SummerT,HouseT,HouseH,HouseP,CPUt
    # 5..6   BedT, BedH
    # 7..8   GardenT, GardenH
    # 9..11  SummerCRC,BedCRC,GardenCRC
    # 12..14 SummerV,BedV,GardenV

    # Default to Humidity
    intBedroom = 6
    intGarden = 8
    intLounge = 2
    fltRange = 10.0
    # Or else do temperatures
    if intType == 1 :
        intBedroom = 5
        intGarden = 7
        intLounge = 1
        fltRange = 5.0
    
    tscreen.LCDclear()
    # Show the most recent 240 samples in the buffer
    if len(_houseData) > 240 :
        start = len(_houseData) - 240
        length = 239
    else :
        start = 0
        length = len(_houseData) - 1

    #print("Start {}".format(start))
    #print("Length {}".format(length))

    # Let's find out the min and max for scaling the display
    min = 100
    max = -100    
    for x in range (start, start + length) :
        d = _houseData[x].split(" ")
        if len(d) > 0 :
            # Let's start with the bedroom
            v = getNum(d[intBedroom])
            if v < min :
                min = v
            if v > max :
                max = v            
            # Now the gardenroom
            v = getNum(d[intGarden])
            if v < min :
                min = v
            if v > max :
                max = v            
            # Finally, the lounge
            v = getNum(d[intLounge])
            if v < min :
                min = v
            if v > max :
                max = v            

    gain = 320 / (max - min)

    #print("Min {}".format(min))    
    #print("Max {}".format(max))
    #print("Gain {}".format(gain))

    min -= fltRange
    if min < 10.0 :
        min = 0.0
    max += fltRange
    if max > 90.0 :
        max = 100.0
        
    if (min > 10.0) and (min < 20.0) :
        min = 10.0
    if (min > 20.0) and (min < 30.0) :
        min = 20.0
    if (min > 30.0) and (min < 40.0) :
        min = 30.0
    if (min > 40.0) and (min < 50.0) :
        min = 40.0
    if (min > 50.0) and (min < 60.0) :
        min = 60.0
    if (min > 60.0) and (min < 70.0) :
        min = 60.0
    if (min > 70.0) and (min < 80.0) :
        min = 70.0
    if (min > 80.0) and (min < 90.0) :
        min = 90.0
        
    if (max > 10.0) and (max < 20.0) :
        max = 20.0
    if (max > 20.0) and (max < 30.0) :
        max = 30.0
    if (max > 30.0) and (max < 40.0) :
        max = 40.0
    if (max > 40.0) and (max < 50.0) :
        max = 50.0
    if (max > 50.0) and (max < 60.0) :
        max = 60.0
    if (max > 60.0) and (max < 70.0) :
        max = 70.0
    if (max > 70.0) and (max < 80.0) :
        max = 80.0
    if (max > 80.0) and (max < 90.0) :
        max = 90.0

    gain = 320 / (max - min)

    #print("Adj Min {}".format(min))    
    #print("Adj Max {}".format(max))
    #print("Adj Gain {}".format(gain))

    # Y axis
    tscreen.LCDdrawLine(0, 0, 0, 319, CONST.WHITE)
    # X axis
    tscreen.LCDdrawLine(0, 159, 239, 159, CONST.WHITE)
    # And some labels for the Y axis
    tscreen.LCDmoveToRowColumn(0, 0)
    tscreen.LCDwriteString("{:2.0f}".format(max), CONST.WHITE)
    tscreen.LCDmoveToRowColumn(13, 0)
    tscreen.LCDwriteString("{:2.0f}".format(((max - min) / 2) + min), CONST.WHITE)
    tscreen.LCDmoveToRowColumn(25, 0)
    tscreen.LCDwriteString("{:2.0f}".format(min), CONST.WHITE)
   
    x = 0
    for xx in range (start, start + length) :
        d = _houseData[xx].split(" ")
        # Let's start with the bedroom
        v = getNum(d[intBedroom])
        y = 320 - ((v - min) * gain)
        tscreen.LCDsetPixel(x, y, CONST.RED)        

        # Now the gardenroom
        v = getNum(d[intGarden])
        y = 320 - ((v - min) * gain)
        tscreen.LCDsetPixel(x, y, CONST.GREEN)        

        # Finally the house
        v = getNum(d[intLounge])
        y = 320 - ((v - min) * gain)
        tscreen.LCDsetPixel(x, y, CONST.YELLOW)        

        x = x + 1
    
    for x in range(0, 10) :
        time.sleep(1.0)

def showLog() :

    addLogMessage("Info {}, {}".format(_fixCount, _resetCount))

    tscreen.LCDclear()
    line = 0
    if len(_logMessages) > 0 :
        for item in _logMessages :
            tscreen.LCDmoveToRowColumn(line, 0)
            tscreen.LCDwriteString(item, CONST.WHITE )
            line = line + 1
    else :
        tscreen.LCDmoveToRowColumn(line, 0)
        tscreen.LCDwriteString("No log messages", CONST.WHITE )
        
    for x in range(0, 10) :
        time.sleep(1.0)
        
def checkForLCDTouch() :

    global _screenIsBlank
    global _timeToBlank
    global _screenIsTemperatures
    global _shutDown

    touched, xCoord, yCoord = tscreen.LCDgetTouchState()
    #addLogMessage("Touch={},{}".format(xCoord, yCoord))
    
    if touched == 1 :
        _timeToBlank = time.time() + 60
        if _screenIsBlank == True :
            _screenIsTemperatures = True
            _screenIsMinMaxCrcFirstTime = True
            TouchScreenSetupInitialLayout()
            TouchScreenUpdateValues()
            _screenIsBlank = False
        else :
            if yCoord > 160 :
                if _screenIsTemperatures == True :
                    # If showing the temperatures, then flick to showing the min/max/crc                    
                    _screenIsTemperatures = False
                    TouchScreenMinMaxCrcLayout()
                else :
                    if yCoord > 260 :
                        if xCoord < 50 :
                            _shutDown = True
                            stopProg()
                            # resetAllMinMax(0)                    
                            # MDH THINK ABOUT THIS - 3 WIRE INTERFACE IS ONE WAY!
                            # And reset the CRC counts on the Arduino...
                            #_serialPortUnit2.write(b'\x52')
                            #_serialPortUnit2.write(b'\x0D')
                        elif xCoord < 120 :
                            showLog()
                        elif xCoord < 180 :
                            drawGraph(0)
                        else :
                            drawGraph(1)

                        TouchScreenSetupInitialLayout()
                        TouchScreenUpdateValues()
                        _screenIsTemperatures = True

    if (time.time() > _timeToBlank) and (_screenIsBlank == False) :
        tscreen.LCDclear()
        tscreen.LCDbacklight(0)
        _screenIsBlank = True

        if NO_TARGET==True :
            root.after(250, checkForLCDTouch)
            return

        #print ("Bye Bye")
        tscreen.LCDputToSleep(3600)

    root.after(250, checkForLCDTouch)
    
    
def createTemperatureWindow() :

    t = Toplevel()
    # If we don't set minsize, then the image does not show...
    t.minsize(width=1000, height=580)
    t.title("Temperature trend")

    # delete any existing image
    if os.path.exists("plot.txt") :
        os.remove("plot.txt")
    # delete any existing image
    if os.path.exists("plot.gif") :
        os.remove("plot.gif")

    # Now create the graph
    fileobj = open("plot.txt", 'a')
    for x in range(0, len(_houseData)) :
        arry = _houseData[x].split(" ")
        if (len(arry) > 9) :
            # Shed
            fileobj.write(str(getNum(arry[0])))
            fileobj.write(" ")
            # House
            fileobj.write(str(getNum(arry[1])))
            fileobj.write(" ")
            # CPU
            fileobj.write(str(getNum(arry[4])))
            fileobj.write(" ")
            # Bedroom
            fileobj.write(str(getNum(arry[5])))
            fileobj.write(" ")
            # Gardenroom
            fileobj.write(str(getNum(arry[7])))
            fileobj.write(" ")
            # Attic
            fileobj.write(str(getNum(arry[16])))
            fileobj.write("\r\n")

    #for x in range(0, 360) :
    #    fileobj.write(str(math.sin((x * math.pi) / 180)))
    #    fileobj.write("\r\n")
    fileobj.close()

    # Now graph the data to plot.gif
    os.system('gnuplot plotT.gp')

    # Make this slightly bigger than the plot size in plot.gp (960 * 540)
    i=PhotoImage(file="/home/pi/MarksStuff/plot.gif")
    c = Canvas(t, width=1000, height=580)
    c.pack()
    # Set this to prevent garbage collection destroying the image
    c.image=i
    # But we still need to set the image in the create...
    c.create_image(20, 20, anchor=NW, image=i)

def createHumidityWindow() :

    t = Toplevel()
    # If we don't set minsize, then the image does not show...
    t.minsize(width=1000, height=580)
    t.title("Humidity trend")

    # delete any existing image
    if os.path.exists("plot.txt") :
        os.remove("plot.txt")
    # delete any existing image
    if os.path.exists("plot.gif") :
        os.remove("plot.gif")

    # Now create the graph
    fileobj = open("plot.txt", 'a')
    for x in range(0, len(_houseData)) :
        arry = _houseData[x].split(" ")
        if (len(arry) > 22) :
            # House
            fileobj.write(str(getNum(arry[2])))
            fileobj.write(" ")
            # Bedroom
            fileobj.write(str(getNum(arry[6])))
            fileobj.write(" ")
            # Gardenroom
            fileobj.write(str(getNum(arry[8])))			
            fileobj.write(" ")
            # Attic
            fileobj.write(str(getNum(arry[18])))			
            fileobj.write(" ")
            # Summerhouse
            fileobj.write(str(getNum(arry[19])))			
            fileobj.write(" ")
            # Light level
            fileobj.write(str(getNum(arry[22])))			
            fileobj.write("\r\n")

    #for x in range(0, 360) :
    #    fileobj.write(str(math.cos((x * math.pi) / 180)))        
    #    fileobj.write("\r\n")
    fileobj.close()

    # Now graph the data to plot.gif
    os.system('gnuplot plotHb.gp')

    # Make this slightly bigger than the plot size in plot.gp (960 * 540)
    i=PhotoImage(file="/home/pi/MarksStuff/plot.gif")
    c = Canvas(t, width=1000, height=580)
    c.pack()
    # Set this to prevent garbage collection destroying the image
    c.image=i
    # But we still need to set the image in the create...
    c.create_image(20, 20, anchor=NW, image=i)
    
# ============================================================================
# The main start of the code.
# Create and layout the graphical elements
# Then get the two event timers running
# ============================================================================
	
root=Tk()

root.title("Arduino/Pi climatic condition reporting station")

checkForSavedValues()

# NOTE: All ITEMS that are updated dynamically MUST have the grid setting done AFTER The definition of the label

labelSlounge=Label(root, text="LOUNGE (0)", bg=CONST.HOUSE_COLOUR, fg=CONST.BACKGROUND_COLOUR)
labelSlounge.grid(row=1, column=0, rowspan=2, pady=2)
labelSbedroom=Label(root, text="BEDROOM (0)", bg=CONST.HOUSE_COLOUR, fg=CONST.BACKGROUND_COLOUR)
labelSbedroom.grid(row=3, column=0, rowspan=2, pady=2)
labelSgardenroom=Label(root, text="GARDEN ROOM (0)", bg=CONST.HOUSE_COLOUR, fg=CONST.BACKGROUND_COLOUR)
labelSgardenroom.grid(row=5, column=0, rowspan=2, pady=2)
labelSsummerhouse=Label(root, text="SUMMERHOUSE (0)", bg=CONST.SUMMERHOUSE_COLOUR, fg=CONST.BACKGROUND_COLOUR)
labelSsummerhouse.grid(row=7, column=0, rowspan=2, pady=2)
labelSattic=Label(root, text="Attic (0)", bg=CONST.ATTIC_COLOUR, fg="white")
labelSattic.grid(row=9, column=0, rowspan=2, pady=5)

# Attach all button events to the left mouse click <Button-1>, <Button-2> is the right mouse click
btnResetLoungeMinMax = Button(root, text="Reset Mn/Mx", width=10)
btnResetLoungeMinMax.bind('<Button-1>', resetLoungeMinMax)
btnResetLoungeMinMax.grid(row=1, column=1, rowspan=2, padx=5, pady=10)
btnResetBedroomMinMax=Button(root, text="Reset Mn/Mx", width=10)
btnResetBedroomMinMax.bind('<Button-1>', resetBedroomMinMax)
btnResetBedroomMinMax.grid(row=3, column=1, rowspan=2, padx=5, pady=10)
btnResetGardenroomMinMax=Button(root, text="Reset Mn/Mx", width=10)
btnResetGardenroomMinMax.bind('<Button-1>', resetGardenroomMinMax)
btnResetGardenroomMinMax.grid(row=5, column=1, rowspan=2, padx=5, pady=10)
btnResetSummerhouseMinMax=Button(root, text="Reset Mn/Mx", width=10)
btnResetSummerhouseMinMax.bind('<Button-1>', resetSummerhouseMinMax)
btnResetSummerhouseMinMax.grid(row=7, column=1, rowspan=2, padx=5, pady=10)
btnResetAtticMinMax = Button(root, text="Reset Mn/Mx", width=10)
btnResetAtticMinMax.bind('<Button-1>', resetAtticMinMax)
btnResetAtticMinMax.grid(row=9, column=1, rowspan=2, padx=5, pady=10)

btnResetAll=Button(root, text="Reset ALL Mn/Mx", width=20)
btnResetAll.bind('<Button-1>',resetAllMinMax)
btnResetAll.grid(row=12, column=0, columnspan=4, padx=20, pady=0)
btnExit=Button(root, text="Exit", width=30)
btnExit.bind('<Button-1>',stopProg)
btnExit.grid(row=13, column=0, columnspan=8, padx=20, pady=1)

_intResetAtMidnight = IntVar(value=1)
chkbutton = Checkbutton(root, text="Auto reset min/max at midnight", variable=_intResetAtMidnight)
chkbutton.grid(row=12, column=4, columnspan=4, pady=0)

# All the MINIMUM labels
labelLoungeTempMin = Label(root, text="Mn=0", bg=CONST.HOUSE_COLOUR, fg=CONST.BACKGROUND_COLOUR)
labelLoungeTempMin.grid(column=3, row=1, pady=10)
labelLoungeHumMin = Label(root, text="Mn=0", bg=CONST.HOUSE_COLOUR, fg=CONST.BACKGROUND_COLOUR)
labelLoungeHumMin.grid(column=5, row=1, pady=10)
labelLoungePresMin = Label(root, text="Mn=950", bg=CONST.HOUSE_COLOUR, fg=CONST.BACKGROUND_COLOUR)
labelLoungePresMin.grid(column=7, row=1, pady=10, padx=10)

labelBedroomTempMin = Label(root, text="Mn=0", bg=CONST.HOUSE_COLOUR, fg=CONST.BACKGROUND_COLOUR)
labelBedroomTempMin.grid(column=3, row=3, pady=10)
labelBedroomHumMin = Label(root, text="Mn=0", bg=CONST.HOUSE_COLOUR, fg=CONST.BACKGROUND_COLOUR)
labelBedroomHumMin.grid(column=5, row=3, pady=10)
labelBedroomVoltMin = Label(root, text="Mn=0", bg=CONST.HOUSE_COLOUR, fg=CONST.BACKGROUND_COLOUR)
labelBedroomVoltMin.grid(column=7, row=3, pady=10)

labelGardenroomTempMin = Label(root, text="Mn=0", bg=CONST.HOUSE_COLOUR, fg=CONST.BACKGROUND_COLOUR)
labelGardenroomTempMin.grid(column=3, row=5, pady=10)
labelGardenroomHumMin = Label(root, text="Mn=0", bg=CONST.HOUSE_COLOUR, fg=CONST.BACKGROUND_COLOUR)
labelGardenroomHumMin.grid(column=5, row=5, pady=10)
labelGardenroomVoltMin = Label(root, text="Mn=0", bg=CONST.HOUSE_COLOUR, fg=CONST.BACKGROUND_COLOUR)
labelGardenroomVoltMin.grid(column=7, row=5, pady=10)

labelSummerhouseTempMin = Label(root, text="Mn=0", bg=CONST.SUMMERHOUSE_COLOUR, fg=CONST.BACKGROUND_COLOUR)
labelSummerhouseTempMin.grid(column=3, row=7, pady=10)
labelSummerhouseVoltMin = Label(root, text="Mn=0", bg=CONST.SUMMERHOUSE_COLOUR, fg=CONST.BACKGROUND_COLOUR)
labelSummerhouseVoltMin.grid(column=7, row=7, pady=10)
labelSummerhouseHumMin = Label(root, text="Mn=0", bg=CONST.SUMMERHOUSE_COLOUR, fg=CONST.BACKGROUND_COLOUR)
labelSummerhouseHumMin.grid(column=5, row=7, pady=10)

labelAtticTempMin = Label(root, text="Mx=0", bg=CONST.ATTIC_COLOUR, fg="white")
labelAtticTempMin.grid(column=3, row=9, pady=10)
labelAtticVoltMin = Label(root, text="Mx=0", bg=CONST.ATTIC_COLOUR, fg="white")
labelAtticVoltMin.grid(column=7, row=9, pady=10)
labelAtticHumMin = Label(root, text="Mx=0", bg=CONST.ATTIC_COLOUR, fg="white")
labelAtticHumMin.grid(column=5, row=9, pady=10)

# All the MAXIMUM labels
labelLoungeTempMax = Label(root, text="Mx=0", bg=CONST.HOUSE_COLOUR, fg=CONST.BACKGROUND_COLOUR)
labelLoungeTempMax.grid(column=3, row=2, pady=10)
labelLoungeHumMax = Label(root, text="Mx=0", bg=CONST.HOUSE_COLOUR, fg=CONST.BACKGROUND_COLOUR)
labelLoungeHumMax.grid(column=5, row=2, pady=10)
labelLoungePresMax = Label(root, text="Mx=950", bg=CONST.HOUSE_COLOUR, fg=CONST.BACKGROUND_COLOUR)
labelLoungePresMax.grid(column=7, row=2, pady=10, padx=10)

labelBedroomTempMax = Label(root, text="Mx=0", bg=CONST.HOUSE_COLOUR, fg=CONST.BACKGROUND_COLOUR)
labelBedroomTempMax.grid(column=3, row=4, pady=10)
labelBedroomHumMax = Label(root, text="Mx=0", bg=CONST.HOUSE_COLOUR, fg=CONST.BACKGROUND_COLOUR)
labelBedroomHumMax.grid(column=5, row=4, pady=10)
labelBedroomVoltMax = Label(root, text="Mx=0", bg=CONST.HOUSE_COLOUR, fg=CONST.BACKGROUND_COLOUR)
labelBedroomVoltMax.grid(column=7, row=4, pady=10)

labelGardenroomTempMax = Label(root, text="Mx=0", bg=CONST.HOUSE_COLOUR, fg=CONST.BACKGROUND_COLOUR)
labelGardenroomTempMax.grid(column=3, row=6, pady=10)
labelGardenroomHumMax = Label(root, text="Mx=0", bg=CONST.HOUSE_COLOUR, fg=CONST.BACKGROUND_COLOUR)
labelGardenroomHumMax.grid(column=5, row=6, pady=10)
labelGardenroomVoltMax = Label(root, text="Mx=0", bg=CONST.HOUSE_COLOUR, fg=CONST.BACKGROUND_COLOUR)
labelGardenroomVoltMax.grid(column=7, row=6, pady=10)

labelSummerhouseTempMax = Label(root, text="Mx=0", bg=CONST.SUMMERHOUSE_COLOUR, fg=CONST.BACKGROUND_COLOUR)
labelSummerhouseTempMax.grid(column=3, row=8, pady=10)
labelSummerhouseVoltMax = Label(root, text="Mx=0", bg=CONST.SUMMERHOUSE_COLOUR, fg=CONST.BACKGROUND_COLOUR)
labelSummerhouseVoltMax.grid(column=7, row=8, pady=10)
labelSummerhouseHumMax = Label(root, text="Mx=0", bg=CONST.SUMMERHOUSE_COLOUR, fg=CONST.BACKGROUND_COLOUR)
labelSummerhouseHumMax.grid(column=5, row=8, pady=10)

labelAtticTempMax = Label(root, text="Mx=0", bg=CONST.ATTIC_COLOUR, fg="white")
labelAtticTempMax.grid(column=3, row=10, pady=10)
labelAtticVoltMax = Label(root, text="Mx=0", bg=CONST.ATTIC_COLOUR, fg="white")
labelAtticVoltMax.grid(column=7, row=10, pady=10)
labelAtticHumMax = Label(root, text="Mx=0", bg=CONST.ATTIC_COLOUR, fg="white")
labelAtticHumMax.grid(column=5, row=10, pady=10)

# CPU temperature is a label on its own
labelCpuTemp = Label(root, text="CPU Temp=0 (Mn=0 , Mx=0)", bg=CONST.CPU_COLOUR, fg=CONST.BACKGROUND_COLOUR)
labelCpuTemp.grid(column=0, row=11, columnspan=4, pady=10)

labelLightLevel = Label(root, text="Light level=0", bg=CONST.CPU_COLOUR, fg=CONST.BACKGROUND_COLOUR)
labelLightLevel.grid(column=4, row=11, columnspan=4, pady=10)

# All the METERS
loungeTempMeter = m.Meter(root, width = 160, height = 160)
loungeTempMeter.setrange(0, 30)
loungeTempMeter.set(0)
loungeTempMeter.setbezelcolour(CONST.HOUSE_COLOUR)
loungeTempMeter.grid(row=1, rowspan=2, column=2, pady=5)
loungeTempMeter.setsmalltext("Temperature")

loungeHumMeter = m.Meter(root, width = 160, height = 160)
loungeHumMeter.setrange(0, 100)
loungeHumMeter.set(0)
loungeHumMeter.setbezelcolour(CONST.HOUSE_COLOUR)
loungeHumMeter.grid(row=1, rowspan=2, column=4, pady=5)
loungeHumMeter.setsmalltext("Humidity")

loungePresMeter = m.Meter(root, width = 160, height = 160)
loungePresMeter.setrange(950, 1050)
loungePresMeter.set(0)
loungePresMeter.setbezelcolour(CONST.HOUSE_COLOUR)
loungePresMeter.grid(row=1, rowspan=2, column=6, pady=5)
loungePresMeter.setsmalltext("Pressure")

bedroomTempMeter = m.Meter(root, width = 160, height = 160)
bedroomTempMeter.setrange(0, 30)
bedroomTempMeter.set(_currentBedroomTemperature)
bedroomTempMeter.setbezelcolour(CONST.HOUSE_COLOUR)
bedroomTempMeter.grid(row=3, rowspan=2, column=2, pady=5)
bedroomTempMeter.setsmalltext("Temperature")

bedroomHumMeter = m.Meter(root, width = 160, height = 160)
bedroomHumMeter.setrange(0, 100)
bedroomHumMeter.set(_currentBedroomHumidity)
bedroomHumMeter.setbezelcolour(CONST.HOUSE_COLOUR)
bedroomHumMeter.grid(row=3, rowspan=2, column=4, pady=5)
bedroomHumMeter.setsmalltext("Humidity")

bedroomVoltMeter = m.Meter(root, width = 160, height = 160)
bedroomVoltMeter.setrange(3, 6)
bedroomVoltMeter.set(_currentBedroomVolt)
bedroomVoltMeter.setbezelcolour(CONST.HOUSE_COLOUR)
bedroomVoltMeter.grid(row=3, rowspan=2, column=6, pady=5)
bedroomVoltMeter.setsmalltext("Volts")

gardenroomTempMeter = m.Meter(root, width = 160, height = 160)
gardenroomTempMeter.setrange(0, 30)
gardenroomTempMeter.set(_currentGardenroomTemperature)
gardenroomTempMeter.setbezelcolour(CONST.HOUSE_COLOUR)
gardenroomTempMeter.grid(row=5, rowspan=2, column=2, pady=5)
gardenroomTempMeter.setsmalltext("Temperature")

gardenroomHumMeter = m.Meter(root, width = 160, height = 160)
gardenroomHumMeter.setrange(0, 100)
gardenroomHumMeter.set(_currentGardenroomHumidity)
gardenroomHumMeter.setbezelcolour(CONST.HOUSE_COLOUR)
gardenroomHumMeter.grid(row=5, rowspan=2, column=4, pady=5)
gardenroomHumMeter.setsmalltext("Humidity")

gardenroomVoltMeter = m.Meter(root, width = 160, height = 160)
gardenroomVoltMeter.setrange(3, 6)
gardenroomVoltMeter.set(_currentGardenroomVolt)
gardenroomVoltMeter.setbezelcolour(CONST.HOUSE_COLOUR)
gardenroomVoltMeter.grid(row=5, rowspan=2, column=6, pady=5)
gardenroomVoltMeter.setsmalltext("Volts")

summerhouseTempMeter = m.Meter(root, width = 160, height = 160)
summerhouseTempMeter.setrange(-10, 30)
summerhouseTempMeter.set(_currentSummerhouseTemperature)
summerhouseTempMeter.setbezelcolour(CONST.SUMMERHOUSE_COLOUR)
summerhouseTempMeter.grid(row=7, rowspan=2, column=2, pady=5)
summerhouseTempMeter.setsmalltext("Temperature")

summerhouseVoltMeter = m.Meter(root, width = 160, height = 160)
summerhouseVoltMeter.setrange(3, 6)
summerhouseVoltMeter.set(_currentSummerhouseVolt)
summerhouseVoltMeter.setbezelcolour(CONST.SUMMERHOUSE_COLOUR)
summerhouseVoltMeter.grid(row=7, rowspan=2, column=6, pady=5)
summerhouseVoltMeter.setsmalltext("Volts")

summerhouseHumMeter = m.Meter(root, width = 160, height = 160)
summerhouseHumMeter.setrange(0, 100)
summerhouseHumMeter.set(_currentSummerhouseHumidity)
summerhouseHumMeter.setbezelcolour(CONST.SUMMERHOUSE_COLOUR)
summerhouseHumMeter.grid(row=7, rowspan=2, column=4, pady=5)
summerhouseHumMeter.setsmalltext("Humidity")

atticTempMeter = m.Meter(root, width = 160, height = 160)
atticTempMeter.setrange(-10, 50)
atticTempMeter.set(_currentAtticTemperature)
atticTempMeter.setbezelcolour(CONST.ATTIC_COLOUR)
atticTempMeter.grid(row=9, rowspan=2, column=2, pady=5)
atticTempMeter.setsmalltext("Temperature")

atticVoltMeter = m.Meter(root, width = 160, height = 160)
atticVoltMeter.setrange(3, 6)
atticVoltMeter.set(_currentAtticVolt)
atticVoltMeter.setbezelcolour(CONST.ATTIC_COLOUR)
atticVoltMeter.grid(row=9, rowspan=2, column=6, pady=5)
atticVoltMeter.setsmalltext("Volts")

atticHumMeter = m.Meter(root, width = 160, height = 160)
atticHumMeter.setrange(0, 100)
atticHumMeter.set(_currentAtticHumidity)
atticHumMeter.setbezelcolour(CONST.ATTIC_COLOUR)
atticHumMeter.grid(row=9, rowspan=2, column=4, pady=5)
atticHumMeter.setsmalltext("Humidity")

menubar = Menu(root)
graphmenu = Menu(menubar, tearoff=0)
graphmenu.add_command(label="Temperatures", command=createTemperatureWindow)
graphmenu.add_command(label="Humidities", command=createHumidityWindow)
menubar.add_cascade(label="Graphs", menu=graphmenu)
root.config(menu=menubar)
root.resizable(False, False)

updateHouse.recordCountFromLounge = 0
checkForNewDay.thisDay = -1

# hard reset the touch display
GPIO.setmode(GPIO.BCM)
GPIO.setup(CONST.TOUCHSCREEN_RESET, GPIO.OUT)
GPIO.output(CONST.TOUCHSCREEN_RESET, 0)
GPIO.setup(CONST.TOUCHSCREEN_RESET, GPIO.IN)

# Reset the ARDUINO 3 wire comms link
GPIO.setup(CONST.WIRECLK, GPIO.OUT)
GPIO.output(CONST.WIRECLK, 0)
# Reset
GPIO.setup(CONST.WIRERESET, GPIO.OUT)
GPIO.output(CONST.WIRERESET, 0)
# Data
GPIO.setup(CONST.WIREDATA, GPIO.IN)
# Now toggle reset to force Arduino to load its buffers
GPIO.output(CONST.WIRERESET, 1)
time.sleep(1.0)
GPIO.output(CONST.WIRERESET, 0)

# Wait for the display to reset (5 seconds) before sending any serial comms to it
# Also gives chance for Arduino to complete the 3 wire reset so don't remove!
time.sleep(5)

tscreen = touchscreen.screen()

if tscreen.LCDgetSerialPort(9600, True) == 0 :
    addLogMessage("Touchscreen err")

# Set us to 115200 - our default power on is 9600
tscreen.LCDsetBaudRate()

updateHouse.trendCount = 0

TouchScreenSetupInitialLayout()

# Start the regular timer events running
updateRadioUnits()
updateMinutesSinceCounters()

_timeToBlank = time.time() + 60
_screenIsBlank = False
checkForLCDTouch()

root.mainloop()

if _shutDown == True :
    call("sudo nohup shutdown -h now", shell=True)
