// ============================================================
// TITLE:  InHouseClimateBME.c
// AUTHOR: M Hollingworth
// DATE:   21/11/2018
//
// This application is to be used in conjunction with the 
// InHouseClimate application
// This one sits on an Arduino UNO with an RF transceiver and BME280 pressure/humidity/temperature sensor
// Continually monitor the RF transceiver for messages sent by the summerhouse, bedroom, gardenroom and attic units
// Send all readings via a proprietary 3 wire link to a Raspberry Pi.

// NOTE: Can't use on-board LED (pin 13) with Transceiver module
//       as it uses the pin for the SCK signal on the SPI bus

// ============================================================


#include <RFM12B.h>
#include <PString.h>
#include <EEPROM.h>
#include <digitalWriteFast.h>

#include <Adafruit_Sensor.h>
#include <Adafruit_BME280.h>

// Marks' proprietary 3 wire interface
#define MY_3_WIRE_BUFFER_SIZE 256
#define MY_RESET 5
#define MY_DATA  9
// Assign this to a pin change interrupt
#define MY_CLOCK 3

#define SHED    2
#define BEDROOM 10
#define GARDEN  11
#define ATTIC   12

// Remove this when going live
//#define USING_DUMMY_DATA 1

#define USING_3WIRE_INTERFACE 1

// You will need to initialize the radio by telling it what ID it has and what network it's on
// The NodeID takes values from 1-127, 0 is reserved for sending broadcast messages (send to all nodes)
// The Network ID takes values from 0-255
// By default the SPI-SS line used is D10 on Atmega328. You can change it by calling .SetCS(pin) where pin can be {8,9,10}
#define NODEID           1   //network ID used for this unit
#define NETWORKID        99  //the network ID we are on
#define SERIAL_BAUD      57600    


// 17 minutes (in milliseconds) - summerhouse transmits a message every 15 minutes
#define MESSAGE_TIMEOUT 1020000
// Maximum serial input buffer length
#define MAX_COMMAND_LEN 4
// Maximum size of an incoming RF message in bytes
#define MAX_RF_MESSAGE_SIZE 64

// Pin number on the ARDUINO board that the light sensor (light dependent resistor) is attached to
#define NORPS12_PIN   A0

// Comment this out for the final version
//#define SERIAL_DEBUG    1
//#define PACKET_DEBUG 1

//encryption is OPTIONAL
//to enable encryption you will need to:
// - provide a 16-byte encryption KEY (same on all nodes that talk encrypted)
// - to call .Encrypt(KEY) to start encrypting
// - to stop encrypting call .Encrypt(NULL)
//uint8_t KEY[] = "ABCDABCDABCDABCD";

// Need an instance of the Radio Module
RFM12B         radio;
int            mintMessageNumber = 0;

word           mwrdBadCountShed;
word           mwrdBadCountBedroom;
word           mwrdBadCountGardenroom;
word           mwrdBadCountAttic;
float          mfltShedTemp;
float          mfltAtticTemp;
float          mfltBedroomTemp;
float          mfltGardenroomTemp;
float          mfltBedroomHumidity;
float          mfltGardenroomHumidity;
float          mfltAtticHumidity;
float          mfltShedHumidity;
int            mintShedMessageCount;
int            mintAtticMessageCount;
int            mintBedroomMessageCount;
int            mintGardenroomMessageCount;
float          mfltShedVoltage;
float		       mfltBedroomVoltage;
float		       mfltGardenroomVoltage;
float          mfltAtticVoltage;
float          mfltHouseTemp;
float          mfltHouseHumidity;
float          mfltHousePressure;
int            mintCorrectedCount;
int            mintLight;

char           mbytValues[10][10];
char           mbytCRC1;
char           mbytCRC2;

char           mbytData[MAX_RF_MESSAGE_SIZE];

byte           mbyt3wireValues[MY_3_WIRE_BUFFER_SIZE];
byte           mbytLastResetState = 0;
byte           mdataPtr = 0;
byte           mbitCount = 0;


// Pressure/Temp/Humidity sensor on I2C
Adafruit_BME280 bme;

#ifdef PACKET_DEBUG
long           mlngStart;
#endif


