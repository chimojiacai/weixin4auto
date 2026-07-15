from weixin4auto.utils.tools import (
    detect_message_direction
)
from weixin4auto import uia
from weixin4auto.ui_config import WxUI41Config
from .mattr import (
    SystemMessage,
    FriendMessage,
    SelfMessage
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
import time
import os
import re

if TYPE_CHECKING:
    from weixin4auto.ui.chatbox import ChatBox

def _detect_direction_by_message_index(control: uia.Control, parent: 'ChatBox') -> tuple:
    """通过消息控件在消息列表中的位置来判断方向（新方法）
    
    获取消息控件在消息列表中的所有控件中的索引，然后获取相邻消息的位置来判断方向
    
    Returns:
        tuple: (direction, confidence) - direction 为 'left' 或 'right', confidence 为置信度 (0-1)
    """
    try:
        # 获取所有消息控件
        all_controls = list(parent._iter_message_controls())
        if len(all_controls) < 2:
            return None, 0.0
        
        # 找到当前消息控件在列表中的索引
        current_index = None
        for idx, ctrl in enumerate(all_controls):
            if ctrl.runtimeid == control.runtimeid:
                current_index = idx
                break
        
        if current_index is None:
            return None, 0.0
        
        # 获取当前消息和相邻消息的位置
        current_rect = control.BoundingRectangle
        msgbox_rect = parent.msgbox.BoundingRectangle
        msgbox_width = msgbox_rect.right - msgbox_rect.left
        
        # 获取前后几条消息的位置，计算平均位置
        sample_count = min(3, len(all_controls))
        positions = []
        
        # 获取当前消息前后的消息位置
        start_idx = max(0, current_index - sample_count // 2)
        end_idx = min(len(all_controls), current_index + sample_count // 2 + 1)
        
        for idx in range(start_idx, end_idx):
            if idx == current_index:
                continue
            try:
                ctrl_rect = all_controls[idx].BoundingRectangle
                # 如果边界矩形和消息框不一样，说明是真正的消息气泡
                if abs(ctrl_rect.width() - msgbox_width) >= 10:
                    ctrl_center_x = (ctrl_rect.left + ctrl_rect.right) / 2
                    msgbox_center_x = (msgbox_rect.left + msgbox_rect.right) / 2
                    offset = ctrl_center_x - msgbox_center_x
                    positions.append(offset)
            except:
                continue
        
        # 如果找到了其他消息的位置，使用它们来判断
        if positions:
            avg_offset = sum(positions) / len(positions)
            # 如果平均偏移是正数，说明消息在右侧（自己发送）
            # 如果平均偏移是负数，说明消息在左侧（好友发送）
            if avg_offset > 50:  # 明显在右侧
                return 'right', min(abs(avg_offset) / msgbox_width, 1.0)
            elif avg_offset < -50:  # 明显在左侧
                return 'left', min(abs(avg_offset) / msgbox_width, 1.0)
        
        return None, 0.0
    except:
        return None, 0.0

def _detect_direction_by_window_position(control: uia.Control, parent: 'ChatBox') -> tuple:
    """通过消息控件在窗口（消息框）中的位置来判断方向（主要方法）
    
    使用消息框的中心位置来判断消息在窗口的左侧还是右侧：
    微信4.1的布局是：
    - 如果消息中心在窗口左侧，是好友发送的（left -> friend）
    - 如果消息中心在窗口右侧，是自己发送的（right -> self）
    
    注意：如果消息控件的边界矩形和消息框一样，说明获取的是容器，需要使用其他方法
    
    Returns:
        tuple: (direction, confidence) - direction 为 'left' 或 'right', confidence 为置信度 (0-1)
    """
    try:
        control_rect = control.BoundingRectangle
        msgbox_rect = parent.msgbox.BoundingRectangle
        
        # 计算消息框的宽度和中心点
        msgbox_width = msgbox_rect.right - msgbox_rect.left
        if msgbox_width <= 0:
            return None, 0.0
        
        # 关键优化：如果消息控件的边界矩形和消息框一样，说明获取的是容器而不是真正的消息气泡
        # 需要从子控件中找到真正的消息气泡位置
        if abs(control_rect.width() - msgbox_width) < 10:
            # 边界矩形宽度几乎和消息框一样，说明是容器，需要查找子控件
            try:
                children = control.GetChildren()
                # 查找真正的消息气泡控件
                best_child_rect = None
                best_child_width = 0
                for child in children:
                    child_classname = child.ClassName
                    # ChatBubbleItemView 或 ChatTextItemView 是真正的消息气泡
                    if child_classname in [WxUI41Config.MSG_BUBBLE_ITEM_CLS, WxUI41Config.MSG_TEXT_ITEM_CLS, WxUI41Config.MSG_REFER_ITEM_CLS]:
                        try:
                            child_rect = child.BoundingRectangle
                            child_width = child_rect.width()
                            # 选择宽度最大的子控件（通常是真正的消息气泡）
                            # 但宽度要明显小于消息框宽度（至少小10%）
                            if child_width > 0 and child_width < msgbox_width * 0.9 and child_width > best_child_width:
                                best_child_rect = child_rect
                                best_child_width = child_width
                        except:
                            continue
                
                if best_child_rect:
                    # 找到了真正的消息气泡，使用它的位置
                    control_rect = best_child_rect
                else:
                    # 如果没找到子控件，尝试通过消息索引位置判断（使用相邻消息的位置）
                    index_result = _detect_direction_by_message_index(control, parent)
                    if index_result[0]:
                        return index_result
                    # 如果索引方法也失败，返回None，让截图检测来处理
                    return None, 0.0
            except:
                # 如果查找子控件失败，尝试通过消息索引位置判断
                index_result = _detect_direction_by_message_index(control, parent)
                if index_result[0]:
                    return index_result
                return None, 0.0
        
        # 如果边界矩形有效，直接使用位置判断
        
        msgbox_center_x = (msgbox_rect.left + msgbox_rect.right) / 2
        
        # 计算消息中心点在窗口中的X坐标
        msg_center_x = (control_rect.left + control_rect.right) / 2
        
        # 计算消息中心点相对于窗口中心的位置偏移（像素）
        offset = msg_center_x - msgbox_center_x
        
        # 如果偏移量太小（<5像素），说明消息在中心，无法判断
        if abs(offset) < 5:
            return None, 0.0
        
        # 计算相对位置比例（相对于窗口宽度的一半）
        # 负数=左侧，正数=右侧
        position_ratio = offset / (msgbox_width / 2) if msgbox_width > 0 else 0
        
        # 降低阈值，让接近中心的消息也能判断（从0.1降低到0.05）
        # 微信4.1的布局：左侧是好友，右侧是自己
        # 如果消息中心在窗口左侧（< -0.05），是好友发送的
        if position_ratio < -0.05:
            # 置信度基于偏移距离，最大为1.0
            confidence = min(abs(position_ratio), 1.0)
            return 'left', confidence  # left -> friend
        # 如果消息中心在窗口右侧（> 0.05），是自己发送的
        elif position_ratio > 0.05:
            confidence = min(abs(position_ratio), 1.0)
            return 'right', confidence  # right -> self
        # 如果消息中心在窗口中间（-0.05 到 0.05之间），使用更宽松的判断
        else:
            # 即使接近中心，也根据偏移方向判断，但置信度较低
            if offset < 0:
                return 'left', 0.3  # left -> friend
            elif offset > 0:
                return 'right', 0.3  # right -> self
            else:
                return None, 0.0
    except:
        return None, 0.0

def _detect_direction_by_position(control: uia.Control, parent: 'ChatBox') -> tuple:
    """通过消息控件在聊天窗口中的位置来判断方向（备用方法）
    
    使用多种方法综合判断：
    1. 消息右边界相对于消息框右边界的位置（自己发送的消息右边界更靠近消息框右边界）
    2. 消息左边界相对于消息框左边界的位置（好友发送的消息左边界更靠近消息框左边界）
    3. 消息中心点相对于消息框中心点的位置
    
    Returns:
        tuple: (direction, confidence) - direction 为 'left' 或 'right', confidence 为置信度 (0-1)
    """
    try:
        control_rect = control.BoundingRectangle
        msgbox_rect = parent.msgbox.BoundingRectangle
        
        # 关键优化：如果消息控件的边界矩形和消息框一样，说明获取的是容器而不是真正的消息气泡
        # 需要从子控件中找到真正的消息气泡（ChatBubbleItemView 或 ChatTextItemView）
        msgbox_width = msgbox_rect.right - msgbox_rect.left
        if msgbox_width > 0 and abs(control_rect.width() - msgbox_width) < 10:
            # 边界矩形宽度几乎和消息框一样，说明是容器，需要查找子控件
            try:
                children = control.GetChildren()
                # 查找真正的消息气泡控件
                best_child_rect = None
                best_child_width = 0
                for child in children:
                    child_classname = child.ClassName
                    # ChatBubbleItemView 或 ChatTextItemView 是真正的消息气泡
                    if child_classname in [WxUI41Config.MSG_BUBBLE_ITEM_CLS, WxUI41Config.MSG_TEXT_ITEM_CLS, WxUI41Config.MSG_REFER_ITEM_CLS]:
                        child_rect = child.BoundingRectangle
                        child_width = child_rect.width()
                        # 选择宽度最大的子控件（通常是真正的消息气泡）
                        # 但宽度要明显小于消息框宽度（至少小10%）
                        if child_width > 0 and child_width < msgbox_width * 0.9 and child_width > best_child_width:
                            best_child_rect = child_rect
                            best_child_width = child_width
                
                if best_child_rect:
                    control_rect = best_child_rect
            except:
                pass
        
        # 检查边界矩形是否有效
        if control_rect.width() <= 0 or control_rect.height() <= 0:
            # 如果消息控件的边界矩形无效，尝试获取父控件
            try:
                parent_control = control.GetParentControl()
                if parent_control:
                    control_rect = parent_control.BoundingRectangle
            except:
                pass
        
        msgbox_width = msgbox_rect.right - msgbox_rect.left
        if msgbox_width <= 0:
            # 如果消息框宽度无效，尝试使用消息框的实际宽度
            try:
                msgbox_width = msgbox_rect.width()
                if msgbox_width <= 0:
                    return None, 0.0
            except:
                return None, 0.0
        
        # 方法1：使用消息右边界判断（自己发送的消息右边界更靠近消息框右边界）
        msg_right = control_rect.right
        msgbox_right = msgbox_rect.right
        right_distance = msgbox_right - msg_right  # 消息右边界到消息框右边界的距离
        
        # 方法2：使用消息左边界判断（好友发送的消息左边界更靠近消息框左边界）
        msg_left = control_rect.left
        msgbox_left = msgbox_rect.left
        left_distance = msg_left - msgbox_left  # 消息左边界到消息框左边界的距离
        
        # 方法3：使用消息中心点判断
        msg_center_x = (control_rect.left + control_rect.right) / 2
        msgbox_center_x = (msgbox_rect.left + msgbox_rect.right) / 2
        center_offset = msg_center_x - msgbox_center_x
        
        # 计算相对位置比例
        right_ratio = right_distance / msgbox_width  # 越小越靠右（自己发送），范围0-1
        left_ratio = left_distance / msgbox_width     # 越小越靠左（好友发送），范围0-1
        center_ratio = center_offset / (msgbox_width / 2) if msgbox_width > 0 else 0  # 正数=右侧，负数=左侧
        
        # 简化判断逻辑：直接使用边界距离比例
        # 自己发送的消息：right_ratio 应该较小（<0.3），left_ratio 应该较大（>0.3）
        # 好友发送的消息：left_ratio 应该较小（<0.3），right_ratio 应该较大（>0.3）
        
        # 计算自己发送的置信度
        if right_ratio < 0.4 and left_ratio > 0.2:
            # 右边界靠近右边界，左边界远离左边界，很可能是自己发送的
            self_confidence = (0.4 - right_ratio) / 0.4 * 0.6 + (left_ratio - 0.2) / 0.8 * 0.4
            if center_ratio > 0:
                self_confidence += min(center_ratio, 0.5) * 0.2
            return 'right', min(self_confidence, 1.0)
        
        # 计算好友发送的置信度
        if left_ratio < 0.4 and right_ratio > 0.2:
            # 左边界靠近左边界，右边界远离右边界，很可能是好友发送的
            friend_confidence = (0.4 - left_ratio) / 0.4 * 0.6 + (right_ratio - 0.2) / 0.8 * 0.4
            if center_ratio < 0:
                friend_confidence += min(abs(center_ratio), 0.5) * 0.2
            return 'left', min(friend_confidence, 1.0)
        
        # 如果边界判断不明确，使用中心点位置
        if abs(center_ratio) > 0.1:
            if center_ratio > 0:
                return 'right', min(abs(center_ratio), 0.6)
            else:
                return 'left', min(abs(center_ratio), 0.6)
        
        # 如果都不明确，使用更宽松的边界判断
        if right_ratio < left_ratio:
            # 右边界更靠近，可能是自己发送的
            return 'right', 0.4
        else:
            # 左边界更靠近，可能是好友发送的
            return 'left', 0.4
            
    except Exception as e:
        return None, 0.0

def parse_msg_attr(
    control: uia.Control,
    parent: 'ChatBox'
):
    # 注意：微信4.1的布局是：
    # - 如果消息在窗口左侧，是好友发送的（left -> friend）
    # - 如果消息在窗口右侧，是自己发送的（right -> self）
    msg_direction_hash = {
        'left': 'friend',  # 左侧是好友发送的
        'right': 'self'    # 右侧是自己发送的
    }
    if control.AutomationId:
        # 方法1：通过窗口位置检测（主要方法，基于消息框中心）
        window_direction, window_confidence = _detect_direction_by_window_position(control, parent)
        
        # 方法2：通过截图检测（使用基础版，返回的是距离，更可靠）
        msg_screenshot = control.ScreenShot()
        screenshot_direction, screenshot_distance = detect_message_direction(msg_screenshot)
        os.remove(msg_screenshot)
        
        # 方法3：通过控件位置检测（备用方法，用于验证）
        position_direction, position_confidence = _detect_direction_by_position(control, parent)
        
        # 综合判断：优先使用位置检测（最可靠），截图检测作为备用
        
        # 注意：截图检测返回的left/right表示气泡从哪个方向开始出现
        # left表示从左边开始出现（距离左边界的距离），right表示从右边开始出现（距离右边界的距离）
        # 如果left_idx < right_idx，说明从左边开始出现，气泡在左侧（好友发送）
        # 如果right_idx < left_idx，说明从右边开始出现，气泡在右侧（自己发送）
        # 但是，如果left_idx很大（>200）而right_idx很小（<50），说明气泡在右侧（自己发送）
        # 如果right_idx很大（>200）而left_idx很小（<50），说明气泡在左侧（好友发送）
        
        # 改进截图检测判断：如果距离差异很大，说明检测更可靠
        screenshot_reliable = False
        if screenshot_distance < 50:
            # 距离很小，非常明显
            screenshot_reliable = True
        elif screenshot_distance > 200:
            # 距离很大，可能是误判，但如果和位置检测一致，也可以使用
            screenshot_reliable = False
        
        # 1. 如果窗口位置检测有结果且置信度较高，优先使用（最可靠）
        if window_direction and window_confidence > 0.2:
            msg_direction = window_direction
            msg_direction_distence = window_confidence * 1000
        # 2. 如果位置检测有结果且置信度较高，使用位置检测
        elif position_direction and position_confidence > 0.3:
            msg_direction = position_direction
            msg_direction_distence = position_confidence * 1000
        # 3. 如果窗口位置检测和截图检测一致，使用窗口位置检测（更可靠）
        elif window_direction and window_direction == screenshot_direction:
            msg_direction = window_direction
            msg_direction_distence = window_confidence * 1000 if window_confidence > 0 else screenshot_distance
        # 4. 如果位置检测和截图检测一致，使用位置检测（更可靠）
        elif position_direction and position_direction == screenshot_direction:
            msg_direction = position_direction
            msg_direction_distence = position_confidence * 1000
        # 5. 如果截图检测距离很小（<50，非常明显），直接使用截图检测
        elif screenshot_reliable:
            msg_direction = screenshot_direction
            msg_direction_distence = screenshot_distance
        # 6. 如果窗口位置检测有结果（即使置信度较低），使用窗口位置检测
        elif window_direction:
            msg_direction = window_direction
            msg_direction_distence = window_confidence * 1000 if window_confidence > 0 else 100
        # 7. 如果位置检测有结果（即使置信度较低），使用位置检测
        elif position_direction:
            msg_direction = position_direction
            msg_direction_distence = position_confidence * 1000
        # 8. 如果截图检测距离合理（<200），使用截图检测
        elif screenshot_distance < 200:
            msg_direction = screenshot_direction
            msg_direction_distence = screenshot_distance
        # 9. 如果位置检测和截图检测不一致，优先使用位置检测（如果置信度足够）
        elif position_direction and position_confidence > 0.2:
            # 位置检测与截图检测不一致，优先使用位置检测
            msg_direction = position_direction
            msg_direction_distence = position_confidence * 1000
        # 10. 如果窗口位置检测有结果但置信度较低，仍然使用（比截图检测更可靠）
        elif window_direction and window_confidence > 0.2:
            msg_direction = window_direction
            msg_direction_distence = window_confidence * 1000
        # 9. 如果所有检测都不可靠，且截图检测距离很大（>=200），仍然使用截图检测
        # 因为位置检测可能完全失效，截图检测是唯一可用的方法
        else:
            # 即使距离很大，也使用截图检测（因为位置检测可能完全失效）
            msg_direction = screenshot_direction
            msg_direction_distence = screenshot_distance
        
        msg_attr = msg_direction_hash.get(msg_direction)

        additonal_attr = {
            'direction': msg_direction,
            'direction_distence': msg_direction_distence
        }
        
    else:
        msg_attr = 'system'

    if msg_attr == 'system':
        return SystemMessage(control, parent)
    elif msg_attr == 'friend':
        # return FriendMessage(control, parent)
        return parse_msg_type(control, parent, 'Friend', additonal_attr)
    elif msg_attr == 'self':
        # return SelfMessage(control, parent)
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