#!/usr/bin/env bash

# replace `4700` with your PIN
echo -e 'AT+CPIN="4700"\r' > /dev/ttyUSB2
sleep 3
quectel-CM