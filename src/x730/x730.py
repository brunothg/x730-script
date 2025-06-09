from gpiozero import DigitalInputDevice, DigitalOutputDevice
from enum import Enum


class Pins(Enum):
    """
    X730 GPIO-Pins (BCM)
    """

    BUTTON = 18
    SHUTDOWN = 4
    BOOT = 17


class X730:
    """
    Class for controlling the X730 expansion board.

    Shutdown button sequence: 1-2 sec for reboot, 3-7 for poweroff (default) 8+ crash (pull the plug)
    """

    REBOOT_PULSE_MINIMUM = 200
    REBOOT_PULSE_MAXIMUM = 600

    def __init__(self):
        self._shutdown_button_pin = DigitalOutputDevice(pin=Pins.BUTTON.value, active_high=True, initial_value=False)
        self._shutdown_status_pin = DigitalInputDevice(pin=Pins.SHUTDOWN.value, pull_up=False, bounce_time=None)
        self._boot_status_pin = DigitalOutputDevice(pin=Pins.BOOT.value, active_high=True, initial_value=True)

    def poweroff(self, force: bool = False) -> None:
        """
        Powers the board off.

        :param force: If True, force the power off (cut off the power).
        :return:
        """
        # TODO poweroff

    def restart(self) -> None:
        """
        Restarts the board.

        :return:
        """
        # TODO restart
