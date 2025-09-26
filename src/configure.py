import modem
from usr.libs.common import Database


# 默认用户配置文件路径
DEFAULT_CONFIG_PATH = '/usr/default.json'


class Settings(Database):
    """配置类"""

    # 主控版本
    VERSION = "1.0.0"

    # AIGC_API_URL = "https://aigc-api.iotomp.com/v2/aibiz/openapi/v1/chatgpt/createSession"  # 国内
    # AIGC_API_URL = "https://aigc-api.landecia.com/v2/aibiz/openapi/v1/chatgpt/createSession"  # 北美
    AIGC_API_URL = "https://aigc-api.acceleronix.io/v2/aibiz/openapi/v1/chatgpt/createSession"  # 欧洲
    PRODUCT_KEY = "p11vMU"
    DEVICE_KEY = modem.getDevImei()
    PRODUCT_SECRET = "ZFFrbFdOUHl0L0s0"
    ACCESS_SECRET = "6715b6c655754376a4a3a4a06b48244b"
    AUTHORIZATION_VALUE = "af78e30677dd671fa5351017a299847"
    # QTH_SERVER = "mqtt://iot-south.acceleronix.io:1883"  # 欧洲
    QTH_SERVER = "mqtt://iot-south.quectelcn.com:1883"  # 国内

    # 仿真环境
    # AIGC_API_URL = "https://uat-one-api.iotomp.com/v2/aibiz/openapi/v1/chatgpt/createSession"
    # AIGC_API_URL = "https://uat-one-api.iotomp.com/v2/aibiz/openapi/v1/chatgpt/production/test/createSession"
    # PRODUCT_KEY = "p11BZP"
    # PRODUCT_SECRET = "Z1ZJc3luOEFHTTJF"
    # ACCESS_SECRET = "3eaba7d62d8c44a6a15c373ce7c5755d"

    @classmethod
    def get_version(cls):
        return cls.VERSION


# 全局配置对象
settings = Settings(DEFAULT_CONFIG_PATH)
