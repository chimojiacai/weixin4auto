import sys

from api.app import create_app
from api.config import ApiConfig
from api.manager import WeChatManager


def main():
    try:
        info = WeChatManager().init_wechat()
        print(f'微信已连接，昵称: {info["nickname"]}')
    except Exception as e:
        print(f'启动失败: 未检测到已登录的微信客户端\n{e}', file=sys.stderr)
        sys.exit(1)

    app = create_app()
    app.run(host=ApiConfig.HOST, port=ApiConfig.PORT, debug=ApiConfig.DEBUG)


if __name__ == '__main__':
    main()
