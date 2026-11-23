# Stage 1: Build React + Vite frontend
FROM node:20-slim AS frontend-builder
WORKDIR /build
COPY frontend/package*.json ./
RUN npm install
COPY frontend/ ./
RUN npm run build

# Stage 2: Runtime Python container
FROM python:3.11-slim

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

# Install system packages needed by Chromium, Playwright, fonts, and Makefile execution
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    git \
    make \
    fontconfig \
    libgl1 \
    libglib2.0-0 \
    libnss3 \
    libnspr4 \
    libatk1.0-0 \
    libatk-bridge2.0-0 \
    libcups2 \
    libdrm2 \
    libdbus-1-3 \
    libxkbcommon0 \
    libxcomposite1 \
    libxdamage1 \
    libxfixes3 \
    libxrandr2 \
    libgbm1 \
    libpango-1.0-0 \
    libcairo2 \
    libasound2 \
    && rm -rf /var/lib/apt/lists/*

# Install python dependencies and headless Chromium with dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt && playwright install --with-deps chromium

# Copy fonts to system directory and refresh font cache
COPY assets/fonts/ /usr/share/fonts/truetype/sanket/
RUN fc-cache -f -v

# Copy full application source
COPY . .

# Copy compiled frontend from builder stage
COPY --from=frontend-builder /build/dist /app/frontend/dist

EXPOSE 8501

CMD ["make", "demo"]
