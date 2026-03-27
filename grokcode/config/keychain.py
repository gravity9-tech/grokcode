from __future__ import annotations

import os

SERVICE_NAME = "grokcode"
USERNAME = "xai_api_key"


def get_api_key() -> str | None:
    """Retrieve API key: tries keyring first, then XAI_API_KEY env var."""
    try:
        import keyring

        key = keyring.get_password(SERVICE_NAME, USERNAME)
        if key:
            return key
    except Exception:
        pass

    return os.environ.get("XAI_API_KEY")


def set_api_key(key: str) -> None:
    """Store API key in the system keychain."""
    try:
        import keyring

        keyring.set_password(SERVICE_NAME, USERNAME, key)
    except Exception as e:
        raise RuntimeError(
            f"Could not store key in keychain: {e}\n"
            "Try setting XAI_API_KEY as an environment variable instead, "
            "or install keyrings.alt: pip install keyrings.alt"
        ) from e


def delete_api_key() -> None:
    """Remove API key from the system keychain."""
    try:
        import keyring

        keyring.delete_password(SERVICE_NAME, USERNAME)
    except Exception:
        pass
