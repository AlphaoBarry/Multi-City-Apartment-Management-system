# ─────────────────────────────────────────────────────────────────
# PAMS — Paragon Apartment Management System
# Dockerfile
#
# Builds a Python 3.11 environment with PyQt5 support.
# The SQLite DB file is stored in a mounted volume (/app/data)
# so data persists across container restarts.
# ─────────────────────────────────────────────────────────────────

FROM --platform=linux/amd64 python:3.11-bookworm

# Metadata
LABEL maintainer="ASD Group 6 — UWE Bristol"
LABEL project="Paragon Apartment Management System (PAMS)"

# ── System dependencies for PyQt5 ─────────────────────────────────
RUN apt-get update && apt-get install -y --no-install-recommends \
    # PyQt5 display dependencies
    libgl1-mesa-glx \
    libglib2.0-0 \
    libxcb-icccm4 \
    libxcb-image0 \
    libxcb-keysyms1 \
    libxcb-render-util0 \
    libxcb-xinerama0 \
    libxcb-xkb1 \
    libxkbcommon-x11-0 \
    libdbus-1-3 \
    # For headless/CI testing (no display)
    xvfb \
    # Utilities
    sqlite3 \
    && rm -rf /var/lib/apt/lists/*

# ── Working directory ──────────────────────────────────────────────
WORKDIR /app

# ── Install Python dependencies ────────────────────────────────────
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# ── Copy application source ────────────────────────────────────────
COPY . .

# ── Create data directory for SQLite DB volume ─────────────────────
RUN mkdir -p /app/data

# ── Environment ────────────────────────────────────────────────────
ENV PAMS_DB_PATH=/app/data/pams.db
ENV PYTHONPATH=/app
ENV PYTHONUNBUFFERED=1

# ── Expose nothing (desktop app — no HTTP port needed) ────────────

# ── Default command ────────────────────────────────────────────────
# For GUI: use docker-compose with DISPLAY forwarding
# For seeding only: override with: docker run pams python database/seed.py
CMD ["python", "main.py"]