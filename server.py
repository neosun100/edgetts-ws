from aiohttp import web
import edge_tts, base64, json

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
    stream = body.get('stream', False)
    if not text:
        return web.json_response({'error': 'Missing input'}, status=400, headers=cors())

    rate = f"+{round((speed-1)*100)}%" if speed >= 1 else f"-{round((1-speed)*100)}%"

    try:
        c = edge_tts.Communicate(text, voice, rate=rate, boundary="WordBoundary")

        if stream:
            resp = web.StreamResponse(headers={**cors(), 'Content-Type': 'application/x-ndjson'})
            await resp.prepare(request)
            async for chunk in c.stream():
                if chunk["type"] == "WordBoundary":
                    await resp.write((json.dumps({'type':'word','text':chunk['text'],'offset':chunk['offset']/10000,'duration':chunk['duration']/10000})+'\n').encode())
                elif chunk["type"] == "audio":
                    await resp.write((json.dumps({'type':'audio','data':base64.b64encode(chunk['data']).decode()})+'\n').encode())
            await resp.write((json.dumps({'type':'done'})+'\n').encode())
            await resp.write_eof()
            return resp

        # Non-streaming
        timestamps = []
        audio_chunks = []
        async for chunk in c.stream():
            if chunk["type"] == "WordBoundary":
                timestamps.append({'text':chunk['text'],'offset':chunk['offset']/10000,'duration':chunk['duration']/10000})
            elif chunk["type"] == "audio":
                audio_chunks.append(chunk["data"])
        return web.json_response({
            'audio': base64.b64encode(b''.join(audio_chunks)).decode(),
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
