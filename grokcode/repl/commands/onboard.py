from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from rich.panel import Panel
from rich.progress import BarColumn, Progress, SpinnerColumn, TaskProgressColumn, TextColumn

from grokcode.utils.ui import console, print_error, print_success

if TYPE_CHECKING:
    from grokcode.config.config import AppConfig

HELP_TEXT = """\
/onboard [--voice <name>] [--no-audio] [--no-play] [-y]

Analyse the codebase and generate an onboarding audio guide.

Reads the project, generates a ≤200-word spoken script with Grok,
saves it as onboarding.md, converts it to speech via the xAI Audio API,
saves it as onboarding.mp3, and plays it in the terminal."""


async def handle_onboard(args: list[str], config: AppConfig, api_key: str) -> None:
    """Run the full onboarding pipeline: analyse → script → save md → audio → play."""
    if "--help" in args or "-h" in args:
        console.print(HELP_TEXT)
        return

    # Parse flags
    voice = "eve"
    no_audio = "--no-audio" in args
    no_play = "--no-play" in args
    overwrite = "-y" in args or "--overwrite" in args

    if "--voice" in args:
        idx = args.index("--voice")
        if idx + 1 < len(args):
            voice = args[idx + 1]

    path = Path.cwd()

    console.print(
        Panel(
            f"[bold]GrokCode Onboarding Generator[/bold]\n[dim]Analysing:[/dim] {path}",
            border_style="cyan",
        )
    )

    # ── Step 1: Scan codebase ────────────────────────────────────────────────
    from grokcode.onboarding.analyser import build_summary, collect_files

    console.print("\n  [cyan]●[/cyan] Scanning codebase...")
    files = collect_files(path)

    if not files:
        print_error(f"No source files found in {path}. Are you in a project directory?")
        return

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TaskProgressColumn(),
        console=console,
        transient=True,
    ) as progress:
        task = progress.add_task("Reading files...", total=len(files))
        summary = build_summary(path, files)
        progress.update(task, advance=len(files))

    console.print(f"  [dim]{len(files)} files collected[/dim]")

    # ── Step 2: Generate script ──────────────────────────────────────────────
    console.print("\n  [cyan]●[/cyan] Generating onboarding script with Grok...")
    from grokcode.onboarding.script import count_words, generate_script, save_onboarding_md

    try:
        script = generate_script(summary, api_key)
    except Exception as e:
        print_error(f"Script generation failed: {e}")
        return

    word_count = count_words(script)

    preview = script[:500] + ("..." if len(script) > 500 else "")
    console.print(
        Panel(
            f"[bold]Script ({word_count} words)[/bold]\n\n{preview}",
            border_style="green",
        )
    )
    if word_count > 200:
        console.print(
            f"  [yellow]⚠ Script is {word_count} words (over limit). Saved as-is.[/yellow]"
        )

    # ── Step 3: Save onboarding.md ───────────────────────────────────────────
    md_path = path / "onboarding.md"
    saved = save_onboarding_md(script, md_path, overwrite=overwrite)
    if not saved:
        console.print("  [dim]Aborted.[/dim]")
        return

    print_success("Saved: onboarding.md")
    _update_gitignore(path)

    # ── Step 4: Audio generation ─────────────────────────────────────────────
    if no_audio:
        console.print("\n  [green]✓[/green] Done. Share onboarding.md with your team.")
        return

    console.print("\n  [cyan]●[/cyan] Generating audio with xAI Audio API...")
    from grokcode.onboarding.audio import generate_audio, save_audio

    audio_bytes = generate_audio(script, api_key, voice=voice)
    if audio_bytes is None:
        console.print("\n  [green]✓[/green] Done. Share onboarding.md with your team.")
        return

    mp3_path = path / "onboarding.mp3"
    try:
        save_audio(audio_bytes, mp3_path)
    except OSError as e:
        print_error(f"Failed to save audio: {e}. Try re-running with --no-audio.")
        return

    size_kb = len(audio_bytes) // 1024
    print_success(f"Saved: onboarding.mp3 ({size_kb} KB)")

    # ── Step 5: Playback ─────────────────────────────────────────────────────
    if not no_play:
        from grokcode.onboarding.player import play_audio

        with console.status("[cyan]♪ Playing onboarding audio...[/cyan]"):
            play_audio(str(mp3_path))

    console.print(
        "\n  [green]✓[/green] Done. Share onboarding.md and onboarding.mp3 with your team."
    )


def _update_gitignore(path: Path) -> None:
    """Add onboarding.mp3 to .gitignore if one exists and the entry isn't already there."""
    gitignore = path / ".gitignore"
    if not gitignore.exists():
        return
    content = gitignore.read_text(encoding="utf-8")
    if "onboarding.mp3" not in content:
        with gitignore.open("a", encoding="utf-8") as f:
            f.write("\n# GrokCode generated audio\nonboarding.mp3\n")
