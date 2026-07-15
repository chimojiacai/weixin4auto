from wxauto4 import uia
from wxauto4.param import (
    WxParam, 
    WxResponse,
)
from wxauto4.utils.win32 import (
    SetClipboardFiles,
    SetClipboardData,
    SetClipboardText
)
from wxauto4.ui.component import (
    Menu
)
from .base import (
    BaseUISubWnd
)
from wxauto4.msgs.msg import parse_msg
from wxauto4.ui_config import WxUI41Config

import time
import os
import re
from typing import Iterable, Optional, Sequence, Tuple, Union

def truncate_string(s: str, n: int=8) -> str:
    s = s.replace('\n', '').strip()
    return s if len(s) <= n else s[:n] + '...'

USED_MSG_IDS = {}
LAST_MSG_COUNT = {}

class ChatBox(BaseUISubWnd):
    def __init__(self, control: uia.Control, parent):
        self.control: uia.Control = control
        self.root = parent
        self.parent = parent  # `wx` or `chat`
        self.init()

    def _lang(self, text: str):
        return text
    
    @property
    def id(self):
        if self.msgbox.Exists(0):
            return self.msgbox.runtimeid
        return None
    
    @property
    def used_msg_ids(self):
        if self.id in USED_MSG_IDS:
            return USED_MSG_IDS[self.id]
        else:
            USED_MSG_IDS[self.id] = tuple()
            return USED_MSG_IDS[self.id]
    
    @property
    def who(self):
        if hasattr(self, '_who'):
            return self._who
        self._who = self.editbox.Name
        return self._who
    
    def get_info(self):
        chat_info = {}
        chat_info_control = self.control.GetParentControl().GroupControl(ClassName=WxUI41Config.CHAT_INFO_VIEW_CLS)
        aid_head = 'top_content_h_view.top_spacing_v_view.top_left_info_v_view.big_title_line_h_view.'
        v_view = "top_content_h_view.top_spacing_v_view.top_left_info_v_view"
        aids = {
            'chatname': "current_chat_name_label",
            'chat_count': "current_chat_count_label",
            'company': "current_chat_openim_name",
            'comicon': "openim_icon"
        }
        chat_info['chat_type'] = 'friend'
        for aid in aids:
            control = chat_info_control.TextControl(
                AutomationId=aid_head+aids[aid]
            )
            if control.Exists(0):
                if aid == 'chatname':
                    chat_info['chat_name'] = control.Name
                    if (
                        'chat_remark' not in chat_info
                        and (cnc := chat_info_control.GroupControl(AutomationId=v_view).GroupControl().TextControl()).Exists(0)
                    ):
                        chat_info['chat_remark'] = chat_info['chat_name']
                        chat_info['chat_name'] = cnc.Name

                elif aid == 'chat_count':
                    chat_info['group_member_count'] = int(re.findall(r'\d+', control.Name)[0])
                    chat_info['chat_type'] = 'group'
                elif aid == 'company':
                    chat_info['chat_type'] = 'service'
            if chat_info_control.ButtonControl(Name="公众号主页").Exists(0):
                    chat_info['chat_type'] = 'official'
        return chat_info
        
    
    def _activate_editbox(self):
        if not self.editbox.HasKeyboardFocus:
            self.editbox.MiddleClick()

    def _find_child_by_class(self, ctrl, target_cls, max_depth=5):
        """递归查找子控件"""
        if ctrl is None or max_depth < 0:
            return None
        try:
            if ctrl.ClassName == target_cls:
                return ctrl
            for child in ctrl.GetChildren():
                result = self._find_child_by_class(child, target_cls, max_depth - 1)
                if result:
                    return result
        except:
            pass
        return None

    def init(self):
        if self.control is None:
            # 控件未找到时，设置空占位控件
            self.msgbox = uia.ListControl()
            self.editbox = uia.EditControl()
            self.sendbtn = uia.ButtonControl()
            self.tools = uia.ToolBarControl()
            self._empty = True
            return
        
        # 尝试直接路径查找（旧版微信）
        msg_view = self.control.GroupControl(ClassName=WxUI41Config.CHAT_MESSAGE_VIEW_CLS)
        if msg_view.Exists(0):
            self.msgbox = msg_view.ListControl()
        else:
            # 递归查找 MessageView
            found = self._find_child_by_class(self.control, WxUI41Config.CHAT_MESSAGE_VIEW_CLS)
            if found:
                self.msgbox = found.ListControl()
            else:
                self.msgbox = uia.ListControl()
        
        # 查找输入框
        editbox = self.control.EditControl(ClassName=WxUI41Config.CHAT_INPUT_FIELD_CLS)
        if editbox.Exists(0):
            self.editbox = editbox
        else:
            found = self._find_child_by_class(self.control, WxUI41Config.CHAT_INPUT_FIELD_CLS)
            if found:
                self.editbox = found
            else:
                # 回退：查找任意 EditControl
                self.editbox = self.control.EditControl()
        
        # 查找发送按钮（新版微信可能不存在，send_text 中用 Enter 键替代）
        sendbtn = self.control.ButtonControl(Name=self._lang('发送(S)'))
        if not sendbtn.Exists(0):
            sendbtn = self.control.ButtonControl(Name='发送')
        self.sendbtn = sendbtn if sendbtn.Exists(0) else uia.ButtonControl()
        
        self.tools = self.control.ToolBarControl()
        self._empty = False
        if (cid := self.id) and cid not in USED_MSG_IDS:
            try:
                msg_controls = self.msgbox.GetChildren()
                msg_count = len([c for c in msg_controls if c.ControlTypeName == 'ListItemControl'])
                LAST_MSG_COUNT[cid] = msg_count
            except:
                pass
            try:
                if not self.msgbox.GetChildren():
                    self._empty = True
            except:
                self._empty = True

    def _send(self):
        """发送消息：优先点击发送按钮，找不到则用 Enter 键"""
        if self.sendbtn.Exists(0):
            self.sendbtn.Click()
        else:
            self.editbox.SendKeys('{Enter}')

    def clear_edit(self):
        self._show()
        self.editbox.Click()
        self.editbox.SendKeys('{Ctrl}a', waitTime=0)
        self.editbox.SendKeys('{DELETE}')


    def send_text(self, content: str):
        self._show()
        t0 = time.time()
        while True:
            if time.time() - t0 > 10:
                return WxResponse.failure(f'Timeout --> {self.who} - {content}')
            SetClipboardText(content)
            self._activate_editbox()
            self.editbox.SendKeys('{Ctrl}v')
            if self.editbox.GetValuePattern().Value.replace('￼', '').strip():
                break
            self.editbox.SendKeys('{Ctrl}v')
            if self.editbox.GetValuePattern().Value.replace('￼', '').strip():
                break
            self.editbox.RightClick()
            menu = Menu(self)
            menu.select('粘贴')
            if self.editbox.GetValuePattern().Value.replace('￼', '').strip():
                break
        t0 = time.time()
        while self.editbox.GetValuePattern().Value:
            if time.time() - t0 > 10:
                return WxResponse.failure(f'Timeout --> {self.who} - {content}')
            self._activate_editbox()
            self._send()
            
            if not self.editbox.GetValuePattern().Value:
                return WxResponse.success(f"success")
            elif not self.editbox.GetValuePattern().Value.replace('￼', '').strip():
                return self.send_text(content)

    def send_msg(self, content: str, clear: bool=True, at=None):
        if not content and not at:
            return WxResponse.failure(f"`content` and `at` can't be empty at the same time")
        
        if clear:
            self.clear_edit()
        if at:
            self.input_at(at)

        return self.send_text(content)
    
    def send_file(self, file_path):
        """发送文件/图片
        
        Args:
            file_path: 文件路径（str）或文件路径列表（list）
            
        Returns:
            WxResponse: 发送结果
        """
        if isinstance(file_path, str):
            file_path = [file_path]
        file_path = [os.path.abspath(f) for f in file_path]
        
        # 校验文件是否存在
        for f in file_path:
            if not os.path.isfile(f):
                return WxResponse.failure(f'文件不存在：{f}')
        
        self.clear_edit()

        SetClipboardFiles(file_path)
        self.editbox.SendKeys('{Ctrl}v')
        time.sleep(0.5)
        self._send()
        return WxResponse.success('success')

    def input_at(self, at_list):
        if isinstance(at_list, str):
            at_list = [at_list]
        self._activate_editbox()
        for friend in at_list:
            self.editbox.SendKeys('@'+friend.replace(' ', ''))
            atmenu = AtMenu(self)
            atmenu.select(friend)
        
    def get_msgs(self):
        if self.msgbox.Exists(0):
            return [
                parse_msg(msg_control, self)
                for msg_control in self._iter_message_controls()
                if uia.IsElementInWindow(self.msgbox, msg_control)
            ]
        return []

    def get_new_msgs(self):
        """获取新消息（优化版：基于窗口状态/布局变化检测）
        
        核心思路：
        1. 启动监听时，记录当前窗口状态（所有消息ID）
        2. 后续检查时，比较当前状态和已记录状态
        3. 只有当状态变化时（有新消息），才返回新消息
        
        注意：此方法在监听模式下会被频繁调用，应避免触发窗口激活操作
        """
        # 优化：使用Exists(0)快速检查，不等待，避免触发窗口激活
        # Exists(0) 不会触发窗口激活，只是检查控件是否存在
        try:
            if not self.msgbox.Exists(0):
                return []
        except:
            # 如果检查失败，直接返回空列表，避免后续操作触发窗口激活
            return []
        
        # 快速检查：先获取消息控件（只获取 ListItemControl 类型的控件）
        try:
            all_controls = self.msgbox.GetChildren()
            # 只获取 ListItemControl 类型的控件（真正的消息控件）
            msg_controls = [c for c in all_controls if c.ControlTypeName == 'ListItemControl']
            current_msg_count = len(msg_controls)
        except:
            return []
        
        if current_msg_count == 0:
            return []
        
        # 获取已记录的消息ID列表（窗口状态）
        current_used_ids = self.used_msg_ids or tuple()
        
        # 获取上次记录的消息数量
        last_msg_count = LAST_MSG_COUNT.get(self.id, 0)
        
        if self._empty and current_used_ids:
            self._empty = False
        
        # 启动监听时的初始化：如果状态还没记录，记录当前窗口状态（所有消息ID），但不返回历史消息
        if not current_used_ids:
            if not self._empty:
                try:
                    all_msg_ids = tuple((i.runtimeid for i in msg_controls))
                    USED_MSG_IDS[self.id] = all_msg_ids[-100:] if len(all_msg_ids) > 100 else all_msg_ids
                    LAST_MSG_COUNT[self.id] = current_msg_count
                except:
                    pass
            return []
        
        # 比较当前窗口状态和已记录的状态，如果状态变化则返回新消息
        msg_count_increased = current_msg_count > last_msg_count
        
        if msg_count_increased:
            new_msg_count = current_msg_count - last_msg_count
            check_count = min(new_msg_count + 10, current_msg_count)
            try:
                recent_controls = msg_controls[-check_count:] if check_count < len(msg_controls) else msg_controls
                recent_msg_ids = tuple((i.runtimeid for i in recent_controls))
            except:
                return []
            
            candidate_new_ids = recent_msg_ids[-new_msg_count:] if len(recent_msg_ids) >= new_msg_count else recent_msg_ids
            used_msg_ids_set = set(current_used_ids)
            confirmed_new_ids = [msg_id for msg_id in candidate_new_ids if msg_id not in used_msg_ids_set]
            
            if confirmed_new_ids:
                try:
                    all_msg_ids = tuple((i.runtimeid for i in msg_controls))
                    USED_MSG_IDS[self.id] = all_msg_ids[-100:] if len(all_msg_ids) > 100 else all_msg_ids
                    LAST_MSG_COUNT[self.id] = current_msg_count
                except:
                    pass
                
                new_controls = [i for i in recent_controls if i.runtimeid in confirmed_new_ids]
                return [parse_msg(msg_control, self) for msg_control in new_controls]
        
        # 如果消息数量没变，检查最后20条消息是否有ID变化
        check_count = min(20, current_msg_count)
        try:
            recent_controls = msg_controls[-check_count:] if check_count < len(msg_controls) else msg_controls
            recent_msg_ids = tuple((i.runtimeid for i in recent_controls))
        except:
            return []
        
        used_msg_ids_set = set(current_used_ids)
        new_ids = [msg_id for msg_id in recent_msg_ids if msg_id not in used_msg_ids_set]
        
        if new_ids:
            try:
                all_msg_ids = tuple((i.runtimeid for i in msg_controls))
                USED_MSG_IDS[self.id] = all_msg_ids[-100:] if len(all_msg_ids) > 100 else all_msg_ids
                LAST_MSG_COUNT[self.id] = current_msg_count
            except:
                pass
            
            new_controls = [i for i in recent_controls if i.runtimeid in new_ids]
            return [parse_msg(msg_control, self) for msg_control in new_controls]

        return []

    def _update_used_msg_ids(self):
        if not self.msgbox.Exists(0):
            USED_MSG_IDS[self.id] = tuple()
            LAST_MSG_COUNT[self.id] = 0
            return
        msg_controls = [
            ctrl for ctrl in self.msgbox.GetChildren()
            if ctrl.ControlTypeName == 'ListItemControl'
        ]
        if not msg_controls:
            USED_MSG_IDS[self.id] = tuple()
            LAST_MSG_COUNT[self.id] = 0
            return
        USED_MSG_IDS[self.id] = tuple(ctrl.runtimeid for ctrl in msg_controls[-100:])
        LAST_MSG_COUNT[self.id] = len(msg_controls)

    def _iter_message_controls(self) -> Iterable[uia.Control]:
        if not self.msgbox.Exists(0):
            return []
        return [
            ctrl
            for ctrl in self.msgbox.GetChildren()
            if ctrl.ControlTypeName == 'ListItemControl'
        ]

    def _normalize_msg_id(self, msg_id: Union[Sequence[int], str, None]) -> Optional[Tuple[int, ...]]:
        if msg_id is None:
            return None
        if isinstance(msg_id, str):
            parts = re.findall(r"\d+", msg_id)
            if not parts:
                return None
            return tuple(int(p) for p in parts)
        if isinstance(msg_id, tuple):
            try:
                return tuple(int(p) for p in msg_id)
            except (TypeError, ValueError):
                return None
        if isinstance(msg_id, list):
            try:
                return tuple(int(p) for p in msg_id)
            except (TypeError, ValueError):
                return None
        return None

    def get_msg_by_id(self, msg_id: Union[Sequence[int], str]) -> Optional['Message']:
        normalized_id = self._normalize_msg_id(msg_id)
        if normalized_id is None:
            return None
        for msg_control in self._iter_message_controls():
            if msg_control.runtimeid == normalized_id:
                return parse_msg(msg_control, self)
        return None

    def get_msg_by_hash(self, msg_hash: str) -> Optional['Message']:
        if not msg_hash:
            return None
        msg_hash = msg_hash.strip()
        is_digest = bool(re.fullmatch(r"[0-9a-fA-F]{32}", msg_hash))
        controls = list(self._iter_message_controls())
        for msg_control in reversed(controls):
            msg = parse_msg(msg_control, self)
            candidate = msg.hash if is_digest else getattr(msg, 'hash_text', None)
            if candidate == msg_hash:
                return msg
        return None

    def get_last_msg(self) -> Optional['Message']:
        message_controls = list(self._iter_message_controls())
        if not message_controls:
            return None
        return parse_msg(message_controls[-1], self)


