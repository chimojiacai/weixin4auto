import threading
from collections import defaultdict
from typing import Dict, List, Optional

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

    def send_files(self, who: str, filepath, exact: bool = False) -> dict:
        wx = self._ensure_wx()
        result = wx.SendFiles(filepath=filepath, who=who, exact=exact)
        return {'success': result.is_success, 'message': result.get('message', '')}

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
        data = {
            'chat': chat.who,
            'is_group': getattr(chat, 'is_group', False),
            'type': getattr(msg, 'type', 'unknown'),
            'attr': getattr(msg, 'attr', 'unknown'),
            'content': str(getattr(msg, 'content', '')),
            'is_self': getattr(msg, 'is_self', False),
            'is_system': getattr(msg, 'is_system', False),
            'sender': getattr(msg, 'sender', None) or chat.who,
            'time': getattr(msg, 'time', None),
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
