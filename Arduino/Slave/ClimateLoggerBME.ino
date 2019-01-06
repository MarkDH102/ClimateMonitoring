// ============================================================
// TITLE:  ClimateLoggerBME.c - BEDROOM
// AUTHOR: M Hollingworth
// DATE:   03/06/2018
//
// This application is to be used in conjunction with the 
// InHouseAlarm application
// This one sits on an Arduino UNO with a RF transceiver
// and a BME280e temperature/humidity/pressure sensor
// As this is running off a battery, current consumption is
// important so utilise the sleep mode with interrupt wakeup
// Wake up and read temperature/humidity every 15 minutes.
// Tx to InHouse

// NOTE: Can't use on-board LED (pin 13) with Transceiver module
//       as it uses the pin for the SCK signal on the SPI bus

// ============================================================


// ============================================================
// #defines
// ============================================================

#include <RFM12B.h>
#include <avr/sleep.h>
#include <avr/wdt.h>
#include <OneWire.h>
#include <PString.h>

#include <Adafruit_Sensor.h>
#include <Adafruit_BME280.h>

// Comment this out for the final version
//#define SERIAL_DEBUG    1

// Multiply this number by 15 to get the number of minutes between VCC readings (48 * 15 = 720 = 12 Hours)
#define VCC_TIMEOUT 48

// You will need to initialize the radio by telling it what ID it has and what network it's on
// The NodeID takes values from 1-127, 0 is reserved for sending broadcast messages (send to all nodes)
// The Network ID takes values from 0-255
// By default the SPI-SS line used is D10 on Atmega328. You can change it by calling .SetCS(pin) where pin can be {8,9,10}
#define NODEID       10  //network ID used for this unit
#define NETWORKID    99  //the network ID we are on
#define GATEWAYID     1  //the node ID we're sending to
#define ACK_TIME     50  // # of ms to wait for an ack
#define SERIAL_BAUD  9600

//encryption is OPTIONAL
//to enable encryption you will need to:
// - provide a 16-byte encryption KEY (same on all nodes that talk encrypted)
// - to call .Encrypt(KEY) to start encrypting
// - to stop encrypting call .Encrypt(NULL)
//uint8_t KEY[] = "ABCDABCDABCDABCD";

RFM12B          radio;
Adafruit_BME280 bme;

byte            mbytTakeVccReading;
long            mlngVcc;
char            mBuffConcat[64];
byte            mbytCRC;
byte            mbytConcatPtr;
byte            mbytADC;


// Watchdog will wake up the processor
ISR(WDT_vect, ISR_NAKED)
{
  asm("reti");
}


inline void configure_wdt(void)
{
    /* A 'timed' sequence is required for configuring the WDT, so we need to 
     * disable interrupts here.
     */
    cli(); 
    wdt_reset();
    MCUSR &= ~_BV(WDRF);
    /* Start the WDT Config change sequence. */
    WDTCSR |= _BV(WDCE) | _BV(WDE);
    /* Configure the prescaler and the WDT for interrupt mode only*/
    WDTCSR =  _BV(WDP0) | _BV(WDP3) | _BV(WDIE);
    sei();
}


long readVcc() 
{ 
    long result; 

    // Put ADC back to normal high power mode
    ADCSRA = mbytADC;

    // Read 1.1V reference against AVcc 
    ADMUX = _BV(REFS0) | _BV(MUX3) | _BV(MUX2) | _BV(MUX1); 
    delay(2); 
    // Wait for Vref to settle
    ADCSRA |= _BV(ADSC); 
    // Convert 
    while (bit_is_set(ADCSRA,ADSC)); 
    result = ADCL; 
    result |= ADCH<<8; 
    result = 1126400L / result; 
    // Back-calculate AVcc in mV 

    // Back to drawing no power...
    ADCSRA = 0;
    
    return result; 
}


void addToConcat(char *p)
{
  char x = 0;
  char v = p[0];
  
  while(v != 0)
  {
    mbytCRC ^= v;
    mBuffConcat[mbytConcatPtr++] = v;
    x++;
    v = p[x];
  }
  mBuffConcat[mbytConcatPtr++] = ',';
  mbytCRC ^= ',';
}