void setup()
{
  word temp;
  
  radio.Initialize(NODEID, RF12_433MHZ, NETWORKID, 0, 35);

  bme.begin();

  Serial.begin(SERIAL_BAUD);
  
  mwrdBadCountShed = 0;
  mwrdBadCountBedroom = 0;
  mwrdBadCountGardenroom = 0;
  mwrdBadCountAttic = 0;

  mfltShedVoltage = 0.0;
  mfltBedroomVoltage = 0.0;
  mfltGardenroomVoltage = 0.0;
  mfltAtticVoltage = 0.0;
  
  mintShedMessageCount = 0;
  mintBedroomMessageCount = 0;
  mintGardenroomMessageCount = 0; 
  mintAtticMessageCount = 0; 

  mfltShedTemp = 0.0;
  mfltAtticTemp = 0.0;
  mfltBedroomTemp = 0.0;
  mfltGardenroomTemp = 0.0;

  mfltBedroomHumidity = 0.0;
  mfltGardenroomHumidity = 0.0;
  mfltAtticHumidity = 0.0;

  mfltHouseTemp = 0.0;
  mfltHousePressure = 0.0;
  mfltHouseHumidity = 0.0;
  mfltShedHumidity = 0.0;

  mintCorrectedCount = 0;
  mintLight = 0;
  
  #ifdef PACKET_DEBUG
  mlngStart = millis();
  #endif

  // Keep a reset count
  EEPROM.get(0, temp);
  temp++;
  EEPROM.put(0, temp);

  #ifdef USING_DUMMY_DATA
  mfltShedVoltage = 5.61;
  mfltBedroomVoltage = 4.95;
  mfltGardenroomVoltage = 5.2;
  mfltAtticVoltage = 4.9;
  mwrdBadCountShed = 1;
  mwrdBadCountBedroom = 2;
  mwrdBadCountGardenroom = 3;
  mwrdBadCountAttic = 4;
  mintShedMessageCount = 5;
  mintBedroomMessageCount = 6;
  mintGardenroomMessageCount = 7; 
  mintAtticMessageCount = 8;
  mfltShedTemp = 12.1;
  mfltAtticTemp = 9.3;
  mfltBedroomTemp = 22.1;
  mfltGardenroomTemp = 25.5;
  mfltShedHumidity = 81.2;
  mfltBedroomHumidity = 67.4;
  mfltGardenroomHumidity = 56.6;
  mfltAtticHumidity = 77.2;
  mfltHouseTemp = 32.5;
  mfltHousePressure = 1001.54;
  mfltHouseHumidity = 51.23;
  mintLight = 44;
  #endif

  pinModeFast(MY_CLOCK, INPUT);
  pinModeFast(MY_DATA, OUTPUT);
  pinModeFast(MY_RESET, INPUT);
  attachInterrupt(digitalPinToInterrupt(MY_CLOCK), myClockInterrupt, RISING);

  mdataPtr = 0;
  mbitCount = 0;
  mbytLastResetState = 0;
  // Copy some proper data to 3 wire interface buffer
  sendData();
}


// Rising clock edge - we need tx next data bit
void myClockInterrupt(void)
{
  if (mbyt3wireValues[mdataPtr] & (1 << mbitCount) )
    digitalWriteFast(MY_DATA, HIGH);
  else
    digitalWriteFast(MY_DATA, LOW);

  mbitCount++;
  if (mbitCount == 8)
  {
    mbitCount = 0;
    mdataPtr++;
    if (mdataPtr >= MY_3_WIRE_BUFFER_SIZE)
    {
        mdataPtr = 0;
    }
  }
}


int addToConcat(char *p, int index)
{
    int  i = index;
    char v = p[0];
    int  x = 0;
    
    // Allow extra at end for the terminating ,,,
    while (v !=0 && i < MY_3_WIRE_BUFFER_SIZE - 3)
    {
        mbyt3wireValues[i++] = v;
        x++;        
        v = p[x];
    }
    if (i < MY_3_WIRE_BUFFER_SIZE - 3)
    {
        mbyt3wireValues[i++] = ',';
    }
    else
    {
        mbyt3wireValues[i] = ',';        
    }

    return i;
}


