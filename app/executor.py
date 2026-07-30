import os
import glob
import subprocess
import psutil
import json
import asyncio
import socket

def get_cpu_model():
    try:
        if os.path.exists("/proc/cpuinfo"):
            with open("/proc/cpuinfo", "r") as f:
                for line in f:
                    if "model name" in line:
                        return line.split(":", 1)[1].strip()
    except Exception:
        pass
    return "x86_64 Processor"

def get_system_stats():
    cpu_percent = psutil.cpu_percent(interval=0.3)
    mem = psutil.virtual_memory()
    swap = psutil.swap_memory()
    disk = psutil.disk_usage('/')
    boot_time = psutil.boot_time()
    
    cpu_model = get_cpu_model()
    cpu_logical = psutil.cpu_count(logical=True) or 1
    cpu_physical = psutil.cpu_count(logical=False) or cpu_logical
    
    load_avg = [0.0, 0.0, 0.0]
    if hasattr(os, "getloadavg"):
        try:
            load_avg = [round(x, 2) for x in os.getloadavg()]
        except Exception:
            pass
            
    cpu_freq_mhz = 0
    try:
        freq = psutil.cpu_freq()
        if freq and freq.current:
            cpu_freq_mhz = round(freq.current, 1)
    except Exception:
        pass
        
    cached_mb = round(getattr(mem, 'cached', 0) / (1024 * 1024), 1)
    buffers_mb = round(getattr(mem, 'buffers', 0) / (1024 * 1024), 1)
    
    return {
        "cpu_percent": cpu_percent,
        "cpu_details": {
            "model": cpu_model,
            "logical_cores": cpu_logical,
            "physical_cores": cpu_physical,
            "load_avg": load_avg,
            "freq_mhz": cpu_freq_mhz
        },
        "memory": {
            "total_mb": round(mem.total / (1024 * 1024), 1),
            "used_mb": round(mem.used / (1024 * 1024), 1),
            "free_mb": round(mem.free / (1024 * 1024), 1),
            "available_mb": round(mem.available / (1024 * 1024), 1),
            "cached_mb": cached_mb,
            "buffers_mb": buffers_mb,
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

def get_process_list():
    processes = []
    for proc in psutil.process_iter(['pid', 'name', 'username', 'cpu_percent', 'memory_info', 'memory_percent']):
        try:
            pinfo = proc.info
            mem_mb = round(pinfo['memory_info'].rss / (1024 * 1024), 1) if pinfo.get('memory_info') else 0.0
            if mem_mb > 0.0:
                processes.append({
                    "pid": pinfo['pid'],
                    "name": pinfo['name'] or "unknown",
                    "user": pinfo['username'] or "root",
                    "cpu_percent": round(pinfo['cpu_percent'] or 0.0, 1),
                    "ram_mb": mem_mb,
                    "ram_percent": round(pinfo['memory_percent'] or 0.0, 2)
                })
        except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
            pass
            
    processes.sort(key=lambda x: x['ram_mb'], reverse=True)
    return processes[:100]

KNOWN_GITHUB_MAP = {
    "9router": "https://github.com/decolua/9router",
    "vps-manager": "https://github.com/kushaldotdev/vps-manager",
    "gcli2api": "https://github.com/kushaldotdev/gcli2api",
    "wireguard": "https://github.com/WireGuard/wireguard-linux-compat",
    "nginx": "https://github.com/nginx/nginx"
}

def clean_github_url(url: str) -> str:
    if not url:
        return ""
    url = url.strip()
    if url.startswith("git@github.com:"):
        url = "https://github.com/" + url[len("git@github.com:"):]
    if url.endswith(".git"):
        url = url[:-4]
    if not url.startswith("http"):
        url = "https://" + url
    return url

def get_git_info(repo_dir: str, service_id: str = ""):
    github_url = KNOWN_GITHUB_MAP.get(service_id, "")
    
    # 1. Host directory with .git repository
    if repo_dir and os.path.exists(repo_dir) and os.path.isdir(repo_dir):
        git_dir = os.path.join(repo_dir, ".git")
        if os.path.exists(git_dir):
            try:
                remote_url_cmd = f"git -C '{repo_dir}' remote get-url origin"
                remote_url_out = subprocess.run(remote_url_cmd, shell=True, capture_output=True, text=True).stdout.strip()
                if remote_url_out:
                    github_url = clean_github_url(remote_url_out)

                cmd_ver = f"git -C '{repo_dir}' log -1 --format='%h (%cr)'"
                version_str = subprocess.run(cmd_ver, shell=True, capture_output=True, text=True).stdout.strip()
                if not version_str:
                    version_str = "v1.0.0"

                local_hash = subprocess.run(f"git -C '{repo_dir}' rev-parse HEAD", shell=True, capture_output=True, text=True).stdout.strip()

                has_update = False
                remote_out = subprocess.run(f"git -C '{repo_dir}' ls-remote origin HEAD refs/heads/main refs/heads/master", shell=True, timeout=6, capture_output=True, text=True).stdout.strip()
                if remote_out:
                    for line in remote_out.splitlines():
                        parts = line.split()
                        if len(parts) >= 1:
                            r_hash = parts[0]
                            if r_hash and not local_hash.startswith(r_hash) and not r_hash.startswith(local_hash):
                                has_update = True
                                break

                return version_str, has_update, github_url
            except Exception:
                pass

    # 2. Docker container without host .git repository (e.g. 9router)
    if service_id:
        try:
            cmd_inspect = f"docker inspect {service_id} --format '{{{{index .Config.Labels \"org.opencontainers.image.revision\"}}}}'"
            c_hash = subprocess.run(cmd_inspect, shell=True, capture_output=True, text=True).stdout.strip()
            
            c_ver = f"{c_hash[:7]}" if c_hash else "latest"

            if github_url:
                target_url = github_url if github_url.endswith(".git") else f"{github_url}.git"
                remote_cmd = f"git ls-remote {target_url} HEAD refs/heads/main refs/heads/master"
                r_out = subprocess.run(remote_cmd, shell=True, timeout=6, capture_output=True, text=True).stdout.strip()
                if r_out:
                    for line in r_out.splitlines():
                        parts = line.split()
                        if len(parts) >= 1:
                            r_hash = parts[0]
                            if c_hash and r_hash and not r_hash.startswith(c_hash) and not c_hash.startswith(r_hash):
                                return f"{c_ver}", True, github_url

            return c_ver, False, github_url
        except Exception:
            pass

    return "latest", False, github_url

def get_docker_stats_map():
    stats_map = {}
    try:
        cmd = "docker stats --no-stream --format '{{.Name}}|{{.CPUPerc}}|{{.MemUsage}}|{{.PIDs}}'"
        out = subprocess.run(cmd, shell=True, capture_output=True, text=True).stdout.strip()
        if out:
            for line in out.splitlines():
                parts = line.split("|")
                if len(parts) >= 4:
                    c_name = parts[0].strip()
                    stats_map[c_name] = {
                        "cpu": parts[1].strip(),
                        "ram": parts[2].strip().split("/")[0].strip(),
                        "pids": parts[3].strip()
                    }
    except Exception:
        pass
    return stats_map

def get_systemd_stats(service_name: str):
    cpu_total = 0.0
    mem_total_mb = 0.0
    pid_count = 0
    try:
        for proc in psutil.process_iter(['name', 'cpu_percent', 'memory_info']):
            p_name = proc.info.get('name', '')
            if service_name in p_name:
                cpu_total += proc.info.get('cpu_percent') or 0.0
                mem = proc.info.get('memory_info')
                if mem:
                    mem_total_mb += mem.rss / (1024 * 1024)
                pid_count += 1
    except Exception:
        pass
    return {
        "cpu": f"{round(cpu_total, 1)}%",
        "ram": f"{round(mem_total_mb, 1)} MB",
        "pids": str(pid_count) if pid_count > 0 else "-"
    }

def check_port_open(hosts, port=80):
    for host in hosts:
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.settimeout(0.8)
                if s.connect_ex((host, port)) == 0:
                    return True
        except Exception:
            pass
    return False

def get_services_status(host_domain: str = ""):
    services = []
    registered_ids = set()
    base_url = f"http://{host_domain}" if host_domain else ""
    docker_stats = get_docker_stats_map()

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
                    
                    route_path = f"/{c_name}/"
                    if c_name == "gcli2api":
                        route_path = "/gcli/"
                    elif c_name == "9router":
                        route_path = "/9router/"

                    full_url = f"{base_url}{route_path}" if base_url else route_path

                    project_dir = f"/home/ubuntu/{c_name}"
                    version_str, update_avail, github_url = get_git_info(project_dir, service_id=c_name)

                    c_stats = docker_stats.get(c_name, {"cpu": "0.0%", "ram": "0 MB", "pids": "0"})

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
                        "update_available": update_avail,
                        "github_url": github_url,
                        "cpu_usage": c_stats["cpu"],
                        "ram_usage": c_stats["ram"],
                        "pids": c_stats["pids"]
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
                version_str, update_avail, github_url = get_git_info(folder, service_id=folder_name)
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
                    "update_available": update_avail,
                    "github_url": github_url,
                    "cpu_usage": "0.0%",
                    "ram_usage": "0 MB",
                    "pids": "0"
                })
                registered_ids.add(folder_name)

    # 3. Systemd Services (WireGuard & Nginx)
    if "wireguard" not in registered_ids:
        is_wg_active = os.path.exists("/sys/class/net/wg0")
        if not is_wg_active:
            res_wg = subprocess.run("systemctl is-active wg-quick@wg0", shell=True, capture_output=True, text=True).stdout.strip()
            is_wg_active = (res_wg == "active")
        status_wg = "Running" if is_wg_active else "Stopped"
        wg_stats = get_systemd_stats("wireguard") if status_wg == "Running" else {"cpu": "0.0%", "ram": "0 MB", "pids": "0"}
        _, _, wg_gh = get_git_info("", service_id="wireguard")
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
            "update_available": False,
            "github_url": wg_gh,
            "cpu_usage": wg_stats["cpu"],
            "ram_usage": wg_stats["ram"],
            "pids": wg_stats["pids"]
        })

    if "nginx" not in registered_ids:
        ngx_stats = get_systemd_stats("nginx")
        is_ngx_active = (ngx_stats["pids"] != "-") or check_port_open(["10.0.0.188", "140.238.245.42", "172.17.0.1", "127.0.0.1"], 80)
        if not is_ngx_active:
            res_ngx = subprocess.run("systemctl is-active nginx", shell=True, capture_output=True, text=True).stdout.strip()
            is_ngx_active = (res_ngx == "active")

        status_ngx = "Running" if is_ngx_active else "Stopped"
        ngx_stats = get_systemd_stats("nginx") if status_ngx == "Running" else {"cpu": "0.0%", "ram": "0 MB", "pids": "0"}
        _, _, ngx_gh = get_git_info("", service_id="nginx")
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
            "update_available": False,
            "github_url": ngx_gh,
            "cpu_usage": ngx_stats["cpu"],
            "ram_usage": ngx_stats["ram"],
            "pids": ngx_stats["pids"]
        })

