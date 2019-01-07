# SLAVE

* Network ID is 99 (Same for all units)
* Node ID is : (Code needs the #define NODEID changing for each unit)
* SHED        2
* BEDROOM     10
* GARDEN ROOM 11
* ATTIC       12

Has an 8MHz internal XTAL bootloader and a BME280 temp/humidity/pressure sensor attached.

Runs in extreme low power mode. Wakes up every 15 minutes, reads the humidity and temperature from the BME280 and transmits to the MASTER unit using 433MHz
