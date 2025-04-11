# AutoSubNuclei

Automated Security Scanning Pipeline that combines Subfinder, HTTPx, and Nuclei for comprehensive security testing.

## Features

- Automated installation of required tools (Subfinder, HTTPx, Nuclei)
- Complete security scanning pipeline:
  - Subdomain discovery using Subfinder
  - Alive subdomain detection using HTTPx
  - Vulnerability scanning using Nuclei
- Cross-platform support (Windows, Linux, macOS)
- Automatic tool updates and verification
- Configurable severity levels for Nuclei scans

## Installation

1. Clone the repository:
```bash
git clone https://github.com/aikazu/autosubnuclei.git
cd autosubnuclei
```

2. Install Python dependencies:
```bash
pip install -r requirements.txt
```

## Usage

Basic usage:
```bash
python autosubnuclei.py example.com
```

Advanced options:
```bash
python autosubnuclei.py example.com \
    --templates ~/nuclei-templates/ \
    --output ./results \
    --severities critical,high,medium \
    --no-notify
```

### Command Line Arguments

- `domain`: Target domain to scan (required)
- `--templates`: Path to nuclei templates (default: ~/nuclei-templates/)
- `--output`: Output directory for results (default: ./output)
- `--severities`: Comma-separated Nuclei severity levels (default: critical,high,medium)
- `--no-notify`: Disable notifications
- `--log-file`: Path to log file

## Output

The tool generates the following files in the output directory:
- `subdomains.txt`: All discovered subdomains
- `alive.txt`: Subdomains that are alive
- `results.txt`: Nuclei scan results

## Requirements

- Python 3.7+
- Internet connection for tool downloads
- Sufficient disk space for tools and results

## Contributing

1. Fork the repository
2. Create your feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add some amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## Acknowledgments

- [ProjectDiscovery](https://github.com/projectdiscovery) for their amazing tools:
  - [Subfinder](https://github.com/projectdiscovery/subfinder)
  - [HTTPx](https://github.com/projectdiscovery/httpx)
  - [Nuclei](https://github.com/projectdiscovery/nuclei)