from datetime import datetime

UPDATE_RECORD_FILE = "/home/ubuntu/vps-manager/service_updates.json"

def record_service_update(service_id: str):
    try:
        data = {}
        if os.path.exists(UPDATE_RECORD_FILE):
            with open(UPDATE_RECORD_FILE, "r") as f:
                data = json.load(f)
        data[service_id] = datetime.now().strftime("%b %d, %Y %H:%M")
        with open(UPDATE_RECORD_FILE, "w") as f:
            json.dump(data, f, indent=2)
    except Exception as e:
        print(f"Error recording update for {service_id}: {e}")

def get_last_updated_time(service_id: str, repo_dir: str = ""):
    if os.path.exists(UPDATE_RECORD_FILE):
        try:
            with open(UPDATE_RECORD_FILE, "r") as f:
                rec_data = json.load(f)
                if service_id in rec_data:
                    return rec_data[service_id]
        except Exception:
            pass

    if repo_dir and os.path.exists(repo_dir) and os.path.exists(os.path.join(repo_dir, ".git")):
        try:
            cmd = f"git -C '{repo_dir}' log -1 --format='%cd' --date=format:'%b %d, %Y %H:%M'"
            git_date = subprocess.run(cmd, shell=True, capture_output=True, text=True).stdout.strip()
            if git_date:
                return git_date
        except Exception:
            pass

    if service_id:
        try:
            cmd_c = f"docker inspect {service_id} --format '{{{{.Created}}}}'"
            iso_str = subprocess.run(cmd_c, shell=True, capture_output=True, text=True).stdout.strip()
            if iso_str:
                clean_iso = iso_str.split(".")[0].replace("Z", "")
                dt = datetime.fromisoformat(clean_iso)
                return dt.strftime("%b %d, %Y %H:%M")
        except Exception:
            pass

    return "N/A"

