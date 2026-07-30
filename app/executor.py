import os
import glob
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

def get_git_info(repo_dir: str):
    if not repo_dir or not os.path.exists(repo_dir) or not os.path.isdir(repo_dir):
        return "latest", False
    git_dir = os.path.join(repo_dir, ".git")
    if not os.path.exists(git_dir):
        return "latest", False
    
    try:
        cmd_ver = f"git -C '{repo_dir}' log -1 --format='%h (%cr)'"
        version_str = subprocess.run(cmd_ver, shell=True, capture_output=True, text=True).stdout.strip()
        if not version_str:
            version_str = "v1.0.0"
            
        subprocess.run(f"git -C '{repo_dir}' fetch --quiet", shell=True, timeout=2, capture_output=True)
        
        local_hash = subprocess.run(f"git -C '{repo_dir}' rev-parse HEAD", shell=True, capture_output=True, text=True).stdout.strip()
        remote_hash = subprocess.run(f"git -C '{repo_dir}' rev-parse @{{u}}", shell=True, capture_output=True, text=True).stdout.strip()
        
        has_update = bool(local_hash and remote_hash and local_hash != remote_hash)
        return version_str, has_update
    except Exception:
        return "v1.0.0", False

def get_services_status(host_domain: str = ""):
    services = []
    registered_ids = set()

    base_url = f"http://{host_domain}" if host_domain else ""

    # 1. Dynamic Auto-Discovery of Docker Containers
    try:
        cmd_docker = "docker ps -a --format '{{.Names}}|{{.Status}}|{{.Image}}|{{.Ports}}'"
        out_docker = subprocess.run(cmd_docker, shell=True, capture_output=True, text=True).stdout.strip()
        if out_docker:
            for line in out_docker.splitlines():
                parts = line.split("|")
                if len(parts) >= 3:
                    c_name = parts[0].strip()
                    c_status_str = parts[1].strip()
                    c_image = parts[2].strip()
                    c_ports = parts[3].strip() if len(parts) > 3 else "Internal"

                    if c_name in ["vps-manager"]:
                        continue

                    status = "Running" if "Up" in c_status_str else "Stopped"
                    
                    # Custom URL route mapping
                    route_path = f"/{c_name}/"
                    if c_name == "gcli2api":
                        route_path = "/gcli/"
                    elif c_name == "9router":
                        route_path = "/9router/"

                    full_url = f"{base_url}{route_path}" if base_url else route_path

                    # Version & Update check
                    project_dir = f"/home/ubuntu/{c_name}"
                    version_str, update_avail = get_git_info(project_dir)

                    services.append({
                        "id": c_name,
                        "name": c_name,
                        "description": f"Docker Container ({c_image})",
                        "status": status,
                        "type": "docker",
                        "url_path": route_path,
                        "full_url": full_url,
                        "ports": c_ports or "Internal",
                        "version": version_str,
                        "update_available": update_avail
                    })
                    registered_ids.add(c_name)
    except Exception as e:
        print(f"Error in docker auto discovery: {e}")

    # 2. Dynamic Auto-Discovery of Host Directories (/home/ubuntu/*)
    user_home_folders = glob.glob("/home/ubuntu/*")
    for folder in user_home_folders:
        if os.path.isdir(folder):
            folder_name = os.path.basename(folder)
            if folder_name in ["vps-manager"]:
                continue
            
            has_compose = os.path.exists(os.path.join(folder, "docker-compose.yml")) or os.path.exists(os.path.join(folder, "docker-compose.yaml"))
            has_git = os.path.exists(os.path.join(folder, ".git"))

            if (has_compose or has_git) and folder_name not in registered_ids:
                version_str, update_avail = get_git_info(folder)
                route_path = f"/{folder_name}/"
                services.append({
                    "id": folder_name,
                    "name": folder_name,
                    "description": f"Git / Compose Project ({folder})",
                    "status": "Stopped",
                    "type": "compose_dir",
                    "url_path": route_path,
                    "full_url": f"{base_url}{route_path}" if base_url else route_path,
                    "ports": "Host Project",
                    "version": version_str,
                    "update_available": update_avail
                })
                registered_ids.add(folder_name)

    # 3. Systemd Services (WireGuard & Nginx)
    if "wireguard" not in registered_ids:
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
            "full_url": "#",
            "ports": "51820 (UDP)",
            "version": "v1.0.0",
            "update_available": False
        })

    if "nginx" not in registered_ids:
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
            "full_url": f"{base_url}/" if base_url else "/",
            "ports": "80",
            "version": "1.24.0",
            "update_available": False
        })

    return services

async def stream_action(service_id: str, action: str):
    project_dir = f"/home/ubuntu/{service_id}"
    has_dir = os.path.exists(project_dir) and os.path.isdir(project_dir)
    has_compose = has_dir and (os.path.exists(os.path.join(project_dir, "docker-compose.yml")) or os.path.exists(os.path.join(project_dir, "docker-compose.yaml")))

    if action == "start":
        if has_compose:
            cmd = f"cd '{project_dir}' && (docker compose up -d || docker-compose up -d)"
        else:
            cmd = f"docker start {service_id}"
    elif action == "stop":
        if has_compose:
            cmd = f"cd '{project_dir}' && (docker compose stop || docker-compose stop)"
        else:
            cmd = f"docker stop {service_id}"
    elif action == "restart":
        if has_compose:
            cmd = f"cd '{project_dir}' && (docker compose restart || docker-compose restart)"
        else:
            cmd = f"docker restart {service_id}"
    elif action == "update":
        if has_dir and os.path.exists(os.path.join(project_dir, ".git")):
            if has_compose:
                cmd = f"cd '{project_dir}' && git pull && (docker compose down || docker-compose down) && (docker compose up -d --build || docker-compose up -d --build)"
            else:
                cmd = f"cd '{project_dir}' && git pull"
        else:
            cmd = f"docker pull $(docker inspect --format '{{{{.Config.Image}}}}' {service_id} 2>/dev/null || echo '{service_id}') && docker restart {service_id}"

    # Handle systemd exceptions
    if service_id == "wireguard":
        if action in ["start", "restart"]:
            cmd = "systemctl enable --now wg-quick@wg0"
        elif action == "stop":
            cmd = "systemctl disable --now wg-quick@wg0"
        elif action == "update":
            cmd = "apt-get update && apt-get install --only-upgrade -y wireguard wireguard-tools"

    elif service_id == "nginx":
        if action == "start":
            cmd = "systemctl start nginx"
        elif action == "stop":
            cmd = "systemctl stop nginx"
        elif action in ["restart", "update"]:
            cmd = "nginx -t && systemctl reload nginx"

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
