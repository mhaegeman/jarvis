"""CLI test client for the Jarvis WS protocol.

Usage:
    python -m server.cli_test                                  # REPL
    python -m server.cli_test --text "say hi"                  # one-shot
    python -m server.cli_test --audio-fixture path/to.wav      # replay WAV
    python -m server.cli_test --ws ws://host:port/ws
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
import wave
from typing import Any

from websockets.asyncio.client import connect

from server.audio import encode_mic_chunk


async def _await_ready(ws: Any) -> None:
    while True:
        raw = await ws.recv()
        if isinstance(raw, bytes):
            continue
        msg = json.loads(raw)
        if msg.get("type") == "ready":
            return


async def _drive_text(ws: Any, user_text: str) -> None:
    await ws.send(json.dumps({"type": "text", "content": user_text}))
    sys.stdout.write(f"\n> {user_text}\n< ")
    sys.stdout.flush()
    while True:
        raw = await ws.recv()
        if isinstance(raw, bytes):
            sys.stdout.write(f"[binary {len(raw)}B]")
            continue
        msg = json.loads(raw)
        match msg.get("type"):
            case "llm.token":
                sys.stdout.write(msg["delta"])
                sys.stdout.flush()
            case "llm.end":
                print()
                return
            case "error":
                print(f"\n[error] {msg.get('code')}: {msg.get('message')}")
                return
            case _:
                pass


async def _drive_audio_fixture(ws: Any, wav_path: str) -> None:
    with wave.open(wav_path, "rb") as w:
        if w.getnchannels() != 1 or w.getsampwidth() != 2:
            raise ValueError("fixture must be mono 16-bit PCM")
        rate = w.getframerate()
        await ws.send(
            json.dumps({"type": "audio.start", "sampleRate": rate, "format": "pcm_s16le"})
        )
        frames_per_chunk = max(1, rate // 50)
        while True:
            data = w.readframes(frames_per_chunk)
            if not data:
                break
            await ws.send(encode_mic_chunk(data))
            await asyncio.sleep(0.005)
        await ws.send(json.dumps({"type": "audio.end"}))

    sys.stdout.write("\n< ")
    sys.stdout.flush()
    while True:
        raw = await ws.recv()
        if isinstance(raw, bytes):
            continue
        msg = json.loads(raw)
        t = msg.get("type")
        if t == "stt.final":
            sys.stdout.write(f"\n[stt.final] {msg['text']}\n< ")
            sys.stdout.flush()
        elif t == "llm.token":
            sys.stdout.write(msg["delta"])
            sys.stdout.flush()
        elif t == "llm.end":
            print()
            return
        elif t == "error":
            print(f"\n[error] {msg.get('code')}: {msg.get('message')}")
            return


async def _run(url: str, text: str | None, audio_fixture: str | None) -> int:
    async with connect(url, max_size=4 * 1024 * 1024) as ws:
        await _await_ready(ws)
        if audio_fixture is not None:
            await _drive_audio_fixture(ws, audio_fixture)
            return 0
        if text is not None:
            await _drive_text(ws, text)
            return 0
        loop = asyncio.get_running_loop()
        while True:
            try:
                line = await loop.run_in_executor(None, sys.stdin.readline)
            except (EOFError, KeyboardInterrupt):
                return 0
            if not line:
                return 0
            line = line.strip()
            if not line:
                continue
            await _drive_text(ws, line)


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--ws", default="ws://localhost:8765/ws")
    p.add_argument("--text", default=None)
    p.add_argument("--audio-fixture", default=None, help="Path to a mono 16-bit PCM WAV")
    args = p.parse_args()
    raise SystemExit(asyncio.run(_run(args.ws, args.text, args.audio_fixture)))


if __name__ == "__main__":
    main()
