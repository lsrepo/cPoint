#!/usr/bin/env python3
"""Article read-aloud audio via edge-tts (Microsoft's free, unofficial
wrapper around the Edge browser's Read Aloud voices). Cached as files
under CACHE_DIR (see cache_path) so each article/language pair only
triggers one synthesis call, and served by server.py via FastAPI's
FileResponse -- which (unlike a plain Response) supports HTTP Range
requests. That support turns out to be required, not just nice-to-have:
Chrome's <audio> seeking (currentTime = X) silently resets to 0 instead of
seeking when the response has no Accept-Ranges/ETag, even if the whole
file is already fully buffered client-side (confirmed empirically)."""
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
    return os.path.join(CACHE_DIR, f"{nid}_{lang}.mp3")


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
    """Synthesize + remux text into cache_path(nid, lang) and return that
    path. Writes via a temp file + atomic rename so a concurrent request
    can never read a half-written cache file."""
    raw = await _collect_raw(text, lang)

    os.makedirs(CACHE_DIR, exist_ok=True)
    final_path = cache_path(nid, lang)
    tmp_path = f"{final_path}.tmp"
    try:
        # edge-tts's raw stream is bare MP3 frames with no Xing/seek
        # header (see module docstring for why that breaks seeking).
        # ffmpeg -c copy remux fixes it by writing a proper header -- but
        # only once, since it must seek back to the start of the output
        # after encoding to do so, which requires the output to be a real
        # seekable file, not a pipe (confirmed empirically: piping to
        # pipe:1 silently produces the same headerless output as the
        # input).
        try:
            proc = await asyncio.create_subprocess_exec(
                "ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
                "-f", "mp3", "-i", "pipe:0",
                "-c", "copy",
                "-f", "mp3",
                tmp_path,
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
        except FileNotFoundError as e:
            raise TTSError("ffmpeg is required to remux TTS audio but is not installed") from e

        _, stderr = await proc.communicate(raw)
        if proc.returncode != 0:
            raise TTSError(f"ffmpeg remux failed: {stderr.decode(errors='replace')}")

        os.replace(tmp_path, final_path)
    finally:
        if os.path.exists(tmp_path):
            os.remove(tmp_path)

    return final_path
