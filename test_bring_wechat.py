"""测试脚本：唤起微信窗口到前台，并获取用户昵称

用法：
    python test_bring_wechat.py
"""

from weixin4auto import WeChat

def main():
    print("微信窗口唤起 & 昵称获取测试\n")
    
    # 初始化 WeChat，会自动唤起窗口并打印昵称
    wx = WeChat()
    
    print(f"\n昵称: {wx.nickname}")
    print("测试完成！")

if __name__ == "__main__":
    main()
