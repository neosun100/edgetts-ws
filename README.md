# edgetts-ws

A lightweight HTTP API server that wraps Microsoft Edge TTS with **word-level timestamps**. Returns synthesized audio (base64 MP3) along with per-word timing data (offset + duration in milliseconds), enabling real-time word-by-word highlighting during playback.

## How It Works

Microsoft Edge TTS exposes a WebSocket API that streams audio chunks alongside `WordBoundary` events containing precise timing for each spoken word. This server collects both, then returns them as a single JSON response.

```
Client POST → server.py → Edge TTS WebSocket → WordBoundary events + audio chunks
                                                         ↓
                                              JSON { audio, timestamps }
```

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
  "speed": 0.8
}
```

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `input` | string | *(required)* | Text to synthesize |
| `voice` | string | `en-US-AvaNeural` | Edge TTS voice name |
| `speed` | number | `1.0` | Playback speed (0.5–2.0) |

**Response:**

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

Each timestamp entry:
- `text` — the word spoken
- `offset` — start time in milliseconds from audio beginning
- `duration` — how long the word is spoken in milliseconds

## Frontend Usage Example

```javascript
const resp = await fetch('/v1/audio/speech', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({ input: 'Hello world.', voice: 'en-US-AvaNeural', speed: 1.0 })
});
const { audio, timestamps } = await resp.json();

// Decode audio
const bin = Uint8Array.from(atob(audio), c => c.charCodeAt(0));
const blob = new Blob([bin], { type: 'audio/mpeg' });
const player = new Audio(URL.createObjectURL(blob));

// Highlight words during playback
player.onplay = () => {
  (function tick() {
    if (player.paused) return;
    const ms = player.currentTime * 1000;
    const active = timestamps.findIndex(t => ms >= t.offset && ms < t.offset + t.duration);
    // Apply highlight to word at index `active`
    requestAnimationFrame(tick);
  })();
};
player.play();
```

## Deployment

### With pm2

```bash
pm2 start server.py --name edgetts-ws --interpreter python3
pm2 save
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
    }
}
```

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

## License

MIT
