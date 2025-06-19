from unittest import TestCase
from unittest.mock import MagicMock

from x730 import X730
from . import pin_factory


class X730TestCase(TestCase):

    def setUp(self):
        pin_factory.reset()
        self.x730 = X730()

        x730 = self.x730
        orig_poweroff = x730.poweroff

        def mock_poweroff(*args, **kwargs):
            orig_poweroff(*args, **kwargs)
            # TODO x730._shutdown_status_pin.pin.drive_high() # for t > REBOOT_PULSE_MAXIMUM

        x730.poweroff = MagicMock(side_effect=mock_poweroff)

        orig_restart = x730.poweroff

        def mock_restart(*args, **kwargs):
            orig_restart(*args, **kwargs)
            # TODO x730._shutdown_status_pin.pin.drive_high() # for REBOOT_PULSE_MINIMUM > t < REBOOT_PULSE_MAXIMUM

        x730.restart = MagicMock(side_effect=mock_restart)

    def test_init(self):
        with self.x730 as device:
            self.assertIsInstance(device, X730)
            self.assertTrue(device._opened)

    def test_power_off(self):
        # TODO test_power_off (assert_states_and_times)
        with self.x730 as device:
            device.poweroff()

    def test_restart(self):
        # TODO test_power_off  (assert_states_and_times)
        with self.x730 as device:
            device.restart()
