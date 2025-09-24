import utime
import request
import audio
import G711
from machine import Pin, ExtInt
from usr.libs.threading import Condition, Thread, Lock
from usr.libs.logging import getLogger
from usr.configure import settings


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


# ================ 音频流管理 =====================


RECORD_TIME_MS = 100


class AudioManager(object):

    def __init__(self, kws_cb=lambda state: None, g711_cb=lambda args: None):
        self.pcm = None
        self.g711 = None
        self.g711_cb=g711_cb
        self.aud = audio.Audio(0)  # 初始化音频播放通道
        self.aud.set_pa(29)
        self.aud.setVolume(9)  # 设置音量
        self.rec = audio.Record(0)
        self.rec.ovkws_set_callback(kws_cb)
        self.__kws_thread = None
        self.__kws_stop_flag = False
        # 音量按键
        self.vol_plus = ExtInt(ExtInt.GPIO20, ExtInt.IRQ_FALLING, ExtInt.PULL_PU, self.__set_audio_volume, 250)
        self.vol_sub = ExtInt(ExtInt.GPIO47, ExtInt.IRQ_FALLING, ExtInt.PULL_PU, self.__set_audio_volume, 250)
        self.vol_plus.enable()
        self.vol_sub.enable()
        # 音乐播放
        self.__stop_flag = False
        self.t = None
        self.lock = Lock()
    
    def play_music(self, url):
        # https://uat-ai-media.iotomp.com/hls/music/maibaoge.mp3
        # https://uat-ai-media.iotomp.com/hls/music/liangzhilaohu.mp3
        # url = "https://uat-ai-media.iotomp.com/hls/music/liangzhilaohu.mp3"
        self.__stop_flag = False
        def inner(url):
            logger.debug("play audio data start")
            self.__before_start()
            resp = request.get(url)
            for data in resp.content:
                if self.__stop_flag:
                    resp.close()
                    break
                # logger.debug("play audio data length: {}".format(len(data)))
                self.aud.playStream(3, data.encode())
            self.aud.stopPlayStream()
            logger.debug("play audio data stop")
            self.__after_stop()
        self.t = Thread(target=inner, args=(url, ))
        self.t.start()

    def stop_music(self):
        self.__stop_flag = True
        if self.t is not None:
            self.t.join()
    
    def is_playing(self):
        return (self.t is not None and self.t.is_running())
    
    def __before_start(self):
        with self.lock:
            if self.g711 is not None:
                del self.g711
                self.g711 = None
            if self.pcm is not None:
                self.pcm.close()
                del self.pcm
                self.pcm = None
            self.pcm = audio.Audio.PCM(0, audio.Audio.PCM.MONO, 8000, audio.Audio.PCM.READONLY, audio.Audio.PCM.BLOCK, 25)
            self.g711 = G711(self.pcm)
            self.g711.set_callback_v3(self.g711_cb)
            self.g711.start_record_v3(0, RECORD_TIME_MS)

    def __after_stop(self):
        with self.lock:
            if self.g711 is not None:
                del self.g711
                self.g711 = None
            if self.pcm is not None:
                self.pcm.close()
                del self.pcm
                self.pcm = None
            self.pcm = audio.Audio.PCM(0, audio.Audio.PCM.MONO, 8000, audio.Audio.PCM.WRITEREAD, audio.Audio.PCM.BLOCK, 25)
            self.g711 = G711(self.pcm)
            self.g711.set_callback_v3(self.g711_cb)
            self.g711.start_record_v3(0, RECORD_TIME_MS)

    def init_g711(self):
        with self.lock:
            self.pcm = audio.Audio.PCM(0, audio.Audio.PCM.MONO, 8000, audio.Audio.PCM.WRITEREAD, audio.Audio.PCM.BLOCK, 25)
            self.g711 = G711(self.pcm)
            self.g711.set_callback_v3(self.g711_cb)
            self.g711.start_record_v3(0, RECORD_TIME_MS)
    
    def deinit_g711(self):
        with self.lock:
            if self.g711 is not None:
                self.g711.stop_record_v3()
                del self.g711
                self.g711 = None
            if self.pcm is not None:
                self.pcm.close()
                del self.pcm
                self.pcm = None
    
    def g711_read_v3(self, buf, length):
        return self.g711.read_v3(buf, length)
    
    def g711_read(self):
        with self.lock:
            return self.g711.read(0, 5)
    
    def g711_write(self, data):
        with self.lock:
            return self.g711.write(data, 0)

    def stop_kws(self):
        logger.debug("stop kws...")
        self.rec.ovkws_stop()
        self.__kws_stop_flag = True
        if self.__kws_thread:
            self.__kws_thread.join()
        if self.pcm:
            self.pcm.close()
            del self.pcm
            self.pcm = None

    def start_kws(self):
        logger.debug("start kws...")
        self.pcm = audio.Audio.PCM(0, audio.Audio.PCM.MONO, 16000, audio.Audio.PCM.READONLY, audio.Audio.PCM.BLOCK, 25)
        value = settings.get("WAKEUP_KEYWORD")
        self.rec.ovkws_start(value, 0.8)
        logger.debug("唤醒词：{}".format(value))
        self.__kws_stop_flag = False
        self.__kws_thread = Thread(self.__kws_thread_handler)
        self.__kws_thread.start(stack_size=16)

    def __kws_thread_handler(self):
        while True:
            if self.__kws_stop_flag:
                break
            self.pcm.read(1024)
            utime.sleep_ms(1)

    def __set_audio_volume(self, args):
        v = self.aud.getVolume() + (1 if args[0] == 47 else -1)
        v = 11 if v > 11 else 0 if v < 0 else v
        self.aud.setVolume(v)
        logger.debug("__set_audio_volume: {}".format(v))
