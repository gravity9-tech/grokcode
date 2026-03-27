#!/usr/bin/env python3
"""
Smoke test: sends a simple message to Grok and prints the streaming response.
Run with: python scripts/smoke_test.py
Requires XAI_API_KEY environment variable or keyring entry.
"""
from __future__ import annotations

import asyncio
import sys
from pathlib import Path

# Allow running from repo root without install
sys.path.insert(0, str(Path(__file__).parent.parent))


async def main() -> None:
    from grokcode.agent.grok_client import GrokClient, GrokClientError
    from grokcode.config.keychain import get_api_key

    api_key = get_api_key()
    if not api_key:
        print("ERROR: No API key found.")
        print("Set XAI_API_KEY env var or run: grokcode config set xai_api_key <key>")
        sys.exit(1)

    print(f"Using model: grok-3-mini")
    print("Sending: 'Say hello in one sentence.'\n")
    print("-" * 40)

    try:
        async with GrokClient(api_key=api_key, model="grok-3-mini", max_tokens=128) as client:
            messages = [{"role": "user", "content": "Say hello in one sentence."}]
            async for chunk in client.chat(messages, stream=True):
                if chunk.content:
                    print(chunk.content, end="", flush=True)
        print("\n" + "-" * 40)
        print("\n✓ Smoke test passed — Grok API is working.")
    except GrokClientError as e:
        print(f"\n✗ API Error: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"\n✗ Unexpected error: {type(e).__name__}: {e}")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
