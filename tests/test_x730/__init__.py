import logging

from gpiozero import Device
from gpiozero.pins.mock import MockFactory

logging.basicConfig(
    level=logging.DEBUG,
)

# Get Pi revision number: cat /proc/cpuinfo | grep "Revision"
# More info at gpiozero.pins.pi.PiBoardInfo#from_revision
pin_factory = MockFactory(revision='d03114')  # Using 4B
Device.pin_factory = pin_factory
