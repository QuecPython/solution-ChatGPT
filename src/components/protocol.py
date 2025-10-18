import utime
import ujson
import base64
import request
import ubinascii
import uhashlib
import uwebsocket as ws
from usr.libs.threading import Thread
from usr.libs.logging import getLogger
from usr.configure import settings


logger = getLogger(__name__)


# ======= 获取 openai realtime token ======= 


def _get_sign(pk, dk, time_string, ak):
    """hashlib sha256 生成签名"""
    hash_obj  = uhashlib.sha256()  # 创建hash对象
    hash_obj.update(pk + dk + time_string + ak)
    res = hash_obj.digest()
    hex_msg = ubinascii.hexlify(res)
    return hex_msg.decode()


def get_openai_realtime_token():
    """获取 OpenAI Realtime Token"""
    timestamp = utime.mktime(utime.localtime()) * 1000
    sign = _get_sign(settings.PRODUCT_KEY, settings.DEVICE_KEY, str(timestamp), settings.ACCESS_SECRET)
    logger.debug("request post url: {}".format(settings.AIGC_API_URL))
    resp = request.post(
        settings.AIGC_API_URL,
        headers={
            "Authorization": settings.AUTHORIZATION_VALUE,
            "Content-Type": "application/json"
        },
        data = ujson.dumps(
            {
                "inputAudioFormat": "g711_alaw",
                "outputAudioFormat": "g711_alaw",
                "temperature": 0.8,
                "productKey": settings.PRODUCT_KEY,
                "deviceKey": settings.DEVICE_KEY,
                "timestamp": timestamp,
                "sign": sign,
                # "inputAudioNoiseReduction": "far_field",
                # "turnDetection": None,
                "turnDetection": {
                    "createResponse": True,
                    "interruptResponse": True,
                    "prefixPaddingMs": 800,
                    "silenceDurationMs": 500,
                    "threshold": 0.45,
                    "type": "server_vad"
                }
            }
        )
    )
    json_data = resp.json()
    logger.debug("get_openai_realtime_token resp json data: ", json_data)
    if json_data["code"] != 200:
        raise ValueError("get_openai_realtime_token get code: {}, message: {}".format(json_data["code"], json_data["msg"]))
    return json_data["data"]


class EventIDGenerator(object):

    def __init__(self):
        self.__id = 1

    def get(self):
        self.__id += 1
        if self.__id > 10000:
            self.__id = 1
        return self.__id


