from machine import Pin
from usr.libs import CurrentApp
from usr.libs.threading import Thread, EventSet
from usr.libs.logging import getLogger


logger = getLogger(__name__)


class PowerManager(object):

    def __init__(self, GPIOn=3):
        self.charge_pin = Pin(getattr(Pin, "GPIO{}".format(GPIOn)), Pin.OUT, Pin.PULL_PU)
        self.check_standby_thread = None
        self.standby_event_set = EventSet()
        self.check_lpm_thread = None
        self.lpm_event_set = EventSet()
    
    def init(self):
        logger.debug("init {} extension".format(type(self).__name__))
        self.enable_charge()

    def enable_charge(self):
        self.charge_pin.write(1)
    
    def disable_charge(self):
        self.charge_pin.write(0)

    def start_check_standby(self):
        if self.check_standby_thread and self.check_standby_thread.is_running():
            return
        self.standby_event_set.clear(0b11)
        def inner():
            logger.debug("enter standby mode detection")
            while True:
                rv = self.standby_event_set.wait_any(0b11, timeout=60, clear=True)
                if rv == -1:
                    logger.debug("no conversation detected after 60s, enter standby mode")
                    CurrentApp().ai_manager.protocol.disconnect()
                    break
                if rv & 0b01:
                    logger.debug("exit standby mode detection")
                    break
                # if rv & 0b10:
                #     print("检测到对话，重置60s继续等待")
        self.check_standby_thread = Thread(target=inner)
        self.check_standby_thread.start()
    
    def stop_check_standby(self):
        if self.check_standby_thread and self.check_standby_thread.is_running():
            self.standby_event_set.set(0b01)
            self.check_standby_thread.join()

    def reset_standby_check(self):
        self.standby_event_set.set(0b10)

    def start_check_lpm(self):
        if self.check_lpm_thread and self.check_lpm_thread.is_running():
            return
        self.lpm_event_set.clear(0b11)
        def inner():
            logger.debug("enter lpm detection")
            while True:
                rv = self.lpm_event_set.wait_any(0b11, timeout=120, clear=True)
                if rv == -1:
                    logger.debug("lpm detected after 120s, enter low power mode")
                    CurrentApp().audio_manager.stop_kws()
                    CurrentApp().led_manager.disable_all()
                    break
                if rv & 0b01:
                    logger.debug("exit lpm detection")
                    break
                # if rv & 0b10:
                #     print("检测到，重置120s继续等待")
        self.check_lpm_thread = Thread(target=inner)
        self.check_lpm_thread.start()
    
    def stop_check_lpm(self):
        CurrentApp().led_manager.enable_led()
        if self.check_lpm_thread and self.check_lpm_thread.is_running():
            self.lpm_event_set.set(0b01)
            self.check_lpm_thread.join()

    def reset_lpm_check(self):
        self.lpm_event_set.set(0b10)
