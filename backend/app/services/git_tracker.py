import subprocess
import logging
from pathlib import Path
from app.config import settings

logger = logging.getLogger("loom.git")


def _run_git(args: list[str], cwd: str = None) -> str:
    if cwd is None:
        cwd = str(settings.base_path.parent)  # Loom root
    try:
        result = subprocess.run(
            ["git"] + args,
            cwd=cwd,
            capture_output=True,
            text=True,
            timeout=30,
        )
        if result.returncode != 0:
            logger.warning(f"git {' '.join(args)} failed: {result.stderr}")
        return result.stdout.strip()
    except FileNotFoundError:
        logger.warning("git not found on system")
        return ""
    except subprocess.TimeoutExpired:
        logger.warning(f"git {' '.join(args)} timed out")
        return ""


def init_repo():
    """Initialize git repo if not already initialized."""
    git_dir = settings.base_path.parent / ".git"
    if not git_dir.exists():
        _run_git(["init"])
        # Create .gitignore
        gitignore = settings.base_path.parent / ".gitignore"
        if not gitignore.exists():
            gitignore.write_text(
                "backend/.env\n"
                "backend/__pycache__/\n"
                "backend/app/__pycache__/\n"
                "backend/app/**/__pycache__/\n"
                "data/loom.db\n"
                "data/loom.db-wal\n"
                "data/loom.db-shm\n"
                "*.pyc\n"
                ".venv/\n"
                "venv/\n"
            )
        _run_git(["add", "."])
        _run_git(["commit", "-m", "Initial Loom setup"])
        logger.info("Git repository initialized")


def auto_commit(message: str):
    """Stage all changes and create a commit."""
    _run_git(["add", "-A"])
    # Check if there are staged changes
    status = _run_git(["status", "--porcelain"])
    if status:
        _run_git(["commit", "-m", f"[loom] {message}"])
        logger.info(f"Auto-committed: {message}")
    else:
        logger.debug("No changes to commit")
