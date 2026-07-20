import os
import secrets
import traceback
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any

from fastapi import FastAPI, Depends, HTTPException, status, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse, StreamingResponse
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from dotenv import load_dotenv
from passlib.context import CryptContext
from jose import JWTError, jwt
from google import genai
from google.genai import types
from supabase import create_client, Client
import asyncio
import logging
import json
import uuid

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()
print("API KEY FOUND:", bool(os.getenv("GEMINI_API_KEY")))
print("API KEY PREFIX:", str(os.getenv("GEMINI_API_KEY"))[:10])

# ============================================================
# Supabase client
# ============================================================
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

if not SUPABASE_URL or not SUPABASE_KEY:
    raise RuntimeError("SUPABASE_URL and SUPABASE_KEY must be set in .env")

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
logger.info("Supabase client initialized.")

# ============================================================
# Gemini client
# ============================================================
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
print(f"Loaded Gemini Model: {GEMINI_MODEL}")

if GEMINI_API_KEY:
    # Initialize Gemini client using google-genai SDK (v1+)
    gemini_client = genai.Client(api_key=GEMINI_API_KEY)
    print(f"GEMINI CLIENT: Initialized successfully with model={GEMINI_MODEL}")
else:
    gemini_client = None
    print("GEMINI CLIENT: GEMINI_API_KEY not found in environment — LLM features will fail")

# ============================================================
# Tool Implementations
# ============================================================

import ast
import operator
import math
import urllib.request
import urllib.parse


def _tool_get_current_time() -> str:
    """Returns the current date and time."""
    now = datetime.now()
    return now.strftime("%Y-%m-%d %H:%M:%S")


def _tool_calculate(expression: str) -> str:
    """Safely evaluate a mathematical expression."""
    _operators = {
        ast.Add: operator.add, ast.Sub: operator.sub,
        ast.Mult: operator.mul, ast.Div: operator.truediv,
        ast.FloorDiv: operator.floordiv, ast.Pow: operator.pow,
        ast.Mod: operator.mod, ast.USub: operator.neg, ast.UAdd: operator.pos,
    }
    _functions = {
        'sin': math.sin, 'cos': math.cos, 'tan': math.tan,
        'sqrt': math.sqrt, 'log': math.log, 'log10': math.log10,
        'exp': math.exp, 'pi': math.pi, 'e': math.e,
        'abs': abs, 'round': round,
    }
    def _eval(node):
        if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
            return node.value
        elif isinstance(node, ast.BinOp) and type(node.op) in _operators:
            return _operators[type(node.op)](_eval(node.left), _eval(node.right))
        elif isinstance(node, ast.UnaryOp) and type(node.op) in _operators:
            return _operators[type(node.op)](_eval(node.operand))
        elif isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id in _functions:
            fn = _functions[node.func.id]
            return fn(*[_eval(a) for a in node.args]) if callable(fn) else fn
        elif isinstance(node, ast.Name) and node.id in _functions and not callable(_functions[node.id]):
            return _functions[node.id]
        elif isinstance(node, ast.Expression):
            return _eval(node.body)
        raise ValueError(f"Unsupported syntax: {type(node)}")
    try:
        return str(_eval(ast.parse(expression, mode='eval')))
    except Exception as e:
        return f"Error evaluating expression: {e}"


def _tool_search_wikipedia(query: str) -> str:
    """Search Wikipedia and return a summary."""
    try:
        search_url = (
            f"https://en.wikipedia.org/w/api.php?action=query&list=search"
            f"&srsearch={urllib.parse.quote(query)}&utf8=&format=json&srlimit=1"
        )
        req = urllib.request.Request(search_url, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req, timeout=5.0) as r:
            data = json.loads(r.read().decode())
        results = data.get('query', {}).get('search', [])
        if not results:
            return f"No Wikipedia results found for '{query}'."
        title = results[0]['title']
        summary_url = (
            f"https://en.wikipedia.org/w/api.php?action=query&prop=extracts"
            f"&exsentences=5&exlimit=1&titles={urllib.parse.quote(title)}"
            f"&explaintext=1&formatversion=2&format=json"
        )
        req = urllib.request.Request(summary_url, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req, timeout=5.0) as r:
            sdata = json.loads(r.read().decode())
        pages = sdata.get('query', {}).get('pages', [])
        if not pages or 'extract' not in pages[0]:
            return f"Could not retrieve summary for '{title}'."
        return f"Title: {title}\nSummary: {pages[0]['extract'].strip()}"
    except Exception as e:
        return f"Error searching Wikipedia: {e}"


# Tool registry: name → callable
TOOL_REGISTRY = {
    "get_current_time": _tool_get_current_time,
    "calculate": _tool_calculate,
    "search_wikipedia": _tool_search_wikipedia,
}


def execute_tool(name: str, args: dict) -> str:
    """Execute a registered tool by name."""
    if name not in TOOL_REGISTRY:
        return f"Error: Tool '{name}' not found."
    try:
        result = TOOL_REGISTRY[name](**args)
        return str(result)
    except Exception as e:
        return f"Error executing tool '{name}': {e}"


