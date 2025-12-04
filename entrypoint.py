#!/usr/bin/env python3
"""
ETH VVZ MCP Server Entrypoint
Auto-detects semesters and refreshes database when new data is available.

This container provides an MCP (Model Context Protocol) server for querying
the ETH Zurich course catalog. It automatically:
- Detects the current and upcoming semesters
- Scrapes course data from the official ETH VVZ website
- Provides SQL query access via MCP tools

Environment Variables:
- ETH_SEMESTER: Force specific semester (e.g., "2026S")
- FORCE_REFRESH: Set to "1" to force re-scrape
- SCRAPE_UPCOMING: Set to "1" to also scrape the upcoming semester (default: 1)

Author: Alfonso Ridao
License: MIT
"""
import json
import os
import subprocess
import sys
import urllib.request
import urllib.error
from datetime import datetime
from pathlib import Path
from typing import Optional

__version__ = "1.0.0"

DATA_DIR = Path("/data")
DB_PATH = DATA_DIR / "vvz.db"
METADATA_FILE = DATA_DIR / ".metadata.json"
VVZAPI_DIR = Path("/app/vvzapi")

# Pre-scraped database location (embedded in container)
DEFAULT_DATA_DIR = Path("/app/default-data")
DEFAULT_DB_PATH = DEFAULT_DATA_DIR / "vvz.db"
DEFAULT_METADATA_PATH = DEFAULT_DATA_DIR / ".metadata.json"

# ETH VVZ API endpoint to check available semesters
VVZ_SEMESTERS_URL = "https://vvzapi.ch/api/v1/misc/semesters"


def log(message: str, level: str = "INFO") -> None:
    """Print timestamped log message."""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{timestamp}] [{level}] {message}")


def copy_default_database() -> bool:
    """
    Copy the pre-scraped database from /app/default-data to /data if needed.
    Returns True if database is available (either copied or already existed).
    """
    import shutil

    # If database already exists, nothing to do
    if DB_PATH.exists():
        log("Using existing database from volume")
        return True

    # Check if we have a pre-scraped database
    if not DEFAULT_DB_PATH.exists():
        log("No pre-scraped database available", "WARN")
        return False

    # Copy default database to data directory
    log("Copying pre-scraped database for instant startup...")

    try:
        shutil.copy2(DEFAULT_DB_PATH, DB_PATH)
        log(f"Copied database: {DEFAULT_DB_PATH} -> {DB_PATH}")

        # Also copy metadata if available
        if DEFAULT_METADATA_PATH.exists():
            shutil.copy2(DEFAULT_METADATA_PATH, METADATA_FILE)
            log("Copied metadata file")

        db_size = DB_PATH.stat().st_size / (1024 * 1024)
        log(f"Pre-scraped database ready ({db_size:.1f} MB)")
        return True

    except (OSError, IOError) as e:
        log(f"Failed to copy default database: {e}", "ERROR")
        return False


def get_current_semester() -> str:
    """
    Return semester string like '2026S' or '2025W'.

    ETH Zurich semesters:
    - Spring (Fruhlingssemester): February - July -> 'S'
    - Winter (Herbstsemester): August - January -> 'W'
    """
    now = datetime.now()
    month = now.month
    year = now.year

    if 2 <= month <= 7:
        return f"{year}S"
    elif month >= 8:
        return f"{year}W"
    else:
        return f"{year - 1}W"


def get_upcoming_semester() -> str:
    """
    Return the upcoming semester for course planning.

    Students typically plan courses 1-2 months before the semester starts:
    - Nov-Jan: Planning for Spring semester
    - May-Jul: Planning for Winter semester
    """
    now = datetime.now()
    month = now.month
    year = now.year

    if 5 <= month <= 7:
        return f"{year}W"
    elif month >= 11 or month == 1:
        next_year = year + 1 if month >= 11 else year
        return f"{next_year}S"
    else:
        return get_current_semester()


def check_available_semesters() -> list[str]:
    """
    Query the VVZ API to get list of available semesters.
    Returns list like ['2025W', '2026S', '2026W']
    """
    try:
        with urllib.request.urlopen(VVZ_SEMESTERS_URL, timeout=10) as response:
            data = json.loads(response.read().decode())
            # API returns list of semester objects
            semesters = []
            for sem in data:
                if isinstance(sem, dict) and "semkez" in sem:
                    semesters.append(sem["semkez"])
                elif isinstance(sem, str):
                    semesters.append(sem)
            return sorted(semesters)
    except (urllib.error.URLError, json.JSONDecodeError, KeyError) as e:
        log(f"Could not fetch available semesters: {e}", "WARN")
        return []


