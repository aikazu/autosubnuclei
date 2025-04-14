# AutoSubNuclei

An automated security scanning pipeline that combines Subfinder, Httpx, and Nuclei for comprehensive security testing.

## Features

- 🔍 Automated subdomain discovery with Subfinder
- 🌐 HTTP probing and technology detection with Httpx
- 🎯 Vulnerability scanning with Nuclei
- 💾 Caching support for faster repeat scans (Subfinder)
- 📊 **Enhanced Interactive Progress:** Real-time feedback with timestamps, status updates, and cache usage indicators.
- 👆 **Confirmation Prompts:** Asks for confirmation before starting potentially long scans.
- 🛠️ Automatic tool installation and updates for Subfinder, Httpx, and Nuclei.
- 📥 Automatic Nuclei templates download and management.
- 🔔 Multiple notification options (Discord, Slack, Telegram) via `config.json`.
- 🖥️ Cross-platform support (Windows, Linux, macOS).
- 🎨 Clean output formatting and summary reports (`scan_report.txt`).
- 🚀 Virtual environment support.
- 📁 Local configuration management (`config.json`).
- ⚡ Asynchronous processing for improved performance.
- 🧵 Concurrent scanning with multiple workers.
- 📋 Detailed scan state reporting (`scan_state.json`).
- 📌 Self-contained workspace (tools/templates downloaded locally).

## Requirements

- Python 3.7+
- Virtual environment (recommended)
- Internet connection for tool downloads
- Notification service accounts (optional, for Discord/Slack/Telegram notifications)

## Installation

1. Clone the repository:
```bash
git clone https://github.com/yourusername/autosubnuclei.git
cd autosubnuclei
```

2. Create and activate a virtual environment:

For Windows:
```bash
python -m venv venv
.\venv\Scripts\activate
```

For Linux/Mac:
```bash
python3 -m venv venv
source venv/bin/activate
```

3. Install dependencies:
```bash
pip install -r requirements.txt
```

## Usage

### 1. Setup Notifications (Optional)

Configure notification webhooks/tokens via the interactive setup menu:
```bash
python autosubnuclei.py setup
```
Follow the prompts to add or update Discord, Slack, or Telegram details. These are saved in `config.json`.

You can also manage notifications directly:
```bash
python autosubnuclei.py setup --discord  # Setup/Update Discord
python autosubnuclei.py setup --slack    # Setup/Update Slack
python autosubnuclei.py setup --telegram # Setup/Update Telegram
python autosubnuclei.py setup --disable  # Disable all notifications
```

### 2. Run a Scan

```bash
python autosubnuclei.py scan example.com
```

- **Tool Checks:** The tool first verifies if Subfinder, Httpx, and Nuclei are installed in the `./tools` directory. If not, it will attempt to download the correct versions automatically.
- **Template Checks:** It checks for Nuclei templates in `./nuclei-templates/` (or the path specified by `--templates`). If not found, it will download them.
- **Confirmation:** You will be shown the scan parameters and asked to confirm before proceeding:
  ```
  🚀 Starting security scan for example.com
  🔧 Using templates from: /path/to/autosubnuclei/nuclei-templates
  📂 Saving results to: /path/to/autosubnuclei/output/example.com
  ⚠️  Selected severities: medium, high, critical
  ⏱️  Concurrency: auto
  💾 Cache: enabled
  ------------------------------
  Do you want to proceed with the scan? [Y/n]:
  ```
- **Progress:** During the scan, you will see status updates with timestamps:
  ```
    10:30:01 [INITIALIZING] 🚀 Initializing scan...
    10:30:01 [INFO] Verifying required tools (Subfinder, httpx, Nuclei)...
    10:30:02 [INFO] All required tools are already installed.
    10:30:02 [INFO] Nuclei templates found at /path/to/autosubnuclei/nuclei-templates.
    10:30:02 [DISCOVERING_SUBDOMAINS] 📡 Discovering subdomains (subfinder)...
    10:30:05 [INFO] Using cached results for subfinder.
    10:30:05 [PROBING_SUBDOMAINS] 🌐 Probing subdomains (httpx)... (Found 50 subdomains)
    10:30:15 [SCANNING_VULNERABILITIES] 🔍 Scanning for vulnerabilities (nuclei)... (Found 45/50 alive subdomains)
    10:35:00 [COMPLETED] ✅ Scan completed in 4m 58s. Found 3 potential vulnerabilities.
  ```
