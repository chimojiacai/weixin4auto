"""启动 weixin4auto API 服务

用法：
    python run_api.py
    python run_api.py --host 0.0.0.0 --port 8080
    python run_api.py --debug
"""

import argparse
import sys

from api.app import create_app
from api.config import ApiConfig
from api.manager import WeChatManager


def main():
    parser = argparse.ArgumentParser(description='weixin4auto API 服务')
    parser.add_argument('--host', default=ApiConfig.HOST, help=f'监听地址（默认: {ApiConfig.HOST}）')
    parser.add_argument('--port', type=int, default=ApiConfig.PORT, help=f'端口号（默认: {ApiConfig.PORT}）')
    parser.add_argument('--debug', action='store_true', help='启用调试模式')
    args = parser.parse_args()

    # 启动前检测微信客户端
    try:
        info = WeChatManager().init_wechat()
        print(f'微信已连接，昵称: {info["nickname"]}')
    except Exception as e:
        print(f'启动失败: 未检测到已登录的微信客户端\n{e}', file=sys.stderr)
        sys.exit(1)

    app = create_app()
    app.run(host=args.host, port=args.port, debug=args.debug)


if __name__ == '__main__':
    main()
