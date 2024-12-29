#!/bin/bash

SHUTDOWN=4
REBOOTPULSEMINIMUM=200
REBOOTPULSEMAXIMUM=600
SLEEPPULSESECONDS=$(echo "scale=${#REBOOTPULSEMINIMUM}; $REBOOTPULSEMINIMUM / 1000" | bc)
pinctrl set "$SHUTDOWN" ip pd

BOOT=17
pinctrl set "$BOOT" op pn dl
pinctrl set "$BOOT" dh

getShutdownSignal() {
	echo "$(pinctrl lev "$SHUTDOWN")"
}

getPulseTimestamp() {
	echo "$(date +%s%N | cut -b1-12)"
}

sleepPulse() {
	sleep "$SLEEPPULSESECONDS"
}

echo "X730 Shutting down..."

while :
do
	shutdownSignal=$(getShutdownSignal)
	if [ $shutdownSignal = 0 ]
	then
		sleepPulse
	else
		pulseStart=$(getPulseTimestamp)
		while [ $shutdownSignal = 1 ]
		do
			sleepPulse
			if [ $(( $(getPulseTimestamp) - $pulseStart )) -gt $REBOOTPULSEMAXIMUM ]
			then
				echo "X730 Shutting down, halting Rpi ..."
				sudo poweroff
				exit
			fi
			shutdownSignal=$(getShutdownSignal)
		done
		if [ $(( $(getPulseTimestamp) - $pulseStart )) -gt $REBOOTPULSEMINIMUM ]
		then
			echo "X730 Rebooting, recycling Rpi ..."
			sudo reboot
			exit
		fi
	fi
done
