"""Simple token-based auth using shared password."""

import os
import hashlib
import secrets
from typing import Optional
from datetime import datetime, timezone, timedelta

SHARED_PASSWORD = os.environ.get('SHARED_PASSWORD', 'changeme')
TOKEN_TTL_HOURS = int(os.environ.get('TOKEN_TTL_HOURS', '24'))

tokens = {}

def generate_token(password: str) -> Optional[str]:
    """Validate password and return a token if valid."""
    if password != SHARED_PASSWORD:
        return None
    token = secrets.token_hex(16)
    tokens[token] = datetime.now(timezone.utc) + timedelta(hours=TOKEN_TTL_HOURS)
    return token


def validate_token(token: str) -> bool:
    """Check if token is valid and not expired."""
    if token not in tokens:
        return False
    if datetime.now(timezone.utc) > tokens[token]:
        del tokens[token]
        return False
    return True


def invalidate_token(token: str) -> None:
    """Logout - remove token."""
    if token in tokens:
        del tokens[token]