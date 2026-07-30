import os
import hashlib
import jwt
import datetime

SECRET_KEY = "vps-manager-jwt-secret-key-2026"
ALGORITHM = "HS256"

# Default password 'admin-oracle-2026' SHA256 if .env is missing
DEFAULT_HASH = "811f07f59a0f5896a23b08e5c10ad828b8e05c5be5b4bf3e7bcf527d2c3df4cf"

def get_admin_hash():
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