# ============================================================
# Gemini Tool Declarations (typed function schemas for the SDK)
# ============================================================

GEMINI_TOOLS = types.Tool(
    function_declarations=[
        types.FunctionDeclaration(
            name="get_current_time",
            description=(
                "Returns the current date, time, day of the week, and timezone. "
                "ALWAYS call this tool when the user asks about the current time, "
                "date, day, or timezone. Never answer time questions from memory."
            ),
            parameters=types.Schema(
                type=types.Type.OBJECT,
                properties={},
            ),
        ),
        types.FunctionDeclaration(
            name="calculate",
            description=(
                "Evaluates a mathematical expression and returns the numeric result. "
                "Use this for any arithmetic, algebra, or math calculation."
            ),
            parameters=types.Schema(
                type=types.Type.OBJECT,
                properties={
                    "expression": types.Schema(
                        type=types.Type.STRING,
                        description="The mathematical expression to evaluate, e.g. '325 * 487'",
                    )
                },
                required=["expression"],
            ),
        ),
        types.FunctionDeclaration(
            name="search_wikipedia",
            description=(
                "Searches Wikipedia for a topic and returns a concise summary. "
                "Use this for factual lookups, historical information, or general knowledge."
            ),
            parameters=types.Schema(
                type=types.Type.OBJECT,
                properties={
                    "query": types.Schema(
                        type=types.Type.STRING,
                        description="The search query to look up on Wikipedia",
                    )
                },
                required=["query"],
            ),
        ),
    ]
)

# Keyword sets for hard fallback detection (used if Gemini skips the tool call)
_TIME_KEYWORDS = {
    "time", "clock", "date", "today", "now", "current time", "what time",
    "day", "hour", "minute", "second", "timezone", "what day",
}

# Print registered tools at startup
print("=" * 60)
print("TOOL REGISTRY: Registered tools at startup:")
for tool_name in TOOL_REGISTRY:
    print(f"  [OK] {tool_name}")
print(f"  Total: {len(TOOL_REGISTRY)} tools")
print("=" * 60)

# Authentication Configuration
SECRET_KEY = os.getenv("SECRET_KEY", secrets.token_urlsafe(32))
ALGORITHM = os.getenv("ALGORITHM", "HS256")
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "30"))

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="api/v1/auth/login")

# Mock User Database (auth stays in-memory; swap for Supabase auth later if needed)
users_db = {
    "user@example.com": {
        "username": "user@example.com",
        "full_name": "Test User",
        "email": "user@example.com",
        "hashed_password": pwd_context.hash("password123"),
        "disabled": False,
        "sub": "local-test-uuid",
        "user_id": "local-test-uuid",
    }
}

# In-memory document store (unchanged)
documents_store: Dict[str, Dict[str, Any]] = {}

# In-memory settings and avatars
settings_db: Dict[str, Dict[str, Any]] = {}
avatars_db: Dict[str, str] = {}

app = FastAPI(title="Gemini Chat API")

# Enable CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://127.0.0.1:3000",
    ],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "Accept", "Origin", "X-Requested-With"],
    expose_headers=["Content-Length"],
    max_age=600,
)


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    try:
        raw_body = await request.body()
        body_str = raw_body.decode("utf-8", errors="replace")
    except Exception:
        body_str = "<body unavailable>"

    def _safe_errors(errors):
        safe = []
        for err in errors:
            safe.append({k: (v.decode("utf-8", errors="replace") if isinstance(v, bytes) else str(v) if not isinstance(v, (str, int, float, bool, list, dict, type(None))) else v)
                         for k, v in err.items()})
        return safe

    logger.error(f"Validation error on {request.method} {request.url.path}: {exc.errors()}")
    logger.error(f"Request body: {body_str}")
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={"detail": _safe_errors(exc.errors()), "body": body_str},
    )


# ============================================================
# Pydantic Models
# ============================================================

class Token(BaseModel):
    access_token: str
    token_type: str

class TokenData(BaseModel):
    username: Optional[str] = None

class User(BaseModel):
    username: str
    email: Optional[str] = None
    full_name: Optional[str] = None
    disabled: Optional[bool] = None
    sub: Optional[str] = None  # Supabase UUID (auth.uid()), used as user_id in RLS
    user_id: Optional[str] = None

class UserInDB(User):
    hashed_password: str

class RegisterRequest(BaseModel):
    name: str
    email: str
    password: str

class LoginRequest(BaseModel):
    email: str
    password: str

class ChatRequest(BaseModel):
    message: str
    history: Optional[List[Dict[str, str]]] = []

class ChatResponse(BaseModel):
    response: str

class ChatCreate(BaseModel):
    title: Optional[str] = None

class ChatUpdate(BaseModel):
    title: str

class StreamMessageRequest(BaseModel):
    message: str

