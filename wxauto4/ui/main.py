from .base import BaseUISubWnd, BaseUIWnd
from .navigationbox import NavigationBox
from .sessionbox import SessionBox
from .chatbox import ChatBox
from wxauto4.utils.win32 import (
    FindWindow,
    GetAllWindows,
    GetPathByHwnd,
    get_windows_by_pid
)
from wxauto4.param import WxParam, WxResponse, PROJECT_NAME
from wxauto4.logger import wxlog
from wxauto4 import uia
from wxauto4.ui_config import WxUI41Config
from typing import (
    Union, 
    List,
    Literal
)
import random
import os
import re
import sys
import time

class WeChatSubWnd(BaseUISubWnd):
    _ui_cls_name: str = WxUI41Config.SUB_WINDOW_UI_CLS
    _win_cls_name: str = WxUI41Config.WIN_CLS_NAME
    _chat_api: ChatBox = None
    nickname: str = ''

    def __init__(
            self, 
            key: Union[str, int], 
            parent: 'WeChatMainWnd', 
            timeout: int = 1  # 减少默认超时时间：从3秒减少到1秒
        ):
        self.root = self
        self.parent = parent
        if isinstance(key, str):
            hwnd = FindWindow(classname=self._win_cls_name, name=key, timeout=timeout)
        else:
            hwnd = key
        self.control = uia.ControlFromHandle(hwnd)
        if self.control is not None:
            chatbox_control = self.control.\
                GroupControl(ClassName=WxUI41Config.CHAT_PAGE_CLS).\
                CustomControl(ClassName=WxUI41Config.CHAT_SPLITTER_CLS)
            self._chat_api = ChatBox(chatbox_control, self)
            self.nickname = self.control.Name

    def __repr__(self):
        return f'<{PROJECT_NAME} - {self.__class__.__name__} object("{self.nickname}")>'

    @property
    def pid(self):
        if not hasattr(self, '_pid'):
            self._pid = self.control.ProcessId
        return self._pid
    
    def _get_chatbox(
            self, 
            nickname: str=None, 
            exact: bool=False
        ) -> ChatBox:
        return self._chat_api
    
    def _get_windows(self):
        wins = []
        for hwnd in get_windows_by_pid(self.pid):
            try:
                wins.append(uia.ControlFromHandle(hwnd))
            except:
                pass
        ignore_cls = ['basepopupshadow', 'popupshadow']
        return [win for win in wins if win.ClassName not in ignore_cls]
    
    def chat_info(self):
        """获取聊天窗口信息（已禁用，避免触发点击操作）
        
        注意：此方法已被禁用，因为会触发点击好友头像的操作。
        请使用 self.nickname 获取聊天对象名称。
        """
        # 不再调用 get_info()，避免触发点击操作
        # 只返回窗口标题信息
        return {
            'chat_name': self.nickname,
            'chat_type': 'unknown',
            'is_group': False,
            'group_member_count': 0
        }
    
    def send_msg(
            self, 
            msg: str,
            who: str=None,
            clear: bool=True, 
            at: Union[str, List[str]]=None,
            exact: bool=False,
        ) -> WxResponse:
        chatbox = self._get_chatbox(who, exact)
        if chatbox is None:
            return WxResponse.failure(f"未找到聊天窗口：{who}")
        return chatbox.send_msg(msg, clear, at)
    
    def send_files(
            self, 
            filepath, 
            who=None, 
            exact=False
        ) -> WxResponse:
        chatbox = self._get_chatbox(who, exact)
        if chatbox is None:
            return WxResponse.failure(f"未找到聊天窗口：{who}")
        return chatbox.send_file(filepath)
    
    def get_msgs(self):
        chatbox = self._get_chatbox()
        if chatbox:
            return chatbox.get_msgs()
        return []

    def get_new_msgs(self):
        return self._get_chatbox().get_new_msgs()

    def get_msg_by_id(self, msg_id):
        chatbox = self._get_chatbox()
        if chatbox:
            return chatbox.get_msg_by_id(msg_id)

    def get_msg_by_hash(self, msg_hash: str):
        chatbox = self._get_chatbox()
        if chatbox:
            return chatbox.get_msg_by_hash(msg_hash)

    def get_last_msg(self):
        chatbox = self._get_chatbox()
        if chatbox:
            return chatbox.get_last_msg()

    

