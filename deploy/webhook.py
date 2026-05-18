"""Lightweight GitHub webhook listener for auto-deploy."""
import hashlib
import hmac
import json
import subprocess
import sys
from http.server import HTTPServer, BaseHTTPRequestHandler

# Shared secret — must match GitHub webhook config
WEBHOOK_SECRET = sys.argv[1] if len(sys.argv) > 1 else ""
APP_DIR = "/opt/loom"
DEPLOY_SCRIPT = f"{APP_DIR}/deploy/deploy.sh"


def verify_signature(payload: bytes, signature: str) -> bool:
    if not WEBHOOK_SECRET:
        return True  # No secret configured, skip verification
    expected = "sha256=" + hmac.new(
        WEBHOOK_SECRET.encode(), payload, hashlib.sha256
    ).hexdigest()
    return hmac.compare_digest(expected, signature)


class WebhookHandler(BaseHTTPRequestHandler):
    def do_POST(self):
        if self.path != "/webhook":
            self.send_response(404)
            self.end_headers()
            return

        content_length = int(self.headers.get("Content-Length", 0))
        payload = self.rfile.read(content_length)

        # Verify GitHub signature
        signature = self.headers.get("X-Hub-Signature-256", "")
        if WEBHOOK_SECRET and not verify_signature(payload, signature):
            self.send_response(403)
            self.end_headers()
            self.wfile.write(b"Invalid signature")
            return

        # Only deploy on push to main
        try:
            data = json.loads(payload)
            ref = data.get("ref", "")
            if ref != "refs/heads/main":
                self.send_response(200)
                self.end_headers()
                self.wfile.write(b"Skipped: not main branch")
                return
        except (json.JSONDecodeError, KeyError):
            pass

        # Run deploy
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"Deploying...")

        subprocess.Popen(
            ["bash", DEPLOY_SCRIPT],
            cwd=APP_DIR,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )

    def log_message(self, format, *args):
        print(f"[webhook] {args[0]}")


if __name__ == "__main__":
    port = 9000
    print(f"[webhook] Listening on 127.0.0.1:{port}")
    HTTPServer(("127.0.0.1", port), WebhookHandler).serve_forever()
