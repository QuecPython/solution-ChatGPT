import utime
from machine import Pin
from usr.libs.threading import Condition, Thread


class Led(object):

    def __init__(self, GPIOn):
        self.__led = Pin(
            getattr(Pin, 'GPIO{}'.format(GPIOn)),
            Pin.OUT,
            Pin.PULL_PD,
            0
        )
        self.__off_period = 1000
        self.__on_period = 1000
        self.__count = 0
        self.__running_cond = Condition()
        self.__blink_thread = None
        self.off()

    @property
    def status(self):
        with self.__running_cond:
            return self.__led.read()

    def on(self):
        with self.__running_cond:
            self.__count = 0
            return self.__led.write(0)

    def off(self):
        with self.__running_cond:
            self.__count = 0
            return self.__led.write(1)

    def blink(self, on_period=50, off_period=50, count=None):
        if not isinstance(count, (int, type(None))):
            raise TypeError('count must be int or None type')
        with self.__running_cond:
            if self.__blink_thread is None:
                self.__blink_thread = Thread(target=self.__blink_thread_worker)
                self.__blink_thread.start()
            self.__on_period = on_period
            self.__off_period = off_period
            self.__count = count
            self.__running_cond.notify_all()

    def __blink_thread_worker(self):
        while True:
            with self.__running_cond:
                if self.__count is not None:
                    self.__running_cond.wait_for(lambda: self.__count is None or self.__count > 0)
                status = self.__led.read()
                self.__led.write(1 - status)
                utime.sleep_ms(self.__on_period if status else self.__off_period)
                self.__led.write(status)
                utime.sleep_ms(self.__on_period if status else self.__off_period)
                if self.__count is not None:
                    self.__count -= 1
