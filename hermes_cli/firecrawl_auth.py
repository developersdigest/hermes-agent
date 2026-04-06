"""
Firecrawl browser-based authentication (PKCE flow).

Mirrors the flow from the Firecrawl CLI (firecrawl login):
1. Generate session_id + PKCE code_verifier / code_challenge
2. Open browser to firecrawl.dev/cli-auth with code_challenge
3. Poll firecrawl.dev/api/auth/cli/status with code_verifier
4. On success, save API key to ~/.hermes/.env

Usage:
    hermes tools login firecrawl   # standalone command
    hermes tools                   # integrated into provider selection
"""

from __future__ import annotations

import base64
import hashlib
import logging
import os
import secrets
import sys
import time
import webbrowser
from getpass import getpass
from typing import Any, Dict, Optional

import httpx

from hermes_cli.colors import Colors, color
from hermes_cli.config import get_env_value, load_config, save_config, save_env_value

logger = logging.getLogger(__name__)

# ─── Constants ───────────────────────────────────────────────────────────────

FIRECRAWL_WEB_URL = "https://firecrawl.dev"
FIRECRAWL_DEFAULT_API_URL = "https://api.firecrawl.dev"
AUTH_TIMEOUT_SECONDS = 300  # 5 minutes
POLL_INTERVAL_SECONDS = 2


# ─── PKCE Helpers ────────────────────────────────────────────────────────────

def _generate_session_id() -> str:
    """32 random bytes, hex-encoded."""
    return secrets.token_hex(32)


def _generate_code_verifier() -> str:
    """32 random bytes, base64url-encoded (no padding)."""
    return base64.urlsafe_b64encode(secrets.token_bytes(32)).rstrip(b"=").decode()


def _generate_code_challenge(verifier: str) -> str:
    """SHA-256 hash of verifier, base64url-encoded (no padding)."""
    digest = hashlib.sha256(verifier.encode()).digest()
    return base64.urlsafe_b64encode(digest).rstrip(b"=").decode()


# ─── Browser / Environment ──────────────────────────────────────────────────

def _is_remote_session() -> bool:
    """Detect SSH sessions where browser opening won't work."""
    return bool(os.getenv("SSH_CLIENT") or os.getenv("SSH_TTY"))


def _open_browser(url: str) -> bool:
    """Open URL in default browser. Returns True on success."""
    try:
        return webbrowser.open(url)
    except Exception:
        return False


# ─── Polling ─────────────────────────────────────────────────────────────────

def _poll_auth_status(
    session_id: str,
    code_verifier: str,
    web_url: str = FIRECRAWL_WEB_URL,
) -> Optional[Dict[str, Any]]:
    """Single poll to Firecrawl auth status endpoint.

    Returns {"api_key", "api_url", "team_name"} on success, None if pending.
    """
    status_url = f"{web_url}/api/auth/cli/status"
    try:
        with httpx.Client(timeout=10) as client:
            resp = client.post(
                status_url,
                json={
                    "session_id": session_id,
                    "code_verifier": code_verifier,
                },
            )
        if not resp.is_success:
            return None
        data = resp.json()
        if data.get("status") == "complete" and data.get("apiKey"):
            return {
                "api_key": data["apiKey"],
                "api_url": data.get("apiUrl") or FIRECRAWL_DEFAULT_API_URL,
                "team_name": data.get("teamName"),
            }
    except Exception:
        pass
    return None


def _wait_for_auth(
    session_id: str,
    code_verifier: str,
    web_url: str = FIRECRAWL_WEB_URL,
    timeout: float = AUTH_TIMEOUT_SECONDS,
) -> Dict[str, Any]:
    """Poll until auth completes or timeout.

    Returns {"api_key", "api_url", "team_name"}.
    Raises TimeoutError or KeyboardInterrupt.
    """
    start = time.monotonic()
    dots = 0
    while True:
        elapsed = time.monotonic() - start
        if elapsed > timeout:
            sys.stdout.write("\r" + " " * 60 + "\r")
            sys.stdout.flush()
            raise TimeoutError("Authentication timed out. Please try again.")

        dot_str = "." * (dots % 4)
        sys.stdout.write(f"\r  Waiting for browser authentication{dot_str.ljust(4)}")
        sys.stdout.flush()
        dots += 1

        result = _poll_auth_status(session_id, code_verifier, web_url)
        if result:
            sys.stdout.write("\r" + " " * 60 + "\r")
            sys.stdout.flush()
            return result

        time.sleep(POLL_INTERVAL_SECONDS)


# ─── Login Flows ─────────────────────────────────────────────────────────────

