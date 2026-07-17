# -*- mode: python ; coding: utf-8 -*-
"""
PyInstaller spec 文件 - weixin4auto API 服务打包

用法：
    pyinstaller wxapi.spec
"""

import os
import sys
from pathlib import Path

block_cipher = None
project_root = SPECPATH

# ── 收集所有需要打包的 Python 模块 ──────────────────────────

hidden_imports = [
    # pywin32
    'win32gui',
    'win32ui',
    'win32api',
    'win32con',
    'win32process',
    'win32clipboard',
    'win32event',
    'win32com',
    'win32com.client',
    'pythoncom',
    'pywintypes',
    # comtypes
    'comtypes',
    'comtypes.client',
    'comtypes.stream',
    # PIL
    'PIL',
    'PIL.Image',
    # Flask 生态
    'flask',
    'jinja2',
    'markupsafe',
    'werkzeug',
    'itsdangerous',
    'click',
    'blinker',
    # requests
    'requests',
    'urllib3',
    'certifi',
    'charset_normalizer',
    'idna',
    # 其他
    'tenacity',
    'pyperclip',
    'psutil',
    'colorama',
    # api 包
    'api',
    'api.app',
    'api.config',
    'api.manager',
    # weixin4auto 包
    'weixin4auto',
    'weixin4auto.wx',
    'weixin4auto.param',
    'weixin4auto.logger',
    'weixin4auto.moment',
    'weixin4auto.exceptions',
    'weixin4auto.languages',
    'weixin4auto.ui_config',
    'weixin4auto.ui',
    'weixin4auto.ui.base',
    'weixin4auto.ui.main',
    'weixin4auto.ui.sessionbox',
    'weixin4auto.ui.chatbox',
    'weixin4auto.ui.navigationbox',
    'weixin4auto.ui.component',
    'weixin4auto.uia',
    'weixin4auto.uia.uiautomation',
    'weixin4auto.utils',
    'weixin4auto.utils.lock',
    'weixin4auto.utils.tools',
    'weixin4auto.utils.useful',
    'weixin4auto.utils.win32',
    'weixin4auto.msgs',
    'weixin4auto.msgs.base',
    'weixin4auto.msgs.friend',
    'weixin4auto.msgs.mattr',
    'weixin4auto.msgs.msg',
    'weixin4auto.msgs.mtype',
    'weixin4auto.msgs.parse',
    'weixin4auto.msgs.self',
]

# ── 收集 pywin32 DLLs ────────────────────────────────────────

binaries = []
try:
    import pywintypes
    import pythoncom
    pywin32_dir = os.path.dirname(pywintypes.__file__)
    for dll in os.listdir(pywin32_dir):
        if dll.endswith('.dll'):
            binaries.append((os.path.join(pywin32_dir, dll), '.'))
    com_dir = os.path.dirname(pythoncom.__file__)
    for dll in os.listdir(com_dir):
        if dll.endswith('.dll'):
            binaries.append((os.path.join(com_dir, dll), '.'))
except Exception:
    pass

# ── 收集 Flask/Jinja2 模板文件 ───────────────────────────────

datas = []
try:
    import flask
    flask_dir = os.path.dirname(flask.__file__)
    flask_tpl = os.path.join(flask_dir, 'templates')
    if os.path.isdir(flask_tpl):
        datas.append((flask_tpl, 'flask/templates'))
except Exception:
    pass

a = Analysis(
    [os.path.join(project_root, 'run_api.py')],
    pathex=[project_root],
    binaries=binaries,
    datas=datas,
    hiddenimports=hidden_imports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=['tkinter', 'matplotlib', 'scipy', 'numpy', 'pandas'],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='wxapi',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=True,
    icon=None,
    version=None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='wxapi',
)
