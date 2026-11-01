"""Local OAuth 2.0 Authorization Code + PKCE; encrypted token storage.

This is for a localhost SINGLE-USER app, not a public multi-user service.
"""
import base64
import hashlib
import os
import secrets
import time
from pathlib import Path
from urllib.parse import urlencode

import httpx
from cryptography.fernet import Fernet

PROVIDERS = {"google", "microsoft"}
GOOGLE_SCOPE = "https://www.googleapis.com/auth/calendar.readonly"
MICROSOFT_SCOPE = "offline_access Calendars.Read"
ROOT = Path(__file__).resolve().parents[3]
VAULT_KEY_FILE = Path(os.environ.get("DAYBUILDER_TOKEN_KEY_FILE", str(ROOT / "backend" / ".secrets" / "calendar.key")))


def config(provider: str):
    if provider not in PROVIDERS:
        raise ValueError("Unsupported calendar provider")
    if provider == "google":
        client_id = os.environ.get("GOOGLE_CLIENT_ID", "")
        secret = os.environ.get("GOOGLE_CLIENT_SECRET", "")
    else:
        client_id = os.environ.get("MICROSOFT_CLIENT_ID", "")
        secret = os.environ.get("MICROSOFT_CLIENT_SECRET", "")
    return client_id, secret


def configured(provider: str) -> bool:
    identifier, secret = config(provider)
    return bool(identifier and secret)


def redirect_uri(provider: str):
    # Use localhost (not 127.0.0.1): Microsoft portal supports http://localhost for Web redirect URIs.
    return f"http://localhost:8000/api/integrations/{provider}/callback"


def fernet():
    key = os.environ.get("DAYBUILDER_TOKEN_KEY", "")
    if not key:
        VAULT_KEY_FILE.parent.mkdir(parents=True, exist_ok=True)
        if not VAULT_KEY_FILE.exists():
            # Create without race / accidental overwrite; on Windows use a dedicated local account.
            try:
                with VAULT_KEY_FILE.open("xb") as stream:
                    stream.write(Fernet.generate_key())
            except FileExistsError:
                pass
            if os.name != "nt":
                VAULT_KEY_FILE.chmod(0o600)
        key = VAULT_KEY_FILE.read_text(encoding="ascii").strip()
    return Fernet(key.encode("ascii"))


def seal(value: str) -> str:
    return fernet().encrypt(value.encode()).decode()


def unseal(value: str) -> str:
    return fernet().decrypt(value.encode()).decode()


def sha256(s: str) -> str:
    return hashlib.sha256(s.encode()).hexdigest()


def new_attempt():
    state = secrets.token_urlsafe(32)
    verifier = secrets.token_urlsafe(64)
    challenge = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).rstrip(b"=").decode()
    return state, verifier, challenge


def authorization_url(provider: str, state: str, challenge: str):
    client, _ = config(provider)
    if provider == "google":
        base = "https://accounts.google.com/o/oauth2/v2/auth"
        params = dict(client_id=client, redirect_uri=redirect_uri(provider), response_type="code",
                      scope=GOOGLE_SCOPE, state=state, access_type="offline", prompt="consent",
                      code_challenge=challenge, code_challenge_method="S256")
    else:
        tenant = os.environ.get("MICROSOFT_TENANT_ID", "common")
        # Never interpolate arbitrary server/user URL into oauth endpoints.
        if not (tenant in {"common", "organizations", "consumers"} or
                __import__("re").fullmatch(r"[a-fA-F0-9-]{36}", tenant)):
            raise ValueError("Invalid Microsoft tenant configuration")
        base = f"https://login.microsoftonline.com/{tenant}/oauth2/v2.0/authorize"
        params = dict(client_id=client, redirect_uri=redirect_uri(provider), response_type="code",
                      scope=MICROSOFT_SCOPE, state=state, response_mode="query",
                      code_challenge=challenge, code_challenge_method="S256")
    return base + "?" + urlencode(params)


def token_url(provider: str) -> str:
    if provider == "google":
        return "https://oauth2.googleapis.com/token"
    tenant = os.environ.get("MICROSOFT_TENANT_ID", "common")
    if not (tenant in {"common", "organizations", "consumers"} or
            __import__("re").fullmatch(r"[a-fA-F0-9-]{36}", tenant)):
        raise ValueError("Invalid Microsoft tenant configuration")
    return f"https://login.microsoftonline.com/{tenant}/oauth2/v2.0/token"


async def token_request(provider: str, params: dict) -> dict:
    async with httpx.AsyncClient(timeout=20) as client:
        response = await client.post(token_url(provider), data=params)
        response.raise_for_status()
        data = response.json()
    if "access_token" not in data:
        raise ValueError("OAuth response missing access token")
    return data


async def exchange(provider: str, code: str, verifier: str) -> dict:
    client_id, client_secret = config(provider)
    return await token_request(provider, {
        "client_id": client_id,
        "client_secret": client_secret,
        "grant_type": "authorization_code",
        "code": code,
        "code_verifier": verifier,
        "redirect_uri": redirect_uri(provider),
    })


async def refresh(provider: str, refresh_token: str) -> dict:
    client_id, client_secret = config(provider)
    return await token_request(provider, {
        "client_id": client_id,
        "client_secret": client_secret,
        "grant_type": "refresh_token",
        "refresh_token": refresh_token,
    })


def normalized_tokens(raw: dict, old: dict | None = None) -> dict:
    old = old or {}
    return {
        "access_token": raw["access_token"],
        "refresh_token": raw.get("refresh_token") or old.get("refresh_token"),
        "expires_at": time.time() + max(int(raw.get("expires_in", 3600)) - 90, 0),
    }