def load_metadata() -> dict:
    """Load metadata about scraped semesters."""
    if METADATA_FILE.exists():
        try:
            return json.loads(METADATA_FILE.read_text())
        except json.JSONDecodeError:
            pass
    return {"semesters": {}, "last_check": None, "version": __version__}


def save_metadata(metadata: dict) -> None:
    """Save metadata to file."""
    metadata["version"] = __version__
    metadata["last_check"] = datetime.now().isoformat()
    METADATA_FILE.write_text(json.dumps(metadata, indent=2))


def needs_scrape(semester: str, metadata: dict) -> bool:
    """Check if a semester needs to be scraped."""
    if not DB_PATH.exists():
        return True

    sem_info = metadata.get("semesters", {}).get(semester, {})
    if not sem_info:
        return True

    # Check if scrape was successful
    if not sem_info.get("complete", False):
        return True

    return False


def run_scraper(semester: str) -> bool:
    """
    Run the vvzapi scraper for the given semester.
    Returns True if successful, False otherwise.
    """
    year = semester[:-1]
    sem_type = semester[-1]

    log("=" * 60)
    log(f"SCRAPING: {semester}")
    log(f"Year: {year}, Type: {'Spring' if sem_type == 'S' else 'Winter'}")
    log("=" * 60)

    env = os.environ.copy()
    env["semester"] = sem_type
    env["start_year"] = year
    env["end_year"] = year
    env["db_path"] = str(DB_PATH)

    try:
        # Run alembic migrations
        log("Running database migrations...")
        subprocess.run(
            ["uv", "run", "alembic", "upgrade", "heads"],
            cwd=str(VVZAPI_DIR),
            env=env,
            check=True,
        )

        # Run the scraper
        log("Starting scraper (this may take 30-60 minutes for first run)...")
        subprocess.run(
            ["uv", "run", "-m", "scraper.main"],
            cwd=str(VVZAPI_DIR),
            env=env,
            check=True,
        )

        log(f"Scrape complete for {semester}!")
        return True

    except subprocess.CalledProcessError as e:
        log(f"Scraper failed with exit code {e.returncode}", "ERROR")
        return False


def main():
    """Main entrypoint."""
    print()
    log("=" * 60)
    log("ETH VVZ MCP Server")
    log(f"Version: {__version__}")
    log(f"Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    log("=" * 60)
    print()

    # Ensure data directory exists
    DATA_DIR.mkdir(parents=True, exist_ok=True)

    # Copy pre-scraped database if available and needed
    copy_default_database()

    # Load metadata
    metadata = load_metadata()

    # Determine which semesters to scrape
    force_refresh = os.environ.get("FORCE_REFRESH", "").lower() in ("1", "true", "yes")
    target_semester = os.environ.get("ETH_SEMESTER") or get_upcoming_semester()
    scrape_upcoming = os.environ.get("SCRAPE_UPCOMING", "1").lower() in ("1", "true", "yes")

    log(f"Target semester: {target_semester}")
    log(f"Force refresh: {force_refresh}")

    # Check available semesters from API
    available = check_available_semesters()
    if available:
        log(f"Available semesters from API: {', '.join(available)}")

    # Determine semesters to scrape
    semesters_to_scrape = []

    if force_refresh:
        semesters_to_scrape.append(target_semester)
    elif needs_scrape(target_semester, metadata):
        semesters_to_scrape.append(target_semester)
    else:
        log(f"Database already has data for {target_semester}")

    # Optionally scrape upcoming semester too
    if scrape_upcoming:
        upcoming = get_upcoming_semester()
        if upcoming != target_semester and needs_scrape(upcoming, metadata):
            if not available or upcoming in available:
                semesters_to_scrape.append(upcoming)

    # Run scraper for each semester
    for semester in semesters_to_scrape:
        success = run_scraper(semester)
        metadata["semesters"][semester] = {
            "scraped_at": datetime.now().isoformat(),
            "complete": success,
        }
        save_metadata(metadata)

    # Verify database exists
    if not DB_PATH.exists():
        log("No database available. Cannot start MCP server.", "ERROR")
        sys.exit(1)

    # Show database info
    db_size = DB_PATH.stat().st_size / (1024 * 1024)
    log(f"Database: {DB_PATH} ({db_size:.1f} MB)")
    log(f"Scraped semesters: {', '.join(metadata.get('semesters', {}).keys())}")

    # Start MCP server
    print()
    log("=" * 60)
    log("Starting MCP server on stdio...")
    log("Ready to accept queries!")
    log("=" * 60)
    print()

    os.execvp("python", ["python", "/app/mcp_server.py"])


if __name__ == "__main__":
    main()