class SettingsUpdate(BaseModel):
    settings: Dict[str, Any]

class AvatarUpload(BaseModel):
    avatar_base64: str


# ============================================================
# Auth Utilities
# ============================================================

def verify_password(plain_password, hashed_password):
    return pwd_context.verify(plain_password, hashed_password)

def get_password_hash(password):
    return pwd_context.hash(password)

def get_user(db, username: str):
    if username in db:
        user_dict = db[username]
        return UserInDB(**user_dict)

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None):
    to_encode = data.copy()
    expire = datetime.utcnow() + (expires_delta or timedelta(minutes=15))
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)

async def get_current_user(token: str = Depends(oauth2_scheme), request: Request = None):
    print("REAL AUTH FILE EXECUTED")
    print("AUTH HEADER:", request.headers.get("Authorization") if request else "request not available")
    print("TOKEN:", token[:50])
    # Debug: show token slice
    print("JWT TOKEN FOUND:", token[:50])

    SUPABASE_JWT_SECRET = os.getenv("SUPABASE_JWT_SECRET")
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        # Step 1: Decode header without verification to detect algorithm and issuer
        print("[DEBUG] Decoding JWT header without verification...")
        unverified_header = jwt.get_unverified_header(token)
        alg = unverified_header.get("alg", "HS256")
        print(f"[DEBUG] JWT algorithm from header: {alg}")

        # Step 2: Decode payload without verification to detect if this is a Supabase token
        unverified_payload = jwt.decode(
            token,
            options={"verify_signature": False, "verify_aud": False},
            algorithms=[alg],
            key="",
        )
        iss = unverified_payload.get("iss", "")
        role = unverified_payload.get("role", "")
        print(f"[DEBUG] Unverified payload iss={iss!r} role={role!r}")
        is_supabase_token = (iss == "supabase" or role == "authenticated")
        print(f"[DEBUG] is_supabase_token={is_supabase_token}")

        if is_supabase_token:
            # Step 3a: Validate Supabase JWT
            if not SUPABASE_JWT_SECRET:
                print("[WARN] SUPABASE_JWT_SECRET not set - trusting unverified Supabase payload")
                payload = unverified_payload
            else:
                print(f"[DEBUG] Verifying Supabase token with alg={alg}...")
                payload = jwt.decode(
                    token,
                    SUPABASE_JWT_SECRET,
                    algorithms=[alg],
                    options={"verify_aud": False},
                )
                print("[DEBUG] Supabase token verified successfully")

            # *** Always attach JWT to Supabase client so RLS runs as the authenticated user ***
            print("SETTING SUPABASE JWT")
            print("TOKEN PREFIX =", token[:50])
            supabase.postgrest.auth(token)
            # Also set it on options to be thorough for other clients (storage/realtime)
            supabase.options.headers["Authorization"] = f"Bearer {token}"
            print("SUPABASE AUTH ATTACHED")

            # Supabase uses 'sub' as the user identifier (UUID) — this must match auth.uid() in RLS
            sub = payload.get("sub")
            email = payload.get("email") or payload.get("user_metadata", {}).get("email", "")
            print("JWT SUB =", sub)
            print(f"[DEBUG] Supabase user sub={sub} email={email}")
            if not sub:
                print("AUTH FAILURE REASON: Missing 'sub' in Supabase token payload")
                raise credentials_exception

            # Use email as username (display/lookup key), sub as RLS identity
            username = email or sub
            # Auto-register Supabase user into in-memory db if not present
            if username not in users_db:
                users_db[username] = {
                    "username": username,
                    "full_name": payload.get("user_metadata", {}).get("full_name", "Supabase User"),
                    "email": email,
                    "hashed_password": "",
                    "disabled": False,
                    "sub": sub,  # store the UUID for RLS
                    "user_id": sub,
                }
                print(f"[DEBUG] Auto-provisioned Supabase user: {username} sub={sub}")
            else:
                # Ensure sub is always up-to-date even for existing entries
                users_db[username]["sub"] = sub
                users_db[username]["user_id"] = sub
            return UserInDB(**users_db[username])


        else:
            # Step 3b: Validate local HS256 JWT
            print(f"[DEBUG] Validating local JWT with SECRET_KEY and alg={ALGORITHM}...")
            payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
            username: str = payload.get("sub")
            if username is None:
                print("AUTH FAILURE REASON: Missing 'sub' in local JWT payload")
                raise credentials_exception
            token_data = TokenData(username=username)
            user = get_user(users_db, username=token_data.username)
            if user is None:
                print(f"AUTH FAILURE REASON: User '{token_data.username}' not found in local db")
                raise credentials_exception
            print(f"[DEBUG] Local user authenticated: {user.username}")
            return user

    except HTTPException:
        raise
    except JWTError as e:
        print("JWT ERROR:", str(e))
        print("AUTH FAILURE REASON:", str(e))
        raise credentials_exception
    except Exception as e:
        print("UNEXPECTED AUTH ERROR:", str(e))
        raise

