# x730

Command line interface for controlling the [Geekworm X730 expansion board](https://wiki.geekworm.com/X730) for the Raspberry Pi.

> **NOTE**
> 
> This version targets Raspberry Pi OS versions supporting `gpiozero`  
> For a bash and `pinctrl` implementation refer to version 2.x.
> And a much simpler python implementation is used by version 3.x.


## Prerequisites

1. OS supporting `systemd` and [gpiozero](https://pypi.org/project/gpiozero/)
2. `python3`
3. `uv`


## Development

In order to run the program without installation and/or compiling uvx (e.g. `uvx --refresh . -vvvv --help`) can be used.


## Usage

Use default GUI or terminal possibilities for poweroff/reboot or press the button of you PI's case (short reboot, long shutdown). 
