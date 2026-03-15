from aiohttp import web
import edge_tts, base64

async def handle(request):
    if request.method == 'OPTIONS':
        return web.Response(headers=cors())
    try:
        body = await request.json()
    except Exception:
        return web.json_response({'error': 'Invalid JSON'}, status=400, headers=cors())

    text = body.get('input', '')
    voice = body.get('voice', 'en-US-AvaNeural')
    speed = body.get('speed', 1.0)
    if not text:
        return web.json_response({'error': 'Missing input'}, status=400, headers=cors())

    rate = f"+{round((speed-1)*100)}%" if speed >= 1 else f"-{round((1-speed)*100)}%"

    try:
        c = edge_tts.Communicate(text, voice, rate=rate, boundary="WordBoundary")
        timestamps = []
        audio_chunks = []
        async for chunk in c.stream():
            if chunk["type"] == "WordBoundary":
                # Edge TTS returns offset/duration in 100-nanosecond units, convert to ms
                timestamps.append({
                    'text': chunk['text'],
                    'offset': chunk['offset'] / 10000,
                    'duration': chunk['duration'] / 10000
                })
            elif chunk["type"] == "audio":
                audio_chunks.append(chunk["data"])

        audio = base64.b64encode(b''.join(audio_chunks)).decode()
        return web.json_response({
            'audio': audio,
            'content_type': 'audio/mpeg',
            'timestamps': timestamps
        }, headers=cors())
    except Exception as e:
        return web.json_response({'error': str(e)}, status=500, headers=cors())

def cors():
    return {
        'Access-Control-Allow-Origin': '*',
        'Access-Control-Allow-Methods': 'POST,OPTIONS',
        'Access-Control-Allow-Headers': 'Content-Type,Authorization'
    }

app = web.Application()
app.router.add_route('*', '/', handle)
app.router.add_route('*', '/v1/audio/speech', handle)

if __name__ == '__main__':
    web.run_app(app, host='0.0.0.0', port=8765)