class OpenAIRealTimeConnection(object):

    def __init__(self, event_cb=lambda event: None, debug=True):
        self.debug = debug
        self.__recv_thread = None
        self.__event_cb = event_cb
        self.__event_id_generator = EventIDGenerator()

    def __str__(self):
        return "{}".format(type(self).__name__)

    def __enter__(self):
        self.connect()
        return self

    def __exit__(self, *args, **kwargs):
        return self.disconnect()

    @property
    def conn(self):
        __client__ = getattr(self, "__client__", None)
        if __client__ is None:
            raise RuntimeError("{} not connected".format(self))
        return __client__

    def is_state_ok(self):
        return self.conn.sock.getsocketsta() == 4
    
    def disconnect(self):
        """disconnect websocket"""
        __client__ = getattr(self, "__client__", None)
        if __client__ is not None:
            __client__.close()
            delattr(self, "__client__")
        if self.__recv_thread is not None:
            self.__recv_thread.join()
            self.__recv_thread = None

    def get_realtime_api_info(self):
        """通过移远云接口获取 realtime 连接 url 和 token"""
        data = get_openai_realtime_token()
        url = data["url"] + data["path"]
        token = data["ephemeralToken"]
        expire = data["expireAt"]
        return url, token, expire

    def connect(self):
        """connect websocket"""
        url, token, expire = self.get_realtime_api_info()
        __client__ = ws.Client.connect(
            url,
            headers={
                "Authorization": "Bearer {}".format(token)
            },
            debug=self.debug
        )
        try:
            self.__recv_thread = Thread(target=self.__recv_thread_worker)
            self.__recv_thread.start(stack_size=128)
        except Exception as e:
            __client__.close()
            logger.error("{} connect failed, Exception details: {}".format(self, repr(e)))
        else:
            setattr(self, "__client__", __client__)
            return __client__

    def __recv_thread_worker(self):
        while True:
            try:
                raw = self.conn.recv(1024*32)
            except Exception as e:
                logger.info("{} recv thread break, Exception details: {}".format(self, repr(e)))
                break
            if raw is None or raw == "":
                logger.info("{} recv thread break, Exception details: read none bytes, websocket disconnect".format(self))
                break
            if len(raw) > 1024*4:
                continue
            try:
                self.__event_cb(ujson.loads(raw))
            except Exception as e:
                print("handle event error: {}".format(repr(e)))

    def emit(self, payload):
        """发布客户端event"""
        return self.conn.send(ujson.dumps(payload))

    def session_update(self, payload):
        return self.emit(payload)
    
    def input_audio_buffer_append(self, buffer):
        return self.emit(
            {
                "audio": base64.b64encode(buffer),
                "event_id": "event_{}".format(self.__event_id_generator.get()),
                "type": "input_audio_buffer.append"
            }
        )
    
    def input_audio_buffer_commit(self):
        return self.emit(
            {
                "event_id": "event_{}".format(self.__event_id_generator.get()),
                "type": "input_audio_buffer.commit"
            }
        )
    
    def input_audio_buffer_clear(self):
        return self.emit(
            {
                "event_id": "event_{}".format(self.__event_id_generator.get()),
                "type": "input_audio_buffer.clear"
            }
        )
    
    def conversation_item_create(self):
        return self.emit(
            {
                "type": "conversation.item.create",
                "item": {
                    "type": "message",
                    "role": "user",
                    "content": [
                    {
                        "type": "input_text",
                        "text": "hi"
                    }
                    ]
                },
                "event_id": "event_{}".format(self.__event_id_generator.get()),
            }
        )
    
    def conversation_item_retrieve(self):
        return self.emit(
            {
                "event_id": "event_{}".format(self.__event_id_generator.get()),
                "type": "conversation.item.retrieve",
                "item_id": "item_003"
            }
        )

    def conversation_item_truncate(self, item_id):
        return self.emit(
            {
                "event_id": "event_{}".format(self.__event_id_generator.get()),
                "type": "conversation.item.truncate",
                "item_id": item_id,
                "content_index": 0,
                "audio_end_ms": 0
            }
        )
    
    def conversation_item_delete(self):
        return self.emit(
            {
                "event_id": "event_901",
                "type": "conversation.item.delete",
                "item_id": "item_003"
            }
        )

    def response_create(self):
        return self.emit(
            {
                "event_id": "event_{}".format(self.__event_id_generator.get()),
                "type": "response.create",
                "response": {
                    "output_modalities": [ "audio" ]
                }
            }
        )

    def response_cancel(self):
        return self.emit(
            {
                "event_id": "event_{}".format(self.__event_id_generator.get()),
                "type": "response.cancel"
            }
        )

    def transcription_session_update(self):
        return self.emit(
            {
                "type": "transcription_session.update",
                "session": {
                    "input_audio_format": "pcm16",
                    "input_audio_transcription": {
                        "model": "gpt-4o-transcribe",
                        "prompt": "",
                        "language": ""
                    },
                    "turn_detection": {
                        "type": "server_vad",
                        "threshold": 0.5,
                        "prefix_padding_ms": 300,
                        "silence_duration_ms": 500,
                        "create_response": True,
                    },
                    "input_audio_noise_reduction": {
                        "type": "near_field"
                    },
                    "include": [
                        "item.input_audio_transcription.logprobs",
                    ]
                }
            }
        )