async def get_current_active_user(current_user: User = Depends(get_current_user)):
    if current_user.disabled:
        raise HTTPException(status_code=400, detail="Inactive user")
    return current_user


# ============================================================
# Supabase Helpers
# ============================================================

def db_get_chat(chat_id: str, user_id: str) -> Optional[Dict]:
    """Fetch a single chat row owned by `user_id`. Returns None if not found."""
    print("===== DB_GET_CHAT =====")
    print("chat_id =", chat_id)
    print("user_id =", user_id)
    try:
        # Bypass query — find by id only, ignoring user_id (to detect user_id mismatch)
        bypass = supabase.table("chats").select("*").eq("id", chat_id).execute()
        print("BYPASS QUERY RESULT (no user_id filter) =", bypass.data)
        if bypass.data:
            stored_uid = bypass.data[0].get("user_id")
            print("STORED user_id in DB =", stored_uid)
            print("QUERIED user_id       =", user_id)
            if stored_uid != user_id:
                print("!!! USER_ID MISMATCH — stored:", stored_uid, "queried:", user_id)

        print("SUPABASE QUERY START")
        res = supabase.table("chats").select("*").eq("id", chat_id).eq("user_id", user_id).execute()
        print("QUERY DATA =", res.data)
        print("QUERY COUNT =", len(res.data) if res.data else 0)
        if res.data:
            return res.data[0]
        return None
    except Exception as e:
        print("DB_GET_CHAT EXCEPTION =", str(e))
        logger.error(f"db_get_chat error: {e}")
        return None

def db_list_chats(user_id: str) -> List[Dict]:
    """Return all chats for the given user_id, newest first."""
    try:
        res = supabase.table("chats").select("*").eq("user_id", user_id).order("created_at", desc=True).execute()
        return res.data or []
    except Exception as e:
        logger.error(f"db_list_chats error: {e}")
        return []

def db_create_chat(chat_id: str, user_id: str, title: str) -> Dict:
    """Insert a new chat row into Supabase and return it."""
    now = datetime.utcnow().isoformat()
    record = {
        "id": chat_id,
        "user_id": user_id,
        "title": title,
        "created_at": now,
    }
    print("===== DB_CREATE_CHAT =====")
    print("chat_id =", chat_id)
    print("user_id =", user_id)
    print("INSERT RECORD =", record)

    # STEP 3a: Before Supabase insert – log intent
    print("STEP 3a: Preparing Supabase insert for chat", chat_id)
    print("SUPABASE CLIENT AUTH STATE")
    print(getattr(supabase.postgrest, "_auth_token", None))
    print("Authorization header:", supabase.postgrest.headers.get("Authorization", "<not set>"))
    logger.info(
        "Attempting to insert chat %s for user_id=%s",
        chat_id,
        user_id,
    )

    # STEP 3b: Execute the actual insert
    print("STEP 3b: Executing Supabase insert for chat", chat_id)
    try:
        res = supabase.table("chats").insert(record).execute()
        inserted = res.data[0] if res.data else record
        print("STEP 3c: Supabase insert completed, returned =", inserted)
        logger.info("Chat %s inserted successfully", chat_id)
        return inserted
    except Exception as e:
        print("STEP 3c: Supabase insert FAILED =", str(e))
        logger.error(f"db_create_chat error: {e}")
        raise

def db_update_chat_title(chat_id: str, user_id: str, title: str) -> Optional[Dict]:
    """Update the title of a chat. Returns updated row or None."""
    try:
        res = (
            supabase.table("chats")
            .update({"title": title})
            .eq("id", chat_id)
            .eq("user_id", user_id)
            .execute()
        )
        return res.data[0] if res.data else None
    except Exception as e:
        logger.error(f"db_update_chat_title error: {e}")
        return None

def db_delete_chat(chat_id: str, user_id: str):
    """Delete a chat and its messages (messages cascade if FK set, else delete manually)."""
    # Delete messages first in case no cascade is configured
    supabase.table("messages").delete().eq("chat_id", chat_id).execute()
    supabase.table("chats").delete().eq("id", chat_id).eq("user_id", user_id).execute()

def db_get_messages(chat_id: str) -> List[Dict]:
    """Return all messages for a chat, ordered chronologically."""
    try:
        res = (
            supabase.table("messages")
            .select("*")
            .eq("chat_id", chat_id)
            .order("created_at", desc=False)
            .execute()
        )
        return res.data or []
    except Exception as e:
        logger.error(f"db_get_messages error: {e}")
        return []

def db_insert_message(msg_id: str, chat_id: str, role: str, content: str, citations: list = None) -> Dict:
    """Insert a single message row."""
    now = datetime.utcnow().isoformat()
    record = {
        "id": msg_id,
        "chat_id": chat_id,
        "role": role,
        "content": content,
        "citations": citations or [],
        "created_at": now,
    }
    supabase.table("messages").insert(record).execute()
    return record


# ============================================================
# Routes
# ============================================================

