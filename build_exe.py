"""打包 wxapi 为 exe 文件

前置条件：
    pip install pyinstaller

用法：
    python build_exe.py          # 打包（输出到 dist/wxapi/ 目录）
    python build_exe.py --onefile  # 打包为单文件（较慢）
"""

import argparse
import subprocess
import sys


def main():
    parser = argparse.ArgumentParser(description='打包 weixin4auto API 为 exe')
    parser.add_argument('--onefile', action='store_true', help='打包为单个 exe 文件（默认输出目录）')
    parser.add_argument('--clean', action='store_true', help='打包前清理 build/dist 目录')
    args = parser.parse_args()

    if args.clean:
        import shutil
        for d in ['build', 'dist']:
            try:
                shutil.rmtree(d)
                print(f'已清理 {d}/')
            except FileNotFoundError:
                pass

    cmd = [sys.executable, '-m', 'PyInstaller']

    if args.onefile:
        # 单文件模式：不使用 spec，直接用命令行参数
        cmd += [
            'run_api.py',
            '--name', 'wxapi',
            '--onefile',
            '--console',
            '--noconfirm',
            '--clean',
            '--hidden-import', 'win32gui',
            '--hidden-import', 'win32ui',
            '--hidden-import', 'win32api',
            '--hidden-import', 'win32con',
            '--hidden-import', 'win32process',
            '--hidden-import', 'win32clipboard',
            '--hidden-import', 'win32event',
            '--hidden-import', 'win32com',
            '--hidden-import', 'win32com.client',
            '--hidden-import', 'pythoncom',
            '--hidden-import', 'pywintypes',
            '--hidden-import', 'comtypes',
            '--hidden-import', 'comtypes.client',
            '--hidden-import', 'comtypes.stream',
            '--hidden-import', 'PIL',
            '--hidden-import', 'flask',
            '--hidden-import', 'jinja2',
            '--hidden-import', 'markupsafe',
            '--hidden-import', 'werkzeug',
            '--hidden-import', 'itsdangerous',
            '--hidden-import', 'requests',
            '--hidden-import', 'urllib3',
            '--hidden-import', 'certifi',
            '--hidden-import', 'tenacity',
            '--hidden-import', 'pyperclip',
            '--hidden-import', 'psutil',
            '--hidden-import', 'colorama',
            '--hidden-import', 'api',
            '--hidden-import', 'api.app',
            '--hidden-import', 'api.config',
            '--hidden-import', 'api.manager',
            '--hidden-import', 'weixin4auto',
            '--hidden-import', 'weixin4auto.wx',
            '--hidden-import', 'weixin4auto.uia.uiautomation',
            '--hidden-import', 'weixin4auto.utils.win32',
            '--add-data', 'weixin4auto;weixin4auto',
            '--add-data', 'api;api',
        ]
    else:
        # 目录模式：使用 spec 文件（推荐，速度更快）
        cmd += ['wxapi.spec', '--noconfirm']

    print(f'执行: {" ".join(cmd)}')
    result = subprocess.run(cmd)

    if result.returncode == 0:
        if args.onefile:
            print('\n✅ 打包成功！输出文件: dist/wxapi.exe')
            print('运行: dist\\wxapi.exe')
        else:
            print('\n✅ 打包成功！输出目录: dist/wxapi/')
            print('运行: dist\\wxapi\\wxapi.exe')
    else:
        print('\n❌ 打包失败，请检查错误信息', file=sys.stderr)
        sys.exit(1)


if __name__ == '__main__':
    main()
