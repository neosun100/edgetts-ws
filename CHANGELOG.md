# Changelog

## [1.1.0] - 2026-03-15

### Added
- Streaming mode (`stream: true`) — returns NDJSON with word/audio/done events
- `stream` parameter in API request body

### Changed
- Timestamps now available in both streaming and non-streaming modes

## [1.0.0] - 2026-03-15

### Added
- Initial release
- HTTP API wrapping Microsoft Edge TTS via WebSocket
- Word-level timestamps (offset + duration in ms) via `WordBoundary` events
- Non-streaming JSON response with base64 audio + timestamps
- CORS support for browser frontends
- Speed control (0.5x–2.0x)
- Multiple voice support (all Edge TTS neural voices)