class AtEle:
    def __init__(self, control):
        self.name = control.Name
        self.control = control

class AtMenu(BaseUISubWnd):
    _ui_cls_name: str = WxUI41Config.AT_MENU_CLS
    _ui_name: str = "Weixin"
    _ui_automation_id = WxUI41Config.AT_MENU_AUTOMATION_ID

    def __init__(self, parent):
        self.root = parent.root
        self.control = self.root.control.WindowControl(
            ClassName=self._ui_cls_name,
            Name=self._ui_name,
            AutomationId=self._ui_automation_id
        )

    def clear(self, friend):
        if self.exists():
            self.control.SendKeys('{ESC}')
        for _ in range(len(friend)+1):
            self.root._chat_api.editbox.SendKeys('{BACK}')

    def select(self, friend): 
        friend_ = friend.replace(' ', '')
        if self.exists():
            ateles = self.control.ListControl().GetChildren()
            if len(ateles) == 1:
                ateles[0].Click()
                return WxResponse.success()
            
            else:
                atele = self.control.ListItemControl(Name=friend)
                if atele.Exists(0):
                    uia.RollIntoView(self.control, atele)
                    atele.Click()
                    return WxResponse.success()
                else:
                    self.clear(friend_)
                    return WxResponse.failure('@对象不存在')
        else:
            self.clear(friend_)
            return WxResponse.failure('@选择窗口不存在')
        
    def list(self):
        return [AtEle(i) for i in self.control.ListControl().GetChildren()]