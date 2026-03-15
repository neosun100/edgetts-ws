# edgetts-ws

[![Python](https://img.shields.io/badge/Python-3.9+-blue?logo=python&logoColor=white)](https://python.org)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)
[![Edge TTS](https://img.shields.io/badge/Edge_TTS-WebSocket-purple)](https://github.com/rany2/edge-tts)
[![aiohttp](https://img.shields.io/badge/aiohttp-3.9+-orange)](https://docs.aiohttp.org)

**[中文文档](README_CN.md)**

一个轻量级 HTTP API 服务，封装了微软 Edge TTS，提供**逐词级别的时间戳**。通过 WebSocket 连接 Bing TTS，返回合成音频（base64 MP3）以及每个词的精确时间数据（偏移量 + 持续时间，毫秒级），实现播放时实时逐词高亮。

## 工作原理

```
客户端 POST → server.py (aiohttp) → Edge TTS WebSocket → WordBoundary 事件 + 音频块
                                                                    ↓
                                                         JSON 或 NDJSON 流 → 客户端
```

微软 Edge TTS 通过 WebSocket API 流式推送音频块和 `WordBoundary` 事件（包含每个词的精确时间信息）。`edge_tts` Python 库负责处理 WebSocket 协议、DRM 令牌生成和 SSML 消息封装。本服务将其封装为简单的 HTTP API。

### 关键技术细节

- **协议**：`edge_tts` 库连接 `wss://speech.platform.bing.com/consumer/speech/synthesize/readaloud/edge/v1`
- **认证**：使用 `TrustedClientToken` + `Sec-MS-GEC` DRM 令牌（时间戳 + 令牌的 SHA-256 哈希）
- **时间戳**：`WordBoundary` 事件返回的偏移量/持续时间单位为 100 纳秒，本服务转换为毫秒（`/ 10000`）
- **音频格式**：MP3（audio-24khz-48kbitrate-mono-mp3）

## 功能特性

- 🎯 **逐词时间戳** — 每个词的精确偏移量 + 持续时间（毫秒）
- 🔊 **高质量 TTS** — 微软 Edge 神经网络语音
- ⚡ **流式模式** — NDJSON 流式输出，适用于低延迟场景
- 📦 **非流式模式** — 单次 JSON 响应，包含全部数据
- 🌐 **CORS 支持** — 可直接从浏览器前端调用
- 🎚️ **语速控制** — 可调节播放速度（0.5x–2.0x）
- 🎤 **多种语音** — 支持所有 Edge TTS 神经网络语音

## 快速开始

```bash
pip install -r requirements.txt
python server.py
# 服务启动在 http://0.0.0.0:8765
```

## API 接口

### `POST /v1/audio/speech`

**请求体：**

```json
{
  "input": "The celebrated theory is still the source of great controversy.",
  "voice": "en-US-AvaNeural",
  "speed": 0.8,
  "stream": false
}
```

| 字段 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `input` | string | *（必填）* | 要合成的文本 |
| `voice` | string | `en-US-AvaNeural` | Edge TTS 语音名称 |
| `speed` | number | `1.0` | 播放速度（0.5–2.0） |
| `stream` | boolean | `false` | 是否启用 NDJSON 流式输出 |

### 非流式响应（`stream: false`）

音频合成完成后返回单个 JSON 对象：

```json
{
  "audio": "<base64 编码的 MP3>",
  "content_type": "audio/mpeg",
  "timestamps": [
    { "text": "The", "offset": 100, "duration": 218.75 },
    { "text": "celebrated", "offset": 334.375, "duration": 750 },
    { "text": "theory", "offset": 1100, "duration": 593.75 }
  ]
}
```

### 流式响应（`stream: true`）

返回 NDJSON（每行一个 JSON 事件），数据从 WebSocket 到达时实时推送：

```jsonl
{"type":"word","text":"The","offset":100,"duration":218.75}
{"type":"word","text":"celebrated","offset":334.375,"duration":750}
{"type":"audio","data":"<base64 MP3 块>"}
{"type":"audio","data":"<base64 MP3 块>"}
{"type":"done"}
```

| 事件类型 | 说明 |
|---------|------|
| `word` | 词时间戳 — `text`（词文本）、`offset`（开始时间 ms）、`duration`（持续时间 ms） |
| `audio` | base64 编码的 MP3 音频块 |
| `done` | 合成完成，没有更多事件 |

## 逐词高亮（前端集成指南）

这是本 API 的核心使用场景。完整实现步骤：

### 第 1 步：将每个词渲染为独立的 span

```javascript
const sentence = "The celebrated theory is still the source of great controversy.";
const html = sentence.split(/(\s+)/).map((w, i) =>
  w.trim() ? `<span class="word" data-wi="${i}">${w}</span>` : w
).join('');
```

### 第 2 步：获取音频 + 时间戳

```javascript
const { audio, timestamps } = await fetch('/v1/audio/speech', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({ input: sentence, voice: 'en-US-AvaNeural', speed: 0.8 })
}).then(r => r.json());
```

### 第 3 步：播放音频并同步高亮

```javascript
const bin = Uint8Array.from(atob(audio), c => c.charCodeAt(0));
const player = new Audio(URL.createObjectURL(new Blob([bin], { type: 'audio/mpeg' })));

player.addEventListener('play', () => {
  const words = document.querySelectorAll('.word');
  (function tick() {
    if (player.paused) return;
    const ms = player.currentTime * 1000;
    let activeIdx = -1;
    for (let i = 0; i < timestamps.length; i++) {
      if (ms >= timestamps[i].offset && ms < timestamps[i].offset + timestamps[i].duration + 50)
        activeIdx = i;
    }
    words.forEach(w => {
      const tsIdx = Math.floor(parseInt(w.dataset.wi) / 2);
      w.classList.toggle('highlight', tsIdx === activeIdx);
    });
    requestAnimationFrame(tick);
  })();
});
player.play();
```

> ⚠️ **关键映射关系**：`split(/(\s+)/)` 产生 `[词, 空格, 词, 空格, ...]`，所以 `data-wi` 的值是 `0, 2, 4, 6, ...`。时间戳索引 = `Math.floor(wi / 2)`。

## 部署

### 使用 pm2（推荐）

```bash
pip install -r requirements.txt
pm2 start server.py --name edgetts-ws --interpreter python3
pm2 save
pm2 startup  # 开机自启
```

### Nginx 反向代理

```nginx
server {
    listen 80;
    server_name edgetts-ws.example.com;

    location / {
        proxy_pass http://127.0.0.1:8765;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_buffering off;  # 流式模式必须关闭缓冲
    }
}
```

> ⚠️ **`proxy_buffering off`** 是流式模式正常工作的必要条件。否则 Nginx 会缓冲整个响应后才发送给客户端。

## 可用语音

| 语音 | 口音 |
|------|------|
| `en-US-AvaNeural` | 🇺🇸 美式女声 |
| `en-US-AndrewNeural` | 🇺🇸 美式男声 |
| `en-GB-SoniaNeural` | 🇬🇧 英式女声 |
| `en-GB-RyanNeural` | 🇬🇧 英式男声 |
| `en-AU-WilliamNeural` | 🇦🇺 澳式男声 |

完整列表：`edge-tts --list-voices`

## 关联项目

| 项目 | 说明 |
|------|------|
| [edgetts-ws-worker](https://github.com/neosun100/edgetts-ws-worker) | 相同 API 的 Cloudflare Worker 版本（无服务器） |
| [pte-wfd-216](https://github.com/neosun100/pte-wfd-216) | 使用本 API 实现逐词高亮的完整示例应用 |

## 开发经验总结

1. **时间戳单位转换**：Edge TTS 返回的偏移量/持续时间单位是 100 纳秒，需要除以 10,000 转换为毫秒。
2. **流式模式需要 `proxy_buffering off`**：Nginx 默认会缓冲响应，导致 NDJSON 事件被批量发送而非逐行推送。
3. **`edge_tts` 库封装了所有 WebSocket 复杂性** — DRM 令牌、SSML 封装、重连机制。除非有特殊需求（参见 edgetts-ws-worker 的从零实现），否则不需要自己实现。

## 许可证

MIT
