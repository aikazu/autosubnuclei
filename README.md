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

4. Run the setup command to configure notifications (optional):
```bash
python autosubnuclei.py setup
```

## Usage

### Basic Scan
```bash
python autosubnuclei.py scan example.com
```

### Advanced Options
```bash
python autosubnuclei.py scan example.com \
    --templates ~/nuclei-templates/ \
    --output results \
    --severities critical,high \
    --no-notify
```

### Options
- `--templates`: Path to Nuclei templates (default: ~/nuclei-templates/)
- `--output`: Output directory for results (default: output)
- `--severities`: Comma-separated list of severity levels (default: critical,high,medium,low)
- `--no-notify`: Disable notifications
- `--log-file`: Path to log file

## Project Structure

```
autosubnuclei/
├── autosubnuclei.py          # Main CLI entry point
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
