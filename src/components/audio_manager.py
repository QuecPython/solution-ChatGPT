import utime
import request
import audio
import G711
from machine import ExtInt
from usr.libs import CurrentApp
from usr.libs.threading import Thread, Lock
from usr.libs.logging import getLogger
from usr.configure import settings


logger = getLogger(__name__)


RECORD_TIME_MS = 100


class AudioManager(object):

    def __init__(self,):
        self.pcm = None
        self.g711 = None
        self.aud = audio.Audio(0)  # 初始化音频播放通道
        self.aud.set_pa(29)
        self.aud.set_open_pa_delay(10)
        self.aud.setVolume(9)  # 设置音量
        self.rec = audio.Record(0)
        self.rec.ovkws_set_callback(self.kws_cb)
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
        self.should_upload_data = False
    
    def init(self):
        logger.info("init {} extension".format(type(self).__name__))

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
            self.g711.start_auto_decoder(0, RECORD_TIME_MS, self.g711_cb)

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
            self.g711.start_auto_decoder(0, RECORD_TIME_MS, self.g711_cb)

    def init_g711(self):
        with self.lock:
            self.pcm = audio.Audio.PCM(0, audio.Audio.PCM.MONO, 8000, audio.Audio.PCM.WRITEREAD, audio.Audio.PCM.BLOCK, 25)
            self.g711 = G711(self.pcm)
            self.g711.start_auto_decoder(0, RECORD_TIME_MS, self.g711_cb)
    
    def deinit_g711(self):
        with self.lock:
            if self.g711 is not None:
                self.g711.stop_decoder()
                del self.g711
                self.g711 = None
            if self.pcm is not None:
                self.pcm.close()
                del self.pcm
                self.pcm = None
    
    def set_upload_flag(self, flag=True):
        self.should_upload_data = flag

    def g711_cb(self, args):
        if not self.should_upload_data:
            return
        if(args[1] == 1):
            buf = bytearray(args[0])
            self.g711_read_buff(buf, args[0])
            if len(buf) > 0:
                try:
                    CurrentApp().ai_manager.protocol.input_audio_buffer_append(buf)
                except Exception as e:
                    # logger.debug("g711_cb got: {}".format(repr(e)))
                    pass

    def g711_read_buff(self, buf, length):
        return self.g711.read_buff(buf, length)
    
    def g711_read(self):
        with self.lock:
            return self.g711.read(0, 5)
    
    def g711_write(self, data):
        with self.lock:
            return self.g711.write(data, 0)

    def stop_kws(self):
        logger.debug("stop kws...")
        self.rec.ovkws_stop()
        self.rec.stream_stop()
        # self.__kws_stop_flag = True
        # if self.__kws_thread:
        #     self.__kws_thread.join()
        # if self.pcm:
        #     self.pcm.close()
        #     del self.pcm
        #     self.pcm = None

    def start_kws(self):
        logger.debug("start kws...")
        # self.pcm = audio.Audio.PCM(0, audio.Audio.PCM.MONO, 16000, audio.Audio.PCM.READONLY, audio.Audio.PCM.BLOCK, 25)
        value = settings.get("WAKEUP_KEYWORD")
        logger.debug("wakeup keywords: {}".format(value))
        self.rec.stream_start(2, 16000, 0)
        self.rec.ovkws_start(value, 0.7)
        # self.__kws_stop_flag = False
        # self.__kws_thread = Thread(self.__kws_thread_handler)
        # self.__kws_thread.start(stack_size=16)

    # def __kws_thread_handler(self):
    #     logger.debug("__kws_thread_handler enter")
    #     while True:
    #         if self.__kws_stop_flag:
    #             break
    #         self.pcm.read(1024)
    #         utime.sleep_ms(10)
    #     logger.debug("__kws_thread_handler exit")
    
    def kws_cb(self, state):
        logger.info("on_keyword_spotting: {}".format(state))
        if state[0] == 1 and state[1] == 0:
            # 唤醒词触发
            CurrentApp().ai_manager.on_wakeup_key_click(None)
        else:
            pass

    def __set_audio_volume(self, args):
        v = self.aud.getVolume() + (1 if args[0] == 47 else -1)
        v = 10 if v > 10 else 0 if v < 1 else v
        self.aud.setVolume(v)
        logger.debug("__set_audio_volume: {}".format(v))
