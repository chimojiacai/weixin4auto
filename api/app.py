from flask import Flask, request, jsonify, send_from_directory

from .manager import WeChatManager
from .config import ApiConfig


def create_app() -> Flask:
    app = Flask(__name__)
    mgr = WeChatManager()

    # ── 状态 ─────────────────────────────────────────────────

    @app.route('/api/status', methods=['GET'])
    def status():
        """获取微信状态"""
        return jsonify({'success': True, 'data': {'nickname': mgr.nickname}})

    # ── 发消息 ───────────────────────────────────────────────

    @app.route('/api/message/send', methods=['POST'])
    def send_message():
        """
        发送文本消息
        Body JSON:
            who (str):  发送对象昵称（必填）
            msg (str):  消息内容（必填）
            at (str|list, optional): @对象
            exact (bool, optional): 是否精确匹配，默认 false
        """
        data = request.get_json(silent=True) or {}
        who = data.get('who')
        msg = data.get('msg')
        if not who or not msg:
            return jsonify({'success': False, 'error': '缺少 who 或 msg 参数'})

        result = mgr.send_msg(
            who=who,
            msg=msg,
            at=data.get('at'),
            exact=data.get('exact', True),
        )
        return jsonify(result)

    @app.route('/api/file/send', methods=['POST'])
    def send_file():
        """
        发送文件
        Body JSON:
            who (str):            发送对象昵称（必填）
            filepath (str|list):   文件路径或路径列表
            file_base64 (str):     文件 base64 编码内容，需配合 filename
            filename (str):        base64 模式的文件名（含扩展名）
            file_url (str):        文件下载地址
            exact (bool, optional): 是否精确匹配，默认 false

        注意：filepath / file_base64 / file_url 三选一
              base64 和 url 模式会先存临时文件，发送成功后自动删除
        """
        data = request.get_json(silent=True) or {}
        who = data.get('who')
        if not who:
            return jsonify({'success': False, 'error': '缺少 who 参数'})

        filepath = data.get('filepath')
        file_base64 = data.get('file_base64')
        file_url = data.get('file_url')
        if not filepath and not file_base64 and not file_url:
            return jsonify({'success': False, 'error': '缺少文件来源参数（filepath / file_base64 / file_url）'})

        result = mgr.send_files(
            who=who,
            filepath=filepath,
            file_base64=file_base64,
            filename=data.get('filename'),
            file_url=file_url,
            exact=data.get('exact', False),
        )
        return jsonify(result)

    # ── 监听 ─────────────────────────────────────────────────

    @app.route('/api/listen/start', methods=['POST'])
    def start_listen():
        """
        启动对指定聊天的监听
        Body JSON:
            who (str|list):   要监听的聊天对象（必填）
            webhook_url (str, optional): 消息转发地址
            fetch_sender (bool, optional): 群聊是否获取发送者昵称，默认 true
        """
        data = request.get_json(silent=True) or {}
        nickname = data.get('who')
        if not nickname:
            return jsonify({'success': False, 'error': '缺少 who 参数'})

        webhook_url = data.get('webhook_url')
        fetch_sender = data.get('fetch_sender', True)

        nicknames = [nickname] if isinstance(nickname, str) else list(nickname)
        results = []
        for nick in nicknames:
            r = mgr.start_listen(
                nickname=nick,
                webhook_url=webhook_url,
                fetch_sender=fetch_sender,
            )
            results.append(r)
        return jsonify({'success': True, 'results': results})

    @app.route('/api/listen/stop', methods=['POST'])
    def stop_listen():
        """
        停止监听
        Body JSON:
            who (str, optional): 指定停止的昵称，不传则停止全部
            close_window (bool, optional): 是否关闭窗口，默认 true
        """
        data = request.get_json(silent=True) or {}
        nickname = data.get('who')
        close_window = data.get('close_window', True)

        if nickname:
            result = mgr.stop_listen(nickname, close_window=close_window)
        else:
            result = mgr.stop_all()
        return jsonify(result)

    @app.route('/api/listen/messages', methods=['GET'])
    def get_messages():
        """
        获取监听缓存消息
        Query:
            nickname (str, optional): 指定聊天对象，不传返回全部
            clear (bool, optional): 获取后是否清空缓存，默认 true
        """
        nickname = request.args.get('nickname')
        clear = request.args.get('clear', 'true').lower() == 'true'
        msgs = mgr.get_messages(nickname=nickname, clear=clear)
        return jsonify({'success': True, 'count': len(msgs), 'messages': msgs})

    # ── Webhook 管理 ─────────────────────────────────────────

    @app.route('/api/webhook/add', methods=['POST'])
    def add_webhook():
        """
        添加消息转发地址
        Body JSON:
            nickname (str): 聊天对象昵称（必填），填 "*" 表示所有
            webhook_url (str): 转发目标 URL（必填）
        """
        data = request.get_json(silent=True) or {}
        nickname = data.get('nickname')
        webhook_url = data.get('webhook_url')
        if not nickname or not webhook_url:
            return jsonify({'success': False, 'error': '缺少 nickname 或 webhook_url 参数'})
        result = mgr.add_webhook(nickname, webhook_url)
        return jsonify(result)

    @app.route('/api/webhook/remove', methods=['POST'])
    def remove_webhook():
        """
        移除消息转发地址
        Body JSON:
            nickname (str): 聊天对象昵称（必填）
            webhook_url (str): 要移除的 URL（必填）
        """
        data = request.get_json(silent=True) or {}
        nickname = data.get('nickname')
        webhook_url = data.get('webhook_url')
        if not nickname or not webhook_url:
            return jsonify({'success': False, 'error': '缺少 nickname 或 webhook_url 参数'})
        result = mgr.remove_webhook(nickname, webhook_url)
        return jsonify(result)

    @app.route('/api/webhook/list', methods=['GET'])
    def list_webhooks():
        """
        查看已配置的转发地址
        Query:
            nickname (str, optional): 指定昵称，不传返回全部
        """
        nickname = request.args.get('nickname')
        result = mgr.get_webhooks(nickname)
        return jsonify({'success': True, 'data': result})

    # ── 文件下载目录 ──────────────────────────────────────────

    @app.route('/api/file/<path:filename>', methods=['GET'])
    def get_file(filename):
        """通过文件名访问下载目录中的文件

        示例：GET /api/file/wxauto_image_20260715203810487816.jpg
        """
        return send_from_directory(ApiConfig.DOWNLOAD_DIR, filename)

    @app.route('/api/files', methods=['GET'])
    def list_files():
        """列出下载目录中的所有文件"""
        import os
        try:
            files = []
            for f in os.listdir(ApiConfig.DOWNLOAD_DIR):
                full_path = os.path.join(ApiConfig.DOWNLOAD_DIR, f)
                if os.path.isfile(full_path):
                    files.append({
                        'name': f,
                        'size': os.path.getsize(full_path),
                        'url': f'/api/file/{f}',
                    })
            return jsonify({'success': True, 'count': len(files), 'files': files})
        except FileNotFoundError:
            return jsonify({'success': True, 'count': 0, 'files': []})

    # ── 会话 ─────────────────────────────────────────────────

    @app.route('/api/chat/switch', methods=['POST'])
    def switch_chat():
        """
        切换主窗口到指定聊天
        Body JSON:
            who (str):  聊天对象昵称（必填）
            exact (bool, optional): 是否精确匹配，默认 true
        """
        data = request.get_json(silent=True) or {}
        who = data.get('who')
        if not who:
            return jsonify({'success': False, 'error': '缺少 who 参数'})
        result = mgr.switch_chat(who, exact=data.get('exact', True))
        return jsonify(result)

    @app.route('/api/sessions', methods=['GET'])
    def get_sessions():
        """获取当前会话列表"""
        sessions = mgr.get_sessions()
        return jsonify({'success': True, 'count': len(sessions), 'sessions': sessions})

    return app
