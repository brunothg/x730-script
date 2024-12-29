# x730-script

This is the safe shutdown script for x730

> **NOTE**
> This version targets newer Raspberry Pi OS versions supporting `pinctrl` instead of `/sys/class/gpio` or `raspi-gpio`


## Prequisites

1. OS supporting systemd
2. `/bin/bash` binary
3. `pinctrl` binary on path


## Installation

Run `sudo bash install.sh`


## Usage

Use default GUI or terminal possibilities for poweroff/reboot or press the button of you PI's case (short reboot, long shutdown). 
