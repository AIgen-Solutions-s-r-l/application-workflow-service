# app/core/security.py
from jose import jwt

from app.core.config import settings


def verify_jwt_token(token: str) -> dict:
    """
    Verify JWT token.

    Args:
        token: Token to verify

    Returns:
        Decoded token data
    """
    return jwt.decode(token, settings.secret_key, algorithms=[settings.algorithm])
