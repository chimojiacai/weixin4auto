# weixin4auto API 服务

基于 Flask 封装的微信自动化 HTTP API，提供消息发送、聊天监听、消息转发等能力。

## 快速启动

```bash
# 安装依赖
pip install flask requests

# 启动（默认 0.0.0.0:5000）
python run_api.py

# 自定义端口
python run_api.py --port 8080

# 调试模式
python run_api.py --debug
```

也支持环境变量配置：

```bash
WXAPI_PORT=8080 python -m api
```

---

## 接口文档

### 统一响应格式

```json
{
  "success": true,
  ...
}
```

---

### 1. 状态

#### `GET /api/status`

获取微信连接状态。

**响应示例：**
```json
{ "success": true, "data": { "nickname": "你的昵称" } }
```

---

### 2. 发送消息

#### `POST /api/message/send`

发送文本消息。

**请求体：**
| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| who | string | ✅ | 发送对象昵称 |
| msg | string | ✅ | 消息内容 |
| at | string / list | | @对象 |
| exact | bool | | 是否精确匹配，默认 false |

**示例：**
```bash
curl -X POST http://localhost:5000/api/message/send \
  -H "Content-Type: application/json" \
  -d '{"who": "文件传输助手", "msg": "你好"}'
```

```bash
# @某人
curl -X POST http://localhost:5000/api/message/send \
  -H "Content-Type: application/json" \
  -d '{"who": "群名", "msg": "开会了", "at": ["张三", "李四"]}'
```

---

### 3. 引用回复消息

#### `POST /api/message/quote`

引用指定消息并发送回复。

**请求体：**
| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| who | string | ✅ | 聊天对象昵称 |
| msg_id | string | ✅ | 要引用的消息 ID（支持 `id` 或 `hash`，从监听消息中获取） |
| msg | string | ✅ | 回复内容 |
| exact | bool | | 是否精确匹配，默认 true |

**示例：**
```bash
curl -X POST http://localhost:5000/api/message/quote \
  -H "Content-Type: application/json" \
  -d '{"who": "文件传输助手", "msg_id": "a1b2c3d4e5f6...", "msg": "收到，马上处理"}'
```

**响应示例：**
```json
{ "success": true, "message": "success" }
```

> **说明：**  
> - `msg_id` 支持两种格式：监听消息返回的 `hash`（32位 MD5）或 `id`（runtimeid）
> - 如果已在监听中的聊天，直接在子窗口操作；否则会自动切换主窗口
> - 仅支持可引用的消息类型（文本、图片等，系统消息不支持）

---

### 4. 发送文件

#### `POST /api/file/send`

发送文件或图片，支持三种文件来源（三选一）。

**请求体：**
| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| who | string | ✅ | 发送对象昵称 |
| filepath | string / list | | 文件绝对路径或路径列表 |
| file_base64 | string | | 文件 base64 编码内容，需配合 `filename` |
| filename | string | | base64 模式的文件名（含扩展名） |
| file_url | string | | 文件下载地址 |
| exact | bool | | 是否精确匹配，默认 false |

> **注意：** `filepath` / `file_base64` / `file_url` 三选一。  
> `base64` 和 `url` 模式会先存为临时文件，发送成功后自动删除。

**示例：**
```bash
# 方式1：直接文件路径
curl -X POST http://localhost:5000/api/file/send \
  -H "Content-Type: application/json" \
  -d '{"who": "文件传输助手", "filepath": "C:/image.png"}'

# 方式2：base64 编码
curl -X POST http://localhost:5000/api/file/send \
  -H "Content-Type: application/json" \
  -d '{"who": "文件传输助手", "file_base64": "iVBORw0KGgo...", "filename": "photo.png"}'

# 方式3：URL 下载
curl -X POST http://localhost:5000/api/file/send \
  -H "Content-Type: application/json" \
  -d '{"who": "文件传输助手", "file_url": "https://example.com/image.png"}'

# 发送多个文件
curl -X POST http://localhost:5000/api/file/send \
  -H "Content-Type: application/json" \
  -d '{"who": "文件传输助手", "filepath": ["C:/a.png", "C:/b.pdf"]}'
```

---

### 5. 消息监听

#### `POST /api/listen/start`

启动对指定聊天的监听，可选配置 webhook 实时转发。

**请求体：**
| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| who | string / list | ✅ | 监听对象，支持单个或批量 |
| webhook_url | string | | 消息实时转发地址 |
| fetch_sender | bool | | 群聊是否获取发送者昵称，默认 true |

**示例：**
```bash
# 监听单个聊天
curl -X POST http://localhost:5000/api/listen/start \
  -H "Content-Type: application/json" \
  -d '{"who": "文件传输助手", "webhook_url": "http://your-server/webhook"}'

# 批量监听
curl -X POST http://localhost:5000/api/listen/start \
  -H "Content-Type: application/json" \
  -d '{"who": ["张三", "李四"]}'
```

---

#### `POST /api/listen/stop`

停止监听。

**请求体：**
| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| nickname | string | | 指定停止的昵称，不传则停止全部 |
| close_window | bool | | 是否关闭子窗口，默认 true |

