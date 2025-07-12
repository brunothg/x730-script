from typing import cast
from unittest import TestCase
from unittest.mock import MagicMock, Mock

from gpiozero.pins.mock import MockPin

from x730 import X730
from . import pin_factory, sleep_at_least


class X730TestCase(TestCase):

    def setUp(self):
        pin_factory.reset()

        self.x730 = x730 = X730()
        x730._sys_reboot = MagicMock()
        x730._sys_poweroff = MagicMock()

        def mock_shutdown_status(pulse: float):
            x730._shutdown_status_pin.pin.drive_high()
            sleep_at_least(pulse)
            x730._shutdown_status_pin.pin.drive_low()

        def mock_poweroff(*args, **kwargs):
            X730.poweroff(x730, *args, **kwargs)
            mock_shutdown_status(X730.SHUTDOWN_STATUS_REBOOT_PULSE_MAXIMUM)

        x730.poweroff = MagicMock(side_effect=mock_poweroff)

        def mock_restart(*args, **kwargs):
            X730.reboot(x730, *args, **kwargs)
            mock_shutdown_status(X730.SHUTDOWN_STATUS_REBOOT_PULSE_MINIMUM)

        x730.reboot = MagicMock(side_effect=mock_restart)

    def test_init(self):
        with self.x730 as device:
            self.assertIsInstance(device, X730)
            self.assertTrue(device._opened)

    def test_power_off(self):
        with self.x730 as device:
            device.poweroff()
            cast(MockPin, self.x730._shutdown_button_pin.pin).assert_states_and_times([
                [0, False],
                [0, True],
                [X730.SHUTDOWN_BUTTON_POWEROFF_PULSE, False]
            ])
            cast(Mock, self.x730._sys_poweroff).assert_called_once()
            cast(Mock, self.x730._sys_reboot).assert_not_called()

    def test_power_off_crash(self):
        with self.x730 as device:
            device.poweroff(force=True)
            cast(MockPin, self.x730._shutdown_button_pin.pin).assert_states_and_times([
                [0, False],
                [0, True],
                [X730.SHUTDOWN_BUTTON_CRASH_PULSE, False]
            ])
            cast(Mock, self.x730._sys_poweroff).assert_called_once()
            cast(Mock, self.x730._sys_reboot).assert_not_called()

    def test_reboot(self):
        with self.x730 as device:
            device.reboot()
            cast(MockPin, self.x730._shutdown_button_pin.pin).assert_states_and_times([
                [0, False],
                [0, True],
                [X730.SHUTDOWN_BUTTON_REBOOT_PULSE, False]
            ])
            cast(Mock, self.x730._sys_reboot).assert_called_once()
            cast(Mock, self.x730._sys_poweroff).assert_not_called()
