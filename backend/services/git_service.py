"""Git auto-commit service for tracking config changes."""
import logging
import subprocess
from pathlib import Path

from backend.config import settings

logger = logging.getLogger(__name__)


def auto_commit(message: str):
    """Stage and commit changes in the data directory."""
    if not settings.GIT_AUTO_COMMIT:
        return

    try:
        project_root = Path(__file__).resolve().parent.parent.parent

        # Check if git repo exists
        result = subprocess.run(
            ["git", "status", "--porcelain"],
            cwd=str(project_root),
            capture_output=True,
            text=True,
        )

        if result.returncode != 0:
            logger.warning("Not a git repository, skipping auto-commit")
            return

        if not result.stdout.strip():
            logger.debug("No changes to commit")
            return

        # Stage data directory changes
        subprocess.run(
            ["git", "add", "data/configs/"],
            cwd=str(project_root),
            capture_output=True,
        )

        # Commit
        subprocess.run(
            ["git", "commit", "-m", f"[loom] {message}"],
            cwd=str(project_root),
            capture_output=True,
        )

        logger.info(f"Auto-committed: {message}")

    except Exception as e:
        logger.error(f"Auto-commit failed: {e}")
