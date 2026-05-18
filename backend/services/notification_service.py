import httpx
import logging
import os

logger = logging.getLogger(__name__)

# Telegram config from .env (optional — leave blank to disable Telegram notifications)
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_NOTIFY_CHAT_ID", "")


async def _send_telegram(message: str):
    """Send a message to the configured Telegram chat."""
    if not TELEGRAM_BOT_TOKEN:
        return
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.post(url, json={
                "chat_id": TELEGRAM_CHAT_ID,
                "text": message,
            })
            if resp.status_code != 200:
                logger.error(f"Telegram API returned {resp.status_code}: {resp.text}")
    except Exception as e:
        logger.error(f"Failed to send Telegram notification: {e}")


async def notify_error(workflow_id: str, execution_id: str, error_message: str):
    """Send error alert to Telegram."""
    message = f"⚠️ Loom Workflow Failed\n\n📙 Workflow: {workflow_id}\n❌ Error: {error_message[:200]}"
    await _send_telegram(message)


async def notify_activity(action: str, entity_type: str, entity_id: str, details: str = ""):
    """Send activity notification to Telegram.

    Args:
        action: created, updated, deleted, activated, deactivated, etc.
        entity_type: page, workflow, credential, datatable, step, campaign, niche, etc.
        entity_id: ID of the entity
        details: optional extra info
    """
    icons = {
        "created": "🆕",
        "updated": "✏️",
        "deleted": "🗑️",
        "renamed": "🏷️",
        "cloned": "📋",
        "duplicated": "📋",
        "activated": "▶️",
        "deactivated": "⏸️",
        "paused": "⏸️",
        "resumed": "▶️",
        "triggered": "🚀",
        "deployed": "🚀",
        "synced": "🔄",
    }
    icon = icons.get(action, "📌")
    message = f"{icon} {entity_type.title()} {action}\n\n🆔 {entity_id}"
    if details:
        message += f"\n📝 {details}"
    await _send_telegram(message)
