import gc
import usys
import utime
import base64
from machine import ExtInt, Pin
from usr.libs.threading import Thread, BoundedSemaphore, EventSet, Lock
from usr.libs.logging import getLogger
from usr.utils import ChargeManager, Led, AudioManager
from usr.openai import OpenAIRealTimeConnection
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
        self.protocol = OpenAIRealTimeConnection(event_cb=self.on_openai_event)

        # 音频管理
        self.audio_manager = AudioManager(kws_cb=self.on_keyword_spotting, g711_cb=self.g711_cb)
        self.chat_thread = None
        
        # Wakeup 按键
        self.wakeup_key = ExtInt(ExtInt.GPIO41, ExtInt.IRQ_FALLING, ExtInt.PULL_PU, self.on_wakeup_key_click, 250)

        self.__semphore = BoundedSemaphore(value=1)
        self.event_set = EventSet()
        self.lock = Lock()

        self.audio_delta_pack_count = 0

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
        self.qth_init(settings.PRODUCT_KEY, settings.PRODUCT_SECRET)  # 云控制平台
        self.on_wakeup_key_click(None)

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
            self.audio_manager.stop_kws()
            self.audio_manager.init_g711()
            with self.protocol:
                if not self.event_set.wait(SESSION_CREATED_EVENT, timeout=10, clear=True):
                    logger.debug("protocol connect failed, get no SESSION_CREATED_EVENT after 10 seconds.")
                    return
                logger.debug("protocol connect successed")
                self.power_green_led.on()
                while True:
                    # with self.lock:
                        # data = self.audio_manager.g711_read()
                        # if len(data) > 0:
                        #     self.protocol.input_audio_buffer_append(data)
                            # logger.debug("input_audio_buffer_append {} data".format(len(data)))
                    # utime.sleep_ms(10)
                    if not self.protocol.is_state_ok():
                        break
                    utime.sleep(1)
        except Exception as e:
            usys.print_exception(e)
            logger.debug("chat process got {}".format(repr(e)))
        finally:
            logger.debug("chat process thread break out")
            self.__semphore.release()
            self.audio_manager.deinit_g711()
            self.audio_manager.start_kws()
            self.power_green_led.blink(250, 250)
    
    def g711_cb(self, args):
        global count
        if(args[1] == 1):
            buf = bytearray(args[0])
            self.audio_manager.g711_read_v3(buf, args[0])
            if len(buf) > 0:
                try:
                    self.protocol.input_audio_buffer_append(buf)
                except:
                    pass

    def on_openai_event(self, event):
        try:
            if "type" in event:
                event_type = event["type"].replace(".", "_")
                getattr(self, "on_{}".format(event_type))(event)
        except Exception as e:
            logger.error("{} on_event got: {}".format(type(self).__name__, repr(e)))

    def on_error(self, event):
        logger.error("on_error: \n{}".format(event))

    def on_session_created(self, event):
        logger.debug("on_session_created: \n{}".format(event))
        self.event_set.set(SESSION_CREATED_EVENT)
    
    def on_session_updated(self, event):
        logger.debug("on_session_updated: \n{}".format(event))
    
    def on_input_audio_buffer_speech_started(self, event):
        logger.debug("on_input_audio_buffer_speech_started: \n{}".format(event))
        self.wifi_green_led.on()
        self.audio_manager.stop_music()

    def on_input_audio_buffer_speech_stopped(self, event):
        logger.debug("on_input_audio_buffer_speech_stopped: \n{}".format(event))
        logger.debug("on_input_audio_buffer_speech_stopped")
        self.wifi_green_led.off()
        self.audio_delta_pack_count = 0

    def on_input_audio_buffer_speech_committed(self, event):
        logger.debug("on_input_audio_buffer_speech_committed: \n{}".format(event))
    
    def on_input_audio_buffer_committed(self, event):
        logger.debug("on_input_audio_buffer_committed: \n{}".format(event))
    
    def on_input_audio_buffer_cleared(self, event):
        logger.debug("on_input_audio_buffer_cleared: \n{}".format(event))

    def on_conversation_item_created(self, event):
        logger.debug("on_conversation_item_created: \n{}".format(event))
    
    def on_conversation_item_input_audio_transcription_completed(self, event):
        logger.debug("on_conversation_item_input_audio_transcription_completed: \n{}".format(event))

    def on_conversation_item_truncated(self, event):
        logger.debug("on_conversation_item_truncated event: \n{}".format(event))

    def on_response_created(self, event):
        logger.debug("on_response_created: \n{}".format(event))

    def on_response_cancelled(self, event):
        logger.debug("on_response_cancelled: \n{}".format(event))

    def on_rate_limits_updated(self, event):
        logger.debug("on_rate_limits_updated: \n{}".format(event))

    def on_response_output_item_added(self, event):
        logger.debug("on_response_output_item_added: \n{}".format(event))
    
    def on_response_content_part_added(self, event):
        logger.debug("on_response_content_part_added: \n{}".format(event))

    def on_response_text_delta(self, event):
        logger.debug("on_response_text_delta: \n{}".format(event))

    def on_response_audio_transcript_delta(self, event):
        logger.debug("on_response_audio_transcript_delta: \n{}".format(event))
    
    def on_response_audio_transcript_done(self, event):
        logger.debug("on_response_audio_transcript_done: \n{}".format(repr(event["text"])))

    def on_response_content_part_done(self, event):
        logger.debug("on_response_content_part_done: \n{}".format(event))

    def on_response_output_item_done(self, event):
        logger.debug("on_response_output_item_done: \n{}".format(event))

    def on_response_audio_delta(self, event):
        data = base64.b64decode(event["delta"])
        self.audio_manager.g711_write(data)

    def on_response_audio_done(self, event):
        logger.debug("on_response_audio_done: \n{}".format(event))

    def on_response_done(self, event):
        logger.debug("on_response_done: \n{}".format(event))
        gc.collect()

    def on_response_function_call_arguments_delta(self, event):
        logger.debug("on_response_done: \n{}".format(event))
    
    def on_response_function_call_arguments_done(self, event):
        logger.debug("on_response_done: \n{}".format(event))

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
                self.audio_manager.aud.setVolume(val)
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
                self.audio_manager.play_music(val)
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