**示例：**
```bash
# 停止指定监听
curl -X POST http://localhost:5000/api/listen/stop \
  -H "Content-Type: application/json" \
  -d '{"who": "文件传输助手"}'

# 停止全部
curl -X POST http://localhost:5000/api/listen/stop \
  -H "Content-Type: application/json" \
  -d '{}'
```

---

#### `GET /api/listen/messages`

获取监听缓存中的消息。

**Query 参数：**
| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| nickname | string | | 指定聊天对象，不传返回全部 |
| clear | bool | | 获取后是否清空缓存，默认 true |

**示例：**
```bash
# 获取指定聊天的消息
curl "http://localhost:5000/api/listen/messages?nickname=文件传输助手"

# 获取全部消息，不清空缓存
curl "http://localhost:5000/api/listen/messages?clear=false"
```

**响应示例：**
```json
{
  "success": true,
  "count": 2,
  "messages": [
    {
      "chat": "文件传输助手",
      "is_group": false,
      "type": "text",
      "attr": "friend",
      "content": "你好",
      "id": "(12345, 67890)",
      "hash": "a1b2c3d4e5f6...",
      "is_self": false,
      "is_system": false,
      "sender": "文件传输助手",
      "time": "2026-07-17 10:30:22"
    }
  ]
}
```

---

### 6. Webhook 消息转发

监听启动时可配置 `webhook_url`，收到消息会实时 POST 到目标地址。也可以单独管理 webhook。

#### `POST /api/webhook/add`

为已有监听追加转发地址。

**请求体：**
| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| nickname | string | ✅ | 聊天对象昵称，`"*"` 表示所有 |
| webhook_url | string | ✅ | 转发目标 URL |

---

#### `POST /api/webhook/remove`

移除转发地址。

**请求体：**
| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| nickname | string | ✅ | 聊天对象昵称 |
| webhook_url | string | ✅ | 要移除的 URL |

---

#### `GET /api/webhook/list`

查看已配置的转发地址。

**Query 参数：**
| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| nickname | string | | 指定昵称，不传返回全部 |

---

### 7. 文件下载目录

#### `GET /api/file/<filename>`

访问下载目录中的文件（图片消息自动下载后存放于此）。

**示例：**
```
GET http://localhost:5000/api/file/wxauto_image_20260715203810487816.jpg
```

---

#### `GET /api/files`

列出下载目录中的所有文件。

**响应示例：**
```json
{
  "success": true,
  "count": 2,
  "files": [
    {"name": "wxauto_image_xxx.jpg", "size": 12345, "url": "/api/file/wxauto_image_xxx.jpg"}
  ]
}
```

---

### 8. 会话管理

#### `POST /api/chat/switch`

切换主窗口到指定聊天。

**请求体：**
| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| who | string | ✅ | 聊天对象昵称 |
| exact | bool | | 是否精确匹配，默认 true |

---

#### `GET /api/sessions`

获取当前会话列表。

---

## Webhook 推送格式

消息实时转发时，POST 请求体为 JSON：

```json
{
  "chat": "群名或昵称",
  "is_group": false,
  "type": "text",
  "attr": "friend",
  "content": "消息内容",
  "id": "(12345, 67890)",
  "hash": "a1b2c3d4e5f6...",
  "is_self": false,
  "is_system": false,
  "sender": "发送者昵称",
  "time": "2026-07-17 10:30:22"
}
```

| 字段 | 说明 |
|------|------|
| chat | 所属聊天窗口名称 |
| is_group | 是否群聊 |
| type | 消息类型：text / image / voice / card 等 |
| attr | 消息属性：self / friend / system |
| content | 消息内容（字符串） |
| id | 消息 runtimeid（可用于引用回复） |
| hash | 消息 MD5 哈希（可用于引用回复） |
| is_self | 是否自己发送 |
| is_system | 是否系统消息（时间分割线等） |
| sender | 发送者昵称 |
| time | 消息时间 |

---

## 目录结构

```
api/
├── __init__.py      # 包入口
├── __main__.py      # python -m api 入口
├── app.py           # Flask 路由定义
├── config.py        # 配置（支持环境变量覆盖）
└── manager.py       # WeChat 实例管理器（单例）
run_api.py           # 启动脚本（支持命令行参数）
wxapi.spec           # PyInstaller 打包配置
build_exe.py         # 打包辅助脚本
```

---

## 打包为 exe

### 安装 PyInstaller

```bash
pip install pyinstaller
```

### 打包

```bash
# 目录模式（推荐，启动更快）
python build_exe.py

# 单文件模式（输出单个 wxapi.exe）
python build_exe.py --onefile

# 清理旧产物后打包
python build_exe.py --clean
```

### 输出

| 模式 | 输出路径 | 运行方式 |
|------|----------|----------|
| 目录模式 | `dist/wxapi/wxapi.exe` | `dist\wxapi\wxapi.exe` |
| 单文件模式 | `dist/wxapi.exe` | `dist\wxapi.exe` |

### 运行

```bash
# 默认启动（0.0.0.0:5000）
dist\wxapi\wxapi.exe

# 支持环境变量
WXAPI_PORT=8080 dist\wxapi\wxapi.exe
```

> **注意：** 打包后的 exe 必须在安装了微信客户端的 Windows 机器上运行，启动前会自动检测微信是否已登录。
