from weixin4auto import uia
from weixin4auto.ui.component import (
    Menu,
    SelectContactWnd
)
from weixin4auto.utils import uilock
from weixin4auto.param import WxParam, WxResponse, PROJECT_NAME
from abc import ABC, abstractmethod
from typing import (
    Dict,
    List,
    Union,
    Any,
    TYPE_CHECKING,
    Iterator,
    Tuple
)
from hashlib import md5

if TYPE_CHECKING:
    from weixin4auto.ui.chatbox import ChatBox

def truncate_string(s: str, n: int=8) -> str:
    s = s.replace('\n', '').strip()
    return s if len(s) <= n else s[:n] + '...'

class Message:
    """消息对象基类

    该类不会直接实例化，而是作为所有消息类型的基类提供
    常用的工具方法。实际的属性均由子类在 ``__init__`` 中
    动态注入。
    """

    _EXCLUDE_FIELDS = {"control", "parent", "root"}

    # region --- 迭代/映射相关 -------------------------------------------------
    def _iter_public_items(self) -> Iterator[Tuple[str, Any]]:
        """遍历当前消息可公开的字段"""

        if not hasattr(self, "__dict__"):
            return

        for key, value in self.__dict__.items():
            if key.startswith("_") or key in self._EXCLUDE_FIELDS:
                continue
            if key == "hash" and not WxParam.MESSAGE_HASH:
                continue
            yield key, value

    def __iter__(self) -> Iterator[str]:
        for key, _ in self._iter_public_items():
            yield key

    def __len__(self) -> int:
        return sum(1 for _ in self._iter_public_items())

    def __getitem__(self, item: str) -> Any:
        for key, value in self._iter_public_items():
            if key == item:
                return value
        raise KeyError(item)

    def __contains__(self, key: object) -> bool:
        if not isinstance(key, str):
            return False
        return any(field == key for field, _ in self._iter_public_items())

    # endregion ----------------------------------------------------------------

    # region --- 字段访问 -------------------------------------------------------
    def keys(self) -> Tuple[str, ...]:
        return tuple(key for key, _ in self._iter_public_items())

    def values(self) -> Tuple[Any, ...]:
        return tuple(value for _, value in self._iter_public_items())

    def items(self) -> Tuple[Tuple[str, Any], ...]:
        return tuple(self._iter_public_items())

    def get(self, key: str, default: Any = None) -> Any:
        for field, value in self._iter_public_items():
            if field == key:
                return value
        return default

    def to_dict(self) -> Dict[str, Any]:
        return dict(self._iter_public_items())

    def copy(self) -> Dict[str, Any]:
        return self.to_dict().copy()

    # endregion ----------------------------------------------------------------

    # region --- 状态判断 -------------------------------------------------------
    def match(self, **conditions: Any) -> bool:
        """判断当前消息是否同时满足给定的字段条件"""

        data = self.to_dict()
        return all(data.get(key) == value for key, value in conditions.items())

    @property
    def is_self(self) -> bool:
        return getattr(self, "attr", None) == "self"

    @property
    def is_friend(self) -> bool:
        return getattr(self, "attr", None) == "friend"

    @property
    def is_system(self) -> bool:
        return getattr(self, "attr", None) == "system"

    # endregion ----------------------------------------------------------------

    # region --- 魔术方法 -------------------------------------------------------
    def __str__(self) -> str:
        content = getattr(self, "content", None)
        if content is None:
            return super().__str__()
        return str(content)

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, Message):
            return NotImplemented

        self_id = getattr(self, "id", None)
        other_id = getattr(other, "id", None)
        if self_id is not None and other_id is not None:
            return self_id == other_id

        if WxParam.MESSAGE_HASH:
            return getattr(self, "hash", None) == getattr(other, "hash", None)

        return self is other

    def __hash__(self) -> int:
        msg_id = getattr(self, "id", None)
        if msg_id is not None:
            return hash(msg_id)

        if WxParam.MESSAGE_HASH:
            return hash(getattr(self, "hash", None))

        return super().__hash__()

    # endregion ----------------------------------------------------------------