- **Output:** Results are saved in the `output/<domain>/` directory, including:
    - `results.txt`: Raw Nuclei findings.
    - `scan_state.json`: Summary statistics and status.
    - `scan_report.txt`: Human-readable summary of findings by severity.
    - `.cache/`: Contains cached results for subfinder.

### 3. View Scan Results

Display a summary of a previous scan:
```bash
python autosubnuclei.py results example.com
```
This reads the `scan_state.json` and `results.txt` files to provide a formatted summary.

### 4. Update Tools and Templates

Check for and download the latest versions of tools and Nuclei templates:
```bash
# Update everything (prompts for confirmation)
python autosubnuclei.py update

# Update only tools
python autosubnuclei.py update --tools

# Update only templates
python autosubnuclei.py update --templates

# Update all components, forcing download even if up-to-date
python autosubnuclei.py update --all --force
```

## Command Options

Based on `python autosubnuclei.py --help`

### Main Commands
```
Usage: autosubnuclei.py [OPTIONS] COMMAND [ARGS]...

  AutoSubNuclei - Automated Security Scanning Pipeline

Options:
  --help  Show this message and exit.

Commands:
  results  View the summary of previous scan results for a domain.
  scan     Run a security scan on a target domain.
  setup    Configure notification settings interactively or via flags.
  update   Update external tools and Nuclei templates.
```

### `scan` Options
```
Usage: autosubnuclei.py scan [OPTIONS] DOMAIN

  Run a security scan on a target domain.

Arguments:
  DOMAIN  [required]

Options:
  --templates TEXT    Path to nuclei templates directory.  [default:
                      ./nuclei-templates/]
  --output PATH       Output directory for results.  [default: output]
  --no-notify         Disable notifications (if configured).  [default:
                      False]
  --severities TEXT   Comma-separated Nuclei severity levels (critical, high,
                      medium, low, info).  [default: medium,high,critical]
  --log-file PATH     Path to log file (optional).
  --concurrency INTEGER
                      Maximum number of concurrent operations (0 = auto).
                      [default: auto]
  --cache / --no-cache
                      Enable/disable caching for faster repeat scans.
                      [default: True]
  --help              Show this message and exit.
```

### `results` Options
```
Usage: autosubnuclei.py results [OPTIONS] DOMAIN

  View the summary of previous scan results for a domain.

Arguments:
  DOMAIN  [required]

Options:
  --output PATH  Output directory where results were saved.  [default:
                 output]
  --help         Show this message and exit.
```

### `update` Options
```
Usage: autosubnuclei.py update [OPTIONS]

  Update external tools and Nuclei templates.

Options:
  --tools          Update security tools (Subfinder, Nuclei, httpx).
  --templates      Update Nuclei templates.
  --all            Update both tools and templates.  [default: False]
  --templates-dir TEXT
                   Path to Nuclei templates directory.  [default:
                   ./nuclei-templates/]
  --force          Force update even if up-to-date.  [default: False]
  --help           Show this message and exit.
```

### `setup` Options
```
Usage: autosubnuclei.py setup [OPTIONS]

  Configure notification settings interactively or via flags.

Options:
  --discord   Setup/Update Discord webhook URL.
  --slack     Setup/Update Slack webhook URL.
  --telegram  Setup/Update Telegram Bot Token and Chat ID.
  --disable   Disable all previously configured notifications.
  --help      Show this message and exit.
```

## Configuration

Primary configuration is handled via command-line arguments. Notification settings are stored in `config.json` after running the `setup` command.

## Tool Management

- Required tools (Subfinder, httpx, Nuclei) are automatically downloaded to the `./tools` directory if not found during the first run of a command that needs them (like `scan` or `update --tools`).
- Use `python autosubnuclei.py update` to check for and install the latest versions.

## Notifications

The tool can send notifications through multiple channels:
- Discord webhooks
- Slack webhooks
- Telegram bots

Notifications are sent for:
- Scan start
- Subdomain discovery
- Alive subdomains
- Scan completion
- Scan cancellation
- Errors and warnings

## Contributing

1. Fork the repository
2. Create a feature branch
3. Commit your changes
4. Push to the branch
5. Create a Pull Request

## License

This project is licensed under the MIT License - see the LICENSE file for details.

## Acknowledgments

- [ProjectDiscovery](https://projectdiscovery.io/) for their amazing tools
- All contributors and users of this project
