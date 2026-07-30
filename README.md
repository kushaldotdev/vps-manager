# VPS Manager - Oracle Cloud Infrastructure Control Panel

A lightweight, standalone, password-protected web interface to monitor system metrics (CPU, RAM, Disk, Swap) and manage hosted services (`9Router`, `gcli2api`, `WireGuard`, `Nginx`) with Start, Stop, Restart, and Update capabilities.

## Features
- **Real-Time System Metrics**: Monitored via `psutil` (CPU %, RAM, Disk, Swap, Uptime).
- **Service Lifecycle Management**: Start, stop, restart, or update target docker containers & systemd services.
- **Live Build Log Streaming**: Streaming terminal modal showing build/git progress in real-time.
- **SSH-Only Password Security**: Admin password can only be updated via SSH CLI script (`./set-password.sh <new_password>`).
- **Nginx Reverse Proxy Ready**: Accessible securely via `/manager/` path.

## Tech Stack
- **Backend**: FastAPI, Uvicorn, Python 3.11+, PyJWT, psutil.
- **Package Manager**: `uv` (Fast Python package installer & resolver).
- **Frontend**: Vanilla HTML5/CSS3/JavaScript (Dark Mode, Glassmorphism, Micro-animations).
- **Deployment**: Docker & Docker Compose.

## Changing Admin Password (SSH Only)
To change the admin login password from your SSH terminal:
```bash
cd /home/ubuntu/vps-manager
./set-password.sh YourNewSecretPassword
```

## Local Development & UV Setup
```bash
uv sync
uv run uvicorn app.main:app --port 9999
```
