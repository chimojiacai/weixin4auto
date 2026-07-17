# weixin4auto - 微信 4.1 自动化框架

<p align="center">
  <img src="https://img.shields.io/badge/Version-41.0.0-blue.svg" alt="Version">
  <img src="https://img.shields.io/badge/Python-3.9%2B%20%7C%203.13-blue.svg" alt="Python">
  <img src="https://img.shields.io/badge/Platform-Windows%2010+-lightgrey.svg" alt="Platform">
  <img src="https://img.shields.io/badge/WeChat-4.1-green.svg" alt="WeChat">
</p>

weixin4auto 是基于 Windows UI Automation 的微信 4.1 客户端自动化框架，提供 Python SDK 和 HTTP API 两种接入方式，支持消息收发、文件传输、实时监听、Webhook 转发等功能。

> **⚠️ 仅适用于微信 4.1 版本 Windows 客户端**

---

## 目录

- [安装](#安装)
- [快速开始](#快速开始)
- [Python SDK](#python-sdk)
  - [WeChat 主窗口](#1-初始化微信实例)
  - [发送消息](#2-发送消息)
  - [发送文件](#3-发送文件)
  - [监听消息](#4-监听消息)
  - [引用回复](#5-引用回复消息)
  - [会话管理](#6-会话管理)
  - [子窗口](#7-子窗口管理)
  - [消息对象](#8-消息对象)
- [HTTP API 服务](#http-api-服务)
- [项目结构](#项目结构)
- [常见问题](#常见问题)

---

## 安装

```bash
# 从 PyPI 安装
pip install weixin4auto

# 从 GitHub 安装
pip install git+https://github.com/cluic/weixin4auto.git

# 从源码安装（开发模式）
git clone https://github.com/cluic/weixin4auto.git
cd weixin4auto
pip install -e .
```

**依赖项：** `pywin32` `comtypes` `pillow` `psutil` `flask` `requests` `pyperclip` `tenacity`

---

## 快速开始

```python
from weixin4auto import WeChat

wx = WeChat()

# 发送消息
wx.SendMsg('你好！', who='文件传输助手')

# 发送文件
wx.SendFiles(r'C:\image.png', who='文件传输助手')

# 监听消息（阻塞模式）
wx.ListenChats('文件传输助手', callback=lambda msg, chat: print(f'[{chat.who}] {msg.content}'), block=True)
```

---

## Python SDK

### 1. 初始化微信实例

```python
from weixin4auto import WeChat

wx = WeChat()           # 自动连接已登录的微信主窗口
print(wx.nickname)      # 当前登录用户昵称
```

> 初始化前需确保微信 4.1 客户端已登录并处于前台或可唤起状态。

---

### 2. 发送消息

```python
# 发送给指定好友（自动搜索并切换聊天窗口）
wx.SendMsg('你好', who='好友昵称')

# 精确匹配（推荐，避免同名误匹配）
wx.SendMsg('你好', who='好友昵称', exact=True)

# 发送给当前聊天对象（不切换窗口）
wx.SendMsg('你好')

# @指定成员（群聊场景）
wx.SendMsg('开会了', who='群名', at=['张三', '李四'])
```

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `msg` | str | ✅ | 消息内容 |
| `who` | str | | 发送对象，不填则发给当前聊天 |
| `exact` | bool | | 是否精确匹配，默认 `False` |
| `at` | str/list | | @成员，支持字符串或列表 |

**返回值：** `WxResponse` 对象，通过 `.is_success` 判断是否成功。

---

### 3. 发送文件

```python
# 发送单个文件
wx.SendFiles(r'C:\report.pdf', who='好友昵称')

# 发送多个文件
wx.SendFiles([r'C:\a.png', r'C:\b.pdf'], who='好友昵称')

# 发送给当前聊天对象
wx.SendFiles(r'C:\image.png')
```

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `filepath` | str/list | ✅ | 文件绝对路径，支持单个或多个 |
| `who` | str | | 发送对象，不填则发给当前聊天 |
| `exact` | bool | | 是否精确匹配，默认 `False` |

---

### 4. 监听消息

#### AddListenChat - 添加单个监听

```python
def on_message(msg, chat):
    print(f'[{chat.who}] {msg.content}')
    if msg.content == 'ping':
        chat.SendMsg('pong')

wx.AddListenChat('好友昵称', on_message)
wx.KeepRunning()  # 阻塞等待，Ctrl+C 退出
```

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `nickname` | str | ✅ | 监听对象昵称 |
| `callback` | Callable | ✅ | 回调函数，接收 `(msg, chat)` |
| `fetch_sender` | bool | | 群聊是否获取真实发送者昵称，默认 `True` |

> 监听会将聊天窗口独立为子窗口，不影响主窗口操作。

#### ListenChats - 高层监听接口（推荐）

```python
# 简单缓存模式（消息自动缓存，后续通过 GetListenMessages 获取）
wx.ListenChats('文件传输助手')

# 自动回复
wx.ListenChats('文件传输助手', auto_reply='收到：{msg}')

# 自定义回调 + 阻塞
wx.ListenChats(
    ['张三', '李四'],
    callback=lambda msg, chat: print(msg.content),
    block=True
)
```

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `nickname` | str/list | ✅ | 监听对象，支持单个或多个 |
| `callback` | Callable | | 回调函数，不填则自动缓存消息 |
| `auto_reply` | str | | 自动回复模板，`{msg}` 替换为消息内容 |
| `block` | bool | | 是否阻塞当前线程，默认 `False` |
| `fetch_sender` | bool | | 群聊是否获取发送者昵称，默认 `True` |

#### 获取缓存消息

```python
# 获取指定聊天的缓存消息
msgs = wx.GetListenMessages('好友昵称')

# 获取所有监听的缓存消息
all_msgs = wx.GetListenMessages()
```

#### 停止监听

```python
wx.RemoveListenChat('好友昵称')   # 移除指定监听
wx.StopListening()                 # 停止所有监听
```

---

### 5. 引用回复消息

通过消息 ID 定位历史消息并发送引用回复（需先切换到对应聊天窗口或已在监听中）：

```python
# 获取消息对象
chat = wx.GetSubWindow('好友昵称')   # 从子窗口获取
# 或：先切换主窗口，再操作
wx.ChatWith('好友昵称')

# 通过消息 ID 查找并引用回复
msg = chat.GetMessageById('(12345, 67890)')
if msg:
    msg.quote('收到，马上处理')

# 或通过 hash 查找（需开启 WxParam.MESSAGE_HASH = True）
msg = chat.GetMessageByHash('a1b2c3d4e5f6...')
if msg:
    msg.quote('好的')
```

> **注意：** 仅支持可引用的消息类型（文本、图片等），系统消息、时间分割线不支持引用。

---

### 6. 会话管理

```python
# 切换主窗口到指定聊天
wx.ChatWith('好友昵称', exact=True)

# 获取当前会话列表
sessions = wx.GetSession()
for s in sessions:
    print(s.name, s.content)
```

---

### 7. 子窗口管理

子窗口是独立出去的聊天窗口，可以在不干扰主窗口的情况下操作。

```python
# 获取指定聊天的子窗口
chat = wx.GetSubWindow('好友昵称')
if chat:
    chat.SendMsg('通过子窗口发送的消息')
    print(chat.who)           # 聊天对象名称
    print(chat.is_group)      # 是否群聊

# 获取所有子窗口
all_chats = wx.GetAllSubWindow()
for chat in all_chats:
    print(chat.who)

# 关闭子窗口
chat.Close()
```

**Chat 对象方法：**

| 方法 | 说明 |
|------|------|
| `SendMsg(msg, ...)` | 发送消息（同 WeChat.SendMsg，`who`/`exact` 参数无效） |
| `SendFiles(filepath, ...)` | 发送文件（`who`/`exact` 参数无效） |
| `GetAllMessage()` | 获取窗口内所有消息 |
| `GetNewMessage()` | 获取新增消息 |
| `GetMessageById(id)` | 按 runtimeid 查找消息 |
| `GetMessageByHash(hash)` | 按 MD5 哈希查找消息 |
| `GetLastMessage()` | 获取最后一条消息 |
| `DetectGroupInfo()` | 检测群聊信息（成员数等） |
| `Close()` | 关闭窗口 |

---

### 8. 消息对象

`GetAllMessage()` / `GetNewMessage()` 返回消息对象列表，每条消息包含以下属性：

| 属性 | 类型 | 说明 |
|------|------|------|
| `content` | str | 消息内容 |
| `type` | str | 消息类型：`text` / `image` / `voice` / `video` / `file` / `card` / `link` / `location` / `emoji` / `quote` |
| `attr` | str | 消息来源：`self`（自己）/ `friend`（对方）/ `system`（系统） |
| `sender` | str | 发送者昵称（群聊中为真实昵称） |
| `is_self` | bool | 是否自己发送 |
| `is_system` | bool | 是否系统消息 |
| `time` | str | 消息时间 |
| `id` | tuple | 消息 runtimeid，可用于引用回复 |
| `hash` | str | 消息 MD5 哈希（需开启 `WxParam.MESSAGE_HASH`） |

**消息对象方法：**

| 方法 | 说明 |
|------|------|
| `quote(text)` | 引用该消息并发送回复 |
| `download()` | 下载图片/文件消息（返回本地路径） |
| `to_text()` | 语音消息转文字 |

```python
for msg in wx.GetAllMessage():
    if msg.type == 'text':
        print(msg.content)
    elif msg.type == 'image':
        result = msg.download()
        if result.is_success:
            print(f'图片已保存: {result["data"]["path"]}')
    elif msg.type == 'voice':
        text = msg.to_text()
        print(f'语音转文字: {text}')
```

---

## HTTP API 服务

项目内置基于 Flask 的 HTTP API 服务，适合远程调用或跨语言集成。

### 启动

```bash
# 命令行启动（默认 0.0.0.0:5000）
wxapi

# 或
python -m api

# 环境变量配置
WXAPI_PORT=8080 WXAPI_DEBUG=true python -m api
```

### 接口一览

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/status` | 获取微信连接状态 |
| POST | `/api/message/send` | 发送文本消息 |
| POST | `/api/message/quote` | 引用回复消息 |
| POST | `/api/file/send` | 发送文件（支持路径/base64/URL） |
| POST | `/api/listen/start` | 启动聊天监听 |
| POST | `/api/listen/stop` | 停止监听 |
| GET | `/api/listen/messages` | 获取监听缓存消息 |
| POST | `/api/webhook/add` | 添加消息转发地址 |
| POST | `/api/webhook/remove` | 移除转发地址 |
| GET | `/api/webhook/list` | 查看已配置转发 |
| GET | `/api/file/<filename>` | 下载文件（图片消息存放目录） |
| GET | `/api/files` | 列出下载目录文件 |
| POST | `/api/chat/switch` | 切换主窗口聊天 |
| GET | `/api/sessions` | 获取会话列表 |

### 请求示例

**发送消息：**
```bash
curl -X POST http://localhost:5000/api/message/send \
  -H "Content-Type: application/json" \
  -d '{"who": "文件传输助手", "msg": "你好"}'
```

**发送文件（三种方式）：**
```bash
# 文件路径
curl -X POST http://localhost:5000/api/file/send \
  -H "Content-Type: application/json" \
  -d '{"who": "文件传输助手", "filepath": "C:/image.png"}'

# base64 编码
curl -X POST http://localhost:5000/api/file/send \
  -H "Content-Type: application/json" \
  -d '{"who": "文件传输助手", "file_base64": "iVBORw0KGgo...", "filename": "photo.png"}'

# URL 下载
curl -X POST http://localhost:5000/api/file/send \
  -H "Content-Type: application/json" \
  -d '{"who": "文件传输助手", "file_url": "https://example.com/image.png"}'
```

**启动监听 + Webhook 转发：**
```bash
curl -X POST http://localhost:5000/api/listen/start \
  -H "Content-Type: application/json" \
  -d '{"who": ["张三", "李四"], "webhook_url": "http://your-server/webhook"}'
```

### Webhook 推送格式

监听启动后，收到消息会实时 POST 到配置的 webhook 地址：

```json
{
  "chat": "好友昵称",
  "is_group": false,
  "type": "text",
  "attr": "friend",
  "content": "消息内容",
  "id": "(12345, 67890)",
  "hash": "a1b2c3d4e5f6...",
  "is_self": false,
  "is_system": false,
  "sender": "发送者昵称",
  "time": "2026-01-01 12:00:00"
}
```

> 详细接口文档见 [api/README.md](api/README.md)

---

## 项目结构

```
wxauto4/
├── weixin4auto/          # 核心自动化库
│   ├── ui/               # UI 控件封装
│   │   ├── main.py       #   主窗口 / 子窗口管理
│   │   ├── chatbox.py    #   聊天区域（消息列表、输入框）
│   │   ├── sessionbox.py #   会话列表
│   │   ├── navigationbox.py  #   导航栏
│   │   ├── component.py  #   通用组件（右键菜单等）
│   │   └── base.py       #   基础 UI 窗口类
│   ├── msgs/             # 消息类型定义
│   │   ├── msg.py        #   消息解析（多类型识别）
│   │   ├── base.py       #   消息基类（quote/download）
│   │   ├── mtype.py      #   具体消息类型
│   │   └── parse.py      #   消息列表解析
│   ├── utils/            # 工具函数
│   │   ├── win32.py      #   Win32 API 封装
│   │   ├── lock.py       #   进程/线程锁（uilock 装饰器）
│   │   └── tools.py      #   消息方向检测等
│   ├── wx.py             # WeChat / Chat 类（对外 API）
│   ├── param.py          # 全局参数配置
│   └── ui_config.py      # UI 控件类名配置
├── api/                  # HTTP API 服务
│   ├── app.py            #   Flask 路由定义
│   ├── manager.py        #   WeChat 实例管理器（单例）
│   ├── config.py         #   API 配置
│   └── __main__.py       #   python -m api 入口
├── pyproject.toml        # 项目配置
└── README.md
```

---

## 常见问题

**Q: 提示"未找到已登录的微信主窗口"？**  
A: 确保微信 4.1 客户端已登录，且窗口未被最小化到托盘。

**Q: SendMsg 发送给了错误的好友？**  
A: 使用 `exact=True` 参数进行精确匹配，避免同名好友误匹配。

**Q: 监听消息回调中能否发送消息？**  
A: 可以。回调中的 `chat` 对象支持 `SendMsg()` / `SendFiles()`，直接在子窗口操作，不影响主窗口。

**Q: 如何获取群聊中的真实发送者？**  
A: `AddListenChat` 的 `fetch_sender=True`（默认）会自动通过头像弹窗获取真实发送者昵称。

**Q: HTTP API 如何打包为 exe？**  
A: 项目支持 PyInstaller 打包，详见 [api/README.md](api/README.md) 中的打包章节。

---

## 免责声明

本工具仅供学习和研究使用，使用者应当遵守相关法律法规。作者不对因使用本工具而产生的任何法律责任承担责任。
