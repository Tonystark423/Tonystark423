"""Stark Financial Holdings — Hugging Face Bucket Sync.

Provides rolling backups and export archiving via Hugging Face Storage Buckets
(hf://buckets/<owner>/<bucket>/...). Non-versioned, mutable, S3-like storage
backed by Xet chunk-level deduplication — ideal for ledger.db and generated
reports where you want overwrite-in-place without accumulating Git history.

Environment variables (all required when using this module):
  HF_TOKEN       Hugging Face write token (Settings → Access Tokens → New token)
  HF_BUCKET      Full bucket path, e.g. "tonystark423/stark-ledger-backups"

Optional:
  HF_BUCKET_PREFIX  Sub-path inside the bucket (default: "ledger")
  DB_PATH           Local path to ledger.db (default: "ledger.db")

Use cases wired up here:
  1. backup_db()         — sync ledger.db → bucket/backups/ledger.db
  2. archive_export()    — push a generated .xlsx or .csv to bucket/exports/
  3. restore_db()        — pull bucket/backups/ledger.db → local (disaster recovery)
  4. list_exports()      — list files stored under bucket/exports/

CLI:
  python hf_bucket_sync.py backup           # backup current ledger.db
  python hf_bucket_sync.py restore          # restore from bucket (OVERWRITES local db)
  python hf_bucket_sync.py archive <file>   # push a report file to exports/
  python hf_bucket_sync.py list             # list exports in bucket
"""

from __future__ import annotations

import os
import sys
from datetime import datetime, timezone
from pathlib import Path


# ---------------------------------------------------------------------------
# Config helpers
# ---------------------------------------------------------------------------

def _require_env(key: str) -> str:
    val = os.getenv(key)
    if not val:
        raise EnvironmentError(
            f"Missing required env var: {key}. "
            "Set it in .env or export it before running."
        )
    return val


def _bucket_path(remote_suffix: str) -> str:
    """Build a full hf://buckets/ path."""
    bucket = _require_env("HF_BUCKET")          # e.g. "tonystark423/stark-ledger-backups"
    prefix = os.getenv("HF_BUCKET_PREFIX", "ledger").strip("/")
    suffix = remote_suffix.lstrip("/")
    return f"hf://buckets/{bucket}/{prefix}/{suffix}"


# ---------------------------------------------------------------------------
# Backup
# ---------------------------------------------------------------------------

def backup_db(db_path: str | None = None) -> dict:
    """Sync ledger.db to the HF bucket's backups/ prefix.

    Uses chunk-level Xet deduplication — only changed chunks are uploaded,
    so successive backups of a mostly-unchanged DB are very fast.

    Returns:
        {"status": "ok", "local": str, "remote": str, "timestamp": str}
    """
    from huggingface_hub import HfApi
    from huggingface_hub import upload_file

    token     = _require_env("HF_TOKEN")
    local     = Path(db_path or os.getenv("DB_PATH", "ledger.db")).resolve()
    bucket    = _require_env("HF_BUCKET")
    prefix    = os.getenv("HF_BUCKET_PREFIX", "ledger").strip("/")
    remote_path = f"{prefix}/backups/ledger.db"

    if not local.exists():
        raise FileNotFoundError(f"Database not found: {local}")

    api = HfApi(token=token)
    api.upload_file(
        path_or_fileobj=str(local),
        path_in_repo=remote_path,
        repo_id=bucket,
        repo_type="bucket",
    )

    ts = datetime.now(timezone.utc).isoformat()
    return {
        "status":    "ok",
        "local":     str(local),
        "remote":    f"hf://buckets/{bucket}/{remote_path}",
        "timestamp": ts,
    }


# ---------------------------------------------------------------------------
# Restore
# ---------------------------------------------------------------------------

