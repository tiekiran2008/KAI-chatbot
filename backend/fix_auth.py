import re

with open("main.py", "r", encoding="utf-8") as f:
    content = f.read()

# Remove passlib import
content = re.sub(r'from passlib\.context import CryptContext\n', '', content)

# Remove auth config and users_db
content = re.sub(
    r'# Authentication Configuration\nSECRET_KEY = os\.getenv\("SECRET_KEY".*?users_db = \{.*?\n\}\n',
    'oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")\n',
    content,
    flags=re.DOTALL
)

# Remove old models
content = re.sub(
    r'class Token\(BaseModel\):.*?class User\(BaseModel\):',
    'class User(BaseModel):',
    content,
    flags=re.DOTALL
)

content = re.sub(
    r'class UserInDB\(User\):.*?class ChatRequest\(BaseModel\):',
    'class ChatRequest(BaseModel):',
    content,
    flags=re.DOTALL
)

# Remove auth utilities
content = re.sub(
    r'def verify_password\(.*?async def get_current_user\(',
    'async def get_current_user(',
    content,
    flags=re.DOTALL
)

# Replace get_current_user body
new_get_current_user = """async def get_current_user(token: str = Depends(oauth2_scheme), request: Request = None):
    print("REAL AUTH FILE EXECUTED")
    print("AUTH HEADER:", request.headers.get("Authorization") if request else "request not available")
    print("TOKEN:", token[:50])

    SUPABASE_JWT_SECRET = os.getenv("SUPABASE_JWT_SECRET")
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        unverified_header = jwt.get_unverified_header(token)
        alg = unverified_header.get("alg", "HS256")

        if not SUPABASE_JWT_SECRET:
            print("[WARN] SUPABASE_JWT_SECRET not set - trusting unverified Supabase payload")
            payload = jwt.decode(
                token,
                options={"verify_signature": False, "verify_aud": False},
                algorithms=[alg],
                key="",
            )
        else:
            payload = jwt.decode(
                token,
                SUPABASE_JWT_SECRET,
                algorithms=[alg],
                options={"verify_aud": False},
            )

        supabase.postgrest.auth(token)
        supabase.options.headers["Authorization"] = f"Bearer {token}"

        sub = payload.get("sub")
        email = payload.get("email") or payload.get("user_metadata", {}).get("email", "")
        if not sub:
            print("AUTH FAILURE REASON: Missing 'sub' in Supabase token payload")
            raise credentials_exception

        username = email or sub
        return User(
            username=username,
            full_name=payload.get("user_metadata", {}).get("full_name", "Supabase User"),
            email=email,
            disabled=False,
            sub=sub,
            user_id=sub,
        )

    except HTTPException:
        raise
    except JWTError as e:
        print("JWT ERROR:", str(e))
        raise credentials_exception
    except Exception as e:
        print("UNEXPECTED AUTH ERROR:", str(e))
        raise

async def get_current_active_user"""

content = re.sub(
    r'async def get_current_user\(.*?async def get_current_active_user',
    new_get_current_user,
    content,
    flags=re.DOTALL
)

# Remove register and login endpoints
content = re.sub(
    r'@app\.post\("/api/v1/auth/register".*?@app\.get\("/api/v1/auth/me"\)',
    '@app.get("/api/v1/auth/me")',
    content,
    flags=re.DOTALL
)

with open("main.py", "w", encoding="utf-8") as f:
    f.write(content)