class BaseMessage(Message, ABC):
    type: str = 'base'
    attr: str = 'base'
    control: uia.Control

    def __init__(
            self, 
            control: uia.Control, 
            parent: "ChatBox",
            additonal_attr: Dict[str, Any]={}
        ):
        self.parent = parent
        self.control = control
        self.direction = additonal_attr.get('direction', None)
        self.distince = additonal_attr.get('direction_distence', None)
        self.detect_method = additonal_attr.get('detect_method', 'unknown')
        self.root = parent.root
        self.id = self.control.runtimeid
        
        # 优化：对于图片等消息，优先从子控件中获取内容
        # 消息控件可能包含多个子控件，需要找到正确的消息类型和内容
        main_name = self.control.Name or ""
        content_name = main_name
        
        # 检查子控件，找到真正的消息内容
        # 优先级：图片 > 动画表情 > 其他特殊类型 > 文本
        try:
            children = control.GetChildren()
            found_image = False
            found_emoji = False
            
            for child in children:
                child_name = child.Name or ""
                child_classname = child.ClassName
                
                # 优先检查 ChatBubbleReferItemView（图片、动画表情等）
                if child_classname == 'mmui::ChatBubbleReferItemView':
                    if child_name == "图片":
                        content_name = "图片"
                        found_image = True
                        break  # 找到图片，直接使用
                    elif child_name == "动画表情":
                        content_name = "动画表情"
                        found_emoji = True
                        # 继续检查是否有图片（图片优先级更高）
                
                # 如果已经找到图片，不再检查其他类型
                if found_image:
                    break
        except:
            pass
        
        self.content = content_name
        
        # 提取发送者信息（特别是群消息）
        self.sender = None
        self.sender_remark = None
        if self.attr == 'friend':
            # 尝试从控件结构中提取发送者名称
            try:
                children = control.GetChildren()
                for child in children:
                    child_name = (child.Name or "").strip()
                    child_classname = child.ClassName
                    
                    # 查找发送者标签控件（通常是 TextControl 且在消息内容之前）
                    if child_classname in ['mmui::ChatBubbleNickNameView', 'ChatBubbleNickNameView']:
                        if child_name and len(child_name) < 50:
                            self.sender = child_name
                            break
                    
                    # 或者检查子控件名称是否包含换行符（发送者\n内容 格式）
                    elif '\n' in child_name:
                        parts = child_name.split('\n', 1)
                        if len(parts) >= 2:
                            potential_sender = parts[0].strip()
                            potential_content = parts[1].strip()
                            # 发送者通常较短，且不包含消息内容关键词
                            if (potential_sender and 
                                len(potential_sender) < 30 and 
                                potential_content and
                                potential_sender not in ['图片', '动画表情', '视频', '文件']):
                                self.sender = potential_sender
                                # 更新 content 为去掉发送者的部分
                                if potential_content:
                                    self.content = potential_content
                                break
            except:
                pass
            
            # 如果没找到发送者，使用聊天对象名称（单聊情况）
            if not self.sender:
                try:
                    parent_parent = getattr(parent, 'parent', None)
                    if parent_parent and hasattr(parent_parent, 'nickname'):
                        self.sender = parent_parent.nickname
                except:
                    pass
        
        elif self.attr == 'self':
            self.sender = '我'
        
        rect = self.control.BoundingRectangle
        self.hash_text = f'({rect.height()},{rect.width()}){self.content}'
        self.hash = md5(self.hash_text.encode()).hexdigest()

    def __repr__(self):
        cls_name = self.__class__.__name__
        content = truncate_string(self.content)
        return f"<{PROJECT_NAME} - {cls_name}({content}) at {hex(id(self))}>"
    
    def roll_into_view(self):
        if not self.exists():
            return WxResponse.failure('消息目标控件不存在，无法滚动至显示窗口')
        if uia.RollIntoView(
            self.parent.msgbox, 
            self.control
        ) == 'not exist':
            return WxResponse.failure('消息目标控件不存在，无法滚动至显示窗口')
        return WxResponse.success('成功')
    
    def exists(self):
        if self.control.Exists(0) and self.control.BoundingRectangle.height() > 0:
            return True
        return False
    
    def get_info(self) -> Dict[str, Any]:
        """获取消息的详细信息，包括消息ID、内容、发送者、聊天信息等
        
        Returns:
            Dict[str, Any]: 包含消息详细信息的字典
        """
        from datetime import datetime
        
        info = {}
        
        # 1. 消息ID（优先使用hash）
        if hasattr(self, 'hash') and self.hash:
            info['msg_id'] = self.hash
            info['msg_id_type'] = 'hash'
        elif hasattr(self, 'hash_text') and self.hash_text:
            info['msg_id'] = self.hash_text[:50] + '...' if len(self.hash_text) > 50 else self.hash_text
            info['msg_id_type'] = 'hash_text'
        elif hasattr(self, 'id') and self.id:
            if isinstance(self.id, tuple):
                info['msg_id'] = '-'.join(str(x) for x in self.id)
            else:
                info['msg_id'] = str(self.id)
            info['msg_id_type'] = 'runtimeid'
        else:
            info['msg_id'] = '未知'
            info['msg_id_type'] = 'unknown'
        
        # 2. 消息基本信息
        info['content'] = getattr(self, 'content', '')
        info['type'] = getattr(self, 'type', 'unknown')
        info['attr'] = getattr(self, 'attr', 'unknown')  # 'self' 或 'friend' 或 'system'
        info['direction'] = getattr(self, 'direction', None)  # 'left' 或 'right'
        info['direction_distance'] = getattr(self, 'distince', None)  # 距离值
        info['detect_method'] = getattr(self, 'detect_method', 'unknown')  # 使用的检测方法
        
        # 3. 聊天信息
        # 完全依赖父窗口的 nickname（窗口标题），避免调用 ChatInfo() 可能触发的点击操作
        chat_name = None
        try:
            # self.parent 是 ChatBox，self.parent.parent 可能是 WeChatSubWnd 或 WeChatMainWnd
            parent_parent = getattr(self.parent, 'parent', None)
            if parent_parent and hasattr(parent_parent, 'nickname'):
                chat_name = parent_parent.nickname
        except:
            pass
        
        # 如果从父窗口获取失败，尝试使用 who（但 who 可能是输入框名称，不可靠）
        if not chat_name:
            who = getattr(self.parent, 'who', None)
            # 如果 who 是"输入"或类似输入框提示文本，忽略它
            if who and who not in ['输入', '请输入', '']:
                chat_name = who
        
        info['chat_name'] = chat_name or '未知'
        
        # 不调用 ChatInfo()，避免触发点击操作
        # 如果需要判断是否为群聊，可以通过其他方式（如窗口标题包含特定标识）
        info['chat_type'] = 'unknown'
        info['is_group'] = False
        info['group_member_count'] = 0
        
        # 4. 发送者信息（优先使用 __init__ 时提取的 sender）
        if hasattr(self, 'sender') and self.sender:
            sender = self.sender
        elif info['attr'] == 'self':
            sender = '我'
        elif info['attr'] == 'friend':
            sender = info['chat_name']
        else:
            sender = '未知'
        
        sender_remark = getattr(self, 'sender_remark', None)
        
        info['sender'] = sender
        if sender_remark and sender_remark != sender:
            info['sender_remark'] = sender_remark
        
        # 5. 位置验证信息（用于调试方向检测）
        # 注意：访问 msgbox 可能会触发某些操作，暂时禁用位置信息获取
        # 如果需要调试位置信息，可以手动启用
        control_position_info = None
        # 暂时禁用位置信息获取，避免触发点击操作
        # try:
        #     rect = self.control.BoundingRectangle
        #     if hasattr(self.parent, 'msgbox'):
        #         try:
        #             msgbox_rect = self.parent.msgbox.BoundingRectangle
        #             msgbox_width = msgbox_rect.right - msgbox_rect.left
        #             msg_center_x = (rect.left + rect.right) / 2
        #             msgbox_center_x = (msgbox_rect.left + msgbox_rect.right) / 2
        #             position_ratio = (msg_center_x - msgbox_center_x) / (msgbox_width / 2) if msgbox_width > 0 else 0
        #             
        #             right_distance = msgbox_rect.right - rect.right
        #             left_distance = rect.left - msgbox_rect.left
        #             right_ratio = right_distance / msgbox_width if msgbox_width > 0 else 0
        #             left_ratio = left_distance / msgbox_width if msgbox_width > 0 else 0
        #             
        #             offset = msg_center_x - msgbox_center_x
        #             window_position_ratio = offset / (msgbox_width / 2) if msgbox_width > 0 else 0
        #             
        #             control_position_info = {
        #                 'position_ratio': position_ratio,
        #                 'right_ratio': right_ratio,
        #                 'left_ratio': left_ratio,
        #                 'msgbox_rect': {
        #                     'left': msgbox_rect.left,
        #                     'right': msgbox_rect.right,
        #                     'width': msgbox_width
        #                 },
        #                 'message_rect': {
        #                     'left': rect.left,
        #                     'right': rect.right,
        #                     'width': rect.width()
        #                 },
        #                 'window_position_ratio': window_position_ratio,
        #                 'message_center_x': msg_center_x,
        #                 'window_center_x': msgbox_center_x,
        #                 'offset': offset
        #             }
        #         except Exception as e:
        #             control_position_info = {'error': str(e)}
        # except Exception as e:
        #     control_position_info = {'error': str(e)}
        
        info['position_info'] = control_position_info
        
        # 6. 消息控件信息（用于调试）
        # 注意：获取子控件信息可能会触发某些操作，暂时只获取基本信息
        control_info = None
        try:
            control_info = {
                'class_name': getattr(self.control, 'ClassName', 'N/A'),
                'automation_id': getattr(self.control, 'AutomationId', 'N/A'),
                'control_type_name': getattr(self.control, 'ControlTypeName', 'N/A'),
                'name': str(getattr(self.control, 'Name', 'N/A'))[:100]
            }
            
            # 暂时禁用子控件信息获取，避免触发点击操作
            # try:
            #     children = self.control.GetChildren()
            #     control_info['children_count'] = len(children)
            #     control_info['children'] = []
            #     for i, child in enumerate(children[:5]):  # 只取前5个
            #         try:
            #             child_rect = child.BoundingRectangle
            #             control_info['children'].append({
            #                 'index': i + 1,
            #                 'class_name': getattr(child, 'ClassName', 'N/A'),
            #                 'rect': {
            #                     'left': child_rect.left,
            #                     'right': child_rect.right,
            #                     'width': child_rect.width()
            #                 },
            #                 'name': str(getattr(child, 'Name', ''))[:50]
            #             })
            #         except:
            #             pass
            # except:
            #     control_info['children_count'] = 0
            #     control_info['children'] = []
            control_info['children_count'] = 0
            control_info['children'] = []
        except:
            control_info = {'error': '无法获取控件信息'}
        
        info['control_info'] = control_info
        
        # 7. 接收时间
        info['receive_time'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        
        return info
    


class HumanMessage(BaseMessage, ABC):
    attr = 'human'

    def __init__(
            self, 
            control: uia.Control, 
            parent: "ChatBox",
            additonal_attr: Dict[str, Any]={}
        ):
        super().__init__(control, parent, additonal_attr)

    @abstractmethod
    def _click(self, x, y, right=False):...

    @abstractmethod
    def _bias(self):...

    def click(self):
        self._click(right=False, x=self._bias*2, y=WxParam.DEFAULT_MESSAGE_YBIAS)

    def right_click(self):
        self._click(right=True, x=self._bias, y=WxParam.DEFAULT_MESSAGE_YBIAS)

    @uilock
    def select_option(self, option: str, timeout=2) -> WxResponse:
        if not self.exists():
            return WxResponse.failure('消息对象已失效')
        self._click(right=True, x=self._bias*2, y=WxParam.DEFAULT_MESSAGE_YBIAS)
        if menu := Menu(self, timeout):
            return menu.select(option)
        else:
            return WxResponse.failure('操作失败')
    
    @uilock
    def forward(
        self, 
        targets: Union[List[str], str], 
        timeout: int = 3,
        interval: float = 0.1
    ) -> WxResponse:
        """转发消息

        Args:
            targets (Union[List[str], str]): 目标用户列表
            timeout (int, optional): 超时时间，单位为秒，若为None则不启用超时设置
            interval (float): 选择联系人时间间隔

        Returns:
            WxResponse: 调用结果
        """
        if not self.exists():
            return WxResponse.failure('消息对象已失效')
        if not self.select_option('转发...', timeout=timeout):
            return WxResponse.failure('当前消息无法转发')
        
        select_wnd = SelectContactWnd(self)
        return select_wnd.send(targets, interval=interval)
    
    @uilock
    def quote(
            self, text: str, 
            at: Union[List[str], str] = None, 
            timeout: int = 3
        ) -> WxResponse:
        """引用消息
        
        Args:
            text (str): 引用内容
            at (List[str], optional): @用户列表
            timeout (int, optional): 超时时间，单位为秒，若为None则不启用超时设置

        Returns:
            WxResponse: 调用结果
        """
        if not self.exists():
            return WxResponse.failure('消息对象已失效')
        if not self.select_option('引用', timeout=timeout):
            return WxResponse.failure('当前消息无法引用')
        
        if at:
            self.parent.input_at(at)

        return self.parent.send_text(text)
