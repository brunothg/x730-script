#!/bin/bash

BUTTON=18

pinctrl set "$BUTTON" op pn dl
pinctrl set "$BUTTON" dh

SLEEP=${1:-4}

re='^[0-9\.]+$'
if ! [[ $SLEEP =~ $re ]] ; then
   echo "error: sleep time not a number" >&2; exit 1
fi

echo "X730 Shutting down..."
sleep $SLEEP

#restore GPIO 18
pinctrl set "$BUTTON" dl
