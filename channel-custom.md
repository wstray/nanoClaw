# 添加新 Channel 指南

## Context

nanoClaw 使用 channel 架构支持多种消息平台（目前有 Telegram 和 Console）。添加新 channel 需要遵循特定的接口模式并集成到 Gateway 中。

## 架构概览

```
┌─────────────────────────────────────────────────────────────┐
│                        Gateway                               │
│  - 管理所有 channel                                          │
│  - 路由消息到 Agent                                          │
│  - 处理主动消息（cron 任务）                                 │
└─────────────────────────────────────────────────────────────┘
         │                    │                    │
         ▼                    ▼                    ▼
    TelegramChannel    ConsoleChannel      [NewChannel]
         │                    │                    │
         └────────────────────┴────────────────────┘
                      通过 gateway.handle_incoming()
                                │
                                ▼
                             Agent
```

## 关键文件

| 文件 | 作用 |
|------|------|
| `nanoclaw/channels/telegram.py` | Telegram channel 实现参考（完整示例） |
| `nanoclaw/channels/console.py` | Console channel 实现参考（简单示例） |
| `nanoclaw/channels/gateway.py` | Gateway 消息路由器 |
| `nanoclaw/core/config.py` | 配置模型定义 |

## 添加新 Channel 的步骤

### Step 1: 创建 Channel 类文件

在 `nanoclaw/channels/` 下创建新文件，如 `discord.py`：

```python
"""New channel description."""

from __future__ import annotations
import asyncio
from typing import TYPE_CHECKING, Any, Optional

from nanoclaw.core.logger import get_logger

if TYPE_CHECKING:
    from nanoclaw.channels.gateway import Gateway
    from nanoclaw.core.config import NewChannelConfig

logger = get_logger(__name__)


class NewChannel:
    """新 Channel 的描述."""

    def __init__(self, config: "NewChannelConfig", gateway: "Gateway"):
        """
        初始化 Channel.

        Args:
            config: channel 配置
            gateway: Gateway 实例用于消息路由
        """
        self.config = config
        self.gateway = gateway
        # 初始化平台特定的客户端
        self.client: Any = None

    async def start(self) -> None:
        """启动 channel - 连接平台、注册处理器."""
        # 1. 初始化平台客户端
        # 2. 注册消息处理器
        # 3. 连接到平台
        logger.info("NewChannel started")

    async def _handle_message(self, ...) -> None:
        """
        处理传入消息 - 由平台 SDK 回调.

        核心逻辑：调用 gateway.handle_incoming()
        """
        response = await self.gateway.handle_incoming(
            channel_id="newchannel",      # channel 标识符
            user_id=user_id,              # 平台用户 ID
            message=message_text,         # 用户消息
            confirm_callback=self._ask_confirmation,  # 可选：确认回调
        )
        # 发送响应给用户
        await self._send_response(user_id, response)

    async def _ask_confirmation(self, question: str) -> bool:
        """
        可选：实现用户确认机制（如 Yes/No 按钮）.
        返回 True/False
        """
        # 平台特定的确认 UI 实现
        return True

    async def _send_response(self, user_id: str, response: str) -> None:
        """发送响应给用户."""
        # 处理长消息分割
        # 处理 markdown 格式
        pass

    async def send_proactive(self, text: str) -> None:
        """
        发送主动消息（由 cron 任务或后台任务调用）.
        """
        # 遍历已授权用户发送消息
        pass

    async def stop(self) -> None:
        """优雅关闭 - 清理资源."""
        logger.info("NewChannel stopped")
```

### Step 2: 添加配置模型

在 `nanoclaw/core/config.py` 中添加配置类：

```python
class NewChannelConfig(BaseModel):
    """新 channel 配置."""

    enabled: bool = False
    api_key: str = ""
    # 添加其他配置项...

    model_config = {"populate_by_name": True}
```

然后在 `ChannelsConfig` 类中添加字段：

```python
class ChannelsConfig(BaseModel):
    """Communication channels configuration."""

    telegram: TelegramConfig = Field(default_factory=TelegramConfig)
    newchannel: NewChannelConfig = Field(default_factory=NewChannelConfig)  # 新增
```

### Step 3: 在 Gateway 中注册

在 `nanoclaw/channels/gateway.py` 的 `start()` 方法中添加：

```python
async def start(self) -> None:
    """Start all components."""
    # ... 现有代码 ...

    # Start NewChannel if enabled
    if self.config.channels.newchannel.enabled:
        from nanoclaw.channels.newchannel import NewChannel

        newchannel = NewChannel(self.config.channels.newchannel, self)
        await newchannel.start()
        self.channels["newchannel"] = newchannel
        logger.info("NewChannel started")
```

### Step 4: 更新依赖

在 `pyproject.toml` 中添加平台 SDK 依赖（如需要）：

```toml
[project.dependencies]
platform-sdk = "x.x.x"
```

### Step 5: 添加配置示例

在项目 `config.example.json` 或文档中说明配置格式：

```json
{
  "channels": {
    "newchannel": {
      "enabled": true,
      "apiKey": "your-api-key"
    }
  }
}
```

## Channel 接口要求

每个 channel **必须**实现：

| 方法 | 必需 | 说明 |
|------|------|------|
| `__init__(config, gateway)` | ✅ | 初始化，接收配置和 gateway |
| `start()` | ✅ | 启动 channel，连接平台 |
| `stop()` | ✅ | 优雅关闭 |
| `send_proactive(text)` | ✅ | 发送主动消息（cron 用） |
| `_handle_message(...)` | ✅ | 处理平台消息，调用 `gateway.handle_incoming()` |

## 关键集成点

### 1. 消息路由
```python
response = await self.gateway.handle_incoming(
    channel_id="your_channel_id",
    user_id=str(platform_user_id),
    message=platform_message_text,
    confirm_callback=self._ask_confirmation,  # 可选
)
```

### 2. 确认回调（可选）
用于 shell 工具执行前的用户确认。返回 `bool`。

### 3. 主动消息
用于 cron 定时任务或后台通知发送消息给用户。

## 验证步骤

1. 安装依赖：`uv sync`
2. 配置 `~/.nanoclaw/config.json`
3. 启动：`uv run nanoclaw serve`
4. 测试发送消息
5. 测试 cron 主动消息：`uv run nanoclaw cron test "* * * * *" "test message"`

## 参考实现

- **Telegram** (`nanoclaw/channels/telegram.py`): 完整实现，包括确认按钮、长消息分割、Markdown 解析
- **Console** (`nanoclaw/channels/console.py`): 简化实现，适合学习和测试
