import base64
import os
import re
import tempfile
import threading
from collections import defaultdict
from datetime import datetime
from typing import Dict, List, Optional
from urllib.parse import urlparse, unquote

import requests

from weixin4auto import WeChat
from .config import ApiConfig


class WeChatManager:
    """WeChat 实例管理器（单例）"""

    _instance: Optional['WeChatManager'] = None
    _lock = threading.Lock()

    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        if hasattr(self, '_inited'):
            return
        self._inited = True
        self.wx: Optional[WeChat] = None
        self.nickname: str = ''
        self._webhook_urls: Dict[str, List[str]] = defaultdict(list)
        self._messages: Dict[str, list] = defaultdict(list)
        self._msg_lock = threading.Lock()

    # ── 初始化 ──────────────────────────────────────────────

    def init_wechat(self) -> dict:
        if self.wx is not None:
            return {'nickname': self.nickname}
        self.wx = WeChat()
        self.nickname = self.wx.nickname
        return {'nickname': self.nickname}

    def _ensure_wx(self) -> WeChat:
        if self.wx is None:
            self.init_wechat()
        return self.wx

    # ── 发消息 ──────────────────────────────────────────────

    def send_msg(self, who: str, msg: str, at=None, exact: bool = False) -> dict:
        wx = self._ensure_wx()
        result = wx.SendMsg(msg=msg, who=who, at=at, exact=exact)
        return {'success': result.is_success, 'message': result.get('message', '')}

    def send_files(
        self,
        who: str,
        filepath=None,
        file_base64: str = None,
        filename: str = None,
        file_url: str = None,
        exact: bool = False,
    ) -> dict:
        wx = self._ensure_wx()
        temp_files = []

        try:
            # 模式1：base64 内容
            if file_base64:
                if not filename:
                    return {'success': False, 'message': 'base64 模式需要提供 filename 参数'}
                path = self._save_base64(file_base64, filename)
                temp_files.append(path)
                filepath = path

            # 模式2：URL 下载
            elif file_url:
                path = self._download_file(file_url)
                temp_files.append(path)
                filepath = path

            if not filepath:
                return {'success': False, 'message': '缺少文件来源参数（filepath / file_base64 / file_url）'}

            result = wx.SendFiles(filepath=filepath, who=who, exact=exact)
            return {'success': result.is_success, 'message': result.get('message', '')}
        finally:
            for f in temp_files:
                try:
                    os.remove(f)
                except Exception:
                    pass

    def _save_base64(self, data: str, filename: str) -> str:
        """将 base64 内容解码并保存为临时文件，返回文件路径"""
        raw = base64.b64decode(data)
        suffix = os.path.splitext(filename)[1] or '.tmp'
        fd, path = tempfile.mkstemp(suffix=suffix, prefix='wxapi_')
        with os.fdopen(fd, 'wb') as f:
            f.write(raw)
        return path

    def _download_file(self, url: str) -> str:
        """从 URL 下载文件保存为临时文件，返回文件路径"""
        resp = requests.get(url, timeout=60)
        resp.raise_for_status()
        # 从 URL 或 Content-Disposition 提取文件名
        name = ''
        cd = resp.headers.get('Content-Disposition', '')
        if 'filename=' in cd:
            name = unquote(cd.split('filename=')[-1].strip('"\' '))
        if not name:
            name = unquote(urlparse(url).path.split('/')[-1]) or 'file.tmp'
        suffix = os.path.splitext(name)[1] or '.tmp'
        fd, path = tempfile.mkstemp(suffix=suffix, prefix='wxapi_')
        with os.fdopen(fd, 'wb') as f:
            f.write(resp.content)
        return path

    # ── 监听 ────────────────────────────────────────────────

    def start_listen(
        self,
        nickname: str,
        webhook_url: str = None,
        fetch_sender: bool = True,
    ) -> dict:
        wx = self._ensure_wx()

        if webhook_url:
            urls = self._webhook_urls[nickname]
            if webhook_url not in urls:
                urls.append(webhook_url)

        def _on_message(msg, chat):
            data = self._format_message(msg, chat)
            msgType = getattr(msg, 'type', None)
            if msgType == "text" and data["content"] == "ping":
                chat.SendMsg("pong_r")
                return
            # 图片消息自动下载
            if msgType == 'image':
                try:
                    result = msg.download()
                    if result.is_success:
                        file_path = result['data']['path']
                        data['file_path'] = file_path
                        data['file_url'] = f'/api/file/{os.path.basename(file_path)}'
                    else:
                        data['download_error'] = result.get('message', '下载失败')
                except Exception as e:
                    data['download_error'] = str(e)
            self._buffer_message(chat.who, data)
            self._forward_to_webhooks(chat.who, data)

        wx.ListenChats(nickname=nickname, callback=_on_message, fetch_sender=fetch_sender)
        return {'success': True, 'nickname': nickname}

    def stop_listen(self, nickname: str, close_window: bool = True) -> dict:
        wx = self._ensure_wx()
        result = wx.RemoveListenChat(nickname, close_window=close_window)
        self._webhook_urls.pop(nickname, None)
        return {'success': result.is_success, 'message': result.get('message', '')}

    def stop_all(self) -> dict:
        wx = self._ensure_wx()
        wx.StopListening(remove=True)
        self._webhook_urls.clear()
        return {'success': True}

    def get_messages(self, nickname: str = None, clear: bool = True) -> list:
        with self._msg_lock:
            if nickname:
                msgs = list(self._messages.get(nickname, []))
                if clear:
                    self._messages.pop(nickname, None)
                return msgs
            all_msgs = []
            for msgs in self._messages.values():
                all_msgs.extend(msgs)
            if clear:
                self._messages.clear()
            return all_msgs

    # ── Webhook 管理 ────────────────────────────────────────

    def add_webhook(self, nickname: str, webhook_url: str) -> dict:
        urls = self._webhook_urls[nickname]
        if webhook_url not in urls:
            urls.append(webhook_url)
        return {'success': True, 'webhooks': list(urls)}

    def remove_webhook(self, nickname: str, webhook_url: str) -> dict:
        urls = self._webhook_urls.get(nickname, [])
        if webhook_url in urls:
            urls.remove(webhook_url)
        return {'success': True, 'webhooks': list(urls)}

    def get_webhooks(self, nickname: str = None) -> dict:
        if nickname:
            return {nickname: list(self._webhook_urls.get(nickname, []))}
        return {k: list(v) for k, v in self._webhook_urls.items()}

    # ── 引用回复 ─────────────────────────────────────────────

    def quote_msg(self, who: str, msg_id: str, msg: str, exact: bool = True) -> dict:
        """引用指定消息并发送回复

        Args:
            who: 聊天对象昵称
            msg_id: 消息 ID（runtimeid 字符串或 hash）
            msg: 回复内容
            exact: 搜索聊天对象时是否精确匹配

        Returns:
            dict: 操作结果
        """
        wx = self._ensure_wx()

        # 优先在监听子窗口中查找
        chat = None
        listen_key = None
        if hasattr(wx, 'listen'):
            for key, (c, _) in wx.listen.items():
                if key == who or who in key or key in who:
                    chat = c
                    listen_key = key
                    break
            # 反查原始昵称
            if chat is None and hasattr(wx, '_listen_nicknames'):
                for actual, orig in wx._listen_nicknames.items():
                    if orig == who and actual in wx.listen:
                        chat, _ = wx.listen[actual]
                        listen_key = actual
                        break

        # 未找到监听窗口，切换到主窗口
        if chat is None:
            wx.ChatWith(who=who, exact=exact)
            from weixin4auto.wx import Chat
            chat = Chat(wx._api)

        # 查找消息：优先 hash，再试 runtimeid
        target_msg = None
        if re.fullmatch(r'[0-9a-fA-F]{32}', msg_id):
            target_msg = chat.GetMessageByHash(msg_id)
        if target_msg is None:
            target_msg = chat.GetMessageById(msg_id)
        if target_msg is None:
            return {'success': False, 'message': f'未找到消息: {msg_id}（消息可能已滚出可视区域）'}

        # 调用消息对象的 quote 方法（已内置于 BaseMessage）
        result = target_msg.quote(msg)
        return {'success': result.is_success, 'message': result.get('message', '')}

    # ── 会话 ────────────────────────────────────────────────

    def switch_chat(self, who: str, exact: bool = True) -> dict:
        wx = self._ensure_wx()
        wx.ChatWith(who=who, exact=exact)
        return {'success': True, 'who': who}

    def get_sessions(self) -> list:
        wx = self._ensure_wx()
        sessions = wx.GetSession()
        return [{'name': s.name, 'content': s.content} for s in sessions]

    # ── 内部方法 ────────────────────────────────────────────

    def _format_message(self, msg, chat) -> dict:
        content = str(getattr(msg, 'content', ''))
        # 语音消息：等待转写完成后获取文字
        if getattr(msg, 'type', None) == 'voice':
            try:
                text = msg.to_text()
                if text:
                   content = text
            except Exception:
                pass
        data = {
            'chat': chat.who,
            'is_group': getattr(chat, 'is_group', False),
            'type': getattr(msg, 'type', 'unknown'),
            'attr': getattr(msg, 'attr', 'unknown'),
            'content': content,
            'id': str(getattr(msg, 'id', '')) or None,
            'hash': getattr(msg, 'hash', None),
            'is_self': getattr(msg, 'is_self', False),
            'is_system': getattr(msg, 'is_system', False),
            'sender': getattr(msg, 'sender', None) or chat.who,
            'time': getattr(msg, 'time', None) or datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        }
        return data

    def _buffer_message(self, who: str, data: dict):
        with self._msg_lock:
            buf = self._messages[who]
            buf.append(data)
            if len(buf) > ApiConfig.MESSAGE_BUFFER_SIZE:
                self._messages[who] = buf[-ApiConfig.MESSAGE_BUFFER_SIZE:]

    def _forward_to_webhooks(self, who: str, data: dict):
        urls = self._webhook_urls.get(who, []) + self._webhook_urls.get('*', [])
        for url in urls:
            try:
                requests.post(url, json=data, timeout=ApiConfig.WEBHOOK_TIMEOUT)
            except Exception:
                pass
