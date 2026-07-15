from weixin4auto.ui.base import BaseUISubWnd, BaseUIWnd
from weixin4auto.ui import WeChatMainWnd, WeChatSubWnd
from weixin4auto.logger import wxlog
from weixin4auto.param import WxParam, WxResponse, PROJECT_NAME
from weixin4auto.utils import GetAllWindows, uilock
from weixin4auto.utils.tools import delete_update_files
from weixin4auto.moment import Moment
from concurrent.futures import ThreadPoolExecutor
from abc import ABC, abstractmethod
import threading
import traceback
import time
import sys
import os
from typing import (
    Callable,
    TYPE_CHECKING,
    Union, 
    List,
    Dict,
    Literal,
    Optional,
)
if TYPE_CHECKING:
    from weixin4auto.msgs.base import Message
    from weixin4auto.ui.sessionbox import SessionElement

class Listener(ABC):
    # 清理更新文件的间隔（秒），避免频繁 I/O
    _CLEANUP_INTERVAL = 60.0
    # 窗口检查失败的最大重试次数（0.3s/次，100次≈30s），超过后才认为窗口已关闭
    _MAX_CHECK_RETRIES = 100

    def _listener_start(self):
        wxlog.debug('开始监听')
        self._listener_is_listening = True
        self._listener_messages = {}
        self._lock = threading.RLock()
        self._listener_stop_event = threading.Event()
        self._listener_thread = threading.Thread(target=self._listener_listen, daemon=True)
        # 每个监听对象的重试计数器
        self._check_fail_counts = {}
        # 每个监听对象的昵称（用于窗口恢复时重新打开）
        self._listen_nicknames = {}
        self._listener_thread.start()

    def _listener_listen(self):
        self._excutor = ThreadPoolExecutor(max_workers=WxParam.LISTENER_EXCUTOR_WORKERS)
        if not hasattr(self, 'listen') or not self.listen:
            self.listen = {}
        last_cleanup = time.time()
        while not self._listener_stop_event.is_set():
            # 定期清理更新文件，而非每次循环都清理
            now = time.time()
            if now - last_cleanup >= self._CLEANUP_INTERVAL:
                try:
                    delete_update_files()
                except Exception:
                    pass
                last_cleanup = now
            try:
                self._get_listen_messages()
            except KeyboardInterrupt:
                wxlog.debug("监听消息终止")
                self._listener_stop()
                break
            except Exception:
                wxlog.debug(f'监听消息失败：{traceback.format_exc()}')
            time.sleep(WxParam.LISTEN_INTERVAL)

    def _safe_callback(
            self, 
            callback: Callable[['Message', 'Chat'], None], 
            msg: 'Message', 
            chat: 'Chat'
        ):
        try:
            callback(msg, chat)
        except Exception as e:
            wxlog.debug(f"监听消息回调发生错误：{traceback.format_exc()}")

    def _listener_stop(self):
        self._listener_is_listening = False
        self._listener_stop_event.set()
        self._listener_thread.join()
        self._excutor.shutdown(wait=True)

    @abstractmethod
    def _get_listen_messages(self):
        ...

