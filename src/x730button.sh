#!/usr/bin/env bash

SHUTDOWN=4
REBOOT_PULSE_MINIMUM_MILLISECONDS=200
REBOOT_PULSE_MAXIMUM_MILLISECONDS=600
SLEEP_PULSE_SECONDS="0.200"
pinctrl set "$SHUTDOWN" ip pd

BOOT=17
pinctrl set "$BOOT" op pn dl
pinctrl set "$BOOT" dh

exSleep() {
  sleep "$1" \
	|| perl -e "select(undef, undef, undef, $1)" \
	|| "$(command -v python3 || command -v python || command -v python2)" -c "import time; time.sleep($1)"
}

getShutdownSignal() {
	pinctrl lev "$SHUTDOWN"
}

getPulseTimestamp() {
  if [ -n "$EPOCHREALTIME" ]
  then
    local us="${EPOCHREALTIME/[^0-9]/}"
    echo "${us:0:-3}"
  else
	  date +%s%3N
	fi
}

sleepPulse() {
	exSleep "$SLEEP_PULSE_SECONDS"
}

echo "X730 Shutting down..."

while :
do
	shutdownSignal=$(getShutdownSignal)
	if [ "$shutdownSignal" = 0 ]
	then
		sleepPulse
	else
		pulseStart=$(getPulseTimestamp)
		while [ "$shutdownSignal" = 1 ]
		do
			sleepPulse
			if [ $(( $(getPulseTimestamp) - $pulseStart )) -gt $REBOOT_PULSE_MAXIMUM_MILLISECONDS ]
			then
				echo "X730 Shutting down, halting Rpi ..."
				sudo poweroff
				exit
			fi
			shutdownSignal=$(getShutdownSignal)
		done
		if [ $(( $(getPulseTimestamp) - $pulseStart )) -gt $REBOOT_PULSE_MINIMUM_MILLISECONDS ]
		then
			echo "X730 Rebooting, recycling Rpi ..."
			sudo reboot
			exit
		fi
	fi
done
