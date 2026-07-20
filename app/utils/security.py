import jwt
from datetime import datetime, timedelta, timezone
from typing import Any, Union

from app.config import settings

ALGORITHM = "HS256"

def create_access_token(subject: Union[str, Any], expires_delta: timedelta = None) -> str:
    """
    Create a secure HS256 JWT access token.
    """
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(
            minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES
        )
    
    to_encode = {
        "exp": expire,
        "sub": str(subject),
        "iat": datetime.now(timezone.utc)
    }
    
    encoded_jwt = jwt.encode(to_encode, settings.SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

def decode_access_token(token: str) -> dict:
    """
    Decode and validate a JWT access token.
    Raises jwt.PyJWTError for invalid/expired tokens.
    """
    return jwt.decode(token, settings.SECRET_KEY, algorithms=[ALGORITHM])
