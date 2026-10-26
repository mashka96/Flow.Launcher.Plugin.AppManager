

import sys
import os
import re
import fnmatch
import subprocess
import base64
import ctypes
import winreg
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(BASE_DIR / "lib"))

from flowlauncher import FlowLauncher, FlowLauncherAPI

from winget_utils import (
    get_installed_apps,
    search_packages,
    search_by_tag,
    show_package,
    show_package_by_id,
    get_upgradable_apps,
    parse_winget_table,
    LIST_CACHE,
    UPGRADE_CACHE
)

ICON = "Images/app.png"

SHOW_DETAILS_REQUEST = BASE_DIR / "show_details_request.txt"


def result(title, subtitle="", action=None, context=None):
    """Create a Flow Launcher result."""

    item = {
        "Title": title,
        "SubTitle": subtitle,
        "IcoPath": ICON
    }

    
    if action:
        item["JsonRPCAction"] = {
            "method": action[0],
            "parameters": list(action[1:]),
            "DontHideAfterAction": action[0] == "open_show"
        }


    if context:
        item["ContextData"] = context

    return item


def matches(app, pattern):
    """Match name or ID, including wildcard patterns."""

    if not pattern:
        return True

    if "*" not in pattern and "?" not in pattern:
        pattern = f"*{pattern}*"

    pattern = pattern.casefold()

    return (
        fnmatch.fnmatchcase(
            app.get("name", "").casefold(), pattern
        )
        or fnmatch.fnmatchcase(
            app.get("id", "").casefold(), pattern
        )
    )


def usable_id(package_id):
    """Reject missing or truncated package IDs."""

    return bool(
        package_id
        and "…" not in package_id
        and "..." not in package_id
        and "\n" not in package_id
        and "\r" not in package_id
    )


def find_install_path(app_name):
    """Look for an installation directory in the registry."""

    registry_path = (
        r"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall"
    )

    hives = [winreg.HKEY_CURRENT_USER, winreg.HKEY_LOCAL_MACHINE]
    views = [winreg.KEY_WOW64_64KEY, winreg.KEY_WOW64_32KEY]

    for hive in hives:
        for view in views:
            try:
                with winreg.OpenKey(
                    hive, registry_path, 0,
                    winreg.KEY_READ | view
                ) as root:

                    count = winreg.QueryInfoKey(root)[0]

                    for index in range(count):
                        subkey_name = winreg.EnumKey(root, index)

                        try:
                            with winreg.OpenKey(root, subkey_name) as key:
                                name = winreg.QueryValueEx(
                                    key, "DisplayName"
                                )[0]

                                if name.casefold() != app_name.casefold():
                                    continue

                                location = winreg.QueryValueEx(
                                    key, "InstallLocation"
                                )[0]

                                location = Path(
                                    os.path.expandvars(location.strip('"'))
                                )

                                if location.is_dir():
                                    return str(location)

                        except (OSError, ValueError):
                            continue

            except OSError:
                continue

    return None


def ps_quote(value):
    """Quote one string as a PowerShell literal."""

    return "'" + str(value).replace("'", "''") + "'"