@app.get("/")
async def root():
    return {"message": "Welcome to the Gemini Chat API"}


# --- Auth ---

@app.post("/api/v1/auth/register", status_code=status.HTTP_201_CREATED)
async def register(user: RegisterRequest):
    if user.email in users_db:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already registered"
        )
    users_db[user.email] = {
        "username": user.email,
        "full_name": user.name,
        "email": user.email,
        "hashed_password": get_password_hash(user.password),
        "disabled": False,
    }
    return {"message": "User created successfully"}


@app.post("/api/v1/auth/login")
async def login(credentials: LoginRequest):
    user = get_user(users_db, credentials.email)
    if not user or not verify_password(credentials.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": user.username}, expires_delta=access_token_expires
    )
    return {
        "access_token": access_token,
        "token_type": "bearer",
        "user": {"email": user.email, "name": user.full_name},
    }


@app.get("/api/v1/auth/me")
async def get_me(current_user: User = Depends(get_current_active_user)):
    return {
        "email": current_user.email,
        "full_name": current_user.full_name,
        "username": current_user.username,
        "avatar": avatars_db.get(current_user.username)
    }

# ============================================================
# Settings & Profile Endpoints
# ============================================================

@app.get("/api/v1/settings")
async def get_settings(current_user: User = Depends(get_current_active_user)):
    user_id = current_user.sub or current_user.user_id or current_user.username
    try:
        res = supabase.table("user_settings").select("settings").eq("user_id", user_id).execute()
        if res.data and len(res.data) > 0:
            return {"settings": res.data[0]["settings"]}
    except Exception as e:
        logger.warning(f"Failed to fetch settings from Supabase, using fallback: {e}")
    return {"settings": settings_db.get(user_id, {})}

@app.post("/api/v1/settings")
async def update_settings(update: SettingsUpdate, current_user: User = Depends(get_current_active_user)):
    user_id = current_user.sub or current_user.user_id or current_user.username
    current_settings = settings_db.get(user_id, {})
    current_settings.update(update.settings)
    settings_db[user_id] = current_settings
    try:
        res = supabase.table("user_settings").select("settings").eq("user_id", user_id).execute()
        if res.data and len(res.data) > 0:
            supabase.table("user_settings").update({"settings": current_settings}).eq("user_id", user_id).execute()
        else:
            supabase.table("user_settings").insert({"user_id": user_id, "settings": current_settings}).execute()
    except Exception as e:
        logger.warning(f"Failed to save settings to Supabase, saved to fallback: {e}")
    return {"status": "success", "settings": current_settings}

@app.post("/api/v1/users/avatar")
async def upload_avatar(upload: AvatarUpload, current_user: User = Depends(get_current_active_user)):
    avatars_db[current_user.username] = upload.avatar_base64
    return {"status": "success"}


# ============================================================
# /api/v1/chat  — Chat session CRUD (Supabase-backed)
# ============================================================

def generate_chat_title(message: str) -> str:
    """Generate a short title (4-8 words) from the user's first message."""
    words = message.split()
    if len(words) > 6:
        return " ".join(words[:6]) + "..."
    return " ".join(words)


@app.get("/api/v1/chat")
async def list_chats(current_user: User = Depends(get_current_active_user)):
    """Return all chat sessions for the current user, newest first."""
    uid = current_user.user_id
    chats = db_list_chats(uid)
    result = []
    for c in chats:
        # Fetch the last message for preview
        msgs = db_get_messages(c["id"])
        
        # Retrospective title update for generic "New Chat"
        if (c.get("title") == "New Chat" or not c.get("title")) and msgs:
            first_user_msg = next((m for m in msgs if m["role"] == "user"), None)
            if first_user_msg:
                new_title = generate_chat_title(first_user_msg["content"])
                db_update_chat_title(c["id"], uid, new_title)
                c["title"] = new_title
                
        last_msg = msgs[-1]["content"] if msgs else ""
        result.append({
            "id": c["id"],
            "title": c["title"],
            "created_at": c["created_at"],
            "last_message": last_msg,
        })
    return result


@app.post("/api/v1/chat/", status_code=201)
async def create_chat(
    body: ChatCreate,
    current_user: User = Depends(get_current_active_user),
):
    # STEP 1: Route entered
    print("STEP 1: Route entered")
    # STEP 2: User authenticated (dependency resolved)
    print("STEP 2: User authenticated", current_user.username if hasattr(current_user, "username") else current_user)
    """Create a new chat session in Supabase."""
    chat_id = str(uuid.uuid4())
    # STEP 3: Chat insert started
    print("STEP 3: Chat insert started", chat_id)
    user_id = current_user.user_id
    print("CHAT USER_ID =", user_id)
    record = db_create_chat(
        chat_id=chat_id,
        user_id=user_id,
        title=body.title or "New Chat",
    )
    # STEP 4: Chat insert complete
    print("STEP 4: Chat insert complete", record)
    # Existing debug prints (keep for reference)
    print("CURRENT USER:", current_user)
    print("INSERT RECORD:", record)
    return {"id": record["id"], "title": record["title"], "created_at": record["created_at"]}


