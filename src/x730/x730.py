import logging
import subprocess
import threading
import time
from enum import Enum

from gpiozero import DigitalInputDevice, DigitalOutputDevice


class Pins(Enum):
    """
    X730 GPIO-Pins (BCM)
    """

    BUTTON = 18
    SHUTDOWN = 4
    BOOT = 17


# TODO monitor _shutdown_status_pin
class X730:
    """
    Singleton class for controlling the X730 expansion board.

    Shutdown button sequence: 1-2 sec for reboot, 3-7 for poweroff (default) 8+ crash (pull the plug)
    """
    _LOG = logging.getLogger(__name__)

    REBOOT_PULSE_MINIMUM = 200
    REBOOT_PULSE_MAXIMUM = 600

    def __new__(cls):
        singleton_attr_name = '_INSTANCE'
        if not hasattr(cls, singleton_attr_name):
            setattr(cls, singleton_attr_name, super(X730, cls).__new__(cls))
        return getattr(cls, singleton_attr_name)

    def __init__(self):
        self._lock = threading.RLock()
        self._shutdown_button_pin = DigitalOutputDevice(pin=Pins.BUTTON.value, active_high=True, initial_value=False)
        self._shutdown_status_pin = DigitalInputDevice(pin=Pins.SHUTDOWN.value, pull_up=False, bounce_time=None)
        self._boot_status_pin = DigitalOutputDevice(pin=Pins.BOOT.value, active_high=True, initial_value=True)

    def _sys_poweroff(self):
        X730._LOG.info("System power off")
        subprocess.run('poweroff', check=True)

    def _sys_reboot(self):
        X730._LOG.info("System reboot")
        subprocess.run('reboot', check=True)

    def poweroff(self, force: bool = False) -> None:
        """
        Powers the board off.

        :param force: If True, force the power off (cut off the power).
        :return:
        """
        with self._lock:
            X730._LOG.info("Powering off board")
            self._shutdown_button_pin.on()
            time.sleep(5)
            self._shutdown_button_pin.off()

    def restart(self) -> None:
        """
        Restarts the board.

        :return:
        """
        with self._lock:
            X730._LOG.info("Restarting the board")
            self._shutdown_button_pin.on()
            time.sleep(1.5)
            self._shutdown_button_pin.off()
