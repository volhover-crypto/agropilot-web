# backend/connectors/oauth.py -- PKCE S256 для oauth-коннекторов (§39.3)
#
# Фикс-паттерн Octop «OAuth 回调安全加固»: код-обмен только с PKCE S256,
# callback -- только по явному списку redirect_uri (точное совпадение).

import base64
import hashlib
import secrets

# «unreserved characters» RFC 7636: ALPHA / DIGIT / "-" / "." / "_" / "~"
_VERIFIER_ALPHABET = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-._~"


def make_code_verifier(length: int = 64) -> str:
    """Верификатор 43–128 символов из разрешённого алфавита."""
    if not 43 <= length <= 128:
        raise ValueError("code_verifier length must be 43..128")
    return "".join(secrets.choice(_VERIFIER_ALPHABET) for _ in range(length))


def make_code_challenge(verifier: str) -> str:
    """S256: BASE64URL(SHA256(verifier)) без padding."""
    digest = hashlib.sha256(verifier.encode("ascii")).digest()
    return base64.urlsafe_b64encode(digest).decode("ascii").rstrip("=")


def check_redirect_uri(uri: str, allowed: list[str]) -> bool:
    """Точное совпадение с явным списком разрешённых redirect-uri."""
    return bool(uri) and uri in set(allowed or [])
