from .net_manager import NetManager
from .audio_manager import AudioManager
from .power_manager import PowerManager
from .led_manager import LedManager
from .qth_client import QthClient
from .ai_manager import AIManager


led_manager = LedManager()
net_manager = NetManager()
power_manager = PowerManager()
audio_manager = AudioManager()
qth_client = QthClient()
ai_manager = AIManager()
