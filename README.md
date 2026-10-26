\# App Manager for Flow Launcher



\*\*App Manager\*\* is a Python plugin for \[Flow Launcher](https://www.flowlauncher.com/) that integrates Windows Package Manager (winget), allowing users to search, install, download, update, and uninstall Windows applications directly from Flow Launcher.



\## Features



\- \*\*Installed Apps (`app list`):\*\* Browse and search installed applications with wildcard matching. Context menu options include Upgrade, Uninstall, and Copy Installation Path.

\- \*\*Package Search (`app search`):\*\* Search available winget packages by name, with options to install, download the installer, or view detailed package information.

\- \*\*Tag Search (`app tag`):\*\* Discover applications by package tags, with the same installation, download, and details options.

\- \*\*Available Updates (`app upgrade`):\*\* List applications with available updates and upgrade individual packages directly.

\- \*\*Package Details:\*\* View version, publisher, description, homepage, license, and other available metadata.

\- \*\*Caching (`app refresh`):\*\* Uses a 12-hour cache for installed applications, with manual refresh support to reduce unnecessary winget executions.



\## Requirements



\- Windows 10/11

\- Flow Launcher

\- Windows Package Manager (`winget`)



\## Usage



Type `app` in Flow Launcher, followed by a command such as `app list`, `app search firefox`, or `app tag file-manager`.



Use \*\*Right Arrow\*\* on a selected application to access its context menu and available management actions.