def get_recreate_container_cmd(service_id: str) -> str:
    try:
        out = subprocess.run(f"docker inspect {service_id}", shell=True, capture_output=True, text=True).stdout.strip()
        if not out or out == "[]":
            return f"docker pull {service_id} && docker restart {service_id}"
        data = json.loads(out)[0]
        image = data.get("Config", {}).get("Image", service_id)

        flags = ["-d", f"--name {service_id}"]

        restart = data.get("HostConfig", {}).get("RestartPolicy", {}).get("Name")
        if restart:
            flags.append(f"--restart {restart}")

        port_bindings = data.get("HostConfig", {}).get("PortBindings", {}) or {}
        for c_port, h_bindings in port_bindings.items():
            if h_bindings:
                for b in h_bindings:
                    h_port = b.get("HostPort")
                    h_ip = b.get("HostIp")
                    if h_port:
                        if h_ip:
                            flags.append(f"-p {h_ip}:{h_port}:{c_port}")
                        else:
                            flags.append(f"-p {h_port}:{c_port}")

        binds = data.get("HostConfig", {}).get("Binds", []) or []
        for bind in binds:
            flags.append(f"-v \"{bind}\"")

        env_list = data.get("Config", {}).get("Env", []) or []
        ignore_envs = {"PATH", "HOSTNAME", "HOME", "NODE_VERSION", "YARN_VERSION", "PHPIZE_DEPS"}
        for env_item in env_list:
            if "=" in env_item:
                k, v = env_item.split("=", 1)
                if k not in ignore_envs:
                    flags.append(f"-e {k}=\"{v}\"")

        net_mode = data.get("HostConfig", {}).get("NetworkMode")
        if net_mode and net_mode not in ["default", "bridge"]:
            flags.append(f"--net {net_mode}")

        flags_str = " ".join(flags)
        return f"docker pull {image} && (docker stop {service_id} || true) && (docker rm {service_id} || true) && docker run {flags_str} {image}"
    except Exception as e:
        return f"docker pull {service_id} && docker restart {service_id}"

