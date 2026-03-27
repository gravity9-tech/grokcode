from __future__ import annotations

from unittest.mock import patch

import pytest

from grokcode.onboarding.player import play_audio


def _mock_run(returncode: int):
    """Return a mock subprocess.run that always gives returncode."""
    from unittest.mock import MagicMock
    mock = MagicMock()
    mock.returncode = returncode
    return mock


def test_macos_uses_afplay() -> None:
    with patch("platform.system", return_value="Darwin"):
        with patch("subprocess.run", return_value=_mock_run(0)) as mock_run:
            result = play_audio("onboarding.mp3")
    assert result is True
    cmd = mock_run.call_args[0][0]
    assert cmd[0] == "afplay"


def test_linux_tries_mpg123_first() -> None:
    with patch("platform.system", return_value="Linux"):
        with patch("subprocess.run", return_value=_mock_run(0)) as mock_run:
            result = play_audio("onboarding.mp3")
    assert result is True
    cmd = mock_run.call_args[0][0]
    assert cmd[0] == "mpg123"


def test_linux_falls_back_to_ffplay() -> None:
    calls = []

    def fake_run(cmd, **kwargs):
        calls.append(cmd[0])
        mock = _mock_run(1 if cmd[0] == "mpg123" else 0)
        return mock

    with patch("platform.system", return_value="Linux"):
        with patch("subprocess.run", side_effect=fake_run):
            result = play_audio("onboarding.mp3")

    assert result is True
    assert calls == ["mpg123", "ffplay"]


def test_all_players_fail_prints_message(capsys) -> None:
    with patch("platform.system", return_value="Linux"):
        with patch("subprocess.run", return_value=_mock_run(1)):
            result = play_audio("onboarding.mp3")
    assert result is False


def test_windows_skips_playback() -> None:
    with patch("platform.system", return_value="Windows"):
        with patch("subprocess.run") as mock_run:
            result = play_audio("onboarding.mp3")
    assert result is False
    mock_run.assert_not_called()