def restore_db(db_path: str | None = None) -> dict:
    """Pull the backup copy of ledger.db from the HF bucket to local disk.

    WARNING: This overwrites the local DB. Intended for disaster recovery.

    Returns:
        {"status": "ok", "local": str, "remote": str}
    """
    from huggingface_hub import hf_hub_download

    token   = _require_env("HF_TOKEN")
    bucket  = _require_env("HF_BUCKET")
    prefix  = os.getenv("HF_BUCKET_PREFIX", "ledger").strip("/")
    local   = Path(db_path or os.getenv("DB_PATH", "ledger.db")).resolve()

    remote_path = f"{prefix}/backups/ledger.db"

    downloaded = hf_hub_download(
        repo_id=bucket,
        filename=remote_path,
        repo_type="bucket",
        token=token,
        local_dir=str(local.parent),
        local_dir_use_symlinks=False,
    )

    # hf_hub_download may use a cache path — rename to the expected local path
    dl_path = Path(downloaded)
    if dl_path != local:
        dl_path.replace(local)

    return {
        "status": "ok",
        "local":  str(local),
        "remote": f"hf://buckets/{bucket}/{remote_path}",
    }


# ---------------------------------------------------------------------------
# Export archiving
# ---------------------------------------------------------------------------

def archive_export(file_path: str, subfolder: str = "") -> dict:
    """Push a generated report file (Excel, CSV, PNG) to bucket/exports/.

    Args:
        file_path: local path to the file to archive.
        subfolder: optional sub-path inside exports/ (e.g. "2024-Q1").

    Returns:
        {"status": "ok", "local": str, "remote": str}
    """
    from huggingface_hub import HfApi

    token   = _require_env("HF_TOKEN")
    bucket  = _require_env("HF_BUCKET")
    prefix  = os.getenv("HF_BUCKET_PREFIX", "ledger").strip("/")
    local   = Path(file_path).resolve()

    if not local.exists():
        raise FileNotFoundError(f"File not found: {local}")

    parts = [prefix, "exports"]
    if subfolder:
        parts.append(subfolder.strip("/"))
    parts.append(local.name)
    remote_path = "/".join(parts)

    api = HfApi(token=token)
    api.upload_file(
        path_or_fileobj=str(local),
        path_in_repo=remote_path,
        repo_id=bucket,
        repo_type="bucket",
    )

    return {
        "status": "ok",
        "local":  str(local),
        "remote": f"hf://buckets/{bucket}/{remote_path}",
    }


# ---------------------------------------------------------------------------
# List exports
# ---------------------------------------------------------------------------

def list_exports() -> list[dict]:
    """List files stored under bucket/exports/.

    Returns:
        List of {"name": str, "size": int, "last_modified": str}
    """
    from huggingface_hub import HfApi

    token   = _require_env("HF_TOKEN")
    bucket  = _require_env("HF_BUCKET")
    prefix  = os.getenv("HF_BUCKET_PREFIX", "ledger").strip("/")
    exports_prefix = f"{prefix}/exports/"

    api   = HfApi(token=token)
    items = api.list_repo_tree(
        repo_id=bucket,
        repo_type="bucket",
        path_in_repo=exports_prefix,
        recursive=True,
        expand=True,
    )

    results = []
    for item in items:
        if hasattr(item, "size"):   # RepoFile, not RepoFolder
            results.append({
                "name":          item.rfilename,
                "size":          item.size,
                "last_modified": str(getattr(item, "last_modified", "")),
            })
    return results


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import json
    from dotenv import load_dotenv

    load_dotenv()

    cmd = sys.argv[1] if len(sys.argv) > 1 else "help"

    if cmd == "backup":
        print(json.dumps(backup_db(), indent=2))

    elif cmd == "restore":
        confirm = input("This will overwrite the local ledger.db. Type YES to confirm: ")
        if confirm.strip() == "YES":
            print(json.dumps(restore_db(), indent=2))
        else:
            print("Aborted.")

    elif cmd == "archive":
        if len(sys.argv) < 3:
            print("Usage: python hf_bucket_sync.py archive <file> [subfolder]")
            sys.exit(1)
        subfolder = sys.argv[3] if len(sys.argv) > 3 else ""
        print(json.dumps(archive_export(sys.argv[2], subfolder=subfolder), indent=2))

    elif cmd == "list":
        items = list_exports()
        if not items:
            print("No exports found in bucket.")
        else:
            for item in items:
                size_kb = item["size"] / 1024
                print(f"{size_kb:>10.1f} KB  {item['last_modified'][:19]}  {item['name']}")

    else:
        print(__doc__)
