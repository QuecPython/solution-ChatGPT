import modem


# ======= 获取 openai realtime token ======= 

AIGC_API_CN_URL = "https://aigc-api.iotomp.com/v2/aibiz/openapi/v1/chatgpt/createSession"
AIGC_API_EU_URL = "https://aigc-api.acceleronix.io/v2/aibiz/openapi/v1/chatgpt/createSession"
AIGC_API_US_URL = "https://aigc-api.landecia.com/v2/aibiz/openapi/v1/chatgpt/createSession"

AIGC_API_URL = AIGC_API_EU_URL
PRODUCT_KEY = "p11vMU"
DEVICE_KEY = modem.getDevImei()
PRODUCT_SECRET = "ZFFrbFdOUHl0L0s0"
ACCESS_SECRET = "6715b6c655754376a4a3a4a06b48244b"
AUTHORIZATION_VALUE = "af78e30677dd671fa5351017a299847"


# 仿真环境
# AIGC_API_URL = "https://uat-one-api.iotomp.com/v2/aibiz/openapi/v1/chatgpt/createSession"
# PRODUCT_KEY = "p11AQa"
# PRODUCT_SECRET = "TmMrWjh5b2hPZUVx"
# ACCESS_SECRET = "bea03b3cfe544cd2945195c8f845a0ed"
