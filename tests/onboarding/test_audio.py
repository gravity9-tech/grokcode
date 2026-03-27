from __future__ import annotations

import json
from pathlib import Path

import pytest
import respx
from httpx import Response

from grokcode.onboarding.audio import XAI_TTS_URL, generate_audio, save_audio

FAKE_MP3 = b"\xff\xfb\x90\x00" + b"\x00" * 100  # fake MP3 header bytes


@respx.mock
def test_generate_audio_returns_bytes() -> None:
    respx.post(XAI_TTS_URL).mock(return_value=Response(200, content=FAKE_MP3))
    result = generate_audio("Hello world", "test-key")
    assert result == FAKE_MP3


@respx.mock
def test_generate_audio_sends_correct_body() -> None:
    route = respx.post(XAI_TTS_URL).mock(return_value=Response(200, content=FAKE_MP3))
    generate_audio("Hello world", "test-key", voice="leo")
    body = json.loads(route.calls[0].request.content)
    assert body["text"] == "Hello world"
    assert body["voice_id"] == "leo"
    assert body["language"] == "en"
    assert body["output_format"]["codec"] == "mp3"
    # no "model" field
    assert "model" not in body


@respx.mock
def test_generate_audio_returns_none_on_403() -> None:
    respx.post(XAI_TTS_URL).mock(return_value=Response(403, text="Forbidden"))
    result = generate_audio("Hello", "test-key")
    assert result is None


@respx.mock
def test_generate_audio_returns_none_on_404() -> None:
    respx.post(XAI_TTS_URL).mock(return_value=Response(404, text="Not Found"))
    result = generate_audio("Hello", "test-key")
    assert result is None


@respx.mock
def test_generate_audio_returns_none_on_server_error() -> None:
    respx.post(XAI_TTS_URL).mock(return_value=Response(500, text="Internal Server Error"))
    result = generate_audio("Hello", "test-key")
    assert result is None


@respx.mock
def test_generate_audio_returns_none_on_network_error() -> None:
    import httpx
    respx.post(XAI_TTS_URL).mock(side_effect=httpx.ConnectError("connection refused"))
    result = generate_audio("Hello", "test-key")
    assert result is None


def test_save_audio_writes_bytes(tmp_path: Path) -> None:
    output = tmp_path / "onboarding.mp3"
    save_audio(FAKE_MP3, output)
    assert output.exists()
    assert output.read_bytes() == FAKE_MP3
