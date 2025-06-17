import logging
import subprocess
import time
from enum import Enum
from typing import Self

from gpiozero import DigitalInputDevice, DigitalOutputDevice


class Pins(Enum):
    """
    X730 GPIO-Pins (BCM)
    """

    BUTTON = 18
    SHUTDOWN = 4
    BOOT = 17


class X730:
    """
    Singleton class for controlling the X730 expansion board.

    Shutdown button sequence: 1-2 sec for reboot, 3-7 for poweroff (default) 8+ crash (pull the plug)
    """
    _LOG = logging.getLogger(__name__)

    REBOOT_PULSE_MINIMUM: float = 0.2
    REBOOT_PULSE_MAXIMUM: float = 0.6

    def __new__(cls):
        singleton_attr_name = '_INSTANCE'
        if not hasattr(cls, singleton_attr_name):
            setattr(cls, singleton_attr_name, super(X730, cls).__new__(cls))
        return getattr(cls, singleton_attr_name)

    def __init__(self):
        self._opened: bool = False
        self._boot_status_pin: DigitalOutputDevice | None = None
        self._shutdown_button_pin: DigitalOutputDevice | None = None
        self._shutdown_status_pin: DigitalInputDevice | None = None

    def __enter__(self) -> Self:
        self.open()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()

    def _sys_poweroff(self):
        X730._LOG.info("System power off")
        subprocess.run('poweroff', check=True)
        self.close()

    def _sys_reboot(self):
        X730._LOG.info("System reboot")
        subprocess.run('reboot', check=True)
        self.close()

    def _on_shutdown_status(self):
        begin_time = time.monotonic()
        is_reboot_pulse = self._shutdown_status_pin.wait_for_inactive(X730.REBOOT_PULSE_MAXIMUM)
        diff_time = time.monotonic() - begin_time
        diff_time = min(diff_time, X730.REBOOT_PULSE_MAXIMUM) if is_reboot_pulse else diff_time
        X730._LOG.debug(f"Shutdown status: {diff_time} -> {'reboot' if is_reboot_pulse else 'shutdown'}")

        if diff_time > X730.REBOOT_PULSE_MINIMUM:
            if diff_time <= X730.REBOOT_PULSE_MAXIMUM:
                self._sys_reboot()
            else:
                self._sys_poweroff()

    def open(self):
        if not self._opened:
            return
        self._opened = True

        self._boot_status_pin = DigitalOutputDevice(pin=Pins.BOOT.value, active_high=True, initial_value=True)
        self._shutdown_button_pin = DigitalOutputDevice(pin=Pins.BUTTON.value, active_high=True, initial_value=False)

        self._shutdown_status_pin = DigitalInputDevice(pin=Pins.SHUTDOWN.value, pull_up=False, bounce_time=None)
        self._shutdown_status_pin.when_activated = self._on_shutdown_status

    def close(self):
        if not self._opened:
            return
        self._opened = False

        self._boot_status_pin.close()
        self._boot_status_pin = None

        self._shutdown_button_pin.close()
        self._shutdown_button_pin = None

        self._shutdown_status_pin.close()
        self._shutdown_status_pin = None

    def poweroff(self, force: bool = False) -> None:
        """
        Powers the board off.

        :param force: If True, force the power off (cut off the power).
        :return:
        """
        X730._LOG.info("Powering off board")
        self._shutdown_button_pin.on()
        time.sleep(5)
        self._shutdown_button_pin.off()

    def restart(self) -> None:
        """
        Restarts the board.

        :return:
        """
        X730._LOG.info("Restarting the board")
        self._shutdown_button_pin.on()
        time.sleep(1.2)
        self._shutdown_button_pin.off()
