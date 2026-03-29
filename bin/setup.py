#!/usr/bin/env python3
"""
whoop-journal setup: Interactive OAuth setup for Whoop and Strava.

Handles the entire OAuth dance automatically — spins up a local server
to catch callbacks, opens the browser, exchanges tokens, saves everything.

Zero external dependencies. Works with Python 3.8+.

Usage:
    python3 setup.py                # Full setup (both services)
    python3 setup.py --whoop-only   # Only set up Whoop
    python3 setup.py --strava-only  # Only set up Strava
    python3 setup.py --reauth       # Force re-authentication even if tokens exist
    python3 setup.py --test         # Test existing tokens without re-authenticating
"""

import argparse
import http.server
import json
import os
import secrets
import sys
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
import webbrowser
from pathlib import Path

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

CONFIG_DIR = Path.home() / ".whoop-journal"
CONFIG_FILE = CONFIG_DIR / "config.json"
WHOOP_TOKENS_FILE = CONFIG_DIR / "whoop_tokens.json"
STRAVA_TOKENS_FILE = CONFIG_DIR / "strava_tokens.json"

WHOOP_AUTH_URL = "https://api.prod.whoop.com/oauth/oauth2/auth"
WHOOP_TOKEN_URL = "https://api.prod.whoop.com/oauth/oauth2/token"
WHOOP_API = "https://api.prod.whoop.com/developer"

STRAVA_AUTH_URL = "https://www.strava.com/oauth/authorize"
STRAVA_TOKEN_URL = "https://www.strava.com/oauth/token"
STRAVA_API = "https://www.strava.com/api/v3"

LOCAL_PORT = 1234
REDIRECT_URI = "http://localhost:%d" % LOCAL_PORT

WHOOP_SCOPES = "read:recovery read:cycles read:sleep read:workout read:profile offline"
STRAVA_SCOPES = "read,activity:read_all"


# ---------------------------------------------------------------------------
# Pretty output
# ---------------------------------------------------------------------------

def banner(text):
    print("\n" + "=" * 60)
    print("  " + text)
    print("=" * 60 + "\n")


def step(n, text):
    print("[%d] %s" % (n, text))


def ok(text):
    print("    OK: %s" % text)


def fail(text):
    print("    FAIL: %s" % text)


def prompt(text, default=None):
    if default:
        result = input("    %s [%s]: " % (text, default)).strip()
        return result if result else default
    return input("    %s: " % text).strip()


# ---------------------------------------------------------------------------
# OAuth callback server
# ---------------------------------------------------------------------------

class OAuthCallbackHandler(http.server.BaseHTTPRequestHandler):
    """Handles the OAuth redirect, extracts the auth code, shows a success page."""

    auth_code = None
    state = None
    error = None

    def do_GET(self):
        query = urllib.parse.urlparse(self.path).query
        params = urllib.parse.parse_qs(query)

        if "error" in params:
            OAuthCallbackHandler.error = params["error"][0]
            self._respond("Authorization failed: %s. You can close this tab." %
                          params["error"][0])
            return

        if "code" in params:
            OAuthCallbackHandler.auth_code = params["code"][0]
            OAuthCallbackHandler.state = params.get("state", [None])[0]
            self._respond("Authorization successful! You can close this tab and "
                          "return to the terminal.")
        else:
            self._respond("No authorization code received. Try again.")

    def _respond(self, message):
        html = """<!DOCTYPE html><html><head><style>
            body { font-family: -apple-system, system-ui, sans-serif;
                   display: flex; justify-content: center; align-items: center;
                   height: 100vh; margin: 0; background: #1a1a2e; color: #e0e0e0; }
            .card { text-align: center; padding: 3rem; border-radius: 12px;
                    background: #16213e; box-shadow: 0 4px 24px rgba(0,0,0,0.3); }
            h2 { margin: 0 0 1rem; }
        </style></head><body><div class="card"><h2>%s</h2></div></body></html>""" % message
        self.send_response(200)
        self.send_header("Content-Type", "text/html")
        self.end_headers()
        self.wfile.write(html.encode())

    def log_message(self, format, *args):
        pass  # Suppress server logs


def wait_for_oauth_callback(timeout=120):
    """Start local server, wait for OAuth callback, return auth code."""
    OAuthCallbackHandler.auth_code = None
    OAuthCallbackHandler.state = None
    OAuthCallbackHandler.error = None

    server = http.server.HTTPServer(("localhost", LOCAL_PORT), OAuthCallbackHandler)
    server.timeout = timeout

    def serve():
        while OAuthCallbackHandler.auth_code is None and OAuthCallbackHandler.error is None:
            server.handle_request()

    thread = threading.Thread(target=serve, daemon=True)
    thread.start()
    thread.join(timeout=timeout)
    server.server_close()

    if OAuthCallbackHandler.error:
        return None, OAuthCallbackHandler.error
    return OAuthCallbackHandler.auth_code, None


# ---------------------------------------------------------------------------
# Whoop OAuth
# ---------------------------------------------------------------------------

