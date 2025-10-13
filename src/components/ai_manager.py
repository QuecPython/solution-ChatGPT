import gc
import utime
import base64
from machine import ExtInt
from usr.libs import CurrentApp
from usr.libs.lpm import auto_sleep
from usr.libs.threading import EventSet, Thread
from usr.libs.logging import getLogger
from .protocol import OpenAIRealTimeConnection


logger = getLogger(__name__)


SESSION_CREATED_EVENT = 1 << 0


class AIManager(object):

    def __init__(self):
        # openAI Realtime
        self.protocol = OpenAIRealTimeConnection(event_cb=self.on_openai_event)

        self.chat_thread = None
        
        # Wakeup 按键
        self.wakeup_key = ExtInt(ExtInt.GPIO41, ExtInt.IRQ_FALLING, ExtInt.PULL_PU, self.on_wakeup_key_click, 250)

        self.event_set = EventSet()

        self.conversation_item_id = None  # 记录对话的id
        self.interrupt_flag = False
    
    def init(self):
        self.wakeup_key.enable()  # 使能唤醒按键
        self.on_wakeup_key_click(None)

    def on_wakeup_key_click(self, args):
        if self.chat_thread is None or not self.chat_thread.is_running():
            self.chat_thread = Thread(target=self.chat_process)
            self.chat_thread.start(stack_size=64)
        else:
            self.__cancel_response()

    def __cancel_response(self):
        if self.conversation_item_id is not None:
            try:
                self.protocol.response_cancel()
                self.protocol.conversation_item_truncate(self.conversation_item_id)
            except:
                pass
            self.conversation_item_id = None
            self.__intr_flag = True

    def chat_process(self):
        logger.debug("chat_process thread enter")
        try:
            auto_sleep(False)
            CurrentApp().led_manager.power_green_led.blink(50, 50)
            CurrentApp().power_manager.stop_check_lpm()
            CurrentApp().audio_manager.stop_kws()
            CurrentApp().audio_manager.init_g711()
            with self.protocol:
                if not self.event_set.wait(SESSION_CREATED_EVENT, timeout=10, clear=True):
                    logger.debug("protocol connect failed, get no SESSION_CREATED_EVENT after 10 seconds.")
                    return
                logger.debug("protocol connect successed")
                CurrentApp().led_manager.power_green_led.on()
                CurrentApp().power_manager.start_check_standby()
                while True:
                    if not self.protocol.is_state_ok():
                        break
                    utime.sleep(1)
        except Exception as e:
            logger.debug("chat process got {}".format(repr(e)))
        finally:
            logger.debug("chat process thread break out")
            CurrentApp().power_manager.stop_check_standby()
            CurrentApp().audio_manager.deinit_g711()
            CurrentApp().audio_manager.start_kws()
            CurrentApp().led_manager.power_green_led.blink(250, 250)
            CurrentApp().power_manager.start_check_lpm()
            auto_sleep(True)
        logger.debug("chat_process thread exit")

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
        self.conversation_item_id = event["item"]["id"]

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
        self.interrupt_flag = False
    
    def conversation_item_deleted(self, event):
        logger.debug("conversation_item_deleted: \n{}".format(event))
    
    def input_audio_buffer_committed(self, event):
        logger.debug("input_audio_buffer_committed: \n{}".format(event))
    
    def input_audio_buffer_cleared(self, event):
        logger.debug("input_audio_buffer_cleared: \n{}".format(event))
    
    def input_audio_buffer_speech_started(self, event):
        logger.debug("input_audio_buffer_speech_started: \n{}".format(event))
        CurrentApp().led_manager.wifi_green_led.on()
        CurrentApp().audio_manager.stop_music()
        CurrentApp().power_manager.reset_standby_check()

    def input_audio_buffer_speech_stopped(self, event):
        logger.debug("input_audio_buffer_speech_stopped: \n{}".format(event))
        CurrentApp().led_manager.wifi_green_led.off()
        CurrentApp().power_manager.reset_standby_check()

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
        if self.interrupt_flag:
            return
        data = base64.b64decode(event["delta"])
        CurrentApp().audio_manager.g711_write(data)
        CurrentApp().power_manager.reset_standby_check()

    def response_audio_done(self, event):
        logger.debug("response_audio_done: \n{}".format(event))