int sendTemperatures(int intIndex)
{    
    int intI = intIndex;

    #ifdef USING_SERIAL_INTERFACE
    Serial.print(mfltShedTemp);
    Serial.print(",");
    Serial.print(mfltBedroomTemp);
    Serial.print(",");
    Serial.print(mfltGardenroomTemp);
    Serial.print(",");
    Serial.print(mfltAtticTemp);
    Serial.print(",");
    #endif

    #ifdef USING_3WIRE_INTERFACE
    char buf1[7];
    char buf2[7];
    char buf3[7];
    char buf4[7];

    PString str1(buf1, sizeof(buf1));
    str1.print(mfltShedTemp);
    PString str2(buf2, sizeof(buf2));
    str2.print(mfltBedroomTemp);
    PString str3(buf3, sizeof(buf3));
    str3.print(mfltGardenroomTemp);
    PString str4(buf4, sizeof(buf4));
    str4.print(mfltAtticTemp);
        
    intI = addToConcat(buf1, intI);
    intI = addToConcat(buf2, intI);
    intI = addToConcat(buf3, intI);
    intI = addToConcat(buf4, intI);
    #endif

    return intI;
}


int sendHumidities(int intIndex)
{
    int intI = intIndex;

    #ifdef USING_SERIAL_INTERFACE
    Serial.print(mfltBedroomHumidity);
    Serial.print(",");
    Serial.print(mfltGardenroomHumidity);
    Serial.print(",");
    Serial.print(mfltAtticHumidity);
    Serial.print(",");
    Serial.print(mfltShedHumidity);
    Serial.print(",");
    #endif

    #ifdef USING_3WIRE_INTERFACE
    char buf1[7];
    char buf2[7];
    char buf3[7];
    char buf4[7];

    PString str1(buf1, sizeof(buf1));
    str1.print(mfltBedroomHumidity);
    PString str2(buf2, sizeof(buf2));
    str2.print(mfltGardenroomHumidity);
    PString str3(buf3, sizeof(buf3));
    str3.print(mfltAtticHumidity);
    PString str4(buf4, sizeof(buf4));
    str4.print(mfltShedHumidity);
        
    intI = addToConcat(buf1, intI);
    intI = addToConcat(buf2, intI);    
    intI = addToConcat(buf3, intI);    
    intI = addToConcat(buf4, intI);    
    #endif

    return intI;
}


int sendMessageCounts(int intIndex)
{
    int intI = intIndex;

    #ifdef USING_SERIAL_INTERFACE
    Serial.print(mintShedMessageCount);
    Serial.print(",");
    Serial.print(mintBedroomMessageCount);
    Serial.print(",");
    Serial.print(mintGardenroomMessageCount);
    Serial.print(",");
    Serial.println(mintAtticMessageCount);
    Serial.print(",");
    #endif

    #ifdef USING_3WIRE_INTERFACE
    char buf1[7];
    char buf2[7];
    char buf3[7];
    char buf4[7];

    PString str1(buf1, sizeof(buf1));
    str1.print(mintShedMessageCount);
    PString str2(buf2, sizeof(buf2));
    str2.print(mintBedroomMessageCount);
    PString str3(buf3, sizeof(buf3));
    str3.print(mintGardenroomMessageCount);
    PString str4(buf4, sizeof(buf4));
    str4.print(mintAtticMessageCount);
        
    intI = addToConcat(buf1, intI);
    intI = addToConcat(buf2, intI);
    intI = addToConcat(buf3, intI);
    intI = addToConcat(buf4, intI);
    #endif

    return intI;
}


int sendBadMessageCounts(int intIndex)
{
    int intI = intIndex;

    #ifdef USING_SERIAL_INTERFACE
    Serial.print(mwrdBadCountShed);
    Serial.print(",");
    Serial.print(mwrdBadCountBedroom);
    Serial.print(",");
    Serial.print(mwrdBadCountGardenroom);
    Serial.print(",");
    Serial.print(mwrdBadCountAttic);
    Serial.print(",");
    #endif

    #ifdef USING_3WIRE_INTERFACE
    char buf1[7];
    char buf2[7];
    char buf3[7];
    char buf4[7];

    PString str1(buf1, sizeof(buf1));
    str1.print(mwrdBadCountShed);
    PString str2(buf2, sizeof(buf2));
    str2.print(mwrdBadCountBedroom);
    PString str3(buf3, sizeof(buf3));
    str3.print(mwrdBadCountGardenroom);
    PString str4(buf4, sizeof(buf4));
    str4.print(mwrdBadCountAttic);
        
    intI = addToConcat(buf1, intI);
    intI = addToConcat(buf2, intI);
    intI = addToConcat(buf3, intI);
    intI = addToConcat(buf4, intI);
    #endif

    return intI;
}


