# MASTER

* Network ID is 99 (Same for all units)
* Node ID is 1

Has an 8MHz internal XTAL bootloader and a BME280 temp/humidity/pressure sensor attached.

Talks to the Raspberry Pi via a proprietary 3 wire interface (CLK/DATA/RST)

Gathers the transmissions from the 4 slave units and forms them into a single message sent on the 3 wire interface when requested by the Pi
