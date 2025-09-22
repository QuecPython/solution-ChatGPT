import gc
import usys
import utime
import base64
import G711
import audio
import ql_fs
from machine import ExtInt, Pin
from usr.libs.threading import Thread, BoundedSemaphore, EventSet, Lock
from usr.libs.logging import getLogger
from usr.utils import ChargeManager, Led, Player
from usr.protocol import WebSocketClient
from usr.configure import settings
from usr.libs.logging import getLogger
from usr.libs.qth import qth_init, qth_config, qth_bus


logger = getLogger(__name__)


SESSION_CREATED_EVENT = 1 << 0


class Application(object):

    def __init__(self):
        # 初始化充电管理
        self.charge_manager = ChargeManager()

        # 初始化 led; write(1) 灭； write(0) 亮
        self.wifi_red_led = Led(33)
        self.wifi_green_led = Led(32)  # WIFI 指示灯
        self.power_red_led = Led(39)
        self.power_green_led = Led(38)  # 电量指示灯
        self.lte_red_led = Led(23)
        self.lte_green_led = Led(24)  # LTE 网络指示灯
        self.led_power_pin = Pin(Pin.GPIO27, Pin.OUT, Pin.PULL_DISABLE, 0)

        # openAI Realtime
        self.protocol = WebSocketClient()
        self.protocol.set_callback(event_handler=self.__on_event)

        # 音频管理
        self.aud = audio.Audio(0)  # 初始化音频播放通道
        self.aud.set_pa(29)
        self.aud.setVolume(11)  # 设置音量
        self.player = Player(
            self.aud, 
            start_cb=lambda: self.reset_pcm_object(8000, audio.Audio.PCM.READONLY),
            stop_cb=lambda: self.reset_pcm_object(8000, audio.Audio.PCM.WRITEREAD)
        )
        self.pcm = None
        self.g711 = None
        self.rec = audio.Record(0)
        self.rec.ovkws_set_callback(self.on_keyword_spotting)
        self.chat_thread = None
        
        # Wakeup 按键
        self.wakeup_key = ExtInt(ExtInt.GPIO41, ExtInt.IRQ_FALLING, ExtInt.PULL_PU, self.on_wakeup_key_click, 50)
        
        # 音量按键
        self.vol_plus = ExtInt(ExtInt.GPIO20, ExtInt.IRQ_FALLING, ExtInt.PULL_PU, self.__set_audio_volume, 50)
        self.vol_sub = ExtInt(ExtInt.GPIO47, ExtInt.IRQ_FALLING, ExtInt.PULL_PU, self.__set_audio_volume, 50)

        self.__semphore = BoundedSemaphore(value=1)
        self.event_set = EventSet()
        self.lock = Lock()

        self.__kws_thread = None
        self.__kws_thread_stop_flag = False

    def __set_audio_volume(self, args):
        v = self.aud.getVolume() + (1 if args[0] == 47 else -1)
        v = 11 if v > 11 else 0 if v < 0 else v
        self.aud.setVolume(v)
        logger.debug("__set_audio_volume: {}".format(v))

    def reset_pcm_object(self, samplerate=16000, mode=audio.Audio.PCM.WRITEREAD):
        with self.lock:
            if self.g711:
                self.g711.stop_record_v3()
                del self.g711
                self.g711 = None
            if self.pcm:
                self.pcm.close()
                del self.pcm
                self.pcm = None
            self.pcm = audio.Audio.PCM(0, audio.Audio.PCM.MONO, samplerate, mode, audio.Audio.PCM.BLOCK, 25)
            if samplerate == 8000:
                self.g711 = G711(self.pcm)
                self.g711.set_callback_v3(self.__g711_cb)
                self.g711.start_record_v3(0, 200)
        logger.debug("change pcm object as {} Hz and mode: {}".format(samplerate, mode))
    
    def __g711_cb(self, args):
        if(args[1] == 1):
            buf = bytearray(args[0])
            self.g711.read_v3(buf, args[0])
            try:
                size = len(buf)
                if size > 0:
                    self.protocol.input_audio_buffer_append(buf)
                    # logger.debug("input_audio_buffer_append {} length.".format(size))
            except:
                pass

    def stop_kws(self):
        logger.debug("stop kws...")
        self.rec.ovkws_stop()
        self.__kws_thread_stop_flag = True
        if self.__kws_thread:
            self.__kws_thread.join()

    def start_kws(self):
        logger.debug("start kws...")
        self.reset_pcm_object(samplerate=16000)
        value = settings.get("WAKEUP_KEYWORD")
        self.rec.ovkws_start(value, 0.8)
        logger.debug("唤醒词：{}".format(value))
        self.__kws_thread_stop_flag = False
        self.__kws_thread = Thread(self.__kws_thread_handler)
        self.__kws_thread.start(stack_size=16)

    def __kws_thread_handler(self):
        while True:
            if self.__kws_thread_stop_flag:
                break
            with self.lock:
                self.pcm.read(1024)
            utime.sleep_ms(10)

    def on_keyword_spotting(self, state):
        logger.info("on_keyword_spotting: {}".format(state))
        if state[0] == 0 and state[1] == 1:
            # 唤醒词触发
            self.on_wakeup_key_click(None)
        else:
            pass

    # ========= 入口函数 =========
    def run(self):
        self.led_power_pin.write(1)
        self.power_green_led.blink(250, 250)
        self.charge_manager.enable_charge()  # 开启充电
        self.wakeup_key.enable()  # 使能唤醒按键
        self.vol_plus.enable()
        self.vol_sub.enable()
        self.qth_init(settings.PRODUCT_KEY, settings.PRODUCT_SECRET)  # 云控制平台
        self.protocol.get_realtime_api_info()
        self.start_kws()

    # ========== 业务控制 ===========
    def on_wakeup_key_click(self, args):
        rv = self.__semphore.acquire(block=False)
        if not rv:
            logger.debug("chat is already running.")
            return
        self.chat_thread = Thread(target=self.chat_process)
        self.chat_thread.start(stack_size=64)

    def chat_process(self):
        logger.debug("chat processing...")
        self.power_green_led.blink(50, 50)
        try:
            self.stop_kws()
            self.reset_pcm_object(samplerate=8000)
            with self.protocol:
                if not self.event_set.wait(SESSION_CREATED_EVENT, timeout=10, clear=True):
                    logger.debug("protocol connect failed, get no SESSION_CREATED_EVENT after 10 seconds.")
                    return
                logger.debug("protocol connect successed")
                self.power_green_led.on()
                while True:
                    if not self.protocol.is_state_ok():
                        break
                    utime.sleep(1)
        except Exception as e:
            usys.print_exception(e)
            logger.debug("chat process got {}".format(repr(e)))
        finally:
            logger.debug("chat process thread break out")
            self.__semphore.release()
            self.start_kws()
            self.power_green_led.blink(250, 250)

    def __on_event(self, event):
        try:
            if "type" in event:
                event_type = event["type"].replace(".", "_")
                getattr(self, "on_{}".format(event_type))(event)
        except Exception as e:
            # usys.print_exception(e)
            logger.error("{} on_event got: {}".format(type(self).__name__, repr(e)))

    def on_error(self, event):
        # raise NotImplementedError("on_error not implementd.")
        logger.error("on_error: \n{}".format(event))

    def on_session_created(self, event):
        # raise NotImplementedError("on_session_created not implemented.")
        # logger.debug("on_session_created: \n{}".format(event))
        self.event_set.set(SESSION_CREATED_EVENT)
    
    def on_session_updated(self, event):
        # raise NotImplementedError("on_session_updated not implemented.")
        # logger.debug("on_session_updated: \n{}".format(event))
        pass
    
    def on_input_audio_buffer_speech_started(self, event):
        # raise NotImplementedError("on_input_audio_buffer_speech_started not implemented.")
        # logger.debug("on_input_audio_buffer_speech_started: \n{}".format(event))
        logger.debug("on_input_audio_buffer_speech_started")
        self.wifi_green_led.on()
        if self.player.is_playing():
            self.player.stop()

    def on_input_audio_buffer_speech_stopped(self, event):
        # raise NotImplementedError("on_input_audio_buffer_speech_stopped not implemented.")
        # logger.debug("on_input_audio_buffer_speech_stopped: \n{}".format(event))
        logger.debug("on_input_audio_buffer_speech_stopped")
        self.wifi_green_led.off()

    def on_input_audio_buffer_speech_committed(self, event):
        # raise NotImplementedError("on_input_audio_buffer_speech_committed not implemented.")
        # logger.debug("on_input_audio_buffer_speech_committed: \n{}".format(event))
        pass
    
    def on_input_audio_buffer_committed(self, event):
        # raise NotImplementedError("on_input_audio_buffer_committed not implemented.")
        # logger.debug("on_input_audio_buffer_committed: \n{}".format(event))
        pass
    
    def on_input_audio_buffer_cleared(self, event):
        # logger.debug("on_input_audio_buffer_cleared: \n{}".format(event))
        pass

    def on_conversation_item_created(self, event):
        # raise NotImplementedError("on_conversation_item_created not implemented.")
        # logger.debug("on_conversation_item_created: \n{}".format(event))
        pass
    
    def on_conversation_item_input_audio_transcription_completed(self, event):
        # raise NotImplementedError("on_conversation_item_input_audio_transcription_completed not implemented.")
        logger.debug("on_conversation_item_input_audio_transcription_completed: \n{}".format(repr(event["transcript"])))
    
    def on_conversation_item_truncated(self, event):
        # raise NotImplementedError("on_conversation_item_truncated not implemented.")
        # logger.debug("on_conversation_item_truncated event: \n{}".format(event))
        pass

    def on_response_created(self, event):
        # raise NotImplementedError("on_response_created not implemented.")
        # logger.debug("on_response_created: \n{}".format(event))
        pass

    def on_response_cancelled(self, event):
        # raise NotImplementedError("on_response_cancelled not implemented.")
        # logger.debug("on_response_cancelled: \n{}".format(event))
        pass

    def on_rate_limits_updated(self, event):
        # raise NotImplementedError("on_rate_limits not implemented.")
        # logger.debug("on_rate_limits_updated: \n{}".format(event))
        pass

    def on_response_output_item_added(self, event):
        # raise NotImplementedError("on_response_output_item_added not implemented.")
        # logger.debug("on_response_output_item_added: \n{}".format(event))
        pass
    
    def on_response_content_part_added(self, event):
        # raise NotImplementedError("on_response_content_part_added not implemented.")
        # logger.debug("on_response_content_part_added: \n{}".format(event))
        pass

    def on_response_text_delta(self, event):
        # raise NotImplementedError("on_response_text_delta not implemented.")
        # logger.debug("on_response_text_delta: \n{}".format(event))
        pass

    def on_response_audio_transcript_delta(self, event):
        # raise NotImplementedError("on_response_audio_transcript_delta not implemented.")
        # logger.debug("on_response_audio_transcript_delta: \n{}".format(event))
        pass
    
    def on_response_audio_transcript_done(self, event):
        # raise NotImplementedError("on_response_audio_transcript_done not implemented.")
        logger.debug("on_response_audio_transcript_done: \n{}".format(repr(event["text"])))

    def on_response_content_part_done(self, event):
        # raise NotImplementedError("on_response_content_part_done not implemented.")
        # logger.debug("on_response_content_part_done: \n{}".format(event))
        pass

    def on_response_output_item_done(self, event):
        # raise NotImplementedError("on_response_output_item_done not implemented.")
        # logger.debug("on_response_output_item_done: \n{}".format(event))
        pass

    def on_response_audio_delta(self, event):
        data = base64.b64decode(event["delta"])
        self.g711.write(data, 0)

    def on_response_audio_done(self, event):
        # logger.debug("on_response_audio_done: \n{}".format(event))
        pass

    def on_response_done(self, event):
        # logger.debug("on_response_done: \n{}".format(event))
        gc.collect()

    def on_response_function_call_arguments_delta(self, event):
        # raise NotImplementedError("on_response_done not implemented.")
        # logger.debug("on_response_done: \n{}".format(event))
        pass
    
    def on_response_function_call_arguments_done(self, event):
        # raise NotImplementedError("on_response_done not implemented.")
        # logger.debug("on_response_done: \n{}".format(event))
        pass

    # ========= 云控制 =========
    def qth_init(self, pk, ps):
        qth_init.init()
        qth_config.setServer("mqtt://iot-south.acceleronix.io:1883")
        qth_config.setProductInfo(pk, ps)
        qth_config.setEventCb(
            {
                'devEvent': self.event_cb, 
                'recvTrans': self.recv_trans_cb,
                'recvTsl': self.recv_tsl_cb, 
                'readTsl': self.read_tsl_cb, 
                'readTslServer': self.recv_tsl_server_cb,
                'ota': {
                    'otaPlan': self.ota_plan_cb,
                    'fotaResult': self.fota_result_cb
                }
            }
        )
        qth_init.start()

    def event_cb(self, event, result):
        logger.debug('dev event: {} result: {}'.format(event, result))

    def recv_trans_cb(self, value):
        ret = qth_bus.sendTrans(1, value)
        logger.debug('recvTrans value: {} ret: {}'.format(value, ret))

    def recv_tsl_cb(self, value):

        # logger.debug('recvTsl:{}'.format(value))
        for cmdId, val in value.items():
            if cmdId == 4:
                logger.debug("调节音量: {}".format(val))
                self.aud.setVolume(val)
            if cmdId == 3:
                logger.debug("设置唤醒词为：{}".format(val[0][1]))
                settings.update(
                    DISPLAY_TEXT=val[0][1],
                    WAKEUP_KEYWORD=val[0][2]
                )
                self.protocol.disconnect()
            if cmdId == 6:
                logger.debug("开关：{}".format(val))
            if cmdId == 11:
                logger.debug("智能体参数设置: {}".format(val))
            if cmdId == 13:
                logger.debug("AI 接入方式：{}".format(val))
            if cmdId == 10:
                logger.debug("音乐播放地址: {}".format(val))
                self.player.play(val)
            if cmdId == 7:
                logger.debug("聊天模式：{}".format(val))
            if cmdId == 5:
                logger.debug("设备模式: {}".format(val))
            if cmdId == 1:
                logger.debug("设备重新进入聊天：{}".format(val))
            else:
                pass

    def read_tsl_cb(self, ids, pkgId):
        logger.debug('readTsl ids: {} pkgId: {}'.format(ids, pkgId))
        value=dict()
        for id in ids:
            if id == 1:
                logger.debug("设备重新进入聊天")
            elif id == 2:
                logger.debug("设备重新进入聊天结果")
                value[2] = True
            elif id == 3:
                logger.debug("唤醒词")
                value[3] = [{1: settings.get("DISPLAY_TEXT"), 2: settings.get("WAKEUP_KEYWORD")}]
            elif id == 4:
                logger.debug("音量")
                value[4] = self.aud.getVolume()
            elif id == 5:
                logger.debug("设备模式")
                value[5] = 1
            elif id == 6:
                logger.debug("开关")
            elif id == 7:
                logger.debug("聊天模式")
                value[7] = 1
            elif id == 8:
                logger.debug("电量")
                value[8] = 90
            elif id == 9:
                logger.debug("充电状态")
                value[9] = 1
            elif id == 10:
                logger.debug("音乐播放地址")
            elif id == 13:
                logger.debug("AI接入方式")
                value[13] = 1
            elif id == 14:
                logger.debug("语音检测模式")
                value[14] = 1
            else:
                pass
        qth_bus.ackTsl(1, value, pkgId)

    def recv_tsl_server_cb(self, serverId, value, pkgId):
        logger.debug('recvTslServer serverId:{} value:{} pkgId:{}'.format(serverId, value, pkgId))
        qth_bus.ackTslServer(1, serverId, value, pkgId)

    def ota_plan_cb(self, plans):
        logger.debug('otaPlan:{}'.format(plans))

    def fota_result_cb(self, comp_no, result):
        logger.debug('fotaResult comp_no:{} result:{}'.format(comp_no, result))

    def App_sotaInfoCb(self, comp_no, version, url,fileSize, md5, crc):   # fileSize是可选参数
        logger.debug('sotaInfo comp_no:{} version:{} url:{} fileSize:{} md5:{} crc:{}'.format(comp_no, version, url,fileSize, md5, crc))
        # 当使用url下载固件完成，且MCU更新完毕后，需要获取MCU最新的版本信息，并通过setMcuVer进行更新

    def App_sotaResultCb(self, comp_no, result):
        logger.debug('sotaResult comp_no:{} result:{}'.format(comp_no, result))


if __name__ == "__main__":
    app = Application()
    app.run()