int sendVoltages(int intIndex)
{    
    int intI = intIndex;

    #ifdef USING_SERIAL_INTERFACE
    // I want fixed 3 decimal places on all of the voltage readings
    Serial.print(mfltShedVoltage, 3);
	Serial.print(",");
	Serial.print(mfltBedroomVoltage, 3);
	Serial.print(",");
	Serial.print(mfltGardenroomVoltage, 3);
    Serial.print(",");
    Serial.print(mfltAtticVoltage, 3);
    Serial.print(",");
    #endif

    #ifdef USING_3WIRE_INTERFACE
    char buf1[7];
    char buf2[7];
    char buf3[7];
    char buf4[7];

    PString str1(buf1, sizeof(buf1));
    str1.print(mfltShedVoltage, 3);
    PString str2(buf2, sizeof(buf2));
    str2.print(mfltBedroomVoltage, 3);
    PString str3(buf3, sizeof(buf3));
    str3.print(mfltGardenroomVoltage, 3);
    PString str4(buf4, sizeof(buf4));
    str4.print(mfltAtticVoltage, 3);
        
    intI = addToConcat(buf1, intI);
    intI = addToConcat(buf2, intI);
    intI = addToConcat(buf3, intI);
    intI = addToConcat(buf4, intI);
    #endif

    return intI;
}


int sendMiscellaneous(int intIndex)
{   
    int intI = intIndex;
    word temp;

    // Get the number of resets we've had
    EEPROM.get(0, temp);
    
    #ifdef USING_SERIAL_INTERFACE
    Serial.print(mintCorrectedCount);
    Serial.print(",");
    Serial.print(temp);
    #endif

    #ifdef USING_3WIRE_INTERFACE
    char buf1[7];
    char buf2[7];

    PString str1(buf1, sizeof(buf1));
    str1.print(mintCorrectedCount);
    PString str2(buf2, sizeof(buf2));
    str2.print(temp);
        
    intI = addToConcat(buf1, intI);
    intI = addToConcat(buf2, intI);
    #endif

    return intI;
}


int sendHouseInfo(int intIndex)
{
    int intI = intIndex;

    #ifdef USING_SERIAL_INTERFACE
    Serial.print(mfltHouseTemp);
    Serial.print(",");
    Serial.print(mfltHouseHumidity);
    Serial.print(",");
    Serial.print(mfltHousePressure);
    Serial.print(",");
    #endif

    #ifdef USING_3WIRE_INTERFACE
    char buf1[7];
    char buf2[7];
    char buf3[10];
    char buf4[7];

    PString str1(buf1, sizeof(buf1));
    str1.print(mfltHouseTemp);
    PString str2(buf2, sizeof(buf2));
    str2.print(mfltHouseHumidity);
    PString str3(buf3, sizeof(buf3));
    str3.print(mfltHousePressure);
    PString str4(buf4, sizeof(buf4));
    str4.print(mintLight);
        
    intI = addToConcat(buf1, intI);
    intI = addToConcat(buf2, intI);    
    intI = addToConcat(buf3, intI);    
    intI = addToConcat(buf4, intI);    
    #endif

    return intI;
}


void sendData(void)
{
    int intI;
    
    mbyt3wireValues[0] = 'V';
    mbyt3wireValues[1] = ',';    
    intI = sendTemperatures(2);
    intI = sendHumidities(intI);
    intI = sendVoltages(intI);
    intI = sendMessageCounts(intI);
    intI = sendBadMessageCounts(intI);
    intI = sendMiscellaneous(intI);
    intI = sendHouseInfo(intI);
    // Mark the end of the data with 3 consecutive commas (sendHouseInfo() puts its own final comma in)
    mbyt3wireValues[intI] = ',';
    mbyt3wireValues[++intI] = ',';
    mbyt3wireValues[++intI] = 0;
}


