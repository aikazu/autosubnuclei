Here’s a comprehensive `README.md` file for your GitHub repository. This file provides an overview of the project, instructions for setup and usage, and details about contributing and licensing.

---

# AutoSubNuclei: Automated Security Scanning Pipeline

AutoSubNuclei is a Python-based automation tool for performing security scans using popular tools like **Subfinder**, **Httpx**, and **Nuclei**. It automates the process of subdomain enumeration, HTTP probing, and vulnerability scanning, and sends notifications via Discord for easy monitoring.

---

## Features

- **Subdomain Enumeration**: Uses [Subfinder](https://github.com/projectdiscovery/subfinder) to discover subdomains.
- **HTTP Probing**: Uses [Httpx](https://github.com/projectdiscovery/httpx) to probe live HTTP servers.
- **Vulnerability Scanning**: Uses [Nuclei](https://github.com/projectdiscovery/nuclei) to scan for vulnerabilities.
- **Discord Notifications**: Sends scan results to a Discord channel using [Notify](https://github.com/projectdiscovery/notify).
- **Cross-Platform**: Works on both Linux and Windows.
- **Automatic Binary Management**: Downloads and updates required binaries automatically.

---

## Prerequisites

- Python 3.7 or higher
- Discord webhook URL (for notifications)
- Nuclei templates (optional, but recommended)

---

## Installation

1. Clone the repository:
   ```bash
   git clone https://github.com/your-username/autosubnuclei.git
   cd autosubnuclei
   ```

2. Set up a virtual environment (optional but recommended):
   ```bash
   python -m venv myenv
   source myenv/bin/activate  # On Windows: myenv\Scripts\activate
   ```

3. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

4. Set up your Discord webhook:
   - Create a Discord webhook in your server.
   - Set the `DISCORD_WEBHOOK_URL` environment variable:
     ```bash
     export DISCORD_WEBHOOK_URL="https://discord.com/api/webhooks/your-webhook-url"
     ```
     On Windows:
     ```cmd
     set DISCORD_WEBHOOK_URL="https://discord.com/api/webhooks/your-webhook-url"
     ```

---

## Usage

Run the script with the target domain as an argument:
```bash
python autosubnuclei.py example.com
```

### Command-Line Options

| Option          | Description                                                                 |
|-----------------|-----------------------------------------------------------------------------|
| `--templates`   | Path to Nuclei templates (default: `~/nuclei-templates/`).                  |
| `--output`      | Output directory for scan results (default: `output/`).                     |
| `--no-notify`   | Disable Discord notifications.                                              |
| `--force`       | Force re-download of binaries.                                              |
| `--severities`  | Comma-separated list of Nuclei severities to scan (default: `critical,high,medium,low`). |

### Example

```bash
python autosubnuclei.py example.com --templates ~/custom-nuclei-templates --severities critical,high
```

---

## Output

The script generates the following files in the output directory (`output/<domain>/`):

- `subfinder.txt`: List of discovered subdomains.
- `httpx.txt`: List of live HTTP servers.
- `nuclei/`: Directory containing Nuclei scan results, including `index.md`.

---

## Notifications

Scan results are sent to Discord in the following format:

### Subfinder Results
```
## Subfinder Results
• example.com
• sub.example.com
```

### Httpx Results
```
## Httpx Results
• http://example.com
• http://sub.example.com
```

### Nuclei Results
```
## Nuclei Results
• MEDIUM: laravel-debug-enabled (sso.example.com)
• HIGH: SQL Injection (api.example.com)
```

---

## Contributing

Contributions are welcome! Here’s how you can help:

1. Fork the repository.
2. Create a new branch for your feature or bugfix:
   ```bash
   git checkout -b feature-name
   ```
3. Commit your changes:
   ```bash
   git commit -m "Add new feature"
   ```
4. Push to the branch:
   ```bash
   git push origin feature-name
   ```
5. Open a pull request.

---

## License

This project is licensed under the **MIT License**. See the [LICENSE](LICENSE) file for details.

---

## Acknowledgments

- [ProjectDiscovery](https://github.com/projectdiscovery) for creating Subfinder, Httpx, Nuclei, and Notify.
- The open-source community for their contributions and support.

---

## Support

If you encounter any issues or have questions, feel free to open an issue on GitHub or reach out to the maintainers.

---

Enjoy using AutoSubNuclei! 🚀
