"""测试脚本：消息监听 - 后台线程 + 回调

启动后监听线程在后台持续运行，收到消息自动触发 on_message 回调。
按 Ctrl+C 退出。

用法：
    python test_listen_message.py
    python test_listen_message.py --target "文件传输助手"
    python test_listen_message.py --target "文件传输助手" --auto-reply "收到：{msg}"
"""

import argparse
import sys
from weixin4auto import WeChat


def on_message(msg, chat):
    """收到消息的回调"""
    # 过滤系统消息（时间分割线等）
    if msg.is_system:
        print(f"  [系统] {msg.content}")
        return
    
    # 显示消息来源
    if msg.is_self:
        sender = "我"
    elif hasattr(msg, 'sender') and msg.sender:
        sender = msg.sender
    else:
        sender = chat.who
    
    msg_type = getattr(msg, 'type', 'unknown')
    msg_attr = getattr(msg, 'attr', 'unknown')
    chat_label = "群聊" if chat.is_group else "私聊"
    sender_info = f"发送者: {sender}" if sender != "我" else "我"
    print(f"  [{sender_info}] [{chat_label}] [attr={msg_attr}] ({msg_type}) {msg.content}")

    # 图片消息自动下载
    if msg_type == 'image':
        result = msg.download()
        if result.is_success:
            print(f"  [下载] 图片已保存: {result['data']['path']}")
        else:
            print(f"  [下载] {result['message']}")


def main():
    parser = argparse.ArgumentParser(description="消息监听测试")
    parser.add_argument("--target", default="文件传输助手", help="监听对象（默认：文件传输助手）")
    parser.add_argument("--auto-reply", default=None, help="自动回复（{msg} 替换为消息内容）")
    args = parser.parse_args()

    print("=" * 50)
    print("消息监听测试")
    print("=" * 50)

    wx = WeChat(debug=True)  # 启用调试模式查看发送者检测日志
    print(f"昵称: {wx.nickname}")

    # 启动后台监听，block=True 阻塞主线程，Ctrl+C 退出
    print(f"监听已启动: {args.target}")
    print("等待消息中... (Ctrl+C 退出)\n")
    wx.ListenChats(
        nickname=args.target,
        callback=on_message,
        auto_reply=args.auto_reply,
        block=True,
        fetch_sender=False,
    )
    print("已退出")

    return 0


if __name__ == "__main__":
    sys.exit(main())