/*void handleShedAndAttic(byte bytShedOrAttic)
{
  byte bytVarCount;
  byte bytRealCRC;

  bytVarCount = splitValues(mbytData);          
  bytRealCRC = mbytData[*radio.DataLen - 1];

  if (radio.CRCPass())
  {
    // Only if we have enough variables in the packet
    if (bytVarCount >= 3)
    {
      if (chkValues(1, false) ==  true)
      {
        if (bytShedOrAttic == SHED)
        {
          mfltShedTemp = atof(&mbytValues[1][0]);
          mfltShedVoltage = atof(&mbytValues[2][0]) / 10000.0f;
        }
        else
        {
          mfltAtticTemp = atof(&mbytValues[1][0]);
          mfltAtticVoltage = atof(&mbytValues[2][0]) / 10000.0f;        
        }
      }
    }
  }
  else
  {
    if (mbytCRC1 != bytRealCRC)
    {
      if (mbytCRC2 == bytRealCRC)
      {
        if (bytVarCount >= 5)
        {
          if (chkValues(3, false) ==  true)
          {
            if (bytShedOrAttic == SHED)
            {
              mfltShedTemp = atof(&mbytValues[3][0]);
              mfltShedVoltage = atof(&mbytValues[4][0]) / 10000.0f;            
            }
            else
            {
              mfltAtticTemp = atof(&mbytValues[3][0]);
              mfltAtticVoltage = atof(&mbytValues[4][0]) / 10000.0f;
            }
            mintCorrectedCount++;
          }
        }
      }
      else
      {
        if (bytShedOrAttic == SHED)
          mwrdBadCountShed++;      
        else
          mwrdBadCountAttic++;       
      }
    }
    else
    {
      if (bytVarCount >= 3)
      {
        if (chkValues(1, false) ==  true)
        {
          if (bytShedOrAttic == SHED)
          {
            mfltShedTemp = atof(&mbytValues[1][0]);
            mfltShedVoltage = atof(&mbytValues[2][0]) / 10000.0f;
          }
          else
          {
            mfltAtticTemp = atof(&mbytValues[1][0]);
            mfltAtticVoltage = atof(&mbytValues[2][0]) / 10000.0f;            
          }
          mintCorrectedCount++;
        }
      }
    }
  }
}*/


void handleBedAndGarden(byte bytType)
{
  byte bytVarCount;
  byte bytRealCRC;

  bytVarCount = splitValues(mbytData);              
  bytRealCRC = mbytData[*radio.DataLen - 1];

  if (radio.CRCPass())
  {
    if (bytVarCount >= 4)
    {
      if (chkValues(1, true) ==  true)
      {
        switch (bytType)
        {
            case BEDROOM:
              mfltBedroomTemp = atof(&mbytValues[1][0]);
              mfltBedroomHumidity = atof(&mbytValues[2][0]);
              mfltBedroomVoltage = atof(&mbytValues[3][0]) / 10000.0f;            
            break;
            case GARDEN:
              mfltGardenroomTemp = atof(&mbytValues[1][0]);
              mfltGardenroomHumidity = atof(&mbytValues[2][0]);
              mfltGardenroomVoltage = atof(&mbytValues[3][0]) / 10000.0f;
            break;
            case ATTIC:
              mfltAtticTemp = atof(&mbytValues[1][0]);
              mfltAtticHumidity = atof(&mbytValues[2][0]);
              mfltAtticVoltage = atof(&mbytValues[3][0]) / 10000.0f;
            break;
            case SHED:
              mfltShedTemp = atof(&mbytValues[1][0]);
              mfltShedHumidity = atof(&mbytValues[2][0]);
              mfltShedVoltage = atof(&mbytValues[3][0]) / 10000.0f;
            break;
        }
      }
    }
  }
  else
  {
    if (mbytCRC1 != bytRealCRC)
    {
      if (mbytCRC2 == bytRealCRC)
      {
        if (bytVarCount >= 7)
        {
          if (chkValues(4, true) ==  true)
          {
            switch (bytType)
            {
              case BEDROOM:
                mfltBedroomTemp = atof(&mbytValues[4][0]);
                mfltBedroomHumidity = atof(&mbytValues[5][0]);
                mfltBedroomVoltage = atof(&mbytValues[6][0]) / 10000.0f;            
              break;
              case GARDEN:
                mfltGardenroomTemp = atof(&mbytValues[4][0]);
                mfltGardenroomHumidity = atof(&mbytValues[5][0]);
                mfltGardenroomVoltage = atof(&mbytValues[6][0]) / 10000.0f;
              break;
              case ATTIC:
                mfltAtticTemp = atof(&mbytValues[4][0]);
                mfltAtticHumidity = atof(&mbytValues[5][0]);
                mfltAtticVoltage = atof(&mbytValues[6][0]) / 10000.0f;
              break;
              case SHED:
                mfltShedTemp = atof(&mbytValues[4][0]);
                mfltShedHumidity = atof(&mbytValues[5][0]);
                mfltShedVoltage = atof(&mbytValues[6][0]) / 10000.0f;
              break;
            }
            mintCorrectedCount++;
          }
        }
      }
      else
      {
        if (bytType == BEDROOM)        
          mwrdBadCountBedroom++;
        else if (bytType == GARDEN)
          mwrdBadCountGardenroom++;
        else if (bytType == ATTIC)
          mwrdBadCountAttic++;
        else if (bytType == SHED)
          mwrdBadCountShed++;
      }
    }
    else
    {
      if (bytVarCount >= 4)
      {
        if (chkValues(1, true) ==  true)
        {
          switch (bytType)
          {
            case BEDROOM:
              mfltBedroomTemp = atof(&mbytValues[4][0]);
              mfltBedroomHumidity = atof(&mbytValues[5][0]);
              mfltBedroomVoltage = atof(&mbytValues[6][0]) / 10000.0f;            
            break;
            case GARDEN:
              mfltGardenroomTemp = atof(&mbytValues[4][0]);
              mfltGardenroomHumidity = atof(&mbytValues[5][0]);
              mfltGardenroomVoltage = atof(&mbytValues[6][0]) / 10000.0f;
            break;
            case ATTIC:
              mfltAtticTemp = atof(&mbytValues[4][0]);
              mfltAtticHumidity = atof(&mbytValues[5][0]);
              mfltAtticVoltage = atof(&mbytValues[6][0]) / 10000.0f;
            break;
            case SHED:
              mfltShedTemp = atof(&mbytValues[4][0]);
              mfltShedHumidity = atof(&mbytValues[5][0]);
              mfltShedVoltage = atof(&mbytValues[6][0]) / 10000.0f;
            break;
          }
          mintCorrectedCount++;
        }
      }
    }
  }              
}


