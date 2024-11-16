#!/bin/bash

BUTTON=18

pinctrl set "$BUTTON" op pn dl
pinctrl set "$BUTTON" dh

# 1-2 sec for reboot, 3-7 for shutdown (default) 8+ crash (pull the plug)
SLEEP=${1:-4}

re='^[0-9\.]+$'
if ! [[ $SLEEP =~ $re ]] ; then
   echo "error: sleep time not a number" >&2; exit 1
fi

echo "X730 Shutting down..."
sleep $SLEEP

#restore GPIO 18
pinctrl set "$BUTTON" dl
