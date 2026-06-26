import jwt
import logging
logger = logging.getLogger(__name__)
from typing import AsyncGenerator
from fastapi import Depends, HTTPException, Request, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from app.config import settings
from app.database import get_db
from app.models.user import User
from app.schemas.auth import TokenPayload
from app.utils.security import ALGORITHM

# Reusable OAuth2 password bearer flow pointing to our login route
reusable_oauth2 = OAuth2PasswordBearer(
    tokenUrl=f"{settings.API_V1_STR}/auth/login"
)

async def get_current_user(
    db: AsyncSession = Depends(get_db),
    token: str = Depends(reusable_oauth2),
    request: Request
) -> User:
    """Authenticate request and return the current user, with extensive debug logging."""
    """
    Dependency to authenticate and retrieve the currently logged-in user.
    Supports both local JWTs and federated Supabase JWT tokens.
    Automatically provisions/mirrors federated Supabase users in PostgreSQL.
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate authentication credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    # Debug: incoming header and token
    auth_header = request.headers.get("Authorization")
    print("AUTH HEADER:", auth_header)
    print("TOKEN:", token[:50])
    # Verify SUPABASE_JWT_SECRET is loaded
    if not getattr(settings, "SUPABASE_JWT_SECRET", None):
        print("[WARN] SUPABASE_JWT_SECRET is not configured – Supabase token verification will be skipped")
    else:
        print("[DEBUG] SUPABASE_JWT_SECRET is loaded")
    if not token:
        print("AUTH FAILURE REASON: No token provided")
        raise credentials_exception

    
    payload = None
    is_supabase_token = False
    
    # 1. Inspect Token without verification to determine issuer
    try:
        print("[DEBUG] Attempting unverified token decode to detect issuer...")
        unverified_payload = jwt.decode(token, options={"verify_signature": False, "verify_aud": False})
        print("[DEBUG] Unverified payload iss:", unverified_payload.get("iss"), "role:", unverified_payload.get("role"))
        if unverified_payload.get("iss") == "supabase" or unverified_payload.get("role") == "authenticated":
            is_supabase_token = True
    except jwt.PyJWTError as e:
        print("JWT ERROR:", str(e))
        print("AUTH FAILURE REASON:", str(e))
        raise credentials_exception
    except Exception as e:
        print("UNEXPECTED AUTH ERROR:", str(e))
        raise

    # 2. Decode Supabase Token
    if is_supabase_token:
        if not settings.SUPABASE_JWT_SECRET:
            # No secret configured; trust unverified payload (already decoded)
            payload = unverified_payload
        else:
            try:
                # Determine algorithm from token header to support ES256 and other algorithms
                unverified_header = jwt.get_unverified_header(token)
                alg = unverified_header.get("alg", "HS256")
                payload = jwt.decode(
                    token,
                    settings.SUPABASE_JWT_SECRET,
                    algorithms=[alg],
                    options={"verify_aud": False},
                )
            except jwt.exceptions.InvalidSignatureError as e:
                print("[ERROR] Supabase JWT signature verification failed")
                print("AUTH FAILURE REASON:", str(e))
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Supabase JWT signature verification failed. Ensure SUPABASE_JWT_SECRET matches your Supabase project."
                )
            except jwt.PyJWTError as e:
                print(f"[ERROR] Invalid Supabase token: {str(e)}")
                print("AUTH FAILURE REASON:", str(e))
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail=f"Invalid Supabase token: {str(e)}"
                )
            except Exception as e:
                print("UNEXPECTED AUTH ERROR:", str(e))
                raise
    else:
        # 3. Fallback to Local Auth Token Decoding
        try:
            payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[ALGORITHM])
        except jwt.PyJWTError as e:
            print(f"[ERROR] Local JWT decode failed: {str(e)}")
            print("AUTH FAILURE REASON:", str(e))
            raise credentials_exception
        except Exception as e:
            print("UNEXPECTED AUTH ERROR:", str(e))
            raise

    # Extract dynamic claims
    sub = payload.get("sub")
    email = payload.get("email")
    print(f"[DEBUG] Decoded JWT payload: {payload}")
    if not sub:
        print("AUTH FAILURE REASON: Missing 'sub' claim in JWT payload")
        raise credentials_exception

    # 3. Synchronize / Provision User Profile dynamically inside Relational DB
    import uuid
    try:
        user_uuid = uuid.UUID(str(sub))
    except ValueError:
        # If local subject is not a valid UUID (e.g. integer or custom string)
        # we generate a stable namespace UUID based on the subject string
        user_uuid = uuid.uuid5(uuid.NAMESPACE_DNS, str(sub))

    result = await db.execute(select(User).filter(User.id == user_uuid))
    user = result.scalars().first()

    if not user:
        if is_supabase_token:
            # Auto-provision Supabase authenticated user dynamically in DB
            user_metadata = payload.get("user_metadata", {})
            full_name = user_metadata.get("full_name") or user_metadata.get("name") or "Supabase User"
            
            # If email is not directly in root payload, inspect nested user metadata
            resolved_email = email or user_metadata.get("email") or f"{sub}@supabase.local"
            
            user = User(
                id=user_uuid,
                email=resolved_email,
                hashed_password="",  # Federated accounts do not maintain local passwords
                full_name=full_name,
                is_active=True,
                is_superuser=False
            )
            db.add(user)
            await db.commit()
            await db.refresh(user)
        else:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found in local system records"
            )
    
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Inactive user account"
        )

    return user

async def get_current_active_superuser(
    current_user: User = Depends(get_current_user),
) -> User:
    """
    Dependency to check if the authenticated user is an administrator.
    """
    logger.debug(f"Checking superuser status for user id {current_user.id}")
    if not current_user.is_superuser:
        logger.error("User is not superuser – raising 403")
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="The user does not have enough privileges",
        )
    return current_user
