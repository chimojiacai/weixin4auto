from weixin4auto import uia
from weixin4auto.param import (
    WxParam, 
    WxResponse,
)
from weixin4auto.utils.win32 import (
    SetClipboardFiles,
    SetClipboardData,
    SetClipboardText
)
from weixin4auto.ui.component import (
    Menu
)
from .base import (
    BaseUISubWnd
)
from weixin4auto.msgs.msg import parse_msg
from weixin4auto.ui_config import WxUI41Config

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
        # 始终从 editbox 读取最新名称，避免切换聊天后返回旧值
        try:
            self._who = self.editbox.Name
        except Exception:
            pass
        return getattr(self, '_who', '')
    
    def detect_group_info(self) -> dict:
        """通过检查聊天名称标签的兄弟控件获取群成员数量
        
        原理：群聊时，current_chat_name_label 的下一个兄弟控件文本为 "(N)" 格式，
        其中 N 为群成员数量。
        
        Returns:
            dict: 包含 is_group, group_member_count 的字典
        """
        result = {
            'is_group': False,
            'group_member_count': 0
        }
        
        try:
            chat_name_label = self.control.TextControl(
                AutomationId='content_view.top_content_view.title_h_view.left_v_view.'
                             'left_content_v_view.left_ui_.big_title_line_h_view.current_chat_name_label'
            )
            if chat_name_label.Exists(0.5):
                next_sibling = chat_name_label.GetNextSiblingControl()
                if next_sibling:
                    sibling_name = (next_sibling.Name or '').strip()
                    match = re.match(r'^\((\d+)\)$', sibling_name)
                    if match:
                        result['is_group'] = True
                        result['group_member_count'] = int(match.group(1))
        except Exception as e:
            from weixin4auto.logger import wxlog
            wxlog.debug(f"获取群成员数量失败: {e}")
        
        return result

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
            self._last_msgbox_id = cid
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

    def _re_find_msgbox(self):
        """重新查找 msgbox 控件，避免缓存引用过时"""
        try:
            msg_view = self.control.GroupControl(ClassName=WxUI41Config.CHAT_MESSAGE_VIEW_CLS)
            if msg_view.Exists(0):
                self.msgbox = msg_view.ListControl()
                return True
            found = self._find_child_by_class(self.control, WxUI41Config.CHAT_MESSAGE_VIEW_CLS)
            if found:
                self.msgbox = found.ListControl()
                return True
        except Exception:
            pass
        return False

    def get_new_msgs(self):
        """获取新消息（基于 runtimeid 变更检测 + UIA 树稳定等待）
        
        核心思路：
        1. 检测 msgbox 的 runtimeid 是否变化（UIA 树重建）
        2. 如果变化，自动重置消息追踪状态
        3. 检测到新消息后，等待 UIA 树稳定（连续两次读取一致）
        4. 稳定后再更新状态并返回，避免因 UIA 增量更新导致漏消息
        """
        # 快速检查 msgbox 是否存在
        try:
            if not self.msgbox.Exists(0):
                return []
        except Exception:
            return []
        
        # 获取当前 msgbox 的 runtimeid
        try:
            current_msgbox_id = self.msgbox.runtimeid
        except Exception:
            return []
        
        if current_msgbox_id is None:
            return []
        
        # 检测 runtimeid 是否变化（UIA 树重建/窗口恢复）
        last_known_id = getattr(self, '_last_msgbox_id', None)
        if last_known_id is not None and last_known_id != current_msgbox_id:
            from weixin4auto.logger import wxlog
            wxlog.debug(f"[msgbox] runtimeid 变更: {last_known_id} -> {current_msgbox_id}，重置消息追踪")
            # 清理旧 ID 的数据
            if last_known_id in USED_MSG_IDS:
                del USED_MSG_IDS[last_known_id]
            if last_known_id in LAST_MSG_COUNT:
                del LAST_MSG_COUNT[last_known_id]
            # 重新查找 msgbox 控件，避免缓存引用过时
            self._re_find_msgbox()
            # 重置当前状态
            self._last_msgbox_id = current_msgbox_id
            USED_MSG_IDS[current_msgbox_id] = tuple()
            LAST_MSG_COUNT[current_msgbox_id] = 0
        else:
            self._last_msgbox_id = current_msgbox_id
        
        # 获取所有消息控件
        try:
            all_controls = self.msgbox.GetChildren()
            msg_controls = [c for c in all_controls if c.ControlTypeName == 'ListItemControl']
            current_msg_count = len(msg_controls)
        except Exception:
            return []
        
        if current_msg_count == 0:
            return []
        
        # 获取已记录的消息 ID 列表
        current_used_ids = USED_MSG_IDS.get(current_msgbox_id, tuple())
        
        if self._empty and current_used_ids:
            self._empty = False
        
        # 首次初始化：记录当前状态，不返回历史消息
        if not current_used_ids:
            if not self._empty:
                self._commit_state(current_msgbox_id, msg_controls, current_msg_count)
            return []
        
        used_id_set = set(current_used_ids)
        
        # 快速路径：检查尾部控件，无新消息则直接返回
        check_count = min(30, current_msg_count)
        tail_controls = msg_controls[-check_count:]
        new_ids_in_tail = [c.runtimeid for c in tail_controls if c.runtimeid not in used_id_set]
        if not new_ids_in_tail:
            return []  # 快速路径：无新消息
        
        # ── 检测到新消息：等待 UIA 树稳定 ──
        # WeChat 的 UIA 树是增量更新的，多条消息同时到达时，
        # GetChildren() 可能只返回部分。循环读取直到结果稳定。
        stable_controls = msg_controls
        stable_count = current_msg_count
        for _ in range(3):
            time.sleep(0.05)  # 50ms，给 UIA 树更新时间
            try:
                re_controls = self.msgbox.GetChildren()
                re_controls = [c for c in re_controls if c.ControlTypeName == 'ListItemControl']
                re_count = len(re_controls)
            except Exception:
                break
            if re_count == stable_count:
                break  # 结果稳定，退出等待
            # 数量增加，继续等待
            stable_controls = re_controls
            stable_count = re_count
        
        # 使用稳定后的数据提取新消息
        final_used_ids = USED_MSG_IDS.get(current_msgbox_id, tuple())
        final_used_set = set(final_used_ids)
        final_check = min(30, stable_count)
        final_tail = stable_controls[-final_check:]
        final_new_ids = [c.runtimeid for c in final_tail if c.runtimeid not in final_used_set]
        
        if not final_new_ids:
            # 稳定后没有新消息（之前检测到的可能是 UIA 过渡态）
            self._commit_state(current_msgbox_id, stable_controls, stable_count)
            return []
        
        # 更新状态并返回
        self._commit_state(current_msgbox_id, stable_controls, stable_count)
        new_id_set = set(final_new_ids)
        return [parse_msg(c, self) for c in final_tail if c.runtimeid in new_id_set]

    def _commit_state(self, msgbox_id, msg_controls, msg_count):
        """提交消息追踪状态（仅在 UIA 树稳定后调用）"""
        try:
            all_msg_ids = tuple(c.runtimeid for c in msg_controls)
            USED_MSG_IDS[msgbox_id] = all_msg_ids[-100:] if len(all_msg_ids) > 100 else all_msg_ids
            LAST_MSG_COUNT[msgbox_id] = msg_count
        except Exception:
            pass

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
            parts = re.findall(r"-?\d+", msg_id)
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