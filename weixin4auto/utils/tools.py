from __future__ import annotations

from datetime import datetime, timedelta
from pathlib import Path
import math
import re
import shutil
import time

from PIL import Image

from weixin4auto.uia import uiautomation as uia

from .win32 import GetAllWindows

def get_file_dir(dir_path=None):
    if dir_path is None:
        dir_path = Path('.').absolute()
    elif isinstance(dir_path, str):
        dir_path = Path(dir_path)
    dir_path.mkdir(parents=True, exist_ok=True)
    return dir_path

def find_window_from_root(classname=None, name=None, pid:int=None, uiaclsname:str=None, timeout=1):
    t0 = time.time()
    while True:
        wins = find_all_windows_from_root(classname, name, pid, uiaclsname)
        if len(wins) > 0:
            return wins[0]
        if time.time() - t0 > timeout:
            return None

def find_all_windows_from_root(classname:str=None, name:str=None, pid:int=None, uiaclsname:str=None):
    windows = GetAllWindows()
    targets = []
    for window in windows:
        if (
            (all((classname, name)) and classname == window[1] and name == window[2])
            or (all((classname, not name)) and classname == window[1])
            or (all((not classname, name)) and name == window[2])
        ):
            targets.append(uia.ControlFromHandle(window[0]))
    if pid:
        targets = [w for w in targets if w.ProcessId == pid]
    if uiaclsname:
        targets = [w for w in targets if w.ClassName == uiaclsname]
    return targets

def now_time(fmt='%Y%m%d%H%M%S%f'):
    return datetime.now().strftime(fmt)
        
def parse_wechat_time(time_str):
    """
    时间格式转换函数

    Args:
        time_str: 输入的时间字符串

    Returns:
        转换后的时间字符串
    """
    time_str = time_str.replace('星期天', '星期日')
    match = re.match(r'^(\d{2})-(\d{2}) (\d{2}):(\d{2}):(\d{2})$', time_str)
    if match:
        month, day, hour, minute, second = match.groups()
        current_year = datetime.now().year
        return datetime(current_year, int(month), int(day), int(hour), int(minute), int(second)).strftime('%Y-%m-%d %H:%M:%S')
    
    match = re.match(r'^(\d{1,2}):(\d{1,2})$', time_str)
    if match:
        hour, minute = match.groups()
        return datetime.now().strftime('%Y-%m-%d') + f' {hour}:{minute}:00'

    match = re.match(r'^昨天 (\d{1,2}):(\d{1,2})$', time_str)
    if match:
        hour, minute = match.groups()
        yesterday = datetime.now() - timedelta(days=1)
        return yesterday.strftime('%Y-%m-%d') + f' {hour}:{minute}:00'

    match = re.match(r'^星期([一二三四五六日]) (\d{1,2}):(\d{1,2})$', time_str)
    if match:
        weekday, hour, minute = match.groups()
        weekday_num = ['一', '二', '三', '四', '五', '六', '日'].index(weekday)
        today_weekday = datetime.now().weekday()
        delta_days = (today_weekday - weekday_num) % 7
        target_day = datetime.now() - timedelta(days=delta_days)
        return target_day.strftime('%Y-%m-%d') + f' {hour}:{minute}:00'

    match = re.match(r'^(\d{4})年(\d{1,2})月(\d{1,2})日 (\d{1,2}):(\d{1,2})$', time_str)
    if match:
        year, month, day, hour, minute = match.groups()
        return datetime(*[int(i) for i in [year, month, day, hour, minute]]).strftime('%Y-%m-%d %H:%M:%S')
    
    match = re.match(r'^(\d{2})-(\d{2}) (上午|下午) (\d{1,2}):(\d{2})$', time_str)
    if match:
        month, day, period, hour, minute = match.groups()
        current_year = datetime.now().year
        hour = int(hour)
        if period == '下午' and hour != 12:
            hour += 12
        elif period == '上午' and hour == 12:
            hour = 0
        return datetime(current_year, int(month), int(day), hour, int(minute)).strftime('%Y-%m-%d %H:%M:%S')
    
    return time_str


def is_valid_image(file_path):
    path = Path(file_path)
    
    if not path.exists() or not path.is_file():
        return False

    try:
        with Image.open(path) as img:
            img.verify()  # 只验证图像，不会完全解码
        return True
    except Exception as e:
        return False

def delete_update_files():
    home = Path.home()
    update_dir = home / 'AppData' / 'Roaming' / 'Tencent' / 'xwechat' / 'update'
    if update_dir.exists():
        for file in update_dir.iterdir():
            shutil.rmtree(file) if file.is_dir() else file.unlink()