void acquireAndTransmitData()
{  
  char buff[8];
  char buff1[8];
  char buff2[8];
  char bytCRC;

  buff[0] = 0;
  buff1[0] = 0;
  buff2[0] = 0;
  
  // We get here every 15m, so take a reading every 12 hours...
  if (mbytTakeVccReading++ > VCC_TIMEOUT)
  {
    mlngVcc = readVcc();
    mbytTakeVccReading = 0;
  }

  bme.readForcedModeMarkH();
  PString(buff, sizeof(buff), bme.readTemperature());
  PString(buff1, sizeof(buff1), bme.readHumidity());
  PString(buff2, sizeof(buff2), mlngVcc);

  #ifdef SERIAL_DEBUG  
  Serial.print("T = ");
  Serial.print(bme.readTemperature());
  Serial.println(" Deg C");
  Serial.print("H = ");
  Serial.print(bme.readHumidity());
  Serial.println(" %RH");
  Serial.print("V = ");
  Serial.println(mlngVcc);
  #endif

  mbytCRC = 0;
    
  mbytConcatPtr = 2;

  addToConcat(buff);
  addToConcat(buff1);
  addToConcat(buff2);

  // Just CRC the one lot of DATA so we can compare both sets if the 433MHz crc fails
  bytCRC = mbytCRC;
    
  // Put the data in twice and if we have a bad 433MHz transmission CRC, check either of the sets
  // of data for a matching CRC that I have calculated...
  addToConcat(buff);
  addToConcat(buff1);
  addToConcat(buff2);

  mBuffConcat[mbytConcatPtr++] = bytCRC;
       
  mBuffConcat[mbytConcatPtr] = 0;

  #ifdef SERIAL_DEBUG
  for(byte i = 0; i < mbytConcatPtr + 1; i++)
    Serial.print(mBuffConcat[i]);
  #endif
  
  radio.Wakeup();

  // Don't request an ACK
  radio.Send(GATEWAYID, mBuffConcat, mbytConcatPtr, false);

  // 50mS is long enough at 9600
  long now = millis();
  while (millis() - now <= 50) ;  
    
  radio.Sleep();

  #ifdef SERIAL_DEBUG  
  Serial.println("\r\nTx DONE");
  #endif
}


void setup()
{
  #ifdef SERIAL_DEBUG
  Serial.begin(SERIAL_BAUD);
  #endif

  // 4th param is TXpower (0 = highest), 5th param is speed (35 = 9600bps, default is 38kbps)
  radio.Initialize(NODEID, RF12_433MHZ, NETWORKID, 0, 35);
  //sleep right away to save power
  radio.Sleep();

  // Get the default state of the ADC converter
  mbytADC = ADCSRA;
  
  #ifdef SERIAL_DEBUG
  Serial.println("Startup...");
  #endif
  
  Wire.begin();

  bme.begin();  

  // Force a vcc reading 1st time through
  mbytTakeVccReading = VCC_TIMEOUT + 1;

  // This part of the buffer never changes
  mBuffConcat[0] = 'B';
  mBuffConcat[1] = ',';

  // Give bme time to wake up
  delay(20);
  
  acquireAndTransmitData();
  
  // To give us chance to program the unit before we put it to sleep...
  // Not really sure if this is needed
  delay(20000);

  configure_wdt();
}


void goToSleep(void)
{
  byte c;
  
  // Go to sleep for 8 seconds at a time - 110 times which gives us approx 15 minutes
  for (c = 0; c < 110; c++)
  {
    // Disable the ADC
    ADCSRA = 0;
    
    // Most efficient sleep mode
    set_sleep_mode(SLEEP_MODE_PWR_DOWN);
    // enables the sleep bit in the mcucr register
    sleep_enable();
    // disable the brown out detector - saves 20uA-25uA
    sleep_bod_disable();
    // here the device is actually put to sleep!!
    sleep_mode();
  
    // NOTE: The program continues running from here on wake up
    sleep_disable();

    #ifdef SERIAL_DEBUG
    delay(200);
    Serial.println("We have woken up");
    #endif
  }
    
}


void loop()
{
  goToSleep();
  acquireAndTransmitData();
}