def setup_whoop(config):
    banner("Whoop OAuth Setup")

    client_id = config.get("whoop_client_id", "")
    client_secret = config.get("whoop_client_secret", "")

    if not client_id:
        print("    You need a Whoop developer app.")
        print("    1. Go to https://developer-dashboard.whoop.com")
        print("    2. Create a team (if first time)")
        print("    3. Create an app with redirect URI: %s" % REDIRECT_URI)
        print("    4. Add scopes: read:recovery, read:cycles, read:sleep, read:workout")
        print()
        client_id = prompt("Whoop Client ID")
        client_secret = prompt("Whoop Client Secret")
        config["whoop_client_id"] = client_id
        config["whoop_client_secret"] = client_secret

    state = secrets.token_urlsafe(16)
    auth_params = urllib.parse.urlencode({
        "client_id": client_id,
        "redirect_uri": REDIRECT_URI,
        "response_type": "code",
        "scope": WHOOP_SCOPES,
        "state": state,
    })
    auth_url = WHOOP_AUTH_URL + "?" + auth_params

    print("    Opening browser for Whoop authorization...")
    print("    (If browser doesn't open, visit this URL:)")
    print("    %s" % auth_url)
    webbrowser.open(auth_url)

    print("    Waiting for authorization (up to 2 minutes)...")
    code, error = wait_for_oauth_callback()

    if error or not code:
        fail("Authorization failed: %s" % (error or "timeout"))
        return False

    # Exchange code for tokens
    print("    Exchanging code for tokens...")
    data = urllib.parse.urlencode({
        "grant_type": "authorization_code",
        "code": code,
        "client_id": client_id,
        "client_secret": client_secret,
        "redirect_uri": REDIRECT_URI,
    }).encode()
    req = urllib.request.Request(WHOOP_TOKEN_URL, data=data, method="POST")
    req.add_header("Content-Type", "application/x-www-form-urlencoded")

    try:
        with urllib.request.urlopen(req) as resp:
            tokens = json.loads(resp.read())
    except urllib.error.HTTPError as e:
        fail("Token exchange failed: %s %s" % (e.code, e.read().decode()))
        return False

    whoop_tokens = {
        "access_token": tokens["access_token"],
        "refresh_token": tokens.get("refresh_token", ""),
        "expires_at": time.time() + tokens.get("expires_in", 3600),
    }
    save_tokens(WHOOP_TOKENS_FILE, whoop_tokens)
    ok("Whoop tokens saved to %s" % WHOOP_TOKENS_FILE)

    # Test
    return test_whoop(whoop_tokens)


def test_whoop(tokens=None):
    if tokens is None:
        if not WHOOP_TOKENS_FILE.exists():
            fail("No Whoop tokens found")
            return False
        with open(WHOOP_TOKENS_FILE) as f:
            tokens = json.load(f)

    print("    Testing Whoop API...")
    req = urllib.request.Request(WHOOP_API + "/v1/user/profile/basic")
    req.add_header("Authorization", "Bearer " + tokens["access_token"])
    try:
        with urllib.request.urlopen(req) as resp:
            profile = json.loads(resp.read())
        ok("Connected as: %s %s" % (
            profile.get("first_name", "?"), profile.get("last_name", "?")))
        return True
    except urllib.error.HTTPError as e:
        fail("API test failed: %s" % e.code)
        return False


# ---------------------------------------------------------------------------
# Strava OAuth
# ---------------------------------------------------------------------------

def setup_strava(config):
    banner("Strava OAuth Setup")

    client_id = config.get("strava_client_id", "")
    client_secret = config.get("strava_client_secret", "")

    if not client_id:
        print("    You need a Strava API app.")
        print("    1. Go to https://www.strava.com/settings/api")
        print("    2. Create an application")
        print("    3. Set Authorization Callback Domain to: localhost")
        print()
        client_id = prompt("Strava Client ID")
        client_secret = prompt("Strava Client Secret")
        config["strava_client_id"] = client_id
        config["strava_client_secret"] = client_secret

    state = secrets.token_urlsafe(16)
    auth_params = urllib.parse.urlencode({
        "client_id": client_id,
        "redirect_uri": REDIRECT_URI,
        "response_type": "code",
        "scope": STRAVA_SCOPES,
        "state": state,
        "approval_prompt": "auto",
    })
    auth_url = STRAVA_AUTH_URL + "?" + auth_params

    print("    Opening browser for Strava authorization...")
    print("    (If browser doesn't open, visit this URL:)")
    print("    %s" % auth_url)
    webbrowser.open(auth_url)

    print("    Waiting for authorization (up to 2 minutes)...")
    code, error = wait_for_oauth_callback()

    if error or not code:
        fail("Authorization failed: %s" % (error or "timeout"))
        return False

    # Exchange code for tokens
    print("    Exchanging code for tokens...")
    data = urllib.parse.urlencode({
        "grant_type": "authorization_code",
        "code": code,
        "client_id": client_id,
        "client_secret": client_secret,
    }).encode()
    req = urllib.request.Request(STRAVA_TOKEN_URL, data=data, method="POST")
    req.add_header("Content-Type", "application/x-www-form-urlencoded")

    try:
        with urllib.request.urlopen(req) as resp:
            tokens = json.loads(resp.read())
    except urllib.error.HTTPError as e:
        fail("Token exchange failed: %s %s" % (e.code, e.read().decode()))
        return False

    strava_tokens = {
        "access_token": tokens["access_token"],
        "refresh_token": tokens.get("refresh_token", ""),
        "expires_at": tokens.get("expires_at", time.time() + 21600),
    }
    save_tokens(STRAVA_TOKENS_FILE, strava_tokens)
    ok("Strava tokens saved to %s" % STRAVA_TOKENS_FILE)

    # Test
    return test_strava(strava_tokens)