def get_services_status(host_domain: str = ""):
    services = []
    registered_ids = set()
    base_url = f"http://{host_domain}" if host_domain else ""
    docker_stats = get_docker_stats_map()

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
                    
                    route_path = f"/{c_name}/"
                    if c_name == "gcli2api":
                        route_path = "/gcli/"
                    elif c_name == "9router":
                        route_path = "/9router/"

                    full_url = f"{base_url}{route_path}" if base_url else route_path

                    project_dir = f"/home/ubuntu/{c_name}"
                    version_str, update_avail, github_url = get_git_info(project_dir, service_id=c_name)
                    c_stats = docker_stats.get(c_name, {"cpu": "0.0%", "ram": "0 MB", "pids": "0"})

                    last_updated = get_last_updated_time(c_name, project_dir)

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
                        "update_available": update_avail,
                        "github_url": github_url,
                        "cpu_usage": c_stats["cpu"],
                        "ram_usage": c_stats["ram"],
                        "pids": c_stats["pids"],
                        "last_updated": last_updated
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
                version_str, update_avail, github_url = get_git_info(folder, service_id=folder_name)
                route_path = f"/{folder_name}/"
                last_updated = get_last_updated_time(folder_name, folder)
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
                    "update_available": update_avail,
                    "github_url": github_url,
                    "cpu_usage": "0.0%",
                    "ram_usage": "0 MB",
                    "pids": "0",
                    "last_updated": last_updated
                })
                registered_ids.add(folder_name)

    # 3. Systemd Services (WireGuard & Nginx)
    if "wireguard" not in registered_ids:
        is_wg_active = os.path.exists("/sys/class/net/wg0")
        if not is_wg_active:
            res_wg = subprocess.run("systemctl is-active wg-quick@wg0", shell=True, capture_output=True, text=True).stdout.strip()
            is_wg_active = (res_wg == "active")
        status_wg = "Running" if is_wg_active else "Stopped"
        wg_stats = get_systemd_stats("wireguard") if status_wg == "Running" else {"cpu": "0.0%", "ram": "0 MB", "pids": "0"}
        _, _, wg_gh = get_git_info("", service_id="wireguard")
        last_updated_wg = get_last_updated_time("wireguard", "")
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
            "update_available": False,
            "github_url": wg_gh,
            "cpu_usage": wg_stats["cpu"],
            "ram_usage": wg_stats["ram"],
            "pids": wg_stats["pids"],
            "last_updated": last_updated_wg
        })

    if "nginx" not in registered_ids:
        ngx_stats = get_systemd_stats("nginx")
        is_ngx_active = (ngx_stats["pids"] != "-") or check_port_open(["10.0.0.188", "140.238.245.42", "172.17.0.1", "127.0.0.1"], 80)
        if not is_ngx_active:
            res_ngx = subprocess.run("systemctl is-active nginx", shell=True, capture_output=True, text=True).stdout.strip()
            is_ngx_active = (res_ngx == "active")

        status_ngx = "Running" if is_ngx_active else "Stopped"
        ngx_stats = get_systemd_stats("nginx") if status_ngx == "Running" else {"cpu": "0.0%", "ram": "0 MB", "pids": "0"}
        _, _, ngx_gh = get_git_info("", service_id="nginx")
        last_updated_ngx = get_last_updated_time("nginx", "")
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
            "update_available": False,
            "github_url": ngx_gh,
            "cpu_usage": ngx_stats["cpu"],
            "ram_usage": ngx_stats["ram"],
            "pids": ngx_stats["pids"],
            "last_updated": last_updated_ngx
        })

    return services

