#!/usr/bin/env bash

# unlock with PIN
echo -e 'AT+CPIN="4700"\r' > /dev/ttyUSB2
sleep 3
quectel-CM