# ============================================================================================================================================
#                                                           消息解析方法
# ============================================================================================================================================

def detect_message_direction_by_color(
    image_path: str,
    green_threshold: float = 1.3,
) -> tuple:
    """通过气泡颜色判断消息方向。
    
    微信的气泡颜色：
    - 自己发的消息：绿色气泡 (RGB 中 G 通道明显高于 R 和 B)
    - 好友发的消息：白色/浅灰色气泡 (RGB 三通道接近)
    
    Args:
        image_path: 消息截图路径
        green_threshold: 绿色通道超过其他通道平均值的倍数阈值
    
    Returns:
        tuple: (direction, confidence) - 'left'/'right' 和置信度 (0-1)
    """
    try:
        img = Image.open(image_path)
        if img.mode != 'RGB':
            img = img.convert('RGB')
        w, h = img.size
        pixels = img.load()
        
        # 只扫描中间区域（避免边缘干扰）
        y_start = int(h * 0.2)
        y_end = int(h * 0.8)
        x_start = int(w * 0.1)
        x_end = int(w * 0.9)
        
        green_pixel_count = 0
        white_pixel_count = 0
        total_sampled = 0
        
        # 采样检测（每隔几个像素采样一次，提高性能）
        step = max(1, (x_end - x_start) // 100)
        for y in range(y_start, y_end, step):
            for x in range(x_start, x_end, step):
                r, g, b = pixels[x, y]
                total_sampled += 1
                
                # 检测绿色像素（微信自己发的消息气泡是绿色的）
                # 绿色特征：G 通道明显高于 R 和 B
                avg_rb = (r + b) / 2 if (r + b) > 0 else 1
                if g > avg_rb * green_threshold and g > 100:
                    green_pixel_count += 1
                
                # 检测白色/浅灰像素（好友消息气泡）
                # 白色特征：RGB 三通道都较高且接近
                if r > 200 and g > 200 and b > 200:
                    max_diff = max(r, g, b) - min(r, g, b)
                    if max_diff < 30:
                        white_pixel_count += 1
        
        if total_sampled == 0:
            return None, 0.0
        
        green_ratio = green_pixel_count / total_sampled
        white_ratio = white_pixel_count / total_sampled
        
        from weixin4auto.logger import wxlog
        wxlog.debug(f"[颜色检测] green_ratio={green_ratio:.4f}, white_ratio={white_ratio:.4f}, green_count={green_pixel_count}, white_count={white_pixel_count}")
        
        # 如果有明显的绿色像素，判断为自己发的（右侧）
        if green_ratio > 0.01:  # 绿色像素占比超过 1%
            confidence = min(green_ratio * 50, 1.0)  # 置信度基于绿色像素占比
            return 'right', confidence
        
        # 如果有大量白色像素但几乎没有绿色，判断为好友发的（左侧）
        if white_ratio > 0.05 and green_ratio < 0.005:
            confidence = min(white_ratio * 10, 1.0)
            return 'left', confidence
        
        return None, 0.0
    except Exception as e:
        return None, 0.0


def detect_message_direction_by_content_position(
    image_path: str,
    step: int = 2,
) -> tuple:
    """通过截图中内容像素的位置分布判断消息方向。
    
    原理：微信4.1的 UIA 控件宽度相同（全宽），但实际气泡在截图中的位置不同：
    - 自己发的消息：气泡在截图右侧，文本像素集中在右半边
    - 好友发的消息：气泡在截图左侧，文本像素集中在左半边
    
    通过分析非背景像素的左右分布来判断方向，与颜色检测互补。
    
    Args:
        image_path: 消息截图路径
        step: 采样步长（2=每2个像素采样一次）
    
    Returns:
        tuple: (direction, confidence) - 'left'/'right' 和置信度 (0-1)
    """
    try:
        img = Image.open(image_path)
        if img.mode != 'RGB':
            img = img.convert('RGB')
        w, h = img.size
        pixels = img.load()
        
        # 扫描区域：中间 60% 高度，跳过上下边缘
        y_start = int(h * 0.2)
        y_end = int(h * 0.8)
        # 跳过左右 5% 边缘（避免控件边界干扰）
        x_start = int(w * 0.05)
        x_end = int(w * 0.95)
        mid_x = (x_start + x_end) // 2
        
        left_content = 0
        right_content = 0
        
        for y in range(y_start, y_end, step):
            for x in range(x_start, x_end, step):
                r, g, b = pixels[x, y]
                brightness = (r + g + b) / 3
                max_c = max(r, g, b)
                min_c = min(r, g, b)
                
                # 判断是否为“背景”像素（聊天窗口底色）
                # 背景特征：非常亮（接近白色）或非常暗（接近黑色），且无色差
                is_bg = False
                if max_c - min_c < 20:  # 灰度像素（无色差）
                    if brightness > 235 or brightness < 20:
                        is_bg = True
                
                # 额外排除浅灰/浅绿背景（聊天窗口底色通常很均匀）
                # 如果颜色非常均匀（色差极小）且较亮，也是背景
                if max_c - min_c < 8 and brightness > 220:
                    is_bg = True
                
                if not is_bg:
                    if x < mid_x:
                        left_content += 1
                    else:
                        right_content += 1
        
        total = left_content + right_content
        if total < 20:  # 内容像素太少，无法判断
            return None, 0.0
        
        # 计算分布比例
        right_ratio = right_content / total
        left_ratio = left_content / total
        diff = abs(right_ratio - left_ratio)
        
        from weixin4auto.logger import wxlog
        wxlog.debug(f"[内容位置] left={left_content}, right={right_content}, diff={diff:.3f}")
        
        # 需要明显差异（>10%）才判断，避免误判
        if diff < 0.10:
            return None, 0.0
        
        if right_ratio > left_ratio:
            # 内容集中在右侧 → 自己发的消息
            confidence = min(diff * 3, 1.0)
            return 'right', confidence
        else:
            # 内容集中在左侧 → 好友发的消息
            confidence = min(diff * 3, 1.0)
            return 'left', confidence
            
    except Exception as e:
        return None, 0.0


def detect_message_direction(
    image_path: str,
    avatar_height_ratio: float = 0.8,
    tolerance: int = 5,  # 增加容忍度，从0改为5，提高检测准确性
) -> tuple[str, float]:
    """通过截图判断消息气泡的方向。

    Args:
        image_path: 消息截图路径。
        avatar_height_ratio: 头像在截图中占据的高度比例。
        tolerance: 像素颜色比较的容忍度。

    Returns:
        Tuple[str, float]: ``("left", distance)`` 或 ``("right", distance)``，
        ``distance`` 表示从对应方向开始出现气泡的列索引，便于后续定位。
    """

    img = Image.open(image_path)
    if img.mode != 'RGB':
        img = img.convert('RGB')
    w, h = img.size

    # 仅取中间 band 区域
    band_h = int(h * avatar_height_ratio)
    y0 = (h - band_h) // 2
    y1 = y0 + band_h

    pixels = img.load()  # 获取像素访问对象

    def is_uniform_column(x: int) -> bool:
        # 改进：使用多个采样点而不是只用一个参考点
        sample_points = [y0, (y0 + y1) // 2, y1 - 1]
        colors = [pixels[x, y] for y in sample_points]
        # 检查这些采样点的颜色是否一致
        base = colors[0]
        for color in colors[1:]:
            if (abs(color[0] - base[0]) > tolerance or
                abs(color[1] - base[1]) > tolerance or
                abs(color[2] - base[2]) > tolerance):
                return False
        return True

    # 从左边扫描（跳过前5%的列，避免边缘干扰）
    left_start = max(0, int(w * 0.05))
    left_idx = math.inf
    for x in range(left_start, w):
        if not is_uniform_column(x):
            left_idx = x
            break

    # 从右边扫描（跳过最后5%的列，避免边缘干扰）
    right_start = max(0, int(w * 0.95))
    right_idx = math.inf
    for offset, x in enumerate(range(w - 1, right_start - 1, -1)):
        if not is_uniform_column(x):
            right_idx = offset  # 距右边界的列数
            break

    # 改进判断逻辑：如果距离差异很小，使用更严格的判断
    # 如果 left_idx 和 right_idx 都很小，说明消息气泡在中间，需要更仔细判断
    if left_idx == math.inf and right_idx == math.inf:
        # 都没找到变化列，兜底
        return 'right', math.inf
    
    # 如果两个距离都很小（<50），说明可能是误判，需要更严格的判断
    if left_idx < 50 and right_idx < 50:
        # 选择距离更小的那个方向（更靠近边缘）
        if left_idx < right_idx:
            return 'left', float(left_idx)
        else:
            return 'right', float(right_idx)
    
    # 正常判断：选择距离更小的方向
    # 注意：left_idx 是从左边扫描的距离，right_idx 是从右边扫描的距离
    # 如果 left_idx 很大（>200），说明从左边扫描很远才找到，气泡在右侧（自己发送）
    # 如果 right_idx 很大（>200），说明从右边扫描很远才找到，气泡在左侧（好友发送）
    # 如果两者都很大（>200），说明气泡在中间，需要更仔细判断
    
    # 如果两者都很大（>200），可能是检测不准确，使用更宽松的判断
    if left_idx > 200 and right_idx > 200:
        # 选择距离更小的那个方向
        if left_idx < right_idx:
            return 'left', float(left_idx)
        else:
            return 'right', float(right_idx)
    
    # 正常判断：选择距离更小的方向
    if left_idx <= right_idx:
        return 'left', float(left_idx)
    return 'right', float(right_idx)

def calculate_pixel_variance(region):
    """
    计算图像区域的像素变化程度
    
    Args:
        region: PIL Image对象
    
    Returns:
        float: 像素变化程度的度量值
    """
    if region.size[0] == 0 or region.size[1] == 0:
        return 0
    
    # 获取所有像素值
    pixels = list(region.getdata())
    
    if not pixels:
        return 0
    
    # 分别计算R、G、B通道的方差
    r_values = [p[0] for p in pixels]
    g_values = [p[1] for p in pixels]
    b_values = [p[2] for p in pixels]
    
    r_variance = calculate_variance(r_values)
    g_variance = calculate_variance(g_values)
    b_variance = calculate_variance(b_values)
    
    return r_variance + g_variance + b_variance

def calculate_variance(values):
    """
    计算数值列表的方差
    
    Args:
        values: 数值列表
    
    Returns:
        float: 方差值
    """
    if not values:
        return 0
    
    # 计算平均值
    mean = sum(values) / len(values)
    
    # 计算方差
    variance = sum((x - mean) ** 2 for x in values) / len(values)
    
    return variance

def calculate_color_diversity(region):
    """
    计算区域颜色多样性（备用方法）
    
    Args:
        region: PIL Image对象
    
    Returns:
        float: 颜色多样性得分
    """
    pixels = list(region.getdata())
    
    if not pixels:
        return 0
    
    # 统计不同颜色的数量
    color_set = set(pixels)
    unique_colors = len(color_set)
    
    # 计算颜色多样性比例
    diversity_ratio = unique_colors / len(pixels)
    
    return diversity_ratio

def detect_message_direction_enhanced(
    image_path: str,
    avatar_width_ratio: float = 0.15,
    avatar_height_ratio: float = 0.8,
) -> tuple[str, float]:
    """
    增强版检测，结合方差和颜色多样性
    
    Args:
        image_path: 消息图片路径
        avatar_width_ratio: 头像区域宽度比例
        avatar_height_ratio: 头像区域高度比例
    
    Returns:
        str: 'left' 或 'right'
    """
    
    img = Image.open(image_path).convert('RGB')
    width, height = img.size
    
    avatar_width = int(width * avatar_width_ratio)
    avatar_height = int(height * avatar_height_ratio)
    avatar_start_y = (height - avatar_height) // 2
    avatar_end_y = avatar_start_y + avatar_height
    
    # 截取左右头像区域
    left_box = (0, avatar_start_y, avatar_width, avatar_end_y)
    right_box = (width - avatar_width, avatar_start_y, width, avatar_end_y)
    
    left_region = img.crop(left_box)
    right_region = img.crop(right_box)
    
    # 计算方差和颜色多样性
    left_variance = calculate_pixel_variance(left_region)
    right_variance = calculate_pixel_variance(right_region)
    
    left_diversity = calculate_color_diversity(left_region)
    right_diversity = calculate_color_diversity(right_region)
    
    # 综合评分（方差权重0.7，多样性权重0.3）
    left_score = left_variance * 0.7 + left_diversity * 1000 * 0.3
    right_score = right_variance * 0.7 + right_diversity * 1000 * 0.3
    
    if left_score > right_score:
        return 'left', float(left_score)
    return 'right', float(right_score)

def batch_detect_messages(image_paths, method='basic', **kwargs):
    """
    批量检测多条消息的方向
    
    Args:
        image_paths: 图片路径列表
        method: 检测方法 ('basic' 或 'enhanced')
        **kwargs: 传递给检测函数的额外参数
    
    Returns:
        list: 检测结果列表
    """
    results = []
    
    detect_func = detect_message_direction if method == 'basic' else detect_message_direction_enhanced

    for path in image_paths:
        try:
            result = detect_func(path, **kwargs)
            if isinstance(result, tuple):
                direction, distance = result
            else:
                direction, distance = result, None
            sender = '对方' if direction == 'left' else '自己'
            results.append({
                'path': path,
                'direction': direction,
                'sender': sender,
                'distance': distance,
            })
        except Exception as e:
            results.append({
                'path': path,
                'direction': 'unknown',
                'sender': '未知',
                'error': str(e)
            })
    
    return results


# ============================================================================================================================================
#                                                           消息解析方法End
# ============================================================================================================================================