@app.get("/api/v1/chat/{chat_id}")
async def get_chat(
    chat_id: str,
    current_user: User = Depends(get_current_active_user),
):
    """Fetch a single chat with its full message history from Supabase."""
    uid = current_user.user_id
    chat = db_get_chat(chat_id, uid)
    if not chat:
        raise HTTPException(status_code=404, detail="Chat not found")
    messages = db_get_messages(chat_id)

    # Retrospective update for "New Chat" titles
    if (chat.get("title") == "New Chat" or not chat.get("title")) and messages:
        first_user_msg = next((m for m in messages if m["role"] == "user"), None)
        if first_user_msg:
            new_title = generate_chat_title(first_user_msg["content"])
            db_update_chat_title(chat_id, uid, new_title)
            chat["title"] = new_title

    return {"id": chat["id"], "title": chat["title"], "messages": messages}


@app.delete("/api/v1/chat/{chat_id}", status_code=204)
async def delete_chat(
    chat_id: str,
    current_user: User = Depends(get_current_active_user),
):
    """Delete a chat and all its messages from Supabase."""
    uid = current_user.user_id
    chat = db_get_chat(chat_id, uid)
    if not chat:
        raise HTTPException(status_code=404, detail="Chat not found")
    db_delete_chat(chat_id, uid)


@app.patch("/api/v1/chat/{chat_id}")
async def rename_chat(
    chat_id: str,
    body: ChatUpdate,
    current_user: User = Depends(get_current_active_user),
):
    """Rename a chat session in Supabase."""
    uid = current_user.user_id
    chat = db_get_chat(chat_id, uid)
    if not chat:
        raise HTTPException(status_code=404, detail="Chat not found")
    updated = db_update_chat_title(chat_id, uid, body.title)
    return {"id": chat_id, "title": body.title}


# ============================================================
# POST /api/v1/chat/{id}/stream  — Gemini SSE streaming
# ============================================================

