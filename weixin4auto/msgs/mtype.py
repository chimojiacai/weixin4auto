from .base import (
    BaseMessage, 
    HumanMessage,
)
from weixin4auto import uia
from weixin4auto.param import (
    WxParam, 
    WxResponse, 
    PROJECT_NAME
)

from typing import (
    Dict, 
    List, 
    Any,
    TYPE_CHECKING,
    Optional,
)
import re
import time
import win32api
import win32con
if TYPE_CHECKING:
    from weixin4auto.ui.chatbox import ChatBox
    from pathlib import Path


class TextMessage(BaseMessage):
    type = 'text'

    def __init__(
            self, 
            control: uia.Control, 
            parent: "ChatBox",
            additonal_attr: Dict[str, Any]={}
        ):
        super().__init__(control, parent, additonal_attr)

class QuoteMessage(BaseMessage):
    type = 'quote'
    repattern = r"^(.*?) \n引用 (.*?) 的消息 : (.*?)$"

    def __init__(
            self, 
            control: uia.Control, 
            parent: "ChatBox",
            additonal_attr: Dict[str, Any]={}
        ):
        super().__init__(control, parent, additonal_attr)
        self.content, self.quote_nickname, self.quote_content = \
            re.findall(self.repattern, self.content, re.DOTALL)[0]
        
class VoiceMessage(BaseMessage):
    type = 'voice'

    def __init__(
            self, 
            control: uia.Control, 
            parent: "ChatBox",
            additonal_attr: Dict[str, Any]={}
        ):
        super().__init__(control, parent, additonal_attr)

    def to_text(self) -> str:
        """获取语音转文字内容（需已开启自动转文字功能）
        
        等待 1 秒让微信完成转写，然后重新读取控件 Name 提取转写文本。
        Name 格式: 语音{N}"秒{转写文本}，如 `语音2"秒你好啊`
        
        Returns:
            str: 转写后的文字，未识别到则返回原始 content
        """
        time.sleep(2)
        # 重新读取控件 Name，转写可能尚未完成
        try:
            name = self.control.Name or ''
        except Exception:
            name = self.content or ''
        m = re.match(r'语音\d+"秒(.*)', name)
        if m:
            return m.group(1).strip()
        return self.content or ''

class ImageMessage(BaseMessage):
    type = 'image'
    
    def __init__(
            self, 
            control: uia.Control, 
            parent: "ChatBox",
            additonal_attr: Dict[str, Any]={}
        ):
        super().__init__(control, parent, additonal_attr)

    def download(
            self,
            dir_path: Optional[str] = None,
            original: bool = False,
        ) -> WxResponse:
        """下载图片消息
        
        Args:
            dir_path: 保存目录路径，默认为 WxParam.DEFAULT_SAVE_PATH
            original: 是否下载原图，默认 False
        
        Returns:
            WxResponse: 成功时 data['path'] 为文件路径
        """
        from weixin4auto.ui.component import WeChatImage
        from weixin4auto.logger import wxlog
        
        if not self.exists():
            return WxResponse.failure('消息控件不存在')
        
        # 滚动到可见
        self.roll_into_view()
        time.sleep(0.3)
        
        # 根据消息方向决定点击位置（好友在左，自己在右）
        direction = getattr(self, 'direction', 'left')
        click_pos = 'right' if direction == 'right' else 'left'
        
        # 找到图片控件并点击
        img_control = self._find_image_control()
        if img_control:
            self._click_at_position(img_control, click_pos)
        else:
            self.control.Click()
        
        time.sleep(1.5)
        
        # 如果需要下载原图，先点击"下载原图"按钮
        if original:
            self._try_download_original()
        
        # 通过 WeChatImage 保存（self.parent 是 ChatBox，有 root 属性）
        try:
            wx_img = WeChatImage(self.parent)
            if not wx_img.control or not wx_img.control.Exists(0):
                return WxResponse.failure('图片预览窗口未打开')
            
            result = wx_img.save(dir_path=dir_path)
            if isinstance(result, WxResponse) and not result.is_success:
                return result
            
            return WxResponse.success(data={'path': str(result)})
        except Exception as e:
            wxlog.debug(f"图片下载失败: {e}")
            return WxResponse.failure(f'图片下载失败: {e}')

    def _find_image_control(self):
        """查找图片控件（ChatBubbleReferItemView）"""
        if self.control.ClassName == 'mmui::ChatBubbleReferItemView':
            return self.control
        for ctrl in uia.WalkControl(self.control):
            if ctrl.ClassName == 'mmui::ChatBubbleReferItemView':
                return ctrl
        return None

    @staticmethod
    def _click_at_position(control, position='center'):
        """在控件的指定位置点击"""
        rect = control.BoundingRectangle
        width = rect.right - rect.left
        if position == 'left':
            x = rect.left + width // 4
        elif position == 'right':
            x = rect.right - width // 4
        else:
            x = (rect.left + rect.right) // 2
        y = (rect.top + rect.bottom) // 2
        win32api.SetCursorPos((x, y))
        win32api.mouse_event(win32con.MOUSEEVENTF_LEFTDOWN, x, y, 0, 0)
        win32api.mouse_event(win32con.MOUSEEVENTF_LEFTUP, x, y, 0, 0)

    def _try_download_original(self):
        """尝试点击下载原图按钮"""
        from weixin4auto.logger import wxlog
        from weixin4auto.utils.win32 import GetAllWindows
        from weixin4auto.ui_config import WxUI41Config
        try:
            time.sleep(0.5)
            wins = GetAllWindows(classname=WxUI41Config.WIN_CLS_NAME, name="图片和视频")
            if not wins:
                return
            preview_control = uia.ControlFromHandle(wins[0][0])
            for ctrl in uia.WalkControl(preview_control):
                if hasattr(ctrl, 'Name') and ctrl.Name == '下载原图':
                    ctrl.Click()
                    wxlog.debug("已点击'下载原图'按钮")
                    time.sleep(2)
                    break
        except Exception as e:
            wxlog.debug(f"下载原图失败: {e}")

class VideoMessage(BaseMessage):
    type = 'video'
    repattern = r'视频(\d+):(\d+)'
    
    def __init__(
            self, 
            control: uia.Control, 
            parent: "ChatBox",
            additonal_attr: Dict[str, Any]={}
        ):
        super().__init__(control, parent, additonal_attr)

class FileMessage(BaseMessage):
    type = 'file'
    repattern = r"^文件\n([^\n]+)\n(\d+(\.\d+)?)(B|KB|MB|GB|TB)\n微信电脑版$"
    
    def __init__(
            self, 
            control: uia.Control, 
            parent: "ChatBox",
            additonal_attr: Dict[str, Any]={}
        ):
        super().__init__(control, parent, additonal_attr)

class EmojiMessage(BaseMessage):
    type = 'emoji'
    
    def __init__(
            self, 
            control: uia.Control, 
            parent: "ChatBox",
            additonal_attr: Dict[str, Any]={}
        ):
        super().__init__(control, parent, additonal_attr)

class OtherMessage(BaseMessage):
    type = 'other'
    
    def __init__(
            self, 
            control: uia.Control, 
            parent: "ChatBox",
            additonal_attr: Dict[str, Any]={}
        ):
        super().__init__(control, parent, additonal_attr)