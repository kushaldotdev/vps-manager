import os
import hashlib
import jwt
import datetime

SECRET_KEY = "vps-manager-jwt-secret-key-2026"
ALGORITHM = "HS256"

# Default password 'admin-oracle-2026' SHA256
DEFAULT_HASH = "115aeac5c863e09ff7e13f3709dd8fe779ff114e7a796244b0abe58c810c4610"

def get_admin_hash():
    env_paths = ["/home/ubuntu/vps-manager/.env", "/app/.env"]
    for path in env_paths:
        if os.path.exists(path):
            try:
                with open(path, "r") as f:
                    for line in f:
                        if line.startswith("ADMIN_PASSWORD_HASH="):
                            val = line.split("=", 1)[1].strip()
                            if val:
                                return val
            except Exception:
                pass

    env_hash = os.getenv("ADMIN_PASSWORD_HASH")
    if env_hash and env_hash.strip():
        return env_hash.strip()
    return DEFAULT_HASH

def verify_password(password: str) -> bool:
    hashed = hashlib.sha256(password.encode()).hexdigest()
    return hashed == get_admin_hash()

def create_session_token() -> str:
    expiration = datetime.datetime.utcnow() + datetime.timedelta(hours=24)
    payload = {"sub": "admin", "exp": expiration}
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)

def verify_session_token(token: str) -> bool:
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return payload.get("sub") == "admin"
    except Exception:
        return False
