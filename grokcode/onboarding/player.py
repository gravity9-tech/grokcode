from __future__ import annotations

import platform
import subprocess

from grokcode.utils.ui import console


def play_audio(path: str) -> bool:
    """Attempt cross-platform MP3 playback. Returns True if a player succeeded."""
    system = platform.system()

    if system == "Darwin":
        candidates = [["afplay", path]]
    elif system == "Linux":
        candidates = [
            ["mpg123", path],
            ["ffplay", "-nodisp", "-autoexit", path],
        ]
    else:
        # Windows: SoundPlayer only supports WAV — skip
        console.print(
            f"  [dim]Auto-play not supported on Windows. Open {path} manually to listen.[/dim]"
        )
        return False

    for cmd in candidates:
        result = subprocess.run(cmd, capture_output=True)
        if result.returncode == 0:
            return True

    console.print(f"  [dim]Could not auto-play audio. Open {path} manually to listen.[/dim]")
    return False
