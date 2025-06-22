import logging
import subprocess
import time
from enum import Enum
from typing import Optional

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

    SHUTDOWN_STATUS_REBOOT_PULSE_MINIMUM: float = 0.2
    SHUTDOWN_STATUS_REBOOT_PULSE_MAXIMUM: float = 0.6

    SHUTDOWN_BUTTON_REBOOT_PULSE: float = 1.2
    SHUTDOWN_BUTTON_POWEROFF_PULSE: float = 5
    SHUTDOWN_BUTTON_CRASH_PULSE: float = 10

    def __new__(cls):
        singleton_attr_name = '_INSTANCE'
        if not hasattr(cls, singleton_attr_name):
            setattr(cls, singleton_attr_name, super(X730, cls).__new__(cls))
        return getattr(cls, singleton_attr_name)

    def __init__(self):
        self._opened: bool = False
        self._shutdown_status: tuple[bool, float] = (False, time.monotonic())

        self._boot_status_pin: Optional[DigitalOutputDevice] = None
        self._shutdown_button_pin: Optional[DigitalOutputDevice] = None
        self._shutdown_status_pin: Optional[DigitalInputDevice] = None

    def __del__(self):
        self.close()

    def __enter__(self) -> 'X730':
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

    def _on_shutdown_status(self, status: bool) -> None:
        old_shutdown_status = self._shutdown_status
        new_shutdown_status = (status, time.monotonic())
        diff_shutdown_status = (
            int(new_shutdown_status[0]) - int(old_shutdown_status[0]),
            new_shutdown_status[1] - old_shutdown_status[1]
        )
        self._shutdown_status = new_shutdown_status

        if not diff_shutdown_status[0] == -1:  # not High -> Low edge
            return
        pulse = diff_shutdown_status[1]

        min_pulse = X730.SHUTDOWN_STATUS_REBOOT_PULSE_MINIMUM
        is_min_pulse = pulse > min_pulse
        if not is_min_pulse:
            X730._LOG.debug(f"Shutdown status: short pulse")
            return

        reboot_pulse = X730.SHUTDOWN_STATUS_REBOOT_PULSE_MAXIMUM
        is_reboot_pulse = pulse < reboot_pulse
        X730._LOG.debug(f"Shutdown status: {'reboot' if is_reboot_pulse else 'shutdown'} pulse")
        if is_reboot_pulse:
            self._sys_reboot()
        else:
            self._sys_poweroff()

    def open(self):
        if self._opened:
            return
        self._opened = True

        self._boot_status_pin = DigitalOutputDevice(pin=Pins.BOOT.value, active_high=True, initial_value=True)
        self._shutdown_button_pin = DigitalOutputDevice(pin=Pins.BUTTON.value, active_high=True, initial_value=False)

        self._shutdown_status_pin = DigitalInputDevice(pin=Pins.SHUTDOWN.value, pull_up=False, bounce_time=None)
        self._shutdown_status_pin.when_activated = lambda: self._on_shutdown_status(status=True)
        self._shutdown_status_pin.when_deactivated = lambda: self._on_shutdown_status(status=False)

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
        time.sleep(X730.SHUTDOWN_BUTTON_POWEROFF_PULSE if not force else X730.SHUTDOWN_BUTTON_CRASH_PULSE)
        self._shutdown_button_pin.off()

    def reboot(self) -> None:
        """
        Restarts the board.

        :return:
        """
        X730._LOG.info("Restarting the board")
        self._shutdown_button_pin.on()
        time.sleep(X730.SHUTDOWN_BUTTON_REBOOT_PULSE)
        self._shutdown_button_pin.off()
