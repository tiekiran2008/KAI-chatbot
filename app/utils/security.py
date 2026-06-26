import jwt
from datetime import datetime, timedelta, timezone
from typing import Any, Union
import bcrypt

from app.config import settings

ALGORITHM = "HS256"

def get_password_hash(password: str) -> str:
    """
    Generate a secure bcrypt hash of a plain text password.
    """
    # bcrypt requires bytes
    pwd_bytes = password.encode('utf-8')
    # Increased rounds for better security against brute force
    salt = bcrypt.gensalt(rounds=14)
    hashed = bcrypt.hashpw(pwd_bytes, salt)
    return hashed.decode('utf-8')

def verify_password(plain_password: str, hashed_password: str) -> bool:
    """
    Verify a plain password against the stored bcrypt hash.
    """
    pwd_bytes = plain_password.encode('utf-8')
    hashed_bytes = hashed_password.encode('utf-8')
    return bcrypt.checkpw(pwd_bytes, hashed_bytes)

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
