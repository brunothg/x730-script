# x730

Command line interface and driver for controlling the [Geekworm X730 expansion board](https://wiki.geekworm.com/X730) for the Raspberry Pi.

> [!NOTE]
> 
> This version targets Raspberry Pi OS versions supporting `gpiozero`  
> For a bash and `pinctrl` implementation refer to version 2.x.


## Prerequisites

1. OS supporting `systemd` and [gpiozero](https://pypi.org/project/gpiozero/)
2. `python3` (3.11+)
3. `uv`


## Development

In order to run the program without installation and/or compiling uvx (e.g. `uvx --refresh . -vvvv --help`) can be used.

For building, testing etc. you should use the `Makefile.py` file (a make like CLI).
For example, you could run `uv run Makefile.py test` or `uv run Makefile.py build`.


## Installation

The default installation process is as easy as calling `uv run Makefile.py install`.
This will use `uv tool install` internally.
By default, the installation directory will be `/opt/uv/tools/...` for python files.
Binary links are written to `/usr/local/bin/...`.
SystemD Unit files will be installed into `/etc/systemd/system/...`.
So you'll need sudo rights for those default installation paths.

> [!IMPORTANT]
> 
> Most uv installations are not available globally and because of this not accessible using sudo.
> To work around this issue you can explicitly install uv for root.
> Or alternatively use your users `PATH` env (e.g. `sudo env PATH="$PATH" uv run Makefile.py install`).

> [!IMPORTANT]
> 
> Do not activate the projects virtual environment.
> This will likely force uv to install into the venv instead of the desired location.
> Even `UV_*` environment variables may/will be ignored.

> [!TIP]
> 
> For more information about `uv` and the way you can interfere with the installation process visit their website:
> [uv](https://docs.astral.sh/uv/) or [uv tool docs](https://docs.astral.sh/uv/reference/cli/#uv-tool)


As an alternative you could consider an installation using `pipx`.
Install `pipx` directly or use `uvx pipx`.
You'll need `pipx` in version 1.5.0+.
First build a wheel (`uv run Makefile.py build`), then install it with `sudo pipx --global install dist/x730*.whl`.
For more details visit [pipx docs](https://pipx.pypa.io/latest/docs/).


## Update

Direct updates may work, but are not supported.
Instead, you should uninstall the current version.
Afterward you can download and install the new version.


## Usage

Use default GUI or terminal possibilities for poweroff/reboot or press the button of you PI's case (short reboot, long shutdown). 
