# edgetts-ws

[![Python](https://img.shields.io/badge/Python-3.9+-blue?logo=python&logoColor=white)](https://python.org)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)
[![Edge TTS](https://img.shields.io/badge/Edge_TTS-WebSocket-purple)](https://github.com/rany2/edge-tts)

A lightweight HTTP API server that wraps Microsoft Edge TTS with **word-level timestamps**. Returns synthesized audio (base64 MP3) along with per-word timing data (offset + duration in milliseconds), enabling real-time word-by-word highlighting during playback.

## How It Works

Microsoft Edge TTS exposes a WebSocket API that streams audio chunks alongside `WordBoundary` events containing precise timing for each spoken word. This server collects both, then returns them as either a single JSON response or a streaming NDJSON response.

```
Client POST → server.py → Edge TTS WebSocket → WordBoundary events + audio chunks
                                                         ↓
                                              JSON or NDJSON stream
```

## Features

- 🎯 **Word-level timestamps** — precise offset + duration in milliseconds for each word
- 🔊 **High-quality TTS** — powered by Microsoft Edge neural voices
- ⚡ **Streaming mode** — NDJSON streaming for low-latency applications
- 📦 **Non-streaming mode** — single JSON response with all data
- 🌐 **CORS enabled** — ready for browser-based frontends
- 🎚️ **Speed control** — adjustable playback speed (0.5x–2.0x)
- 🎤 **Multiple voices** — all Edge TTS neural voices supported

## Quick Start

```bash
pip install -r requirements.txt
python server.py
```

Server starts on `http://0.0.0.0:8765`.

## API

### `POST /v1/audio/speech`

**Request:**

```json
{
  "input": "The celebrated theory is still the source of great controversy.",
  "voice": "en-US-AvaNeural",
  "speed": 0.8,
  "stream": false
}
```

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `input` | string | *(required)* | Text to synthesize |
| `voice` | string | `en-US-AvaNeural` | Edge TTS voice name |
| `speed` | number | `1.0` | Playback speed (0.5–2.0) |
| `stream` | boolean | `false` | Enable NDJSON streaming |

### Non-Streaming Response (`stream: false`)

```json
{
  "audio": "<base64-encoded MP3>",
  "content_type": "audio/mpeg",
  "timestamps": [
    { "text": "The", "offset": 100, "duration": 218.75 },
    { "text": "celebrated", "offset": 334.375, "duration": 750 },
    { "text": "theory", "offset": 1100, "duration": 593.75 }
  ]
}
```

### Streaming Response (`stream: true`)

Returns NDJSON (newline-delimited JSON), one event per line:

```jsonl
{"type":"word","text":"The","offset":100,"duration":218.75}
{"type":"word","text":"celebrated","offset":334.375,"duration":750}
{"type":"audio","data":"<base64 MP3 chunk>"}
{"type":"audio","data":"<base64 MP3 chunk>"}
{"type":"done"}
```

Event types:
- `word` — word timestamp (arrives before/during audio)
- `audio` — base64-encoded MP3 audio chunk
- `done` — synthesis complete

### Timestamp Fields

| Field | Type | Description |
|-------|------|-------------|
| `text` | string | The word spoken |
| `offset` | number | Start time in milliseconds from audio beginning |
| `duration` | number | How long the word is spoken in milliseconds |

## Frontend Usage Example

```javascript
// Non-streaming
const resp = await fetch('/v1/audio/speech', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({ input: 'Hello world.', voice: 'en-US-AvaNeural', speed: 1.0 })
});
const { audio, timestamps } = await resp.json();
const bin = Uint8Array.from(atob(audio), c => c.charCodeAt(0));
const player = new Audio(URL.createObjectURL(new Blob([bin], { type: 'audio/mpeg' })));

// Word-by-word highlighting
player.addEventListener('play', () => {
  (function tick() {
    if (player.paused) return;
    const ms = player.currentTime * 1000;
    const active = timestamps.findIndex(t => ms >= t.offset && ms < t.offset + t.duration);
    // Apply highlight to word at index `active`
    requestAnimationFrame(tick);
  })();
});
player.play();
```

```javascript
// Streaming
const resp = await fetch('/v1/audio/speech', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({ input: 'Hello world.', voice: 'en-US-AvaNeural', stream: true })
});
const reader = resp.body.getReader();
const decoder = new TextDecoder();
let buf = '';
while (true) {
  const { done, value } = await reader.read();
  if (done) break;
  buf += decoder.decode(value, { stream: true });
  const lines = buf.split('\n');
  buf = lines.pop();
  for (const line of lines) {
    if (!line.trim()) continue;
    const evt = JSON.parse(line);
    if (evt.type === 'word') console.log(`${evt.offset}ms: ${evt.text}`);
    else if (evt.type === 'audio') { /* append to audio buffer */ }
    else if (evt.type === 'done') { /* playback ready */ }
  }
}
```

## Deployment

### With pm2 (recommended)

```bash
pip install -r requirements.txt
pm2 start server.py --name edgetts-ws --interpreter python3
pm2 save
pm2 startup  # enable auto-start on reboot
```

### With systemd

```ini
[Unit]
Description=Edge TTS WebSocket API
After=network.target

[Service]
ExecStart=/usr/bin/python3 /opt/edgetts-ws/server.py
Restart=always
WorkingDirectory=/opt/edgetts-ws

[Install]
WantedBy=multi-user.target
```

### Reverse Proxy (Nginx)

```nginx
server {
    listen 80;
    server_name edgetts-ws.example.com;

    location / {
        proxy_pass http://127.0.0.1:8765;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_buffering off;  # important for streaming
    }
}
```

> ⚠️ **Important:** Set `proxy_buffering off` for streaming mode to work correctly.

## Available Voices

Some popular English voices:

| Voice | Accent |
|-------|--------|
| `en-US-AvaNeural` | 🇺🇸 US Female |
| `en-US-AndrewNeural` | 🇺🇸 US Male |
| `en-GB-SoniaNeural` | 🇬🇧 UK Female |
| `en-GB-RyanNeural` | 🇬🇧 UK Male |
| `en-AU-WilliamNeural` | 🇦🇺 AU Male |

Full list: `edge-tts --list-voices`

## Architecture

```
┌─────────┐     HTTP POST      ┌────────────┐    WebSocket     ┌──────────────┐
│  Client  │ ──────────────────→│  server.py │ ───────────────→ │ Bing TTS API │
│ (browser)│ ←──────────────────│  (aiohttp) │ ←─────────────── │  (Microsoft) │
└─────────┘  JSON or NDJSON    └────────────┘  audio + metadata └──────────────┘
```

## License

MIT
