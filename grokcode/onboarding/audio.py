from __future__ import annotations

from pathlib import Path

import httpx

from grokcode.utils.ui import print_warning

XAI_TTS_URL = "https://api.x.ai/v1/tts"

# Available xAI voices: eve, ara, rex, sal, leo
DEFAULT_VOICE = "eve"


def generate_audio(script: str, api_key: str, voice: str = DEFAULT_VOICE) -> bytes | None:
    """Call the xAI TTS API. Returns raw MP3 bytes, or None on failure (non-fatal)."""
    try:
        resp = httpx.post(
            XAI_TTS_URL,
            json={
                "text": script,
                "voice_id": voice,
                "language": "en",
                "output_format": {
                    "codec": "mp3",
                    "sample_rate": 24000,
                    "bit_rate": 128000,
                },
            },
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            timeout=60.0,
        )
        if resp.status_code in (403, 404):
            print_warning(
                "Audio API not available — check that your xAI API key has audio access. "
                "The onboarding.md has been saved. You can generate audio manually later."
            )
            return None
        resp.raise_for_status()
        return resp.content
    except httpx.HTTPStatusError as e:
        print_warning(
            f"Audio API error {e.response.status_code} — "
            "The onboarding.md has been saved. You can generate audio manually later."
        )
        return None
    except Exception as e:
        print_warning(f"Audio generation failed: {e}")
        return None


def save_audio(audio_bytes: bytes, output_path: Path) -> None:
    """Write raw audio bytes to file."""
    output_path.write_bytes(audio_bytes)
