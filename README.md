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
- No additional options, just run `python autosubnuclei.py setup` and follow the prompts

## Performance Optimizations

AutoSubNuclei has been optimized for performance:

- **Asynchronous Processing**: Uses Python's asyncio for non-blocking operations
- **Concurrent Execution**: Runs multiple tasks in parallel to maximize throughput
- **Intelligent Batching**: Processes subdomains in batches for better resource utilization
- **Result Caching**: Stores intermediate results to speed up repeated scans
- **Memory Optimization**: Reduces memory footprint by processing data in chunks
- **Progress Monitoring**: Real-time feedback on scan progress with minimal overhead
- **Auto-download Templates**: Automatically downloads nuclei templates into the workspace
- **Self-contained**: All files stay within the workspace directory

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
- Concurrency settings
- Cache configuration

## Tool Management

- Tools are automatically downloaded to the `./tools` directory
- Latest versions are detected and installed
- Tools are added to the system PATH
- Automatic updates when new versions are available
- Concurrent installation of multiple tools

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
