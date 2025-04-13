# AutoSubNuclei

An automated security scanning pipeline that combines Subfinder, Httpx, and Nuclei for comprehensive security testing.

## Features

- 🔍 Automated subdomain discovery with Subfinder
- 🌐 HTTP probing and technology detection with Httpx
- 🎯 Vulnerability scanning with Nuclei
- 🔔 Multiple notification options (Discord, Slack, Telegram)
- 🛠️ Automatic tool installation and updates
- 🖥️ Cross-platform support (Windows, Linux, macOS)
- 🔄 Latest version detection for all tools
- 🎨 Clean output formatting
- 🚀 Virtual environment support
- 📁 Local configuration management
- ⚡ Asynchronous processing for improved performance
- 💾 Caching support for faster repeat scans
- 📊 Progress indicators for real-time feedback
- 🧵 Concurrent scanning with multiple workers
- 📋 Detailed scan state reporting
- 📥 Automatic templates download and management
- 📌 Self-contained workspace (no files outside project directory)

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

### Setup Notifications (Optional)
```bash
python autosubnuclei.py setup
```
This will prompt you with a menu to configure notification options:
- Discord webhooks
- Slack webhooks
- Telegram bot

You can also set up specific notification channels directly:
```bash
python autosubnuclei.py setup --discord  # Set up Discord
python autosubnuclei.py setup --slack    # Set up Slack
python autosubnuclei.py setup --telegram # Set up Telegram
python autosubnuclei.py setup --disable  # Disable all notifications
```

### Basic Scan
```bash
python autosubnuclei.py scan example.com
```

### View Scan Results
```bash
python autosubnuclei.py results example.com
```

### Update Tools and Templates
```bash
python autosubnuclei.py update
```

### Advanced Options
```bash
python autosubnuclei.py scan example.com \
    --templates ./nuclei-templates/ \
    --output output \
    --severities critical,high,medium,low \
    --no-notify \
    --log-file scan.log \
    --concurrency 8 \
    --cache
```

### Command Options

#### Scan Command
- `domain` (required): The target domain to scan
- `--templates`: Path to nuclei templates (default: ./nuclei-templates/, will be automatically downloaded to workspace if not found)
- `--output`: Output directory for results (default: output)
- `--severities`: Comma-separated list of severity levels (default: critical,high,medium,low)
- `--no-notify`: Disable notifications for this scan
- `--log-file`: Path to log file (optional)
- `--concurrency`: Maximum number of concurrent operations (default: auto-detect based on CPU cores)
- `--cache/--no-cache`: Enable/disable caching of results for faster repeat scans (default: enabled)

#### Results Command
- `domain` (required): The target domain to view results for
- `--output`: Directory containing scan results (default: output)

#### Update Command
- `--tools`: Update security tools to the latest versions
- `--templates`: Update nuclei templates to the latest version
- `--all`: Update both tools and templates (default if no option specified)
- `--templates-dir`: Path to nuclei templates directory (default: ./nuclei-templates/)
- `--force`: Force update even if already up to date

#### Setup Command
- `--discord`: Configure Discord webhook notifications
- `--slack`: Configure Slack webhook notifications
- `--telegram`: Configure Telegram bot notifications
- `--disable`: Disable all notifications
- No options: Shows an interactive setup menu

## Notification Setup Guide

### Discord Notifications
1. Open your Discord server settings
2. Go to Integrations > Webhooks
3. Create a new webhook for the channel where you want to receive notifications
4. Copy the webhook URL
5. Run `python autosubnuclei.py setup --discord` and paste the URL

### Slack Notifications
1. Go to your Slack workspace settings
2. Navigate to Apps > Incoming Webhooks
3. Create a new app or use an existing one
4. Activate Incoming Webhooks and create a new webhook
5. Copy the webhook URL
6. Run `python autosubnuclei.py setup --slack` and paste the URL

### Telegram Notifications
1. Talk to [@BotFather](https://t.me/botfather) on Telegram
2. Create a new bot using the `/newbot` command
3. Copy the bot token provided
4. Talk to [@userinfobot](https://t.me/userinfobot) to get your chat ID
5. Run `python autosubnuclei.py setup --telegram` and enter both the token and chat ID

## Configuration

Configuration is stored in `config.json` in the project root and includes:
- Notification settings (Discord, Slack, Telegram)
- Default severity levels
- Output directory settings
- Concurrency settings
- Cache configuration

## Tool Management

- Tools are automatically downloaded to the `./tools` directory
- Latest versions are detected and installed
- Tools are added to the system PATH
- Automatic updates when new versions are available
- Concurrent installation of multiple tools

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
