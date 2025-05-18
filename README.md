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
- ⏸️ Scan resume capability for interrupted scans
- 🧠 Memory-optimized for handling large domain lists

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

### Resume Interrupted Scan
```bash
python autosubnuclei.py resume example.com
```

## Advanced Usage

### Specify Severity Levels
```bash
python autosubnuclei.py scan example.com --severities critical,high,medium
```

### Use Custom Templates
```bash
python autosubnuclei.py scan example.com --templates /path/to/templates
```

### Resume from Specific Checkpoint
```bash
python autosubnuclei.py resume example.com --from-checkpoint /path/to/checkpoint.json
```

### Force Resume from a Specific Phase
```bash
python autosubnuclei.py resume example.com --force-phase subdomain
```

## Technology Stack

- **Python 3.7+**: Core programming language
- **Click**: Command-line interface framework
- **Asyncio**: Asynchronous I/O for improved performance
- **ProjectDiscovery Tools**: Subfinder, Httpx, Nuclei
- **Requests/Aiohttp**: HTTP clients for API interactions
- **Tqdm**: Progress indicators
- **Psutil**: System resource monitoring

## Project Structure

```
autosubnuclei/
├── autosubnuclei.py          # Main CLI entry point
├── autosubnuclei/            # Source code
│   ├── commands/            # CLI commands
│   │   ├── resume.py        # Resume command implementation
│   │   └── setup.py         # Setup command implementation
│   ├── config/             # Configuration management
│   ├── core/               # Core scanning functionality
│   │   ├── scanner.py      # Main scanning logic
│   │   └── checkpoint_manager.py # Checkpoint handling
│   └── utils/              # Utility functions
├── config.json              # User configuration
├── tools/                    # Downloaded security tools
└── output/                   # Scan results
    └── example.com/          # Domain-specific results
        ├── subdomains.txt    # Discovered subdomains
        ├── alive.txt         # Alive subdomains
        ├── results.txt       # Scan results
        └── checkpoints/      # Resume checkpoints
```

## Additional Documentation

- [PLANNING.md](PLANNING.md): Project vision and roadmap
- [ARCHITECTURE.md](ARCHITECTURE.md): Technical architecture
- [TASK.md](TASK.md): Current development tasks
- [TECH-STACK.md](TECH-STACK.md): Detailed technology information

## License

This project is licensed under the MIT License.
