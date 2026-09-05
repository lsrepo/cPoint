#!/usr/bin/env python3
"""Article read-aloud audio via edge-tts (Microsoft's free, unofficial
wrapper around the Edge browser's Read Aloud voices). Cached as files
under CACHE_DIR (see cache_path) so each article/language pair only
triggers one synthesis call, and served by server.py via FastAPI's
FileResponse -- which (unlike a plain Response) supports HTTP Range
requests. That support turns out to be required, not just nice-to-have:
Chrome's <audio>/<video> seeking (currentTime = X) silently resets to 0
instead of seeking when the response has no Accept-Ranges/ETag, even if
the whole file is already fully buffered client-side (confirmed
empirically).

The cache is muxed as an MP4 with a minimal (2x2, 1fps, black) video
track, not a bare MP3 -- confirmed empirically that Chrome's autoplay
policy only ever grants the "muted playback may autoplay without a user
gesture" exception to elements with an actual video track. A bare
<audio> (or a <video> pointed at audio-only content) is never granted
it, in any tested Chrome configuration, including the engine's own
default policy for a fresh visitor with no engagement history. The
frontend plays this back through a (visually hidden) <video> element,
muted at first, unmuting immediately once playback has actually begun
-- see ArticleAudioPlayer.jsx."""
import asyncio
import os

import edge_tts

VOICES = {
    "yue": "zh-HK-WanLungNeural",
    "cmn": "zh-CN-XiaoxiaoNeural",
}

CACHE_DIR = "tts_cache"


class TTSError(Exception):
    pass


def cache_path(nid, lang):
    return os.path.join(CACHE_DIR, f"{nid}_{lang}.mp4")


async def _collect_raw(text, lang):
    voice = VOICES.get(lang)
    if voice is None:
        raise TTSError(f"unsupported lang: {lang}")

    chunks = bytearray()
    try:
        communicate = edge_tts.Communicate(text, voice)
        async for chunk in communicate.stream():
            if chunk["type"] == "audio":
                chunks.extend(chunk["data"])
    except edge_tts.exceptions.EdgeTTSException as e:
        raise TTSError(str(e)) from e

    if not chunks:
        raise TTSError("edge-tts returned no audio data")
    return bytes(chunks)


async def synthesize_to_cache(nid, lang, text):
    """Synthesize + mux text into cache_path(nid, lang) and return that
    path. Writes via a temp file + atomic rename so a concurrent request
    can never read a half-written cache file."""
    raw = await _collect_raw(text, lang)

    os.makedirs(CACHE_DIR, exist_ok=True)
    final_path = cache_path(nid, lang)
    tmp_path = f"{final_path}.tmp"
    try:
        try:
            proc = await asyncio.create_subprocess_exec(
                "ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
                "-f", "lavfi", "-i", "color=c=black:s=2x2:r=1",
                "-f", "mp3", "-i", "pipe:0",
                "-c:v", "libx264", "-tune", "stillimage", "-pix_fmt", "yuv420p",
                "-c:a", "aac", "-b:a", "64k",
                "-shortest", "-movflags", "+faststart",
                "-f", "mp4",
                tmp_path,
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
        except FileNotFoundError as e:
            raise TTSError("ffmpeg is required to package TTS audio but is not installed") from e

        _, stderr = await proc.communicate(raw)
        if proc.returncode != 0:
            raise TTSError(f"ffmpeg muxing failed: {stderr.decode(errors='replace')}")

        os.replace(tmp_path, final_path)
    finally:
        if os.path.exists(tmp_path):
            os.remove(tmp_path)

    return final_path