class WeChatMainWnd(WeChatSubWnd):
    _ui_cls_name: str = WxUI41Config.MAIN_WINDOW_UI_CLS
    _win_cls_name: str = WxUI41Config.WIN_CLS_NAME
    _ui_name: str = '微信'

    def __init__(self, nickname: str = None, hwnd: int = None):
        self.root = self
        self.parent = self
        if hwnd:
            self._setup_ui(hwnd)
        else:
            wxs = [i for i in GetAllWindows() if i[1] == self._win_cls_name]
            if len(wxs) == 0:
                # 尝试查找所有可能的窗口类名
                possible_classes = [
                    self._win_cls_name,  # 当前配置的类名
                    'Qt51514QWindowIcon',  # Qt 5.15.14
                    'Qt6QWindowIcon',  # Qt 6
                ]
                all_wxs = []
                for cls in possible_classes:
                    found = [i for i in GetAllWindows() if i[1] == cls]
                    if found:
                        all_wxs.extend(found)
                
                if len(all_wxs) == 0:
                    error_msg = (
                        f'未找到已登录的微信主窗口！\n'
                        f'尝试的窗口类名: {", ".join(possible_classes)}\n'
                        f'请运行 find_wechat_window.py 查找实际的窗口类名，'
                        f'然后修改 wxauto4/ui_config.py 中的 WIN_CLS_NAME'
                    )
                    raise Exception(error_msg)
                
                # 使用找到的窗口
                wxs = all_wxs
            
            for index, (hwnd, clsname, winname) in enumerate(wxs):
                self._setup_ui(hwnd)
                if self.control.ClassName == self._ui_cls_name:
                    break
                elif index+1 == len(wxs):
                    raise Exception(f'未找到微信窗口：{nickname}')
        # if NetErrInfoTipsBarWnd(self):
        #     raise NetWorkError('微信无法连接到网络')
        
        print(f'初始化成功，获取到已登录窗口：{self.nickname}')

    def _setup_ui(self, hwnd: int):
        self.HWND = hwnd
        self.control = uia.ControlFromHandle(hwnd)
        if self.control is not None:
            navigation_control = self.control.\
                ToolBarControl(ClassName=WxUI41Config.NAVIGATION_BAR_CLS, AutomationId=WxUI41Config.NAVIGATION_BAR_AUTOMATION_ID)
            sessionbox_control = self.control.\
                GroupControl(ClassName=WxUI41Config.SESSION_BOX_CLS)
            chatbox_control = self.control.\
                GroupControl(ClassName=WxUI41Config.CHAT_PAGE_CLS).\
                CustomControl(ClassName=WxUI41Config.CHAT_SPLITTER_CLS)
            self._navigation_api = NavigationBox(navigation_control, self)
            self._session_api = SessionBox(sessionbox_control, self)
            self._chat_api = ChatBox(chatbox_control, self)
            
            # 尝试从导航栏头像获取昵称
            user_nickname = self._navigation_api.get_user_nickname()
            if user_nickname:
                self.nickname = user_nickname
            else:
                # 如果获取失败，使用窗口标题
                self.nickname = self.control.Name

    def __repr__(self):
        return f'<{PROJECT_NAME} - {self.__class__.__name__} object("{self.nickname}")>'

    def _get_wx_path(self):
        return GetPathByHwnd(self.HWND)
    
    def _get_wx_dir(self):
        wxdir = os.path.dirname(self._get_wx_path())
        for d in os.listdir(wxdir):
            if re.match(r'\d+\.\d+\.\d+\.\d+', d):
                return os.path.join(wxdir, d)

    def _get_chatbox(
            self, 
            nickname: str=None, 
            exact: bool=False
        ) -> ChatBox:
        if nickname and (chatbox := WeChatSubWnd(nickname, self, timeout=0)).control:
            return chatbox._chat_api
        else:
            if nickname:
                def extract_name(full_name: str) -> str:
                    """提取名称的第一部分（第一个空格之前）"""
                    if not full_name:
                        return ""
                    first_space_idx = full_name.find(' ')
                    if first_space_idx > 0:
                        return full_name[:first_space_idx].strip()
                    return full_name.strip()
                
                # 优化1：先检查当前窗口是否已经是目标窗口（避免二次点击导致焦点失去）
                try:
                    if self._chat_api.msgbox.Exists(0):
                        current_who = self._chat_api.who
                        current_extracted = extract_name(current_who)
                        clean_keywords = nickname.split('?')[0].split('，')[0].split(',')[0].strip()
                        
                        # 检查是否匹配
                        is_current_window = False
                        if exact:
                            # 精确匹配
                            if (current_extracted == clean_keywords or 
                                current_extracted == nickname or
                                current_who == clean_keywords or 
                                current_who == nickname):
                                is_current_window = True
                        else:
                            # 模糊匹配
                            if (clean_keywords in current_extracted or 
                                nickname in current_extracted or
                                clean_keywords in current_who or 
                                nickname in current_who):
                                is_current_window = True
                        
                        if is_current_window:
                            wxlog.debug(f'当前窗口已是目标窗口，直接发送: current="{current_extracted}" | target="{nickname}"')
                            return self._chat_api
                except Exception as e:
                    wxlog.debug(f'检查当前窗口失败: {e}')
                    # 如果检查失败，继续后续流程
                
                # 优化2：先尝试在当前可见的会话列表中查找（不滚动）
                session = self._session_api.find_session_in_current_view(keywords=nickname, exact=exact)
                session_found = False
                if session:
                    # 找到会话，直接点击切换
                    try:
                        session.click()
                        time.sleep(0.2)  # 等待切换完成
                        if self._chat_api.msgbox.Exists(0.5):
                            session_found = True
                            return self._chat_api
                    except Exception as e:
                        wxlog.debug(f'点击会话失败: {e}')
                        # 如果点击失败，继续使用搜索方式
                
                # 如果当前可见列表中没有找到或点击失败，再使用搜索功能
                if not session_found:
                    switch_result = self._session_api.switch_chat(keywords=nickname, exact=exact)
                    if not switch_result:
                        return None
            if self._chat_api.msgbox.Exists(0.5):
                return self._chat_api

    def switch_chat(
            self, 
            keywords: str, 
            exact: bool = True,
            force: bool = False,
            force_wait: Union[float, int] = 0.5
        ):
        return self._session_api.switch_chat(keywords, exact, force, force_wait)
        
    def get_all_sub_wnds(self):
        """获取所有子窗口，增强错误处理"""
        sub_wxs = GetAllWindows(classname=WeChatSubWnd._win_cls_name)
        result = []
        for i in sub_wxs:
            try:
                control = uia.ControlFromHandle(i[0])
                if control.ClassName == WeChatSubWnd._ui_cls_name:
                    sub_win = WeChatSubWnd(i[0], self)
                    if sub_win.pid == self.pid:
                        result.append(sub_win)
            except:
                continue
        return result
    
    def get_sub_wnd(self, who: str):
        """获取子窗口，支持精确匹配和模糊匹配"""
        subwins = self.get_all_sub_wnds()
        if not subwins:
            return None
        
        for subwin in subwins:
            if subwin.nickname == who:
                return subwin
        
        for subwin in subwins:
            if who in subwin.nickname or subwin.nickname.startswith(who):
                return subwin
        
        for subwin in subwins:
            if subwin.nickname in who:
                return subwin
        
        return None
            
    def open_separate_window(self, keywords: str) -> WeChatSubWnd:
        """打开独立窗口，如果已存在则直接返回，避免重复搜索和拖出"""
        subwin = self.get_sub_wnd(keywords)
        if subwin:
            return subwin
        
        if result := self._session_api.open_separate_window(keywords):
            find_nickname = result['data'].get('nickname', keywords)
            return WeChatSubWnd(find_nickname, self)
        
        return None