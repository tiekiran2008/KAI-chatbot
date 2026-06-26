# Production Deployment Setup & Instructions

This document provides detailed configurations and sequence steps to deploy the **Antigravity AI Chatbot Platform** inside containerized production environments.

---

## 1. Production Architecture Overview

The production container stack comprises:
1. **Next.js Frontend (Port 3000)**: Server-side rendered React, containerized with multi-stage Alpine distributions to keep images ultra-small ($<150\text{MB}$).
2. **FastAPI Backend (Port 8000)**: Asynchronous Python server utilizing Uvicorn, with exception shielding, telemetry request logs, and Gemini exponential retry layers.
3. **ChromaDB (Embedded Persistent Volume)**: Embedded inside the backend container to ensure low-latency vector queries, with vectors persisted dynamically to a secure Docker volume (`chroma_data`).
4. **Supabase Integration**:
   * **Authentication**: Decoded and validated offline on the backend via pyjwt HS256 claims, with dynamic profile mirroring in PostgreSQL.
   * **Database**: Persistent relational storage (chats, messages, document metadata) stored in Supabase PostgreSQL (connected via SQL Alchemy PG-Pooler).

---

## 2. Environment Variables Configuration

Create a production `.env` file in the root workspace directory before starting containers:

```env
# ==============================================================================
# Production Environment Variables Configurations
# ==============================================================================

# --- LLM API ---
GEMINI_API_KEY="your-production-gemini-api-key-here"

# --- Security ---
SECRET_KEY="generate-a-strong-random-cryptographic-hash-here"

# --- Supabase Auth Configurations ---
# Retrieve JWT Secret from Supabase Dashboard -> Settings -> API -> JWT Secret
SUPABASE_JWT_SECRET="your-supabase-jwt-secret-here"

# --- Supabase Database (PostgreSQL pooler link) ---
DATABASE_URL="postgresql+asyncpg://postgres.your-ref-id:password@aws-0-us-east-1.pooler.supabase.com:5432/postgres"

# --- Next.js Frontend Public Configuration ---
# Retrieve these from your Supabase Dashboard
NEXT_PUBLIC_SUPABASE_URL="https://your-project-id.supabase.co"
NEXT_PUBLIC_SUPABASE_ANON_KEY="your-supabase-anon-key-here"
```

---

## 3. Container Deployment via Docker Compose

### Step 1: Clone and Configure Environment
Copy `.env.example` into `.env` and fill out your production tokens:
```bash
cp .env.example .env
# Edit the .env parameters with your actual secrets
```

### Step 2: Build and Launch Containers
Run the Docker Compose orchestration in detached mode to download dependencies, compile static Next.js pages, and start backend servers:
```bash
docker-compose up --build -d
```

### Step 3: Monitor Logs
Ensure that the services booted correctly and connected to ChromaDB/PostgreSQL:
```bash
docker-compose logs -f
```

### Step 4: Verify Status
Verify container states and health-check responses:
```bash
docker-compose ps
```

---

## 4. Production Hardening & Optimization Checklist

1. **Transaction Pooler**: Ensure `DATABASE_URL` uses the **Supabase Transaction Pooler (Port 5432 / 6543)**. Direct connections can easily saturate active PostgreSQL connections under high concurrent traffic.
2. **Reverse Proxy & SSL**: Configure NGINX or Traefik in front of the services. Note that Next.js streaming (SSE) requires `X-Accel-Buffering: no` and `Connection: keep-alive` headers to avoid buffer blockages.
3. **Volume Backups**: Regularly backup the persistent Docker volume (`chroma_data`) to prevent vector embedding losses if container storage is pruned.