def firecrawl_browser_login(
    web_url: str = FIRECRAWL_WEB_URL,
) -> Dict[str, Any]:
    """Run the full PKCE browser login flow.

    Returns {"api_key": str, "api_url": str, "team_name": str | None}.
    Raises TimeoutError or KeyboardInterrupt.
    """
    session_id = _generate_session_id()
    code_verifier = _generate_code_verifier()
    code_challenge = _generate_code_challenge(code_verifier)

    login_url = f"{web_url}/cli-auth?code_challenge={code_challenge}#session_id={session_id}"

    print()
    print(color("  Opening browser for Firecrawl authentication...", Colors.CYAN))
    print(color(f"  If the browser doesn't open, visit:", Colors.DIM))
    print(f"  {login_url}")
    print()

    if not _is_remote_session():
        _open_browser(login_url)

    return _wait_for_auth(session_id, code_verifier, web_url)


def firecrawl_manual_login() -> Dict[str, Any]:
    """Prompt for API key manually.

    Returns {"api_key": str, "api_url": str, "team_name": None}.
    """
    print()
    api_key = getpass(color("  Enter your Firecrawl API key: ", Colors.YELLOW)).strip()

    if not api_key:
        raise ValueError("API key cannot be empty.")

    if not api_key.startswith("fc-"):
        raise ValueError("Invalid API key format. Firecrawl API keys start with 'fc-'.")

    return {
        "api_key": api_key,
        "api_url": FIRECRAWL_DEFAULT_API_URL,
        "team_name": None,
    }


def _save_firecrawl_credentials(result: Dict[str, Any]) -> None:
    """Save API key to ~/.hermes/.env and set web.backend in config."""
    save_env_value("FIRECRAWL_API_KEY", result["api_key"])

    api_url = result.get("api_url", "").strip()
    if api_url and api_url != FIRECRAWL_DEFAULT_API_URL:
        save_env_value("FIRECRAWL_API_URL", api_url)

    config = load_config()
    config.setdefault("web", {})["backend"] = "firecrawl"
    save_config(config)


def _print_login_success(result: Dict[str, Any]) -> None:
    """Print success message after login."""
    print(color("  ✓ Firecrawl login successful!", Colors.GREEN))
    if result.get("team_name"):
        print(color(f"    Team: {result['team_name']}", Colors.DIM))
    print(color("    Web backend set to: firecrawl", Colors.DIM))
    print()


# ─── CLI Command ─────────────────────────────────────────────────────────────

def firecrawl_login_command(args) -> None:
    """CLI handler for ``hermes tools login firecrawl``."""
    existing = get_env_value("FIRECRAWL_API_KEY")
    if existing:
        print()
        print(color("  Firecrawl API key is already configured.", Colors.GREEN))
        try:
            answer = input(color("  Re-authenticate? [y/N]: ", Colors.YELLOW)).strip().lower()
        except (KeyboardInterrupt, EOFError):
            print()
            return
        if answer not in ("y", "yes"):
            return

    print()
    print(color("  🔥 Firecrawl Authentication", Colors.CYAN, Colors.BOLD))
    print()
    print("  1. Login with browser " + color("(recommended)", Colors.DIM))
    print("  2. Enter API key manually")
    print()

    try:
        choice = input(color("  Enter choice [1/2]: ", Colors.YELLOW)).strip()
    except (KeyboardInterrupt, EOFError):
        print()
        return

    try:
        if choice == "2":
            result = firecrawl_manual_login()
        else:
            result = firecrawl_browser_login()
    except KeyboardInterrupt:
        print("\n")
        print(color("  Authentication cancelled.", Colors.DIM))
        return
    except TimeoutError as exc:
        print(color(f"  ✗ {exc}", Colors.RED))
        return
    except ValueError as exc:
        print(color(f"  ✗ {exc}", Colors.RED))
        return

    _save_firecrawl_credentials(result)
    _print_login_success(result)


# ─── Interactive Login (for hermes tools provider flow) ──────────────────────

def firecrawl_interactive_login(config: dict) -> bool:
    """Offer browser vs manual login during ``hermes tools`` provider setup.

    Returns True if API key was obtained and saved (caller should skip its
    own manual prompt). Returns False to fall through to the default flow.
    """
    print()
    print("  1. Login with browser " + color("(recommended)", Colors.DIM))
    print("  2. Enter API key manually")
    print()

    try:
        choice = input(color("  Choose login method [1/2]: ", Colors.YELLOW)).strip()
    except (KeyboardInterrupt, EOFError):
        print()
        return False

    if choice == "2":
        # Fall through to the existing manual prompt in _configure_provider
        return False

    try:
        result = firecrawl_browser_login()
    except KeyboardInterrupt:
        print("\n")
        print(color("  Authentication cancelled.", Colors.DIM))
        return False
    except TimeoutError as exc:
        print(color(f"  ✗ {exc}", Colors.RED))
        return False

    _save_firecrawl_credentials(result)
    _print_login_success(result)
    return True
