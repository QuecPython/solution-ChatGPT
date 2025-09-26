import gc
import utime
import base64
from machine import ExtInt, Pin
from usr.libs.threading import Thread, EventSet
from usr.libs.logging import getLogger
from usr.components.utils import ChargeManager, Led, AudioManager
from usr.components.openai import OpenAIRealTimeConnection
from usr.configure import settings
from usr.libs.logging import getLogger



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

        self.event_set = EventSet()

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

        self.on_wakeup_key_click(None)

    # ========== 业务控制 ===========
    def on_wakeup_key_click(self, args):
        if self.chat_thread is None or not self.chat_thread.is_running():
            self.chat_thread = Thread(target=self.chat_process)
            self.chat_thread.start(stack_size=64)

    def chat_process(self):
        logger.debug("chat_process thread enter")
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
                    if not self.protocol.is_state_ok():
                        break
                    utime.sleep(1)
        except Exception as e:
            logger.debug("chat process got {}".format(repr(e)))
        finally:
            logger.debug("chat process thread break out")
            self.audio_manager.deinit_g711()
            self.audio_manager.start_kws()
            self.power_green_led.blink(250, 250)
        logger.debug("chat_process thread exit")
    
    def g711_cb(self, args):
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
                getattr(self, "{}".format(event_type))(event)
            else:
                logger.warn("open ai event got no type keyword: {}".format(event))
        except Exception as e:
            logger.error("{} on_openai_event got: {}".format(type(self).__name__, repr(e)))

    def error(self, event):
        logger.error("error: \n{}".format(event))

    def session_created(self, event):
        logger.debug("session_created: \n{}".format(event))
        self.event_set.set(SESSION_CREATED_EVENT)
    
    def session_updated(self, event):
        logger.debug("session_updated: \n{}".format(event))
    
    def transcription_session_created(self, event):
        logger.debug("transcription_session_created: \n{}".format(event))

    def transcription_session_updated(self, event):
        logger.debug("transcription_session_updated: \n{}".format(event))

    def conversation_item_created(self, event):
        logger.debug("conversation_item_created: \n{}".format(event))

    def conversation_item_retrieved(self, event):
        logger.debug("conversation_item_retrieved: \n{}".format(event))

    def conversation_item_input_audio_transcription_completed(self, event):
        logger.debug("conversation_item_input_audio_transcription_completed: \n{}".format(event))

    def conversation_item_input_audio_transcription_delta(self, event):
        logger.debug("conversation_item_input_audio_transcription_delta: \n{}".format(event))
    
    def conversation_item_input_audio_transcription_segment(self, event):
        logger.debug("conversation_item_input_audio_transcription_segment: \n{}".format(event))
    
    def conversation_item_input_audio_transcription_failed(self, event):
        logger.debug("conversation_item_input_audio_transcription_failed: \n{}".format(event))

    def conversation_item_truncated(self, event):
        logger.debug("conversation_item_truncated: \n{}".format(event))
    
    def conversation_item_deleted(self, event):
        logger.debug("conversation_item_deleted: \n{}".format(event))
    
    def input_audio_buffer_committed(self, event):
        logger.debug("input_audio_buffer_committed: \n{}".format(event))
    
    def input_audio_buffer_cleared(self, event):
        logger.debug("input_audio_buffer_cleared: \n{}".format(event))
    
    def input_audio_buffer_speech_started(self, event):
        logger.debug("input_audio_buffer_speech_started: \n{}".format(event))
        self.wifi_green_led.on()
        self.audio_manager.stop_music()

    def input_audio_buffer_speech_stopped(self, event):
        logger.debug("input_audio_buffer_speech_stopped: \n{}".format(event))
        self.wifi_green_led.off()

    def input_audio_buffer_speech_committed(self, event):
        logger.debug("input_audio_buffer_speech_committed: \n{}".format(event))
    
    def input_audio_buffer_timeout_triggered(self, event):
        logger.debug("input_audio_buffer_timeout_triggered: \n{}".format(event))

    def response_created(self, event):
        logger.debug("response_created: \n{}".format(event))

    def response_done(self, event):
        logger.debug("response_done: \n{}".format(event))
        gc.collect()

    def response_output_item_added(self, event):
        logger.debug("response_output_item_added: \n{}".format(event))
    
    def response_output_item_done(self, event):
        logger.debug("response_output_item_done: \n{}".format(event))

    def response_content_part_added(self, event):
        logger.debug("response_content_part_added: \n{}".format(event))

    def response_content_part_done(self, event):
        logger.debug("response_content_part_done: \n{}".format(event))

    def response_output_text_delta(self, event):
        logger.debug("response_output_text_delta: \n{}".format(event))

    def response_output_text_done(self, event):
        logger.debug("response_output_text_done: \n{}".format(event))

    def response_output_audio_transcript_delta(self, event):
        logger.debug("response_output_audio_transcript_delta: \n{}".format(event))

    def response_output_audio_transcript_done(self, event):
        logger.debug("response_output_audio_transcript_done: \n{}".format(event))

    def response_output_audio_delta(self, event):
        logger.debug("response_output_audio_delta: \n{}".format(event))

    def response_output_audio_done(self, event):
        logger.debug("response_output_audio_done: \n{}".format(event))
    
    def response_function_call_arguments_delta(self, event):
        logger.debug("response_function_call_arguments_delta: \n{}".format(event))
    
    def response_function_call_arguments_done(self, event):
        logger.debug("response_function_call_arguments_done: \n{}".format(event))
    
    def response_mcp_call_arguments_delta(self, event):
        logger.debug("response_mcp_call_arguments_delta: \n{}".format(event))
    
    def esponse_mcp_call_arguments_done(self, event):
        logger.debug("esponse_mcp_call_arguments_done: \n{}".format(event))

    def response_mcp_call_in_progress(self, event):
        logger.debug("response_mcp_call_in_progress: \n{}".format(event))
    
    def response_mcp_call_completed(self, event):
        logger.debug("response_mcp_call_completed: \n{}".format(event))
    
    def response_mcp_call_failed(self, event):
        logger.debug("response_mcp_call_failed: \n{}".format(event))
    
    def mcp_list_tools_in_progress(self, event):
        logger.debug("mcp_list_tools_in_progress: \n{}".format(event))
    
    def mcp_list_tools_completed(self, event):
        logger.debug("mcp_list_tools_completed: \n{}".format(event))
    
    def mcp_list_tools_failed(self, event):
        logger.debug("mcp_list_tools_failed: \n{}".format(event))
    
    def rate_limits_updated(self, event):
        logger.debug("rate_limits_updated: \n{}".format(event))

    def response_cancelled(self, event):
        logger.debug("response_cancelled: \n{}".format(event))

    def response_text_delta(self, event):
        logger.debug("response_text_delta: \n{}".format(event))

    def response_audio_transcript_delta(self, event):
        logger.debug("response_audio_transcript_delta: \n{}".format(event))
    
    def response_audio_transcript_done(self, event):
        logger.debug("response_audio_transcript_done: \n{}".format(event))
    
    def response_audio_delta(self, event):
        data = base64.b64decode(event["delta"])
        self.audio_manager.g711_write(data)

    def response_audio_done(self, event):
        logger.debug("response_audio_done: \n{}".format(event))
