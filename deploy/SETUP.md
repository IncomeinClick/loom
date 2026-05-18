# Loom Server Setup Guide

## Architecture

```
Internet → Nginx (443/SSL) → Loom uvicorn (127.0.0.1:8000)
```

## Prerequisites

- Ubuntu 22.04+ server
- Nginx installed
- Certbot installed (for SSL)
- Python 3.11+ (`sudo apt install python3 python3-venv python3-pip`)
- Git

---

## Step 1: Clone the repo

```bash
sudo mkdir -p /opt/loom
sudo chown www-data:www-data /opt/loom
sudo -u www-data git clone YOUR_REPO_URL /opt/loom
```

> Replace `YOUR_REPO_URL` with your actual git repo URL.

## Step 2: Set up Python venv

```bash
cd /opt/loom
sudo -u www-data python3 -m venv .venv
sudo -u www-data .venv/bin/pip install -e .
```

## Step 3: Configure environment

```bash
sudo cp deploy/.env.example .env
sudo nano .env
```

Fill in:
- `FERNET_KEY` — generate with: `python3 -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"`
- `API_BEARER_TOKEN` — a strong secret token for API auth
- API keys for LLM providers you use

```bash
sudo chown www-data:www-data .env
sudo chmod 600 .env
```

## Step 4: Create data directories

```bash
sudo -u www-data mkdir -p /opt/loom/data/configs/niches
sudo -u www-data mkdir -p /opt/loom/data/configs/pages
sudo -u www-data mkdir -p /opt/loom/data/configs/workflows
sudo -u www-data mkdir -p /opt/loom/data/assets/generated
```

## Step 5: Install systemd service

```bash
sudo cp deploy/loom.service /etc/systemd/system/loom.service
sudo systemctl daemon-reload
sudo systemctl enable loom
sudo systemctl start loom
```

Verify it's running:
```bash
sudo systemctl status loom
curl http://127.0.0.1:8000/api/health
```

## Step 6: Configure Nginx reverse proxy

```bash
sudo cp deploy/nginx-loom.conf /etc/nginx/sites-available/loom
sudo ln -s /etc/nginx/sites-available/loom /etc/nginx/sites-enabled/loom
```

**Edit the config** — replace `loom.YOURDOMAIN.com` with your actual subdomain:
```bash
sudo nano /etc/nginx/sites-available/loom
```

Test and reload:
```bash
sudo nginx -t
sudo systemctl reload nginx
```

## Step 7: SSL certificate

```bash
sudo certbot --nginx -d loom.YOURDOMAIN.com
```

Certbot will auto-update the nginx config with SSL paths.

## Step 8: DNS

Add an **A record** in your domain DNS:
```
loom.YOURDOMAIN.com → YOUR_SERVER_IP
```

---

## Deploying Updates

From your local machine:
```bash
ssh user@your-server "bash /opt/loom/deploy/deploy.sh"
```

Or SSH in and run:
```bash
cd /opt/loom && bash deploy/deploy.sh
```

## Useful Commands

```bash
# Check status
sudo systemctl status loom

# View logs (live)
sudo journalctl -u loom -f

# View last 50 log lines
sudo journalctl -u loom -n 50

# Restart
sudo systemctl restart loom

# Stop
sudo systemctl stop loom
```

## Troubleshooting

**502 Bad Gateway**: Loom isn't running. Check `systemctl status loom` and logs.

**SSE not working**: Make sure nginx has `proxy_buffering off` (already in the config).

**Permission denied on data/**: Fix ownership: `sudo chown -R www-data:www-data /opt/loom/data`
