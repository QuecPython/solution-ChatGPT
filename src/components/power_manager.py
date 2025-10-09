from machine import Pin
from usr.libs.threading import Event
from usr.libs.logging import getLogger


logger = getLogger(__name__)


class PowerManager(object):

    def __init__(self, GPIOn=3):
        self.charge_pin = Pin(getattr(Pin, "GPIO{}".format(GPIOn)), Pin.OUT, Pin.PULL_PU)
    
    def init(self):
        logger.debug("init {} extension".format(type(self).__name__))
        self.enable_charge()

    def enable_charge(self):
        self.charge_pin.write(1)
    
    def disable_charge(self):
        self.charge_pin.write(0)
