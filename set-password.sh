#!/bin/bash
NEW_PASS="$1"
if [ -z "$NEW_PASS" ]; then
    echo "Usage: ./set-password.sh <new_password>"
    exit 1
fi
PASS_HASH=$(python3 -c "import hashlib; print(hashlib.sha256('$NEW_PASS'.encode()).hexdigest())")
echo "ADMIN_PASSWORD_HASH=$PASS_HASH" > /home/ubuntu/vps-manager/.env
docker cp /home/ubuntu/vps-manager/.env vps-manager:/app/.env 2>/dev/null || true
echo "Password updated successfully!"
docker restart vps-manager 2>/dev/null || true