class Chat:
    """微信聊天窗口实例"""

    def __init__(self, core: WeChatSubWnd=None):
        self._api = core
        self.who = self._api.nickname

    def __repr__(self):
        return f'<{PROJECT_NAME} - {self.__class__.__name__} object("{self._api.nickname}")>'
    
    def __str__(self):
        if hasattr(self, 'who'):
            return self.who
        else:
            return self.nickname
    
    def __add__(self, other):
        if hasattr(self, 'who'):
            return self.who + other
        else:
            return self.nickname + other

    def __radd__(self, other):
        if hasattr(self, 'who'):
            return other + self.who
        else:
            return other + self.nickname
        
    def Show(self):
        """显示窗口"""
        self._api._show()

    def ChatInfo(self) -> Dict[str, str]:
        """获取聊天窗口信息（已禁用，避免触发点击操作）
        
        注意：此方法已被禁用，因为会触发点击好友头像的操作。
        请使用 self.who 获取聊天对象名称。
        
        Returns:
            dict: 聊天窗口信息（仅包含窗口标题）
        """
        # 不再调用 get_info()，避免触发点击操作
        # 只返回窗口标题信息
        return {
            'chat_name': self.who,
            'chat_type': 'unknown',
            'is_group': False,
            'group_member_count': 0
        }

    
    @uilock
    def SendMsg(
            self, 
            msg: str,
            who: str=None,
            clear: bool=True, 
            at: Union[str, List[str]]=None,
            exact: bool=False,
        ) -> WxResponse:
        """发送消息

        Args:
            msg (str): 消息内容
            who (str, optional): 发送对象，不指定则发送给当前聊天对象，**当子窗口时，该参数无效**
            clear (bool, optional): 发送后是否清空编辑框.
            at (Union[str, List[str]], optional): @对象，不指定则不@任何人
            exact (bool, optional): 搜索who好友时是否精确匹配，默认False，**当子窗口时，该参数无效**

        Returns:
            WxResponse: 是否发送成功
        """
        return self._api.send_msg(msg, who, clear, at, exact)
    
    @uilock
    def SendFiles(
            self, 
            filepath, 
            who=None, 
            exact=False
        ) -> WxResponse:
        """向当前聊天窗口发送文件
        
        Args:
            filepath (str|list): 要复制文件的绝对路径  
            who (str): 发送对象，不指定则发送给当前聊天对象，**当子窗口时，该参数无效**
            exact (bool, optional): 搜索who好友时是否精确匹配，默认False，**当子窗口时，该参数无效**
            
        Returns:
            WxResponse: 是否发送成功
        """
        return self._api.send_files(filepath, who, exact)
    
    def GetAllMessage(self) -> List['Message']:
        """获取当前聊天窗口的所有消息
        
        Returns:
            List[Message]: 当前聊天窗口的所有消息
        """
        return self._api.get_msgs()
    
    def GetNewMessage(self) -> List['Message']:
        """获取当前聊天窗口的新消息

        Returns:
            List[Message]: 当前聊天窗口的新消息
        """
        if not hasattr(self, '_last_chat'):
            # 使用窗口标题而不是 ChatInfo()，避免触发点击操作
            self._last_chat = self.who
        # 使用窗口标题而不是 ChatInfo()，避免触发点击操作
        if (_last_chat := self.who) != self._last_chat:
            self._last_chat = _last_chat
            self._api._chat_api._update_used_msg_ids()
            return []
        return self._api.get_new_msgs()

    def GetMessageById(self, msg_id) -> Optional['Message']:
        """根据消息 runtime id 获取消息实例"""

        return self._api.get_msg_by_id(msg_id)

    def GetMessageByHash(self, msg_hash: str) -> Optional['Message']:
        """根据消息哈希值获取消息实例"""

        return self._api.get_msg_by_hash(msg_hash)

    def GetLastMessage(self) -> Optional['Message']:
        """获取当前聊天窗口的最后一条消息"""

        return self._api.get_last_msg()

    def Close(self) -> None:
        """关闭微信窗口"""
        self._api.close()

