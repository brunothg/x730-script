#!/usr/bin/env bash

BUTTON=18

pinctrl set "$BUTTON" op pn dl
pinctrl set "$BUTTON" dh

exSleep() {
  sleep "$1" \
	|| perl -e "select(undef, undef, undef, $1)" \
	|| python3 -c "import time; time.sleep($1)"
}

# 1-2 sec for reboot, 3-7 for poweroff (default) 8+ crash (pull the plug)
SLEEP=${1:-4}

if ! [[ "$SLEEP" =~ ^[0-9\.]+$ ]] ; then
   echo "error: sleep time not a number" >&2; exit 1
fi

echo "X730 Shutting down..."
exSleep "$SLEEP"

#restore GPIO 18
pinctrl set "$BUTTON" dl
