import subprocess
import psutil
import json
import asyncio

def get_system_stats():
    cpu_percent = psutil.cpu_percent(interval=0.3)
    mem = psutil.virtual_memory()
    swap = psutil.swap_memory()
    disk = psutil.disk_usage('/')
    boot_time = psutil.boot_time()
    
    return {
        "cpu_percent": cpu_percent,
        "memory": {
            "total_mb": round(mem.total / (1024 * 1024), 1),
            "used_mb": round(mem.used / (1024 * 1024), 1),
            "free_mb": round(mem.free / (1024 * 1024), 1),
            "available_mb": round(mem.available / (1024 * 1024), 1),
            "percent": mem.percent
        },
        "swap": {
            "total_mb": round(swap.total / (1024 * 1024), 1),
            "used_mb": round(swap.used / (1024 * 1024), 1),
            "percent": swap.percent
        },
        "disk": {
            "total_gb": round(disk.total / (1024 * 1024 * 1024), 1),
            "used_gb": round(disk.used / (1024 * 1024 * 1024), 1),
            "free_gb": round(disk.free / (1024 * 1024 * 1024), 1),
            "percent": disk.percent
        },
        "boot_time": boot_time
    }

def get_services_status():
    services = []
    
    # 1. 9Router
    cmd_9r = "docker ps -a --filter name=9router --format '{{.Status}}|{{.Image}}|{{.Ports}}'"
    res_9r = subprocess.run(cmd_9r, shell=True, capture_output=True, text=True).stdout.strip()
    status_9r = "Stopped"
    if res_9r and "Up" in res_9r:
        status_9r = "Running"
    services.append({
        "id": "9router",
        "name": "9Router",
        "description": "LLM Router & Gateway Proxy",
        "status": status_9r,
        "type": "docker",
        "url_path": "/9router/",
        "ports": "20129 -> 20128"
    })

    # 2. gcli2api
    cmd_gcli = "docker ps -a --filter name=gcli2api --format '{{.Status}}|{{.Image}}|{{.Ports}}'"
    res_gcli = subprocess.run(cmd_gcli, shell=True, capture_output=True, text=True).stdout.strip()
    status_gcli = "Stopped"
    if res_gcli and "Up" in res_gcli:
        status_gcli = "Running"
    services.append({
        "id": "gcli2api",
        "name": "gcli2api",
        "description": "Gemini CLI Proxy API Service",
        "status": status_gcli,
        "type": "docker",
        "url_path": "/gcli/",
        "ports": "7861 (Host)"
    })

    # 3. WireGuard
    cmd_wg = "systemctl is-active wg-quick@wg0"
    res_wg = subprocess.run(cmd_wg, shell=True, capture_output=True, text=True).stdout.strip()
    status_wg = "Running" if res_wg == "active" else "Stopped"
    services.append({
        "id": "wireguard",
        "name": "WireGuard VPN",
        "description": "Kernel-Space WireGuard VPN Tunnel",
        "status": status_wg,
        "type": "systemd",
        "url_path": "#",
        "ports": "51820 (UDP)"
    })

    # 4. Nginx Web Proxy
    cmd_ngx = "systemctl is-active nginx"
    res_ngx = subprocess.run(cmd_ngx, shell=True, capture_output=True, text=True).stdout.strip()
    status_ngx = "Running" if res_ngx == "active" else "Stopped"
    services.append({
        "id": "nginx",
        "name": "Nginx Web Proxy",
        "description": "Port 80 Reverse Proxy Router",
        "status": status_ngx,
        "type": "systemd",
        "url_path": "/",
        "ports": "80"
    })

    return services

async def stream_action(service_id: str, action: str):
    if service_id == "gcli2api":
        if action == "start":
            cmd = "docker start gcli2api"
        elif action == "stop":
            cmd = "docker stop gcli2api"
        elif action == "restart":
            cmd = "docker restart gcli2api"
        elif action == "update":
            cmd = "cd /home/ubuntu/gcli2api && git pull origin main && docker compose down && docker compose up -d --build"
        else:
            yield f"Unknown action: {action}\n"
            return
            
    elif service_id == "9router":
        if action == "start":
            cmd = "docker start 9router"
        elif action == "stop":
            cmd = "docker stop 9router"
        elif action == "restart":
            cmd = "docker restart 9router"
        elif action == "update":
            cmd = "docker pull ghcr.io/decolua/9router:latest && docker stop 9router && docker rm 9router && docker run -d --name 9router --restart unless-stopped -p 20129:20128 -v 9router-data:/app/data -e NODE_ENV=production -e PORT=20128 -e HOSTNAME=0.0.0.0 ghcr.io/decolua/9router:latest"
        else:
            yield f"Unknown action: {action}\n"
            return

    elif service_id == "wireguard":
        if action in ["start", "restart"]:
            cmd = "systemctl enable --now wg-quick@wg0"
        elif action == "stop":
            cmd = "systemctl disable --now wg-quick@wg0"
        elif action == "update":
            cmd = "apt-get update && apt-get install --only-upgrade -y wireguard wireguard-tools"
        else:
            yield f"Unknown action: {action}\n"
            return

    elif service_id == "nginx":
        if action == "start":
            cmd = "systemctl start nginx"
        elif action == "stop":
            cmd = "systemctl stop nginx"
        elif action == "restart":
            cmd = "systemctl reload nginx"
        elif action == "update":
            cmd = "nginx -t && systemctl reload nginx"
        else:
            yield f"Unknown action: {action}\n"
            return
    else:
        yield f"Unknown service: {service_id}\n"
        return

    yield f"Executing: {cmd}\n----------------------------------------\n"
    
    proc = await asyncio.create_subprocess_shell(
        cmd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.STDOUT
    )
    
    while True:
        line = await proc.stdout.readline()
        if not line:
            break
        yield line.decode('utf-8', errors='replace')
        
    await proc.wait()
    yield f"\n----------------------------------------\nAction '{action}' on '{service_id}' completed with return code {proc.returncode}.\n"
