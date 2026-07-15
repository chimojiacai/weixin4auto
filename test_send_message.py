"""测试脚本：发送文本消息 & 发送图片/文件

用法：
    # 测试发送文本（默认发给"文件传输助手"）
    python test_send_message.py

    # 指定发送对象
    python test_send_message.py --target "文件传输助手"

    # 只测试发送文本
    python test_send_message.py --text-only

    # 只测试发送文件（需要指定文件路径）
    python test_send_message.py --file-only --file-path "C:\\path\\to\\image.png"
"""

import argparse
import os
import sys
import time
from pathlib import Path

from weixin4auto import WeChat


def test_send_text(wx: WeChat, target: str) -> bool:
    """测试1：发送文本消息

    Args:
        wx: WeChat 实例
        target: 发送对象昵称

    Returns:
        bool: 是否发送成功
    """
    print("\n" + "=" * 50)
    print("测试1：发送文本消息")
    print("=" * 50)

    timestamp = time.strftime("%H:%M:%S")
    msg = f"[weixin4auto 自动化测试] 文本消息 - {timestamp}"

    print(f"  发送对象: {target}")
    print(f"  消息内容: {msg}")

    try:
        result = wx.SendMsg(msg=msg, who=target, exact=True)
        if result.is_success:
            print("  结果: 发送成功 ✓")
            return True
        else:
            print(f"  结果: 发送失败 ✗ - {result.get('message', '')}")
            return False
    except Exception as e:
        print(f"  结果: 发送异常 ✗ - {e}")
        return False


def test_send_file(wx: WeChat, target: str, file_path: str = None) -> bool:
    """测试2：发送图片或文件

    Args:
        wx: WeChat 实例
        target: 发送对象昵称
        file_path: 要发送的文件路径，为 None 时自动创建测试图片

    Returns:
        bool: 是否发送成功
    """
    print("\n" + "=" * 50)
    print("测试2：发送图片/文件")
    print("=" * 50)

    # 如果没有指定文件，创建一个简单的测试图片
    if file_path is None:
        file_path = _create_test_image()
        if file_path is None:
            print("  结果: 无法创建测试图片 ✗")
            return False
        print(f"  已自动生成测试图片: {file_path}")

    if not os.path.exists(file_path):
        print(f"  结果: 文件不存在 ✗ - {file_path}")
        return False

    file_size = os.path.getsize(file_path)
    print(f"  发送对象: {target}")
    print(f"  文件路径: {file_path}")
    print(f"  文件大小: {file_size / 1024:.1f} KB")

    try:
        result = wx.SendFiles(filepath=file_path, who=target, exact=True)
        if result.is_success:
            print("  结果: 发送成功 ✓")
            return True
        else:
            print(f"  结果: 发送失败 ✗ - {result.get('message', '')}")
            return False
    except Exception as e:
        print(f"  结果: 发送异常 ✗ - {e}")
        return False


def _create_test_image() -> str:
    """创建一个简单的测试图片，返回文件路径"""
    try:
        from PIL import Image, ImageDraw, ImageFont

        img = Image.new("RGB", (400, 200), color=(67, 160, 71))
        draw = ImageDraw.Draw(img)

        timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
        draw.text((20, 30), "weixin4auto Test", fill="white")
        draw.text((20, 80), timestamp, fill="white")
        draw.text((20, 130), "Auto Send Test", fill="white")

        save_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "wxauto_test_img.png")
        img.save(save_path)
        return save_path
    except ImportError:
        print("  警告: 未安装 Pillow，无法自动生成测试图片")
        print("  提示: 请使用 --file-path 参数手动指定文件路径")
        return None


def main():
    parser = argparse.ArgumentParser(description="发送消息测试脚本")
    parser.add_argument("--target", default="文件传输助手", help="发送对象昵称（默认：文件传输助手）")
    parser.add_argument("--text-only", action="store_true", help="只测试发送文本")
    parser.add_argument("--file-only", action="store_true", help="只测试发送文件")
    parser.add_argument("--file-path", default=None, help="要发送的文件路径（不指定则自动生成测试图片）")
    args = parser.parse_args()

    print("微信发送消息测试")
    print(f"目标聊天对象: {args.target}")

    # 初始化微信
    wx = WeChat()
    print(f"微信用户昵称: {wx.nickname}")

    results = {}

    # 测试1：发送文本
    if not args.file_only:
        results["发送文本"] = test_send_text(wx, args.target)
        time.sleep(1)

    # 测试2：发送文件/图片
    if not args.text_only:
        results["发送文件"] = test_send_file(wx, args.target, args.file_path)

    # 打印汇总
    print("\n" + "=" * 50)
    print("测试结果汇总")
    print("=" * 50)
    all_pass = True
    for name, passed in results.items():
        status = "通过 ✓" if passed else "失败 ✗"
        print(f"  {name}: {status}")
        if not passed:
            all_pass = False

    print("=" * 50)
    if all_pass:
        print("所有测试通过！")
    else:
        print("部分测试失败，请检查日志")

    return 0 if all_pass else 1


if __name__ == "__main__":
    sys.exit(main())
