from weixin4auto.utils.tools import (
    detect_message_direction_by_content_position,
    detect_message_direction_by_color
)
from weixin4auto import uia
from weixin4auto.ui_config import WxUI41Config
from .mattr import (
    SystemMessage
)
from .mtype import *
from . import self as selfmsg
from . import friend as friendmsg
from typing import (
    TYPE_CHECKING,
    Literal,
    Dict,
    Any
)
import os
import re

if TYPE_CHECKING:
    from weixin4auto.ui.chatbox import ChatBox

def parse_msg_attr(
    control: uia.Control,
    parent: 'ChatBox'
):
    msg_direction_hash = {
        'left': 'friend',
        'right': 'self'
    }
    if control.AutomationId:
        # 通过截图内容像素位置分布判断方向（right=self, left=friend）
        msg_screenshot = control.ScreenShot()
        msg_direction, msg_direction_distence = detect_message_direction_by_content_position(msg_screenshot)
        
        # 内容位置检测失败时，回退到气泡颜色检测
        if msg_direction is None:
            msg_direction, color_confidence = detect_message_direction_by_color(msg_screenshot)
            if msg_direction is not None:
                msg_direction_distence = color_confidence
        
        os.remove(msg_screenshot)
        
        msg_attr = msg_direction_hash.get(msg_direction)
        
        # 方向仍无法判断时，默认归为 friend（避免消息丢失）
        if msg_attr is None:
            msg_attr = 'friend'
            msg_direction = 'left'
            msg_direction_distence = 0.0

        additonal_attr = {
            'direction': msg_direction,
            'direction_distence': msg_direction_distence,
            'detect_method': 'content_position',
        }
        
    else:
        msg_attr = 'system'

    if msg_attr == 'system':
        return SystemMessage(control, parent)
    elif msg_attr == 'friend':
        return parse_msg_type(control, parent, 'Friend', additonal_attr)
    elif msg_attr == 'self':
        return parse_msg_type(control, parent, 'Self', additonal_attr)

def _find_message_type_from_children(control: uia.Control) -> tuple:
    """从子控件中查找消息类型和内容
    返回: (message_type, content_text, child_control)
    """
    try:
        children = control.GetChildren()
        for child in children:
            child_classname = child.ClassName
            child_name = child.Name
            
            # 优先检查 ChatBubbleReferItemView（图片、动画表情等）
            if child_classname == WxUI41Config.MSG_REFER_ITEM_CLS:
                name_result = _classify_by_name(child_name)
                if name_result:
                    return (name_result, child_name, child)
            
            # 检查 ChatTextItemView（文本消息）
            elif child_classname == WxUI41Config.MSG_TEXT_ITEM_CLS:
                # 如果是文本消息，继续检查是否有其他更重要的子控件
                pass
            
            # 检查其他特殊类型
            classname_result = _classify_by_classname(child_classname)
            if classname_result:
                return (classname_result, child_name, child)
    except:
        pass
    return (None, None, None)

def parse_msg_type(
        control: uia.Control,
        parent,
        attr: Literal['Self', 'Friend'],
        additonal_attr: Dict[str, Any]
    ):
    """
    多层次消息类型识别算法
    基于ClassName、Name等多重验证确保识别准确性
    """
    if attr == 'Friend':
        msgtype = friendmsg
    else:
        msgtype = selfmsg

    msg_text = control.Name
    msg_classname = control.ClassName
    msg_automation_id = control.AutomationId
    
    # 第一层：ClassName强特征识别（最可靠）
    classname_result = _classify_by_classname(msg_classname)
    if classname_result:
        return getattr(msgtype, f'{attr}{classname_result}')(control, parent, additonal_attr)
    
    # 第二层：基于ClassName分类后的详细识别
    if msg_classname == WxUI41Config.MSG_BUBBLE_ITEM_CLS:
        # 先检查子控件，找到真正的消息类型（图片、动画表情等可能在子控件中）
        child_type, child_content, child_control = _find_message_type_from_children(control)
        if child_type:
            # 如果子控件有更明确的类型，使用子控件的信息
            # 但使用主控件作为消息控件（保持一致性）
            return getattr(msgtype, f'{attr}{child_type}')(control, parent, additonal_attr)
        
        # Name前缀特征识别
        prefix_result = _classify_by_name_prefix(msg_text)
        if prefix_result:
            return getattr(msgtype, f'{attr}{prefix_result}')(control, parent, additonal_attr)
        
        # Name完全匹配识别（图片、动画表情等）
        name_result = _classify_by_name(msg_text)
        if name_result:
            return getattr(msgtype, f'{attr}{name_result}')(control, parent, additonal_attr)
        
        # 如果都不匹配，归类为其他消息
        return getattr(msgtype, f'{attr}OtherMessage')(control, parent, additonal_attr)
    
    # 处理 ChatBubbleReferItemView（动画表情等）
    elif msg_classname == WxUI41Config.MSG_REFER_ITEM_CLS:
        # 通过名称识别
        name_result = _classify_by_name(msg_text)
        if name_result:
            return getattr(msgtype, f'{attr}{name_result}')(control, parent, additonal_attr)
        # 如果无法识别，归类为其他消息
        return getattr(msgtype, f'{attr}OtherMessage')(control, parent, additonal_attr)
    
    elif msg_classname == WxUI41Config.MSG_TEXT_ITEM_CLS:
        # 第三层：引用消息处理
        if _is_quote_message(msg_text):
            return getattr(msgtype, f'{attr}QuoteMessage')(control, parent, additonal_attr)
        else:
            return getattr(msgtype, f'{attr}TextMessage')(control, parent, additonal_attr)
    
    return getattr(msgtype, f'{attr}OtherMessage')(control, parent, additonal_attr)


def _classify_by_classname(classname: str) -> str:
    classname_mapping = {
        WxUI41Config.MSG_VOICE_ITEM_CLS: "VoiceMessage",
        WxUI41Config.MSG_CARD_ITEM_CLS: "PersonalCardMessage",
        # 注意：MSG_REFER_ITEM_CLS 可能用于多种消息类型（动画表情、引用消息等）
        # 需要通过名称进一步识别，不在这里直接映射
    }
    return classname_mapping.get(classname, "")


def _classify_by_name_prefix(name: str) -> str:
    if name.startswith("[链接]"):
        return "LinkMessage"

    elif name.startswith("位置"):
        return "LocationMessage"

    elif name.startswith("文件\n"):
        return "FileMessage"

    elif name.startswith("视频"):
        return "VideoMessage"

    return ""

def _classify_by_name(name: str) -> str:
    """通过消息名称识别消息类型"""
    if not name:
        return ""
    name = name.strip()
    if name == "图片":
        return "ImageMessage"
    elif name == "动画表情":
        return "EmojiMessage"
    elif "表情" in name:
        return "EmojiMessage"
    return ""

def _is_quote_message(name: str) -> bool:
    quote_pattern = r'^(.*?)\s*\n引用\s+(.+?)\s+的消息\s*:\s*(.*)$'
    return bool(re.search(quote_pattern, name, re.DOTALL))
    
    
def parse_msg(
    control: uia.Control,
    parent
):
    # t0 = time.time()
    result = parse_msg_attr(control, parent)
    
    # t1 = time.time()
    # msgtype = str(result.__class__.__name__).ljust(20)
    # ms = int((t1 - t0)*1000)
    # print(f'parse_msg: {msgtype} {"□"*ms} {ms}ms')
    return result