def test_strava(tokens=None):
    if tokens is None:
        if not STRAVA_TOKENS_FILE.exists():
            fail("No Strava tokens found")
            return False
        with open(STRAVA_TOKENS_FILE) as f:
            tokens = json.load(f)

    print("    Testing Strava API...")
    req = urllib.request.Request(STRAVA_API + "/athlete")
    req.add_header("Authorization", "Bearer " + tokens["access_token"])
    try:
        with urllib.request.urlopen(req) as resp:
            athlete = json.loads(resp.read())
        ok("Connected as: %s %s" % (
            athlete.get("firstname", "?"), athlete.get("lastname", "?")))
        return True
    except urllib.error.HTTPError as e:
        fail("API test failed: %s" % e.code)
        return False


# ---------------------------------------------------------------------------
# Token persistence
# ---------------------------------------------------------------------------

def save_tokens(path, tokens):
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    with open(path, "w") as f:
        json.dump(tokens, f, indent=2)
    os.chmod(str(path), 0o600)


# ---------------------------------------------------------------------------
# Config management
# ---------------------------------------------------------------------------

def load_or_create_config():
    CONFIG_DIR.mkdir(parents=True, exist_ok=True, mode=0o700)

    if CONFIG_FILE.exists():
        with open(CONFIG_FILE) as f:
            config = json.load(f)
        print("Loaded existing config from %s" % CONFIG_FILE)
        return config

    print("No config found. Creating new configuration.\n")

    # Detect vault path
    default_vault = str(Path.home() / "Documents" / "Cole Family")
    if not Path(default_vault).exists():
        default_vault = ""

    vault_path = prompt("Obsidian vault path", default_vault)
    journal_path = prompt("Journal subfolder (relative to vault)", "_Riley/Journal")

    config = {
        "vault_path": vault_path,
        "journal_path": journal_path,
    }

    save_config(config)
    return config


def save_config(config):
    CONFIG_DIR.mkdir(parents=True, exist_ok=True, mode=0o700)
    with open(CONFIG_FILE, "w") as f:
        json.dump(config, f, indent=2)
    os.chmod(str(CONFIG_FILE), 0o600)
    ok("Config saved to %s" % CONFIG_FILE)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="Set up Whoop + Strava OAuth for whoop-journal")
    parser.add_argument("--whoop-only", action="store_true", help="Only set up Whoop")
    parser.add_argument("--strava-only", action="store_true", help="Only set up Strava")
    parser.add_argument("--reauth", action="store_true", help="Force re-authentication")
    parser.add_argument("--test", action="store_true", help="Test existing tokens")
    args = parser.parse_args()

    banner("whoop-journal Setup")

    config = load_or_create_config()

    if args.test:
        print("Testing existing connections...\n")
        whoop_ok = test_whoop() if not args.strava_only else True
        strava_ok = test_strava() if not args.whoop_only else True
        if whoop_ok and strava_ok:
            banner("All connections working!")
        else:
            banner("Some connections failed. Run setup.py --reauth to fix.")
        return

    do_whoop = not args.strava_only
    do_strava = not args.whoop_only

    # Whoop
    if do_whoop:
        if WHOOP_TOKENS_FILE.exists() and not args.reauth:
            print("Whoop tokens already exist. Testing...")
            if test_whoop():
                print("    Whoop is already configured. Use --reauth to reconnect.\n")
            else:
                print("    Existing tokens failed. Re-authenticating...\n")
                setup_whoop(config)
        else:
            setup_whoop(config)

    # Strava
    if do_strava:
        if STRAVA_TOKENS_FILE.exists() and not args.reauth:
            print("Strava tokens already exist. Testing...")
            if test_strava():
                print("    Strava is already configured. Use --reauth to reconnect.\n")
            else:
                print("    Existing tokens failed. Re-authenticating...\n")
                setup_strava(config)
        else:
            setup_strava(config)

    # Save updated config (may have new client IDs)
    save_config(config)

    banner("Setup Complete!")
    print("Config:        %s" % CONFIG_FILE)
    if do_whoop:
        print("Whoop tokens:  %s" % WHOOP_TOKENS_FILE)
    if do_strava:
        print("Strava tokens: %s" % STRAVA_TOKENS_FILE)
    print()
    print("Test with:  python3 %s --test" % __file__)
    print("Sync with:  python3 %s" % (
        str(Path(__file__).parent / "sync.py")))
    print()


if __name__ == "__main__":
    main()
