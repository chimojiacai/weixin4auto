import os


class ApiConfig:
    HOST = os.getenv('WXAPI_HOST', '0.0.0.0')
    PORT = int(os.getenv('WXAPI_PORT', 5000))
    DEBUG = os.getenv('WXAPI_DEBUG', 'false').lower() == 'true'

    # 消息转发 webhook 超时（秒）
    WEBHOOK_TIMEOUT = 10
    # 消息缓存上限（每个聊天对象）
    MESSAGE_BUFFER_SIZE = 500
