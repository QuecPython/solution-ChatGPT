import utime
import request
from machine import Pin
from usr.libs.threading import Condition, Thread
from usr.libs.logging import getLogger
from usr.settings import *


logger = getLogger(__name__)


# ==================== 充电管理 ====================


class ChargeManager(object):

    def __init__(self, GPIOn=3):
        self.charge_pin = Pin(getattr(Pin, "GPIO{}".format(GPIOn)), Pin.OUT, Pin.PULL_PU)
    
    def enable_charge(self):
        self.charge_pin.write(1)
    
    def disable_charge(self):
        self.charge_pin.write(0)


# ==================== LED ====================


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


# ==================== 音乐播放 ====================


class Player(object):

    def __init__(self, aud, start_cb=lambda: None, stop_cb=lambda: None):
        self.aud = aud
        self.__stop_flag = False
        self.start_cb = start_cb
        self.stop_cb = stop_cb
        self.t = None
    
    def play(self, url):
        # https://uat-ai-media.iotomp.com/hls/music/maibaoge.mp3
        # https://uat-ai-media.iotomp.com/hls/music/liangzhilaohu.mp3
        # url = "https://uat-ai-media.iotomp.com/hls/music/liangzhilaohu.mp3"
        self.__stop_flag = False
        def inner(url):
            logger.debug("play audio data start")
            self.start_cb()
            resp = request.get(url)
            for data in resp.content:
                if self.__stop_flag:
                    resp.close()
                    break
                # logger.debug("play audio data length: {}".format(len(data)))
                self.aud.playStream(3, data.encode())
            self.aud.stopPlayStream()
            logger.debug("play audio data stop")
            self.stop_cb()
        self.t = Thread(target=inner, args=(url, ))
        self.t.start()

    def stop(self):
        self.__stop_flag = True
        if self.t is not None:
            self.t.join()
    
    def is_playing(self):
        return (self.t is not None and self.t.is_running())