async def stream_action(service_id: str, action: str):
    project_dir = f"/home/ubuntu/{service_id}"
    has_dir = os.path.exists(project_dir) and os.path.isdir(project_dir)
    has_compose = has_dir and (os.path.exists(os.path.join(project_dir, "docker-compose.yml")) or os.path.exists(os.path.join(project_dir, "docker-compose.yaml")))

    if action == "logs":
        cmd = f"docker logs {service_id} --tail 200"
    elif action == "start":
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
                cmd = f"cd '{project_dir}' && git pull && (docker compose down || docker-compose down || true) && (docker compose up -d --build || docker-compose up -d --build)"
            else:
                cmd = f"cd '{project_dir}' && git pull"
        else:
            cmd = get_recreate_container_cmd(service_id)

    # Handle systemd exceptions
    if service_id == "wireguard":
        if action == "logs":
            cmd = "journalctl -u wg-quick@wg0 -n 100 --no-pager"
        elif action in ["start", "restart"]:
            cmd = "systemctl enable --now wg-quick@wg0"
        elif action == "stop":
            cmd = "systemctl disable --now wg-quick@wg0"
        elif action == "update":
            cmd = "apt-get update && apt-get install --only-upgrade -y wireguard wireguard-tools"

    elif service_id == "nginx":
        if action == "logs":
            cmd = "journalctl -u nginx -n 100 --no-pager"
        elif action == "start":
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
    if proc.returncode == 0 and action == "update":
        record_service_update(service_id)
    yield f"\n----------------------------------------\nAction '{action}' on '{service_id}' completed with return code {proc.returncode}.\n"


