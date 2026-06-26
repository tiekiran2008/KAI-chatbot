# ==============================================================================
# Production-Grade Next.js Frontend Dockerfile
# ==============================================================================
FROM node:18-alpine AS dependencies

# Install libc6-compat for alpine Node compilation optimizations
RUN apk add --no-cache libc6-compat
WORKDIR /app

# Install dependencies based on preferred lockfile
COPY package.json package-lock.json* ./
RUN npm ci

# --- Build Stage ---
FROM node:18-alpine AS builder
WORKDIR /app

COPY --from=dependencies /app/node_modules ./node_modules
COPY . .

# Set environment variables for production build
ENV NEXT_TELEMETRY_DISABLED=1 \
    NODE_ENV=production

# Execute production build
RUN npm run build

# --- Runner Stage ---
FROM node:18-alpine AS runner
WORKDIR /app

ENV NODE_ENV=production \
    NEXT_TELEMETRY_DISABLED=1 \
    PORT=3000

# Create secure system user to avoid root privilege issues inside production
RUN addgroup --system --gid 1001 nodejs && \
    adduser --system --uid 1001 nextjs

# Copy essential build assets and runner configurations
COPY --from=builder /app/public ./public
# Next.js standalone output copies node_modules and all necessary files automatically
COPY --from=builder --chown=nextjs:nodejs /app/.next/standalone ./
COPY --from=builder --chown=nextjs:nodejs /app/.next/static ./.next/static

USER nextjs

EXPOSE 3000

# Start Next.js optimized standalone server
CMD ["node", "server.js"]
