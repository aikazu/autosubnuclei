# AutoSubNuclei

An automated security scanning pipeline that combines Subfinder, Httpx, and Nuclei for comprehensive security testing.

## Features

- 🔍 Automated subdomain discovery with Subfinder
- 🌐 HTTP probing and technology detection with Httpx
- 🎯 Vulnerability scanning with Nuclei
- 🔔 Discord notifications for scan updates
- 🛠️ Automatic tool installation and updates
- 🖥️ Cross-platform support (Windows, Linux, macOS)
- 🔄 Latest version detection for all tools
- 🎨 Clean output formatting
- 🚀 Virtual environment support
- 📁 Local configuration management

## Requirements

- Python 3.7+
- Virtual environment (recommended)
- Internet connection for tool downloads
- Discord webhook (optional, for notifications)

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
This will prompt you to enter your Discord webhook URL for notifications.

### Basic Scan
```bash
python autosubnuclei.py scan example.com
```

### Advanced Options
```bash
python autosubnuclei.py scan example.com \
    --templates ~/nuclei-templates/ \
    --output output \
    --severities critical,high,medium,low \
    --no-notify \
    --log-file scan.log
```

### Command Options

#### Scan Command
- `domain` (required): The target domain to scan
- `--templates`: Path to Nuclei templates (default: ~/nuclei-templates/)
- `--output`: Output directory for results (default: output)
- `--severities`: Comma-separated list of severity levels (default: critical,high,medium,low)
- `--no-notify`: Disable notifications for this scan
- `--log-file`: Path to log file (optional)

#### Setup Command
- No additional options, just run `python autosubnuclei.py setup` and follow the prompts

## Project Structure

```
autosubnuclei/
├── autosubnuclei.py          # Main CLI entry point
├── autosubnuclei/            # Source code
│   ├── commands/            # CLI commands
│   ├── config/             # Configuration management
│   ├── core/               # Core scanning functionality
│   └── utils/              # Utility functions
├── config/                   # Configuration files
│   └── config.json          # User configuration
├── tools/                    # Downloaded security tools
├── output/                   # Scan results
└── requirements.txt          # Python dependencies
```

## Configuration

Configuration is stored in `./config/config.json` and includes:
- Discord webhook URL
- Notification preferences
- Default severity levels
- Output directory settings

## Tool Management

- Tools are automatically downloaded to the `./tools` directory
- Latest versions are detected and installed
- Tools are added to the system PATH
- Automatic updates when new versions are available

## Notifications

The tool sends Discord notifications for:
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
