"""
fetch_vault_config_report.py
────────────────────────────
Standalone script — NOT part of the Impact Analyzer API.

Connects to Veeva Vault, triggers a Vault Configuration Report
(same report as Admin > Deployment > Vault Configuration Report > Generate Report),
waits for it to finish, and saves the ZIP to the output directory.

Usage:
    python fetch_vault_config_report.py

Configuration — set these in a .env file or as environment variables:
    VAULT_DNS          your-vault.veevavault.com
    VAULT_USERNAME     your@email.com
    VAULT_PASSWORD     yourpassword
    VAULT_API_VERSION  v24.1   (default)
    OUTPUT_DIR         ./vault_reports  (default)
"""

from __future__ import annotations

import os
import sys
import time
import logging
from datetime import datetime
from pathlib import Path

import requests
from dotenv import load_dotenv

load_dotenv()

# ─── Logging ──────────────────────────────────────────────────────────────────

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    stream=sys.stdout,
)
logger = logging.getLogger(__name__)

# ─── Config ───────────────────────────────────────────────────────────────────

VAULT_DNS         = os.getenv("VAULT_DNS", "")
VAULT_USERNAME    = os.getenv("VAULT_USERNAME", "")
VAULT_PASSWORD    = os.getenv("VAULT_PASSWORD", "")
VAULT_API_VERSION = os.getenv("VAULT_API_VERSION", "v24.1")
OUTPUT_DIR        = Path(os.getenv("OUTPUT_DIR", "./vault_reports"))

POLL_INTERVAL_SEC = 5    # seconds between job-status checks
MAX_POLL_ATTEMPTS = 60   # give up after 5 minutes


# ─── Veeva Vault client ───────────────────────────────────────────────────────

class VaultClient:
    def __init__(self, dns: str, version: str):
        self.base = f"https://{dns}/api/{version}"
        self.session = requests.Session()
        self.session.headers.update({"Accept": "application/json"})

    # ── Authentication ────────────────────────────────────────────────────────

    def authenticate(self, username: str, password: str) -> str:
        """Authenticate and store the session token. Returns sessionId."""
        logger.info("Authenticating as %s ...", username)
        resp = self.session.post(
            f"{self.base}/auth",
            data={"username": username, "password": password},
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )
        resp.raise_for_status()
        body = resp.json()

        if body.get("responseStatus") != "SUCCESS":
            errors = body.get("errors", [])
            raise RuntimeError(f"Authentication failed: {errors}")

        session_id = body["sessionId"]
        self.session.headers.update({"Authorization": session_id})
        logger.info("Authenticated successfully (vault: %s)", body.get("vaultId", "?"))
        return session_id

    # ── Trigger config report job ─────────────────────────────────────────────

    def start_config_report(self) -> str:
        """
        Trigger generation of the Vault Configuration Report.
        Returns the job ID to poll.

        API: POST /api/{version}/objects/vault/actions/configreport
        """
        logger.info("Requesting Vault Configuration Report generation ...")
        resp = self.session.post(
            f"{self.base}/objects/vault/actions/configreport"
        )
        resp.raise_for_status()
        body = resp.json()

        if body.get("responseStatus") != "SUCCESS":
            raise RuntimeError(f"Failed to start config report: {body.get('errors')}")

        job_id = str(body.get("job_id") or body.get("jobId") or "")
        if not job_id:
            raise RuntimeError(f"No job_id in response: {body}")

        logger.info("Config report job started — job_id=%s", job_id)
        return job_id

    # ── Poll job status ───────────────────────────────────────────────────────

    def wait_for_job(self, job_id: str) -> None:
        """Poll the job until it succeeds or fails."""
        logger.info("Waiting for job %s to complete ...", job_id)
        for attempt in range(1, MAX_POLL_ATTEMPTS + 1):
            resp = self.session.get(f"{self.base}/services/jobs/{job_id}")
            resp.raise_for_status()
            body = resp.json()

            data = body.get("data", [{}])
            status = data[0].get("status", "").upper() if data else ""

            logger.info("  [%d/%d] Job status: %s", attempt, MAX_POLL_ATTEMPTS, status)

            if status == "SUCCESS":
                return
            if status in ("FAILURE", "ERROR", "CANCELLED"):
                raise RuntimeError(f"Job {job_id} ended with status: {status}")

            time.sleep(POLL_INTERVAL_SEC)

        raise TimeoutError(f"Job {job_id} did not complete within the allotted time.")

    # ── Download report ZIP ───────────────────────────────────────────────────

    def download_config_report(self, job_id: str, output_dir: Path) -> Path:
        """
        Download the completed config report ZIP.

        API: GET /api/{version}/objects/vault/actions/configreport/{job_id}/results
        """
        logger.info("Downloading config report ZIP ...")
        resp = self.session.get(
            f"{self.base}/objects/vault/actions/configreport/{job_id}/results",
            stream=True,
        )
        resp.raise_for_status()

        output_dir.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        out_path = output_dir / f"vault_config_report_{timestamp}.zip"

        with open(out_path, "wb") as f:
            for chunk in resp.iter_content(chunk_size=8192):
                f.write(chunk)

        logger.info("Report saved → %s  (%d bytes)", out_path, out_path.stat().st_size)
        return out_path

    # ── Logout ────────────────────────────────────────────────────────────────

    def logout(self) -> None:
        try:
            self.session.delete(f"{self.base}/session")
            logger.info("Logged out from Vault.")
        except Exception:
            pass


# ─── Main ─────────────────────────────────────────────────────────────────────

def main() -> None:
    # Validate config
    missing = [k for k, v in {
        "VAULT_DNS": VAULT_DNS,
        "VAULT_USERNAME": VAULT_USERNAME,
        "VAULT_PASSWORD": VAULT_PASSWORD,
    }.items() if not v]

    if missing:
        logger.error(
            "Missing required environment variables: %s\n"
            "Set them in a .env file or export them before running.",
            ", ".join(missing),
        )
        sys.exit(1)

    client = VaultClient(VAULT_DNS, VAULT_API_VERSION)

    try:
        client.authenticate(VAULT_USERNAME, VAULT_PASSWORD)
        job_id  = client.start_config_report()
        client.wait_for_job(job_id)
        out     = client.download_config_report(job_id, OUTPUT_DIR)
        print(f"\nDone! Config report saved to:\n  {out.resolve()}\n")
    except Exception as exc:
        logger.error("Failed: %s", exc)
        sys.exit(1)
    finally:
        client.logout()


if __name__ == "__main__":
    main()
