# edgetts-ws

[![Python](https://img.shields.io/badge/Python-3.9+-blue?logo=python&logoColor=white)](https://python.org)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)
[![Edge TTS](https://img.shields.io/badge/Edge_TTS-WebSocket-purple)](https://github.com/rany2/edge-tts)
[![aiohttp](https://img.shields.io/badge/aiohttp-3.9+-orange)](https://docs.aiohttp.org)

A lightweight HTTP API server that wraps Microsoft Edge TTS with **word-level timestamps**. Connects to Bing TTS via WebSocket internally, returns synthesized audio (base64 MP3) along with per-word timing data (offset + duration in milliseconds), enabling real-time word-by-word highlighting during playback.

## How It Works

```
Client POST → server.py (aiohttp) → Edge TTS WebSocket → WordBoundary events + audio chunks
                                                                    ↓
                                                         JSON or NDJSON stream → Client
```

Microsoft Edge TTS exposes a WebSocket API that streams audio chunks alongside `WordBoundary` events containing precise timing for each spoken word. The `edge_tts` Python library handles the WebSocket protocol, DRM token generation, and SSML message framing. This server wraps it as a simple HTTP API.

### Key Technical Details

- **Protocol**: The `edge_tts` library connects to `wss://speech.platform.bing.com/consumer/speech/synthesize/readaloud/edge/v1` via WebSocket
- **Authentication**: Uses a `TrustedClientToken` + `Sec-MS-GEC` DRM token (SHA-256 hash of timestamp + token)
- **Timestamps**: `WordBoundary` events return offset/duration in 100-nanosecond units; this server converts to milliseconds (`/ 10000`)
- **Audio format**: MP3 (audio-24khz-48kbitrate-mono-mp3)

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
# Server starts on http://0.0.0.0:8765
```

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

Returns a single JSON object after all audio is synthesized:

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

Returns NDJSON (newline-delimited JSON), one event per line as data arrives from the WebSocket:

```jsonl
{"type":"word","text":"The","offset":100,"duration":218.75}
{"type":"word","text":"celebrated","offset":334.375,"duration":750}
{"type":"audio","data":"<base64 MP3 chunk>"}
{"type":"audio","data":"<base64 MP3 chunk>"}
{"type":"done"}
```

Event types:
| Type | Description |
|------|-------------|
| `word` | Word timestamp — `text`, `offset` (ms), `duration` (ms) |
| `audio` | Base64-encoded MP3 audio chunk |
| `done` | Synthesis complete, no more events |

### Error Response

```json
{ "error": "Missing input" }
```

## Word-by-Word Highlighting (Frontend Integration)

This is the primary use case for this API. Here's how to implement word highlighting:

### Step 1: Render words as individual spans

```javascript
const sentence = "The celebrated theory is still the source of great controversy.";
const html = sentence.split(/(\s+)/).map((w, i) =>
  w.trim() ? `<span class="word" data-wi="${i}">${w}</span>` : w
).join('');
```

### Step 2: Fetch audio + timestamps

```javascript
const { audio, timestamps } = await fetch('/v1/audio/speech', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({ input: sentence, voice: 'en-US-AvaNeural', speed: 0.8 })
}).then(r => r.json());
```

### Step 3: Play audio with synchronized highlighting

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
      const tsIdx = Math.floor(parseInt(w.dataset.wi) / 2); // split produces [word, space, word, ...]
      w.classList.toggle('highlight', tsIdx === activeIdx);
    });
    requestAnimationFrame(tick);
  })();
});
player.play();
```

> ⚠️ **Critical mapping**: `split(/(\s+)/)` produces `[word, space, word, space, ...]`, so `data-wi` values are `0, 2, 4, 6, ...`. The timestamp index is `Math.floor(wi / 2)`.

## Deployment

### With pm2 (recommended)

```bash
pip install -r requirements.txt
pm2 start server.py --name edgetts-ws --interpreter python3
pm2 save
pm2 startup  # enable auto-start on reboot
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
        proxy_buffering off;  # IMPORTANT for streaming mode
    }
}
```

> ⚠️ **`proxy_buffering off`** is required for streaming mode. Without it, Nginx buffers the entire response before sending to the client, defeating the purpose of streaming.

## Available Voices

| Voice | Accent |
|-------|--------|
| `en-US-AvaNeural` | 🇺🇸 US Female |
| `en-US-AndrewNeural` | 🇺🇸 US Male |
| `en-GB-SoniaNeural` | 🇬🇧 UK Female |
| `en-GB-RyanNeural` | 🇬🇧 UK Male |
| `en-AU-WilliamNeural` | 🇦🇺 AU Male |

Full list: `edge-tts --list-voices`

## Companion Projects

| Project | Description |
|---------|-------------|
| [edgetts-ws-worker](https://github.com/neosun100/edgetts-ws-worker) | Same API as a Cloudflare Worker (serverless) |
| [pte-wfd-216](https://github.com/neosun100/pte-wfd-216) | Example app using this API for word-by-word highlighting |

## Development Lessons

1. **Timestamp unit conversion**: Edge TTS returns offset/duration in 100-nanosecond units. Divide by 10,000 to get milliseconds.
2. **Streaming requires `proxy_buffering off`** in Nginx, otherwise the NDJSON events are batched.
3. **The `edge_tts` library handles all WebSocket complexity** — DRM tokens, SSML framing, reconnection. Don't reimplement unless you need to (see edgetts-ws-worker for a from-scratch implementation).

## License

MIT