@app.post("/api/v1/chat/{chat_id}/stream")
async def stream_chat_message(
    chat_id: str,
    body: StreamMessageRequest,
    current_user: User = Depends(get_current_active_user),
):
    """
    Stream a Gemini response for the given message.
    - Saves the user message to Supabase `messages` table before streaming.
    - Saves the completed AI response to Supabase `messages` table when done.

    SSE event format:
      data: {"token": "..."}                                         — incremental text
      data: {"done": true, "message_id": "...",
             "content": "...", "citations": []}                      — completion signal
    """
    print("========== STREAM DEBUG ==========")
    print("chat_id =", chat_id)
    print("current_user =", current_user)
    print("email =", getattr(current_user, "email", None))
    print("username =", getattr(current_user, "username", None))
    print("sub (RLS uid) =", getattr(current_user, "sub", None))
    print("==================================")

    # Use sub (UUID) as user_id for RLS — must match what db_create_chat stored
    lookup_user_id = current_user.user_id
    print("QUERYING CHAT")
    print("chat_id =", chat_id)
    print("user_id =", lookup_user_id)
    chat = db_get_chat(chat_id, lookup_user_id)
    print("QUERY RESULT")
    print("chat =", chat)
    if not chat:
        # Provide detailed error so frontend knows it's a DB lookup issue, not Gemini
        raise HTTPException(
            status_code=404,
            detail=f"Chat not found for chat_id={chat_id} user_id={lookup_user_id}. "
                   f"This is a DB lookup failure — the Gemini code was never reached."
        )

    # GEMINI STEP 1: Validate API key
    print("GEMINI STEP 1")
    if not GEMINI_API_KEY:
        raise HTTPException(status_code=500, detail="GEMINI_API_KEY not configured")
    if not gemini_client:
        raise HTTPException(status_code=500, detail="Gemini client failed to initialize — check GEMINI_API_KEY")

    # Use model from env (loaded at startup)
    model_name = GEMINI_MODEL
    print("GEMINI STEP 2")
    print("SDK TYPE = google-genai")
    print("MODEL =", model_name)

    async def generate():
        full_response = ""
        assistant_msg_id = str(uuid.uuid4())
        user_msg_id = str(uuid.uuid4())
        try:
            # ── Load chat history from Supabase ─────────────────────────────
            history = db_get_messages(chat_id)
            gemini_history: List[types.Content] = []
            for m in history:
                role = "model" if m["role"] == "assistant" else "user"
                gemini_history.append(
                    types.Content(
                        role=role,
                        parts=[types.Part.from_text(text=m["content"])],
                    )
                )
            # Append current user message
            gemini_history.append(
                types.Content(role="user", parts=[types.Part.from_text(text=body.message)])
            )

            # ── Save user message to Supabase before streaming ──────────────
            db_insert_message(user_msg_id, chat_id, "user", body.message)

            # ── Hard keyword fallback: detect time queries before calling Gemini
            msg_lower = body.message.lower()
            _forced_tool: Optional[str] = None
            _forced_tool_args: dict = {}
            if any(kw in msg_lower for kw in _TIME_KEYWORDS):
                _forced_tool = "get_current_time"
                _forced_tool_args = {}
                print(f"[Tool Fallback] Time keyword detected in: {body.message!r}")
                print(f"[Tool Fallback] Forcing tool: get_current_time")

            # ── System prompt that MANDATES tool usage ───────────────────
            system_instruction = (
                "You are KAI, a helpful and intelligent AI assistant.\n\n"
                "CRITICAL TOOL USAGE RULES — you MUST follow these absolutely:\n"
                "1. You have access to tools. When a matching tool exists for the user's request, "
                "you MUST call the tool instead of answering from your own knowledge.\n"
                "2. For ANY question about the current time, date, day of the week, or timezone: "
                "you MUST call the get_current_time tool. Do NOT say 'As an AI, I don't have access "
                "to real-time information'. That response is FORBIDDEN when a tool exists.\n"
                "3. For ANY mathematical calculation: you MUST call the calculate tool.\n"
                "4. For factual lookups or general knowledge: you MUST call the search_wikipedia tool.\n"
                "5. After the tool returns its result, use that result to compose your final answer.\n"
                "6. Never refuse to use a tool when one is available and appropriate."
            )

            # ── Log which tools are being sent to Gemini ─────────────────
            tool_names = [fd.name for fd in GEMINI_TOOLS.function_declarations]
            print("GEMINI STEP 3")
            print(f"[Tool Calling] Tools sent to Gemini: {tool_names}")
            print(f"[Tool Calling] User message: {body.message!r}")

            # Fetch settings
            user_id_for_settings = current_user.sub or current_user.user_id or current_user.username
            user_settings = settings_db.get(user_id_for_settings, {})
            try:
                res = supabase.table("user_settings").select("settings").eq("user_id", user_id_for_settings).execute()
                if res.data and len(res.data) > 0:
                    user_settings = res.data[0]["settings"]
            except Exception:
                pass

            # Apply user settings to Gemini configuration
            sys_prompt = user_settings.get("system_prompt")
            if sys_prompt and sys_prompt.strip():
                system_instruction = sys_prompt + "\n\n" + system_instruction

            model_id = user_settings.get("ai_model", model_name)
            temperature = float(user_settings.get("temperature", 1.0))
            max_output_tokens = int(user_settings.get("max_tokens", 8192)) if user_settings.get("max_tokens") else None
            print(f"Calling Gemini model={model_id} with {len(gemini_history)} turns (temp={temperature}, max_tokens={max_output_tokens})")

            gemini_config = types.GenerateContentConfig(
                system_instruction=system_instruction,
                temperature=temperature,
                max_output_tokens=max_output_tokens,
                tools=[GEMINI_TOOLS],
                tool_config=types.ToolConfig(
                    function_calling_config=types.FunctionCallingConfig(
                        mode="AUTO",  # Gemini decides when to call tools
                    )
                ),
            )

            # ── Stream the response directly to avoid TTFB delays ──
            print(f"[Tool Calling] Starting generate_content_stream...")
            initial_stream = await gemini_client.aio.models.generate_content_stream(
                model=model_id,
                contents=gemini_history,
                config=gemini_config,
            )

            fc = None
            async for chunk in initial_stream:
                if chunk.candidates and chunk.candidates[0].content and chunk.candidates[0].content.parts:
                    for part in chunk.candidates[0].content.parts:
                        if hasattr(part, "function_call") and part.function_call:
                            fc = part.function_call
                            break
                        if part.text:
                            full_response += part.text
                            yield f"data: {json.dumps({'token': part.text})}\n\n"
                
                # If we detected a function call, break the stream
                if fc:
                    break

            if fc:
                print(f"[Tool Calling] [OK] Gemini requested tool: {fc.name!r}  args: {dict(fc.args or {})!r}")
                fc_name = fc.name
                fc_args = {k: v for k, v in fc.args.items()} if fc.args else {}
                tool_result = execute_tool(fc_name, fc_args)
                print(f"[Tool Calling] [OK] Tool '{fc_name}' result: {tool_result!r}")

                # Build updated contents with tool request + result
                try:
                    fc_part = types.Part.from_function_call(name=fc_name, args=fc_args)
                except AttributeError:
                    fc_part = types.Part(function_call=types.FunctionCall(name=fc_name, args=fc_args))

                gemini_history.append(types.Content(role="model", parts=[fc_part]))
                fr_part = types.Part.from_function_response(
                    name=fc_name,
                    response={"result": tool_result}
                )
                gemini_history.append(types.Content(role="user", parts=[fr_part]))

                print("[Tool Calling] Streaming final answer after tool execution...")
                follow_stream = await gemini_client.aio.models.generate_content_stream(
                    model=model_name,
                    contents=gemini_history,
                    config=gemini_config,
                )
                async for chunk in follow_stream:
                    if chunk.text:
                        full_response += chunk.text
                        yield f"data: {json.dumps({'token': chunk.text})}\n\n"

            elif _forced_tool and not full_response.strip():
                # Hard fallback: Gemini skipped the tool, execute it directly 
                print(f"[Tool Fallback] [!] Gemini skipped tool. Forcing execution of '{_forced_tool}'")
                tool_result = execute_tool(_forced_tool, _forced_tool_args)
                print(f"[Tool Fallback] [OK] Forced tool result: {tool_result!r}")

                try:
                    fc_part = types.Part.from_function_call(name=_forced_tool, args=_forced_tool_args)
                except AttributeError:
                    fc_part = types.Part(function_call=types.FunctionCall(name=_forced_tool, args=_forced_tool_args))

                gemini_history.append(types.Content(role="model", parts=[fc_part]))
                fr_part = types.Part.from_function_response(
                    name=_forced_tool,
                    response={"result": tool_result}
                )
                gemini_history.append(types.Content(role="user", parts=[fr_part]))

                follow_stream = await gemini_client.aio.models.generate_content_stream(
                    model=model_name,
                    contents=gemini_history,
                    config=gemini_config,
                )
                async for chunk in follow_stream:
                    if chunk.text:
                        full_response += chunk.text
                        yield f"data: {json.dumps({'token': chunk.text})}\n\n"

            print(f"GEMINI STEP 3 complete. Response length: {len(full_response)} chars")

        except asyncio.TimeoutError:
            err_msg = f"Gemini request timed out after 60 seconds (model={model_name})"
            logger.error(err_msg)
            err_token = f"[Error: Request timed out. The AI is taking too long to respond.]"
            full_response += err_token
            yield f"data: {json.dumps({'token': err_token, 'error': 'timeout'})}\n\n"

        except Exception as e:
            tb = traceback.format_exc()
            err_str = str(e)
            logger.exception(f"Gemini stream error in chat {chat_id}: {e}\n{tb}")

            # Classify error for better client messages
            if "API_KEY_INVALID" in err_str or "invalid api key" in err_str.lower() or "401" in err_str:
                err_token = "[Error: Invalid Gemini API key. Please check your GEMINI_API_KEY.]"
                logger.error("GEMINI ERROR TYPE: Invalid API key")
            elif "not found" in err_str.lower() and "model" in err_str.lower():
                err_token = f"[Error: Model '{model_name}' not found. Update GEMINI_MODEL in .env.]"
                logger.error(f"GEMINI ERROR TYPE: Model not found — model={model_name}")
            elif "quota" in err_str.lower() or "429" in err_str or "RESOURCE_EXHAUSTED" in err_str:
                err_token = "[Error: Gemini rate limit exceeded. Please wait a moment and try again.]"
                logger.error("GEMINI ERROR TYPE: Rate limit / quota exceeded")
            elif "connect" in err_str.lower() or "network" in err_str.lower() or "ssl" in err_str.lower():
                err_token = "[Error: Network error connecting to Gemini API. Check your internet connection.]"
                logger.error("GEMINI ERROR TYPE: Network / connection error")
            else:
                err_token = f"[Gemini error: {err_str}]"
                logger.error(f"GEMINI ERROR TYPE: Unclassified — {err_str}")

            full_response += err_token
            yield f"data: {json.dumps({'token': err_token, 'traceback': tb})}\n\n"

        finally:
            # GEMINI STEP 4: Save completed response to Supabase
            print("GEMINI STEP 4: Generation finished, saving response")
            db_insert_message(
                msg_id=assistant_msg_id,
                chat_id=chat_id,
                role="assistant",
                content=full_response,
                citations=[],
            )
            
            final_event = {
                'done': True,
                'message_id': assistant_msg_id,
                'content': full_response,
                'citations': []
            }
            
            # If it's the first message, generate and save title, then send to client
            if chat.get("title") == "New Chat" or not chat.get("title"):
                new_title = generate_chat_title(body.message)
                db_update_chat_title(chat_id, lookup_user_id, new_title)
                final_event["new_title"] = new_title

            yield f"data: {json.dumps(final_event)}\n\n"

    return StreamingResponse(generate(), media_type="text/event-stream")


# ============================================================
# /api/v1/documents  — document management (in-memory, unchanged)
# ============================================================

@app.get("/api/v1/documents")
async def list_documents(current_user: User = Depends(get_current_active_user)):
    """Return all documents belonging to the current user."""
    return [d for d in documents_store.values() if d["owner"] == current_user.username]


@app.delete("/api/v1/documents/{doc_id}", status_code=204)
async def delete_document(
    doc_id: str,
    current_user: User = Depends(get_current_active_user),
):
    """Delete a document."""
    doc = documents_store.get(doc_id)
    if not doc or doc["owner"] != current_user.username:
        raise HTTPException(status_code=404, detail="Document not found")
    del documents_store[doc_id]
