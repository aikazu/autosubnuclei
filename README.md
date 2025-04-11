# AutoSubNuclei

An automated security scanning tool that combines Subfinder, Httpx, and Nuclei for comprehensive security testing.

## Features

- 🔍 Automated subdomain discovery using Subfinder
- 🌐 HTTP probing with Httpx
- 🎯 Vulnerability scanning with Nuclei
- 🔔 Discord notifications for scan updates
- 🚫 Graceful cancellation handling with notifications
- 🛠️ Automatic tool installation and management
- 📊 Detailed scan results and logging

## Installation

1. Clone the repository:
```bash
git clone https://github.com/yourusername/autosubnuclei.git
cd autosubnuclei
```

2. Create and activate a virtual environment:
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

3. Install dependencies:
```bash
pip install -r requirements.txt
```

## Configuration

### Discord Notifications

To enable Discord notifications:

1. Run the setup command:
```bash
python autosubnuclei.py setup
```

2. Enter your Discord webhook URL when prompted.

The configuration will be saved in `~/.autosubnuclei/config.json`.

## Usage

### Basic Scan

```bash
python autosubnuclei.py scan example.com
```

### Advanced Options

```bash
python autosubnuclei.py scan example.com \
    --templates /path/to/templates \
    --output /path/to/output \
    --severities critical,high \
    --no-notify
```

### Options

- `--templates`: Path to Nuclei templates (default: built-in templates)
- `--output`: Output directory for scan results (default: ./results)
- `--severities`: Comma-separated list of severity levels (default: all)
- `--no-notify`: Disable notifications for this scan
- `--log-file`: Specify log file path (default: autosubnuclei.log)

## Notification Types

The tool sends the following types of notifications:

1. 🚀 **Scan Started**: When a scan begins
2. 🔍 **Subdomains Found**: List of discovered subdomains
3. 🌐 **Alive Subdomains**: List of responsive subdomains
4. 📊 **Scan Results**: Vulnerability findings
5. ✅ **Scan Completed**: When scan finishes successfully
6. 🚫 **Scan Cancelled**: When scan is interrupted or fails

### Cancellation Scenarios

The tool will send cancellation notifications in the following cases:

- User interrupts the scan (Ctrl+C)
- Tool installation fails
- Critical errors during scanning
- System signals (SIGTERM)

## Tool Management

The tool automatically:
- Checks for required tools (Subfinder, Httpx, Nuclei)
- Installs missing tools
- Verifies tool functionality
- Updates PATH for tool access

Tools are installed in `~/.autosubnuclei/tools/` and are only downloaded if missing.

## Output

Scan results are saved in the specified output directory with the following structure:

```
output/
├── subdomains.txt    # Discovered subdomains
├── alive.txt        # Responsive subdomains
└── results.txt      # Nuclei scan results
```

## Logging

Logs are written to `autosubnuclei.log` by default. You can specify a custom log file using the `--log-file` option.

## Requirements

- Python 3.7+
- Internet connection for tool downloads
- Discord webhook URL (for notifications)

## License

MIT License

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

## Acknowledgments

- [ProjectDiscovery](https://github.com/projectdiscovery) for their amazing tools:
  - [Subfinder](https://github.com/projectdiscovery/subfinder)
  - [HTTPx](https://github.com/projectdiscovery/httpx)
  - [Nuclei](https://github.com/projectdiscovery/nuclei)