void loop()
{
  byte i;
  word wrdNode;
  byte bytVarCount;
  byte bytRealCRC;
  unsigned long currentTime;

  // Reset on the falling edge (gets this every 5 seconds from the Raspberry Pi)
  if (digitalReadFast(MY_RESET) == 0 && mbytLastResetState == 1)
  {
    mdataPtr = 0;
    mbitCount = 0;
    mbytLastResetState = 0;
    
    mfltHouseTemp = bme.readTemperature();
    mfltHouseHumidity = bme.readHumidity();

    mfltHousePressure = bme.readPressure() / 100.0;

    mintLight = analogRead(NORPS12_PIN);

    // Copy data to buffer
    sendData();
  }
  if (digitalReadFast(MY_RESET))
  {
    mbytLastResetState = 1;
  }
    
  //serialParse();
      
  if (radio.ReceiveComplete())
  {
    wrdNode = radio.GetSender();

    #ifdef SERIAL_DEBUG
    Serial.println("Rxed");
    #endif
    
    #ifdef PACKET_DEBUG
    Serial.print(radio.CRCVal(), HEX);
    Serial.print("  [");
    Serial.print(wrdNode);
    Serial.print("]  ");
    Serial.println((millis() - mlngStart) / 1000);
    mlngStart = millis();
    #endif
    
    if (wrdNode == SHED || wrdNode == BEDROOM || wrdNode == GARDEN || wrdNode == ATTIC)
    {      
      #ifdef SERIAL_DEBUG
  	  Serial.print('[');
      Serial.print(wrdNode);
      Serial.print("] ");
      #endif
	  
      #ifdef PACKET_DEBUG
      Serial.println("PASS");
      #endif
      
      for (i = 0; i < *radio.DataLen; i++)
      {
        if (i < MAX_RF_MESSAGE_SIZE)
        {
          mbytData[i] = (char) radio.Data[i];
          #ifdef PACKET_DEBUG
		      Serial.print(mbytData[i], HEX);
          Serial.print(" ");       
		      #endif
        }
      }
      
      #ifdef PACKET_DEBUG
      Serial.println("");
      #endif

      for (i = 0; i < 10; i++)
      {
        // Make all values "0", nul terminated so atof doesn't fail if one is missing...
        mbytValues[i][0] = '0';
        mbytValues[i][1] = 0;
      }
      
      switch (wrdNode)
      {
        case SHED:
          mintShedMessageCount++;
          handleBedAndGarden(SHED);
        break;

        case BEDROOM:
          mintBedroomMessageCount++;
          handleBedAndGarden(BEDROOM);          
        break;

        case GARDEN:
          mintGardenroomMessageCount++;
          handleBedAndGarden(GARDEN);          
        break;

        case ATTIC:
          mintAtticMessageCount++;
          handleBedAndGarden(ATTIC);
        break;

        default :
        break;
      }
      
      if (radio.ACKRequested())
      {
        radio.SendACK();
        #ifdef SERIAL_DEBUG
		    Serial.print(" - ACK sent");
		#endif
      }
    }
    else
    {
      #ifdef PACKET_DEBUG
      Serial.println("FAIL");
      for (i = 0; i < *radio.DataLen; i++)
      {
        mbytData[i] = (char) radio.Data[i];
        Serial.print(mbytData[i], HEX);
        Serial.print(" ");       
      }
      Serial.println("");
      #endif
      
      //MDH Increment the right one dependent upon the node received
      #ifdef SERIAL_DEBUG
      Serial.print("Sender = ");
      #endif          
      switch (wrdNode)
      {
        case SHED:
          #ifdef SERIAL_DEBUG
          Serial.println("Shed");
          #endif          
          mwrdBadCountShed++;
        break;
        case BEDROOM:        
          #ifdef SERIAL_DEBUG
          Serial.println("Bedroom");
          #endif          
          mwrdBadCountBedroom++;
        break;
        case GARDEN:
          #ifdef SERIAL_DEBUG
          Serial.println("Gardenroom");
          #endif          
          mwrdBadCountGardenroom++;
        break;
        case ATTIC:
          #ifdef SERIAL_DEBUG
          Serial.println("Attic");
          #endif          
          mwrdBadCountAttic++;
        break;
        default:
          #ifdef SERIAL_DEBUG
          Serial.print("Unknown - ");
          Serial.println(wrdNode);
          #endif
        break;
      }      
    }
    
	#ifdef SERIAL_DEBUG
	Serial.println();
	#endif
  }

}

