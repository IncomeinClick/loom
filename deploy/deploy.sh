#!/bin/bash
# Loom deployment script — run on server via SSH
set -e

APP_DIR="/opt/loom"
BRANCH="main"

echo "=== Deploying Loom ==="

cd "$APP_DIR"

# Pull latest code
echo "[1/5] Pulling latest code..."
git fetch origin
git reset --hard "origin/$BRANCH"

# Fix ownership so www-data can write data/configs
echo "[2/5] Fixing file ownership..."
chown -R www-data:www-data "$APP_DIR"

# Install/update dependencies
echo "[3/5] Installing dependencies..."
.venv/bin/pip install --upgrade pip -q
.venv/bin/pip install -e . -q

# Restart service
echo "[4/5] Restarting service..."
sudo systemctl restart loom

# Verify
echo "[5/5] Checking status..."
sleep 2
if systemctl is-active --quiet loom; then
    echo "=== Loom deployed successfully ==="
    echo "Status: $(systemctl is-active loom)"
    # Send Telegram notification
    COMMIT_MSG=$(git log -1 --pretty=format:"%s" 2>/dev/null || echo "unknown")
    COMMIT_HASH=$(git log -1 --pretty=format:"%h" 2>/dev/null || echo "unknown")
    if [ -n "${TELEGRAM_BOT_TOKEN}" ] && [ -n "${TELEGRAM_NOTIFY_CHAT_ID}" ]; then
        curl -s -X POST "https://api.telegram.org/bot${TELEGRAM_BOT_TOKEN}/sendMessage" \
            -d chat_id="${TELEGRAM_NOTIFY_CHAT_ID}" \
            -d text="🚀 Loom Deployed

🔖 ${COMMIT_HASH}: ${COMMIT_MSG}" > /dev/null 2>&1 || true
    fi
else
    echo "=== DEPLOY FAILED ==="
    sudo journalctl -u loom --no-pager -n 20
    exit 1
fi
