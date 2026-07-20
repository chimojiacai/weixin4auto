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
import time

if TYPE_CHECKING:
    from weixin4auto.ui.chatbox import ChatBox

def truncate_string(s: str, n: int=8) -> str:
    s = s.replace('\n', '').strip()
    return s if len(s) <= n else s[:n] + '...'

# OCR 单例：避免每次识别都重新加载模型（~3s）
_OCR_ENGINE = None

def _get_ocr_engine():
    """获取或创建 OCR 引擎单例"""
    global _OCR_ENGINE
    if _OCR_ENGINE is None:
        try:
            from rapidocr_onnxruntime import RapidOCR
            _OCR_ENGINE = RapidOCR()
        except ImportError:
            _OCR_ENGINE = False  # 标记为不可用，避免重复尝试
    return _OCR_ENGINE if _OCR_ENGINE else None


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
        
        # 提取消息内容
        # 优先从子控件中获取真正的消息类型（图片、动画表情等）
        self.content = self._extract_content()
        
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

    def _get_sender_by_ocr(self, img=None) -> str:
        """通过 OCR 识别消息控件中的发送者昵称（无需窗口激活）
        
        从消息控件截图，裁剪出顶部发送者昵称区域，使用 OCR 识别文字。
        适用于群聊场景，不需要唤起窗口或点击头像。
        
        Args:
            img: 可选，预先捕获的 PIL Image（主线程截图，线程安全）
                若不传，则自行调用 control.ScreenShot()（非线程安全）
        
        Returns:
            str: 发送者昵称，识别失败返回空字符串
        """
        import re
        import time
        import numpy as np
        from weixin4auto.logger import wxlog
        
        try:
            _t_start = time.time()
            
            # 获取缓存的 OCR 引擎
            ocr = _get_ocr_engine()
            if ocr is None:
                wxlog.debug('[OCR] rapidocr-onnxruntime 未安装')
                return ''
            _t1 = time.time()
            
            # 截图：优先使用预捕获的图片（线程安全），否则自行截图（需主线程）
            if img is None:
                img = self.control.ScreenShot(return_img=True)
            if img is None:
                return ''
            _t2 = time.time()
            
            # 裁剪发送者昵称区域：顶部 0~35px，水平方向跳过左侧头像区域(~50px)
            width, height = img.size
            top_crop = img.crop((50, 0, min(width, 350), min(35, height)))
            _t3 = time.time()

            # 转灰度 + numpy array
            # img_array = np.array(top_crop.convert('L'))
            img_array = np.array(top_crop)
            wxlog.debug(
                f"原图={img.size}, crop={top_crop.size}, array={img_array.shape}"
            )
            _t4 = time.time()
            
            # OCR 识别
            result, _ = ocr(img_array)
            _t5 = time.time()
            
            if not result:
                wxlog.debug(f'[OCR耗时] 引擎={(_t1-_t_start)*1000:.1f}ms 截图={(_t2-_t1)*1000:.1f}ms 裁剪={(_t3-_t2)*1000:.1f}ms 灰度={(_t4-_t3)*1000:.1f}ms OCR识别={(_t5-_t4)*1000:.1f}ms 总计={(_t5-_t_start)*1000:.1f}ms')
                return ''
            text = ' '.join([line[1] for line in result]).strip()
            
            # 清理识别结果
            text = re.sub(r'[^\w\u4e00-\u9fff\-_.]', '', text).strip()
            
            # 过滤无效结果
            if not text or len(text) > 30:
                return ''
            if text in ['图片', '动画表情', '视频', '文件', '语音', '表情']:
                return ''
            
            _t_end = time.time()
            wxlog.debug(f'[OCR耗时] 引擎={(_t1-_t_start)*1000:.1f}ms 截图={(_t2-_t1)*1000:.1f}ms 裁剪={(_t3-_t2)*1000:.1f}ms 灰度={(_t4-_t3)*1000:.1f}ms OCR识别={(_t5-_t4)*1000:.1f}ms 后处理={(_t_end-_t5)*1000:.1f}ms 总计={(_t_end-_t_start)*1000:.1f}ms')
            wxlog.debug(f'[OCR] sender=\'{text}\'')
            return text
        except Exception as e:
            wxlog.debug(f'[OCR] 识别失败: {e}')
            return ''

    def _get_sender_from_avatar(self) -> str:
        """通过点击消息体头像获取发送者昵称（无感知）
        
        使用 SetWinEventHook 按微信PID过滤，拦截微信进程所有新窗口显示事件，
        在弹窗渲染前将其隐藏。UIA 仍可读取隐藏窗口内容。
        
        Returns:
            str: 发送者昵称，获取失败返回空字符串
        """
        import time
        import win32gui
        import win32con
        import win32process
        import ctypes
        import ctypes.wintypes
        from weixin4auto.ui_config import WxUI41Config
        from weixin4auto.logger import wxlog
        
        try:
            self.roll_into_view()
            
            # 计算头像点击坐标
            msg_rect = self.control.BoundingRectangle
            click_x = msg_rect.left + 43
            click_y = msg_rect.top + 27
            wxlog.debug(f"[头像] msg_rect=({msg_rect.left},{msg_rect.top},{msg_rect.right},{msg_rect.bottom}), click=({click_x},{click_y})")
            
            # 获取微信进程PID
            top_hwnd = self.control.GetTopLevelControl().NativeWindowHandle
            _, wx_pid = win32process.GetWindowThreadProcessId(top_hwnd)
            
            # 记录点击前微信进程已有的所有窗口（用于排除）
            existing_hwnds = set()
            def _enum_existing(hwnd, _):
                existing_hwnds.add(hwnd)
                return True
            win32gui.EnumWindows(_enum_existing, None)
            
            user32 = ctypes.windll.user32
            popup_hwnd_holder = [None]
            
            # WinEvent 回调类型
            WINEVENTPROC = ctypes.WINFUNCTYPE(
                None,
                ctypes.wintypes.HANDLE,   # hWinEventHook
                ctypes.wintypes.DWORD,    # event
                ctypes.wintypes.HANDLE,   # hwnd
                ctypes.wintypes.LONG,     # idObject
                ctypes.wintypes.LONG,     # idChild
                ctypes.wintypes.DWORD,    # dwEventThread
                ctypes.wintypes.DWORD,    # dwmsEventTime
            )
            
            # 主窗口句柄（排除，不是弹窗）
            main_hwnd = top_hwnd
            
            def _win_event_callback(hook, event, hwnd, idObject, idChild, thread, time_ms):
                """同步回调：拦截微信进程的新窗口显示"""
                if idObject != 0 or not hwnd:
                    return
                try:
                    # 只处理微信进程的新窗口
                    _, pid = win32process.GetWindowThreadProcessId(hwnd)
                    if pid != wx_pid:
                        return
                    if hwnd in existing_hwnds:
                        return
                    
                    cls = win32gui.GetClassName(hwnd)
                    
                    # 排除主窗口（按句柄排除，而非类名，因为弹窗可能与主窗口同类名）
                    if hwnd == main_hwnd:
                        return
                    
                    # 发现新窗口，无条件隐藏并记录
                    # 不能用 IsWindowVisible 判断：EVENT_OBJECT_CREATE 触发时窗口尚不可见，
                    # 会导致漏拦截；而后续 EVENT_OBJECT_SHOW 又因 hwnd 已在 existing_hwnds 中被跳过
                    win32gui.ShowWindow(hwnd, win32con.SW_HIDE)
                    popup_hwnd_holder[0] = hwnd
                    wxlog.debug(f"[hook] 拦截弹窗: hwnd={hwnd}, cls={cls}")
                except:
                    pass
            
            _callback = WINEVENTPROC(_win_event_callback)
            
            # 按PID过滤：只拦截微信进程的事件
            # EVENT_OBJECT_SHOW(0x8002) + EVENT_SYSTEM_DIALOGSTART(0x0010)
            hook1 = user32.SetWinEventHook(
                0x8002, 0x8002,  # EVENT_OBJECT_SHOW
                0, _callback, wx_pid, 0, 0
            )
            hook2 = user32.SetWinEventHook(
                0x0010, 0x0010,  # EVENT_SYSTEM_DIALOGSTART
                0, _callback, wx_pid, 0, 0
            )
            hook3 = user32.SetWinEventHook(
                0x8000, 0x8000,  # EVENT_OBJECT_CREATE
                0, _callback, wx_pid, 0, 0
            )
            
            try:
                # 点击头像
                uia.Click(click_x, click_y)
                
                # 泵送消息等待事件回调触发（最长1.5s）
                t0 = time.time()
                while popup_hwnd_holder[0] is None and (time.time() - t0) < 1.5:
                    msg = ctypes.wintypes.MSG()
                    while ctypes.windll.user32.PeekMessageW(
                        ctypes.byref(msg), 0, 0, 0, 1  # PM_REMOVE
                    ):
                        ctypes.windll.user32.TranslateMessage(ctypes.byref(msg))
                        ctypes.windll.user32.DispatchMessageW(ctypes.byref(msg))
                    if popup_hwnd_holder[0] is None:
                        time.sleep(0.002)
                
                popup_hwnd = popup_hwnd_holder[0]
                if popup_hwnd is None:
                    wxlog.debug("[头像] 未检测到弹窗(1.5s超时)")
                    return ""
                wxlog.debug(f"[头像] 检测到弹窗 hwnd={popup_hwnd}")
                
                # 弹窗已被拦截隐藏，通过 UIA 读取隐藏窗口内容
                time.sleep(0.05)
                ctrl = uia.ControlFromHandle(popup_hwnd)
                nickname = ""
                
                # 方式1：直接查找 ContactHeadView
                try:
                    head_view = ctrl.ButtonControl(
                        ClassName=WxUI41Config.CONTACT_HEAD_VIEW_CLS,
                        AutomationId=WxUI41Config.CONTACT_HEAD_VIEW_AUTOMATION_ID
                    )
                    if head_view.Exists(0.5):
                        nickname = head_view.Name if hasattr(head_view, 'Name') else ""
                except:
                    pass
                
                # 方式2：递归查找
                if not nickname:
                    def _find_in_popup(c, depth=0, max_depth=5):
                        if depth > max_depth:
                            return None
                        try:
                            for child in c.GetChildren():
                                if (child.ControlTypeName == 'ButtonControl' and
                                    getattr(child, 'ClassName', '') == WxUI41Config.CONTACT_HEAD_VIEW_CLS):
                                    child_name = getattr(child, 'Name', '')
                                    if child_name and child_name.strip():
                                        return child_name.strip()
                                result = _find_in_popup(child, depth + 1, max_depth)
                                if result:
                                    return result
                        except:
                            pass
                        return None
                    nickname = _find_in_popup(ctrl)
                
                # 关闭弹窗
                try:
                    uia.SendKeys('{ESC}')
                except:
                    pass
                
                wxlog.debug(f"[头像] nickname='{nickname}'")
                return nickname.strip() if nickname else ""
            finally:
                try:
                    if hook1: user32.UnhookWinEvent(hook1)
                    if hook2: user32.UnhookWinEvent(hook2)
                    if hook3: user32.UnhookWinEvent(hook3)
                except:
                    pass
        except:
            return ""

    def _extract_content(self) -> str:
        """提取消息内容，支持图片、动画表情等特殊消息类型"""
        main_name = self.control.Name or ""
        
        # 检查子控件，找到真正的消息内容
        try:
            children = self.control.GetChildren()
            for child in children:
                child_name = child.Name or ""
                child_classname = child.ClassName
                
                # ChatBubbleReferItemView：图片、动画表情等
                if child_classname == 'mmui::ChatBubbleReferItemView':
                    if child_name in ("图片", "动画表情"):
                        return child_name
                
                # ChatTextItemView 子控件的 Name 也可能是消息类型标识
                elif child_classname == 'mmui::ChatTextItemView':
                    if child_name in ("图片", "动画表情"):
                        return child_name
        except:
            pass
        
        return main_name

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

    def quote(self, text: str, at=None, timeout: int = 3) -> WxResponse:
        """引用该消息并发送回复

        通过右键菜单选择"引用"，然后输入文本并发送。
        适用于所有非系统消息类型。

        Args:
            text: 回复内容
            at: @用户列表（可选）
            timeout: 等待菜单出现的超时时间（秒）

        Returns:
            WxResponse: 操作结果
        """
        if self.attr == 'system':
            return WxResponse.failure('系统消息不支持引用')
        if not self.exists():
            return WxResponse.failure('消息控件已失效')

        # 1. 滚动到可见
        self.roll_into_view()

        # 2. 右键点击（根据消息方向决定坐标）
        x_bias = WxParam.DEFAULT_MESSAGE_XBIAS * 2
        if self.attr == 'self':
            self.control.RightClick(x=-x_bias, y=WxParam.DEFAULT_MESSAGE_YBIAS, ratioX=1, ratioY=0)
        else:
            self.control.RightClick(x=x_bias, y=WxParam.DEFAULT_MESSAGE_YBIAS, ratioX=0, ratioY=0)

        # 3. 从右键菜单选择"引用"
        time.sleep(0.3)
        menu = Menu(self, timeout=timeout)
        if not menu:
            return WxResponse.failure('右键菜单未出现')
        result = menu.select('引用')
        if not result.is_success:
            # Menu._safe_close() 已安全关闭菜单，无需额外操作
            return WxResponse.failure(f'无法选择引用: {result.get("message", "")}')

        # 4. @某人（可选）
        if at:
            self.parent.input_at(at)

        # 5. 发送文本
        time.sleep(0.3)
        return self.parent.send_text(text)
    
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
