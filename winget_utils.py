
import hashlib
import re
import subprocess
import time
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent

# Cache locations
LIST_CACHE = BASE_DIR / "winget_list_cache.txt"
UPGRADE_CACHE = BASE_DIR / "winget_upgrade_cache.txt"
SEARCH_CACHE_DIR = BASE_DIR / "search_cache"

# Cache durations
LIST_CACHE_SECONDS = 12 * 60 * 60
UPGRADE_CACHE_SECONDS = 15 * 60
SEARCH_CACHE_SECONDS = 15 * 60


def run_winget(arguments):
    """Execute winget without opening a console."""

    result = subprocess.run(
        ["winget"] + arguments,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        creationflags=subprocess.CREATE_NO_WINDOW
    )

    if result.returncode != 0:
        message = result.stderr.strip() or result.stdout.strip()
        raise RuntimeError(message or "Winget command failed")

    return result.stdout


def cached_command(cache_file, arguments, duration, force=False):
    """Reuse cached output while it is valid."""

    if not force and cache_file.exists():
        age = time.time() - cache_file.stat().st_mtime

        if age < duration:
            return cache_file.read_text(encoding="utf-8")

    output = run_winget(arguments)

    cache_file.parent.mkdir(parents=True, exist_ok=True)
    cache_file.write_text(output, encoding="utf-8")

    return output


def get_installed_apps(force_refresh=False):
    return cached_command(
        LIST_CACHE,
        ["list", "--disable-interactivity",
         "--accept-source-agreements"],
        LIST_CACHE_SECONDS,
        force_refresh
    )


def search_packages(search_term):
    """Search available winget packages."""

    key = hashlib.sha256(
        search_term.casefold().encode("utf-8")
    ).hexdigest()

    cache_file = SEARCH_CACHE_DIR / (key + ".txt")

    return cached_command(
        cache_file,
        ["search", "--query", search_term,
         "--disable-interactivity",
         "--accept-source-agreements"],
        SEARCH_CACHE_SECONDS
    )


def get_upgradable_apps(force_refresh=False):
    """Get applications with available upgrades."""

    return cached_command(
        UPGRADE_CACHE,
        ["upgrade", "--disable-interactivity",
         "--accept-source-agreements"],
        UPGRADE_CACHE_SECONDS,
        force_refresh
    )

def show_package(app_name):
    """Retrieve detailed package information."""

    key = hashlib.sha256(
        ("show:" + app_name.casefold()).encode("utf-8")
    ).hexdigest()

    cache_file = SEARCH_CACHE_DIR / (key + ".txt")

    return cached_command(
        cache_file,
        [
            "show",
            "--name", app_name,
            "--disable-interactivity",
            "--accept-source-agreements"
        ],
        SEARCH_CACHE_SECONDS
    )


def search_by_tag(tag):
    """Search winget packages by tag."""

    key = hashlib.sha256(
        ("tag:" + tag.casefold()).encode("utf-8")
    ).hexdigest()

    cache_file = SEARCH_CACHE_DIR / (key + ".txt")

    return cached_command(
        cache_file,
        [
            "search",
            "--tag", tag,
            "--disable-interactivity",
            "--accept-source-agreements"
        ],
        SEARCH_CACHE_SECONDS
    )


def show_package_by_id(package_id):
    """Retrieve detailed information for an exact winget package ID."""

    key = hashlib.sha256(
        ("showid:" + package_id.casefold()).encode("utf-8")
    ).hexdigest()

    cache_file = SEARCH_CACHE_DIR / (key + ".txt")

    return cached_command(
        cache_file,
        [
            "show",
            "--id", package_id,
            "--exact",
            "--disable-interactivity",
            "--accept-source-agreements"
        ],
        SEARCH_CACHE_SECONDS
    )


def parse_winget_table(output):
    """Convert winget's aligned text table into dictionaries."""

    lines = output.splitlines()
    header_index = None

    for index, line in enumerate(lines):
        if re.search(r"\bName\s+Id\s+Version\b", line):
            header_index = index
            break

    if header_index is None:
        return []

    header = lines[header_index]

    # Detect column boundaries from the header.
    names = ["Name", "Id", "Version",
             "Available", "Match", "Source"]

    columns = []

    for name in names:
        match = re.search(
            r"(?<!\S)" + re.escape(name) + r"(?=\s|$)",
            header
        )
        if match:
            columns.append((name, match.start()))

    columns.sort(key=lambda item: item[1])

    # Locate the separator underneath the header.
    start_index = None

    for index in range(header_index + 1, len(lines)):
        stripped = lines[index].strip()

        if stripped and all(c in "-─" for c in stripped):
            start_index = index + 1
            break

    if start_index is None:
        return []

    results = []

    for line in lines[start_index:]:
        if not line.strip():
            continue

        row = {}

        for index, (name, start) in enumerate(columns):
            end = (
                columns[index + 1][1]
                if index + 1 < len(columns)
                else None
            )

            row[name.lower()] = line[start:end].strip()

        # Ignore summaries and other non-package lines.
        if not row.get("name") or not row.get("id"):
            continue

        if len(line) < dict(columns)["Version"]:
            continue

        results.append(row)

    return results