class WeChat(Chat, Listener):
    """微信主窗口实例"""

    def __init__(
            self, 
            nickname: str=None, 
            start_listener: bool=False,
            debug: bool=False,
            **kwargs
        ):
        delete_update_files()
        hwnd = None
        if 'hwnd' in kwargs:
            hwnd = kwargs['hwnd']
        self._api = WeChatMainWnd(nickname, hwnd)
        self.NavigationBox = self._api._navigation_api
        self.SessionBox = self._api._session_api
        self.ChatBox = self._api._chat_api
        self.Moment = Moment(self)
        # nickname 已经在 WeChatMainWnd 初始化时从头像弹窗获取了
        self.nickname = self._api.nickname
        self.listen = {}
        # 消息收集器：{nickname: [msg, ...]}
        self._collected_messages = {}
        self._collected_lock = threading.Lock()
        
        # 唤起微信窗口到前台并打印昵称
        self._api._show()
        print(f'微信用户昵称: {self.nickname}')
        
        if start_listener:
            self._listener_start()
        if debug:
            wxlog.set_debug(True)
            wxlog.debug('Debug mode is on')
        
    def _get_listen_messages(self):
        """获取监听消息（容错重试 + 窗口恢复 + runtimeid 变更检测）"""
        try:
            sys.stdout.flush()
        except:
            pass

        temp_listen = self.listen.copy()
        to_remove = []

        for who, (chat, callback) in temp_listen.items():
            if chat is None:
                to_remove.append(who)
                continue

            # ── 1. 检查聊天窗口是否存在 ──
            try:
                window_exists = chat._api.exists(0)
            except Exception:
                window_exists = False

            if not window_exists:
                fail_count = self._check_fail_counts.get(who, 0) + 1
                self._check_fail_counts[who] = fail_count

                if fail_count >= self._MAX_CHECK_RETRIES:
                    wxlog.debug(f"[{who}] 窗口连续 {fail_count} 次不可用，尝试重新打开")
                    # 不直接移除，尝试重新打开子窗口
                    if self._try_recover_window(who, chat, callback):
                        # 恢复成功，重置失败计数
                        self._check_fail_counts.pop(who, None)
                    else:
                        wxlog.debug(f"[{who}] 窗口恢复失败，移除监听")
                        to_remove.append(who)
                else:
                    if fail_count % 20 == 0:  # 每 20 次（约6s）打印一次，避免日志刷屏
                        wxlog.debug(f"[{who}] 窗口暂不可用 ({fail_count}/{self._MAX_CHECK_RETRIES})")
                continue
            else:
                # 窗口恢复，重置失败计数
                if who in self._check_fail_counts:
                    wxlog.debug(f"[{who}] 窗口已恢复")
                    del self._check_fail_counts[who]

            # ── 2. 获取新消息 ──
            try:
                with self._lock:
                    msgs = chat.GetNewMessage()
                if msgs:
                    wxlog.debug(f"[{who}] 获取到 {len(msgs)} 条新消息")
                    for msg in msgs:
                        wxlog.debug(f"  [{msg.attr}] {who} - {msg.content}")
                        self._excutor.submit(self._safe_callback, callback, msg, chat)
            except Exception as e:
                wxlog.debug(f"[{who}] 获取新消息失败: {e}")
                continue

        # 延迟移除失败的监听对象
        for who in to_remove:
            try:
                self.RemoveListenChat(who, close_window=False)
            except Exception:
                pass
            # 清理相关状态
            self._check_fail_counts.pop(who, None)
            self._listen_nicknames.pop(who, None)

    def _try_recover_window(self, who: str, old_chat: 'Chat', callback) -> bool:
        """尝试恢复不可用的监听窗口（重新打开子窗口）"""
        nickname = self._listen_nicknames.get(who, who)
        try:
            wxlog.debug(f"[{nickname}] 尝试恢复监听窗口...")
            subwin = self._api.open_separate_window(nickname)
            if subwin is None:
                return False
            new_chat = Chat(subwin)
            # 重新初始化消息追踪状态
            chatbox_id = new_chat._api._chat_api.id if hasattr(new_chat._api, '_chat_api') and new_chat._api._chat_api else None
            if chatbox_id:
                from weixin4auto.ui.chatbox import USED_MSG_IDS, LAST_MSG_COUNT
                try:
                    msg_controls = new_chat._api._chat_api.msgbox.GetChildren()
                    msg_controls = [c for c in msg_controls if c.ControlTypeName == 'ListItemControl']
                    all_msg_ids = tuple(c.runtimeid for c in msg_controls)
                    USED_MSG_IDS[chatbox_id] = all_msg_ids[-100:] if len(all_msg_ids) > 100 else all_msg_ids
                    LAST_MSG_COUNT[chatbox_id] = len(msg_controls)
                except Exception:
                    USED_MSG_IDS[chatbox_id] = tuple()
                    LAST_MSG_COUNT[chatbox_id] = 0
            # 替换旧的 chat 对象
            self.listen[who] = (new_chat, callback)
            wxlog.debug(f"[{nickname}] 监听窗口恢复成功")
            return True
        except Exception as e:
            wxlog.debug(f"[{nickname}] 窗口恢复异常: {e}")
            return False

    @property
    def path(self):
        return self._api._get_wx_path()
    
    @property
    def dir(self):
        return self._api._get_wx_dir()

    def KeepRunning(self):
        """保持运行"""
        while not self._listener_stop_event.is_set():
            try:
                time.sleep(1)
            except KeyboardInterrupt:
                wxlog.debug(f'weixin4auto("{self.nickname}") shutdown')
                self.StopListening(True)
                break
    
    def GetSession(self) -> List['SessionElement']:
        """获取当前会话列表

        Returns:
            List[SessionElement]: 当前会话列表
        """
        return self._api._session_api.get_session()
    
    @uilock
    def ChatWith(
        self, 
        who: str, 
        exact: bool=True,
        force: bool=False,
        force_wait: Union[float, int] = 0.5
    ):
        """打开聊天窗口
        
        Args:
            who (str): 要聊天的对象
            exact (bool, optional): 搜索who好友时是否精确匹配，默认True
            force (bool, optional): 不论是否匹配到都强制切换，若启用则exact参数无效，默认False
                > 注：force原理为输入搜索关键字后，在等待`force_wait`秒后不判断结果直接回车，谨慎使用
            force_wait (Union[float, int], optional): 强制切换时等待时间，默认0.5秒
            
        """
        return self._api.switch_chat(who, exact, force, force_wait)
    
    def GetCurrentUserNickname(self) -> str:
        """获取当前登录者的昵称
        
        昵称在初始化时已从导航栏头像获取，直接返回即可
        
        Returns:
            str: 当前登录者的昵称
        """
        return self.nickname
    
    def GetSubWindow(self, nickname: str) -> 'Chat':
        """获取子窗口实例
        
        Args:
            nickname (str): 要获取的子窗口的昵称
            
        Returns:
            Chat: 子窗口实例
        """
        if subwin := self._api.get_sub_wnd(nickname):
            return Chat(subwin)
        
    def GetAllSubWindow(self) -> List['Chat']:
        """获取所有子窗口实例
        
        Returns:
            List[Chat]: 所有子窗口实例
        """
        return [Chat(subwin) for subwin in self._api.get_all_sub_wnds()]
    
    @uilock
    def AddListenChat(
            self,
            nickname: str,
            callback: Callable[['Message', Chat], None],
        ) -> WxResponse:
        """添加监听聊天，将聊天窗口独立出去形成Chat对象子窗口，用于监听
        
        Args:
            nickname (str): 要监听的聊天对象
            callback (Callable[['Message', Chat], None]): 回调函数，参数为(Message对象, Chat对象)，返回值为None
        """
        if not hasattr(self, '_listener_is_listening') or not self._listener_is_listening:
            self._listener_start()
        if nickname in self.listen:
            return self.listen[nickname][0]
        
        subwin = self._api.open_separate_window(nickname)
        if subwin is None:
            return WxResponse.failure('找不到聊天窗口')
        name = subwin.nickname
        chat = Chat(subwin)
        chatbox_id = chat._api._chat_api.id if hasattr(chat._api, '_chat_api') and chat._api._chat_api else None
        if chatbox_id:
            from weixin4auto.ui.chatbox import USED_MSG_IDS, LAST_MSG_COUNT
            try:
                msg_controls = chat._api._chat_api.msgbox.GetChildren()
                msg_controls = [c for c in msg_controls if c.ControlTypeName == 'ListItemControl']
                current_msg_count = len(msg_controls)
                all_msg_ids = tuple((i.runtimeid for i in msg_controls))
                USED_MSG_IDS[chatbox_id] = all_msg_ids[-100:] if len(all_msg_ids) > 100 else all_msg_ids
                LAST_MSG_COUNT[chatbox_id] = current_msg_count
            except:
                USED_MSG_IDS[chatbox_id] = tuple()
                LAST_MSG_COUNT[chatbox_id] = 0
        self.listen[name] = (chat, callback)
        self._listen_nicknames[name] = nickname
        return chat
    
    def StopListening(self, remove: bool = True) -> None:
        """停止监听
        
        Args:
            remove (bool, optional): 是否移除监听对象. Defaults to True.
        """
        while self._listener_thread.is_alive():
            self._listener_stop()
        if remove:
            listen = self.listen.copy()
            for who in listen:
                self.RemoveListenChat(who)

    def StartListening(self) -> None:
        if not self._listener_thread.is_alive():
            self._listener_start()

    @uilock
    def RemoveListenChat(
            self, 
            nickname: str,
            close_window: bool = True
        ) -> WxResponse:
        """移除监听聊天

        Args:
            nickname (str): 要移除的监听聊天对象
            close_window (bool, optional): 是否关闭聊天窗口. Defaults to True.

        Returns:
            WxResponse: 执行结果
        """
        if nickname not in self.listen:
            return WxResponse.failure('未找到监听对象')
        chat, _ = self.listen[nickname]
        if close_window:
            chat.Close()
        del self.listen[nickname]
        return WxResponse.success()

    def ListenChats(
            self,
            nickname: Union[str, List[str]],
            callback: Callable[['Message', Chat], None] = None,
            auto_reply: str = None,
            block: bool = False,
        ) -> None:
        """高层监听接口：一键启动对一个或多个聊天的监听
        
        内部自动完成：启动监听线程 → 打开子窗口 → 注册回调 → 可选阻塞等待
        
        Args:
            nickname: 要监听的聊天对象，支持单个昵称(str)或多个昵称(list)
            callback: 收到消息时的回调函数，签名 callback(msg, chat)
                      如果不指定，消息会自动缓存，可通过 GetListenMessages() 获取
            auto_reply: 自动回复模板，{msg} 会被替换为收到的消息内容
                        例如: "收到：{msg}"  如果设置此项且未指定 callback，会自动生成回调
            block: 是否阻塞当前线程（True 时按 Ctrl+C 退出）
        
        Examples:
            # 最简单用法：监听并缓存消息
            wx.ListenChats("文件传输助手")
            msgs = wx.GetListenMessages("文件传输助手")
            
            # 带自动回复
            wx.ListenChats("文件传输助手", auto_reply="收到：{msg}")
            
            # 自定义回调
            wx.ListenChats("文件传输助手", callback=lambda msg, chat: print(msg.content))
            
            # 监听多个对象并阻塞
            wx.ListenChats(["A", "B"], auto_reply="已读", block=True)
        """
        # 统一为列表
        if isinstance(nickname, str):
            nicknames = [nickname]
        else:
            nicknames = list(nickname)
        
        # 构建回调：用户 callback 始终优先，auto_reply 作为补充
        original_callback = callback
        if callback is None and auto_reply is not None:
            # 无用户回调，有自动回复：缓存 + 自动回复
            def _auto_reply_callback(msg, chat):
                self._collect_message(chat.who, msg)
                reply_text = auto_reply.replace('{msg}', str(msg.content))
                try:
                    chat.SendMsg(reply_text)
                except Exception as e:
                    wxlog.debug(f"自动回复失败: {e}")
            callback = _auto_reply_callback
        elif callback is None:
            # 纯缓存模式
            def _collect_callback(msg, chat):
                self._collect_message(chat.who, msg)
            callback = _collect_callback
        elif auto_reply is not None:
            # 用户回调 + 自动回复
            def _combined_callback(msg, chat):
                self._collect_message(chat.who, msg)
                original_callback(msg, chat)
                reply_text = auto_reply.replace('{msg}', str(msg.content))
                try:
                    chat.SendMsg(reply_text)
                except Exception as e:
                    wxlog.debug(f"自动回复失败: {e}")
            callback = _combined_callback
        else:
            # 纯用户回调
            def _wrapped_callback(msg, chat):
                self._collect_message(chat.who, msg)
                original_callback(msg, chat)
            callback = _wrapped_callback
        
        # 逐个添加监听
        for nick in nicknames:
            result = self.AddListenChat(nick, callback)
            if isinstance(result, WxResponse) and not result.is_success:
                wxlog.debug(f"添加监听失败: {nick} - {result.get('message', '')}")
        
        # 阻塞等待
        if block:
            try:
                self.KeepRunning()
            except KeyboardInterrupt:
                self.StopListening(True)

    def GetListenMessages(
            self,
            nickname: str = None,
            clear: bool = True,
        ) -> List['Message']:
        """获取监听收集到的消息
        
        Args:
            nickname: 指定聊天对象的昵称，不指定则返回所有监听对象的消息
            clear: 获取后是否清空缓存，默认 True
        
        Returns:
            List[Message]: 收集到的消息列表
        """
        with self._collected_lock:
            if nickname is None:
                # 返回所有消息
                all_msgs = []
                for msgs in self._collected_messages.values():
                    all_msgs.extend(msgs)
                if clear:
                    self._collected_messages.clear()
                return all_msgs
            else:
                # 返回指定对象的消息（支持模糊匹配）
                msgs = []
                matched_keys = []
                for key, val in self._collected_messages.items():
                    if key == nickname or nickname in key or key in nickname:
                        msgs.extend(val)
                        matched_keys.append(key)
                if clear:
                    for key in matched_keys:
                        del self._collected_messages[key]
                return msgs

    def _collect_message(self, who: str, msg: 'Message') -> None:
        """内部方法：将消息缓存到收集器"""
        with self._collected_lock:
            if who not in self._collected_messages:
                self._collected_messages[who] = []
            self._collected_messages[who].append(msg)

    def SwitchToChat(self) -> None:
        """切换到聊天页面"""
        self._api._navigation_api.switch_to_chat_page()

    def SwitchToContact(self) -> None:
        """切换到联系人页面"""
        self._api._navigation_api.switch_to_contact_page()

    def SwitchToFavorites(self) -> None:
        """切换到收藏页面"""
        self._api._navigation_api.switch_to_favorites_page()

    def SwitchToFiles(self) -> None:
        """切换到聊天文件页面"""
        self._api._navigation_api.switch_to_files_page()

    def SwitchToMoments(self) -> None:
        """切换到朋友圈页面"""
        self._api._navigation_api.switch_to_moments_page()

    def SwitchToBrowser(self) -> None:
        """切换到搜一搜页面"""
        self._api._navigation_api.switch_to_browser_page()

    def SwitchToVideo(self) -> None:
        """切换到视频号页面"""
        self._api._navigation_api.switch_to_video_page()

    def SwitchToStories(self) -> None:
        """切换到看一看页面"""
        self._api._navigation_api.switch_to_stories_page()

    def SwitchToMiniProgram(self) -> None:
        """切换到小程序面板页面"""
        self._api._navigation_api.switch_to_mini_program_page()

    def SwitchToPhone(self) -> None:
        """切换到手机页面"""
        self._api._navigation_api.switch_to_phone_page()

    def SwitchToSettings(self) -> None:
        """切换到更多设置页面"""
        self._api._navigation_api.switch_to_settings_page()

    def ShutDown(self):
        delete_update_files()
        os.system(f'taskkill /f /pid {self._api.pid}')

