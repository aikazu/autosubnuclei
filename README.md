# AutoSubNuclei

An automated security scanning pipeline that combines Subfinder, Httpx, and Nuclei for comprehensive security testing.

## Problem Statement

Security professionals need efficient ways to discover and scan subdomains for vulnerabilities. Manual scanning is time-consuming and error-prone. AutoSubNuclei automates the entire process from subdomain discovery to vulnerability detection.

## Key Features

- 🔍 Automated subdomain discovery with Subfinder
- 🌐 HTTP probing and technology detection with Httpx
- 🎯 Vulnerability scanning with Nuclei
- 🔔 Discord notifications for scan updates
- 🛠️ Automatic tool installation and updates

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

## Basic Usage

### Setup Notifications (Optional)
```bash
python autosubnuclei.py setup
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

## Technology Stack

- **Python 3.7+**: Core programming language
- **Click**: Command-line interface framework
- **Asyncio**: Asynchronous I/O for improved performance
- **ProjectDiscovery Tools**: Subfinder, Httpx, Nuclei
- **Requests/Aiohttp**: HTTP clients for API interactions
- **Tqdm**: Progress indicators

## Project Structure

```
autosubnuclei/
├── autosubnuclei.py          # Main CLI entry point
├── autosubnuclei/            # Source code
│   ├── commands/            # CLI commands
│   ├── config/             # Configuration management
│   ├── core/               # Core scanning functionality
│   └── utils/              # Utility functions
├── config.json              # User configuration
├── tools/                    # Downloaded security tools
└── output/                   # Scan results
```

## Additional Documentation

- [PLANNING.md](PLANNING.md): Project vision and roadmap
- [ARCHITECTURE.md](ARCHITECTURE.md): Technical architecture
- [TASK.md](TASK.md): Current development tasks

## License

This project is licensed under the MIT License.