static byte splitValues(char *pData)
{
  byte varCount = 0;
  byte c = 0;
  byte i = 0;
  char *ptr = pData;
  bool terminated = false;
  
  mbytCRC1 = mbytCRC2 = 0;
  
  while (*ptr != 0 && i < *radio.DataLen && i < MAX_RF_MESSAGE_SIZE)
  {
    if (c < 10 && varCount < 10)
    {
      if (varCount > 0 && varCount < 4)
      {
        mbytCRC1 ^= *ptr;      
      }
      if (varCount > 3 && varCount < 7)
      {
        mbytCRC2 ^= *ptr;
      }
      if (*ptr == ',')
      {
        mbytValues[varCount][c] = 0;
        varCount++;
        c = 0;        
        terminated = true;
      }
      else
      {
        mbytValues[varCount][c++] = *ptr;
        if (c == 10)
        {
            // No field should be > 10 characters
            // Therefore, we must have corruption, so put in a dummy value of "0" and nul terminate it
            mbytValues[varCount][0] = '0';
            mbytValues[varCount][1] = 0;
            // And start the next variable
            c = 0;
            varCount++;
        }
        terminated = false;
      }
    }

    ptr++;
    i++;
  }

  if (terminated == false && c < 10 && varCount < 10)
  {
    mbytValues[varCount][c] = 0;
  }
      
  return varCount;
}

static bool chkValues(byte i, bool chkHumidity)
{
  // Check temperature
  if (atof(&mbytValues[i][0]) > 50.0)
    return false;
  if (chkHumidity == true)
  {
    // Check humidity
    if (atof(&mbytValues[i + 1][0]) > 100.0)
      return false;
    // Check voltage (in position 2)
    if (atof(&mbytValues[i + 2][0]) < 0.1)
      return false;
  }
  else
  {
    // Check voltage (in position 1, no humidity from shed))
    if (atof(&mbytValues[i + 1][0]) < 0.1)
      return false;
  }
  return true;
}
