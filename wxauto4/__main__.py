import argparse
import sys
from .utils.useful import (
    authenticate,
    authenticate_with_file,
    get_licence_file,
    debug_license
)

def main():
    parser = argparse.ArgumentParser(description="wxauto plus V2命令行工具")
    subparsers = parser.add_subparsers(dest='command')
    
    # 授权相关命令
    parser.add_argument('--auth', '-a', type=str, help='使用wxauto plus V2的授权码进行授权')
    parser.add_argument('--auth-file', '-f', type=str, help='使用wxauto plus V2的授权文件进行授权')
    parser.add_argument('--export', '-e', action='store_true', help='导出wxauto plus V2的授权文件，发给管理员授权')
    parser.add_argument('--debug-license', '-d', action='store_true', help='导出wxauto plus V2的DEBUG授权文件，发给管理员授权')
    
    # send_msg 命令
    send_parser = subparsers.add_parser('send_msg', help='发送消息给指定联系人')
    send_parser.add_argument('target', type=str, help='聊天对象昵称')
    send_parser.add_argument('message', type=str, help='消息内容')
    send_parser.add_argument('--exact', action='store_true', default=True, help='精确匹配（默认开启）')
    send_parser.add_argument('--no-exact', dest='exact', action='store_false', help='模糊匹配')
    
    # send_files 命令
    file_parser = subparsers.add_parser('send_files', help='发送文件/图片给指定联系人')
    file_parser.add_argument('target', type=str, help='聊天对象昵称')
    file_parser.add_argument('files', type=str, nargs='+', help='文件路径（支持多个）')
    file_parser.add_argument('--exact', action='store_true', default=True, help='精确匹配（默认开启）')
    file_parser.add_argument('--no-exact', dest='exact', action='store_false', help='模糊匹配')
    
    args = parser.parse_args()

    if args.command == 'send_msg':
        from wxauto4 import WeChat
        try:
            wx = WeChat()
            resp = wx.SendMsg(msg=args.message, who=args.target, exact=args.exact)
            if resp.is_success:
                print(f'[成功] 已向 {args.target} 发送消息')
            else:
                msg = resp.get("message", "未知错误")
                if '未找到' in msg:
                    print(f'[失败] 找不到联系人「{args.target}」，请确认昵称是否正确')
                else:
                    print(f'[失败] {msg}')
        except Exception as e:
            print(f'[错误] {e}')
            sys.exit(1)
    elif args.command == 'send_files':
        from wxauto4 import WeChat
        import os
        try:
            # 校验文件
            for f in args.files:
                if not os.path.isfile(f):
                    print(f'[错误] 文件不存在：{f}')
                    sys.exit(1)
            wx = WeChat()
            resp = wx.SendFiles(filepath=args.files, who=args.target, exact=args.exact)
            if resp.is_success:
                names = ', '.join(os.path.basename(f) for f in args.files)
                print(f'[成功] 已向 {args.target} 发送文件：{names}')
            else:
                msg = resp.get("message", "未知错误")
                if '未找到' in msg:
                    print(f'[失败] 找不到联系人「{args.target}」，请确认昵称是否正确')
                else:
                    print(f'[失败] {msg}')
        except SystemExit:
            raise
        except Exception as e:
            print(f'[错误] {e}')
            sys.exit(1)
    elif args.auth:
        authenticate(args.auth)
    elif args.auth_file:
        authenticate_with_file(args.auth_file)
    elif args.export:
        get_licence_file()
    elif args.debug_license:
        debug_license()
    else:
        parser.print_help()

if __name__ == '__main__':
    main()