class AppManager(FlowLauncher):

    def query(self, query):

        command = query.strip()
        lower = command.lower()

        # APP REFRESH
        if lower == "refresh":
            return [
                result(
                    "Refresh application data",
                    "Refresh installed applications and upgrades",
                    ("refresh_apps",)
                )
            ]
        
        # APP SHOW
        if lower == "show" or lower.startswith("show "):

            app_name = command[4:].strip()

            if len(app_name) < 3:
                return [
                    result(
                        "Show package information",
                        "Usage: app show <package name>"
                    )
                ]

            
            try:
                if app_name.lower().startswith("--id "):
                    package_id = app_name[5:].strip()
                    output = show_package_by_id(package_id)
                else:
                    output = show_package(app_name)

            except Exception as error:

                return [
                    result(
                        "Unable to retrieve package details",
                        str(error)[:200]
                    )
                ]

            # Winget can return a table if multiple packages match.
            matches_found = parse_winget_table(output)

            if matches_found:
                return [
                    result(app["name"], app["id"])
                    for app in matches_found
                ]

            details = []

            for line in output.splitlines():

                line = line.strip()

                if not line:
                    continue

                # Identify the package header.
                match = re.match(
                    r"^Found (.+?) \[([^\]]+)\](.*)$",
                    line
                )

                if match:
                    details.append(
                        result(match.group(1), match.group(2))
                    )

                    remainder = match.group(3).strip()

                    if remainder:
                        details.append(
                            result("Package information", remainder)
                        )

                    continue

                # Separate metadata labels and values.
                if ":" in line:
                    label, value = line.split(":", 1)

                    details.append(
                        result(label.strip(), value.strip())
                    )

                else:
                    details.append(
                        result(line, "")
                    )

            return details or [
                result("No package information available")
            ]
        
        # APP TAG
        if lower == "tag" or lower.startswith("tag "):

            tag = command[3:].strip()

            if len(tag) < 2:
                return [
                    result(
                        "Search packages by tag",
                        "Usage: app tag <tag name>"
                    )
                ]

            try:
                output = search_by_tag(tag)
                apps = parse_winget_table(output)

            except Exception as error:
                return [
                    result(
                        "Tag search failed",
                        str(error)[:200]
                    )
                ]

            return [
                result(
                    app["name"],
                    app["id"],
                    context=[
                        "available",
                        app["id"],
                        app["name"],
                        app.get("source", "")
                    ]
                )
                for app in apps
            ] or [
                result("No packages found for tag: " + tag)
            ]


        # APP LIST
        if lower == "list" or lower.startswith("list "):

            pattern = command[4:].strip()

            try:
                output = get_installed_apps()
                apps = parse_winget_table(output)
            except Exception as error:
                return [result("Winget list failed", str(error)[:200])]

            return [
                result(
                    app["name"],
                    app["id"],
                    context=[
                        "installed",
                        app["id"],
                        app["name"],
                        app.get("source", "")
                    ]
                )
                for app in apps
                if matches(app, pattern)
            ] or [result("No installed applications found")]

        # APP SEARCH
        if lower == "search" or lower.startswith("search "):

            search_term = command[6:].strip()

            if len(search_term) < 3:
                return [
                    result(
                        "Search winget packages",
                        "Enter at least 3 characters"
                    )
                ]

            try:
                output = search_packages(search_term)
                apps = parse_winget_table(output)
            except Exception as error:
                return [result("Winget search failed", str(error)[:200])]

            return [
                result(
                    app["name"],
                    app["id"],
                    context=[
                        "available",
                        app["id"],
                        app["name"],
                        app.get("source", "")
                    ]
                )
                for app in apps
            ] or [result("No matching packages found")]

        # APP UPGRADE
        if lower == "upgrade" or lower.startswith("upgrade "):

            pattern = command[7:].strip()

            try:
                output = get_upgradable_apps()
                apps = parse_winget_table(output)
            except Exception as error:
                return [result("Upgrade check failed", str(error)[:200])]

            apps = [
                app for app in apps
                if app.get("available")
                and matches(app, pattern)
            ]

            return [
                result(
                    app["name"],
                    app["id"],
                    action=(
                        "run_action",
                        "upgrade",
                        app["id"],
                        app["name"],
                        app.get("source", "")
                    )
                )
                for app in apps
                if usable_id(app["id"])
            ] or [result("No available upgrades found")]

        
        # MAIN COMMAND MENU
        if not command:
            return [
                result("List installed applications", "app list"),
                result("Search winget packages by name", "app search"),
                result("Search packages by tag", "app tag"),
                result("Available upgrades", "app upgrade"),
                result("Refresh application data", "app refresh")
            ]


        return [
            result(
                "Unknown command",
                "Use list, search, upgrade, show tag or refresh"
            )
        ]

    def context_menu(self, data):
        """Build the context menu for a selected package."""

        if not data or len(data) < 4:
            return []

        kind, package_id, name, source = data

        
        # Check whether the user requested package details.
        if kind == "available" and SHOW_DETAILS_REQUEST.exists():

            requested_id = SHOW_DETAILS_REQUEST.read_text(
                encoding="utf-8"
            ).strip()

            # Clear the request after reading it.
            SHOW_DETAILS_REQUEST.unlink(missing_ok=True)

            if requested_id == package_id:
                return self.query(
                    f"show --id {package_id}"
                )


        if not usable_id(package_id):
            return [
                result(
                    "Package ID is incomplete",
                    "Winget truncated this ID; action unavailable"
                )
            ]

        # INSTALLED APPLICATION CONTEXT MENU
        if kind == "installed":
            return [
                result(
                    "Upgrade",
                    name,
                    ("run_action", "upgrade", package_id, name, source)
                ),
                result(
                    "Uninstall",
                    name,
                    ("run_action", "uninstall", package_id, name, source)
                ),
                result(
                    "Copy path",
                    "Copy the installation directory",
                    ("copy_path", name)
                )
            ]

        # AVAILABLE PACKAGE CONTEXT MENU
        
        if kind == "available":
            return [
                result(
                    "Install",
                    name,
                    ("run_action", "install", package_id, name, source)
                ),
                result(
                    "Download installer",
                    "Save installer to Downloads",
                    ("run_action", "download", package_id, name, source)
                ),
                result(
                    "Show details",
                    "View package information",
                    ("open_show", package_id)
                )
            ]


        return []
    
    
    def open_show(self, package_id):
        """Display package details in the current context menu."""

        # Remember the selected package.
        SHOW_DETAILS_REQUEST.write_text(
            package_id,
            encoding="utf-8"
        )

        # Refresh the context menu without changing pages.
        FlowLauncherAPI.change_query("", True)



    def run_action(self, operation, package_id, name, source=""):
        """Start a package operation in a separate terminal."""

        allowed = {"install", "download", "upgrade", "uninstall"}

        if operation not in allowed or not usable_id(package_id):
            return

        # Confirm uninstallation before proceeding.
        if operation == "uninstall":
            answer = ctypes.windll.user32.MessageBoxW(
                None,
                f"Uninstall {name}?\n\nPackage ID: {package_id}",
                "App Manager",
                0x24
            )

            if answer != 6:
                return

        arguments = [
            operation, "--id", package_id, "--exact"
        ]

        if source:
            arguments += ["--source", source]

        if operation in {"install", "upgrade", "download"}:
            arguments += [
                "--accept-source-agreements",
                "--accept-package-agreements"
            ]

        if operation == "download":
            arguments += [
                "--download-directory",
                str(Path.home() / "Downloads")
            ]

        # Build a PowerShell command with quoted arguments.
        winget_command = "& winget " + " ".join(
            ps_quote(arg) for arg in arguments
        )

        invalidate = ""

        if operation in {"install", "upgrade", "uninstall"}:
            invalidate = (
                f"Remove-Item -LiteralPath {ps_quote(LIST_CACHE)} "
                "-Force -ErrorAction SilentlyContinue\n"
                f"Remove-Item -LiteralPath {ps_quote(UPGRADE_CACHE)} "
                "-Force -ErrorAction SilentlyContinue"
            )

        script = f"""
Write-Host {ps_quote(operation.upper() + ": " + name)}
Write-Host ""

{winget_command}

$exitCode = $LASTEXITCODE

{invalidate}

Write-Host ""
Write-Host "Winget exit code: $exitCode"
Read-Host "Press Enter to close this window"
"""

        encoded = base64.b64encode(
            script.encode("utf-16le")
        ).decode("ascii")

        subprocess.Popen(
            [
                "powershell.exe",
                "-NoProfile",
                "-EncodedCommand",
                encoded
            ],
            creationflags=subprocess.CREATE_NEW_CONSOLE,
            close_fds=True
        )

    def copy_path(self, app_name):
        """Copy an application's installation directory."""

        path = find_install_path(app_name)

        if not path:
            ctypes.windll.user32.MessageBoxW(
                None,
                "Windows did not report an installation directory.",
                "App Manager",
                0x40
            )
            return

        environment = os.environ.copy()
        environment["APP_MANAGER_COPY_PATH"] = path

        result_code = subprocess.run(
            [
                "powershell.exe",
                "-NoProfile",
                "-NonInteractive",
                "-Command",
                "Set-Clipboard -Value $env:APP_MANAGER_COPY_PATH"
            ],
            env=environment,
            capture_output=True,
            creationflags=subprocess.CREATE_NO_WINDOW
        ).returncode

        if result_code == 0:
            ctypes.windll.user32.MessageBoxW(
                None,
                path,
                "Copied installation directory",
                0x40
            )

    def refresh_apps(self):
        get_installed_apps(force_refresh=True)
        get_upgradable_apps(force_refresh=True)


if __name__ == "__main__":
    AppManager()
