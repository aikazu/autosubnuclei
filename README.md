# Automate Enumeration

This script is an automated security scanner that performs subdomain enumeration, live host detection, and vulnerability scanning on a given domain. It utilizes several tools from the ProjectDiscovery suite to provide a comprehensive security assessment.

## Features

- Subdomain enumeration using Subfinder
- Live host detection using httpx
- Vulnerability scanning using Nuclei
- Automatic downloading and updating of required tools
- Notification system using Discord webhooks (optional)
- **Improved error handling and progress indication**
- **Flexible output directory**
- **Configuration file for storing Discord webhook settings**

## Prerequisites

- Python 3.6 or higher
- Internet connection for downloading tools and scanning
- `requests` and `tqdm` Python packages: `pip install requests tqdm`

## Installation

1. Clone this repository or download the script file.
2. Ensure you have Python 3.6+ installed on your system.
3. Install the required Python packages:

```bash
pip install requests tqdm
```

## Usage

Run the script with the following command:

```bash
python3 autosubnuclei.py <domain>
```

Replace `<domain>` with the target domain you want to scan.

### Optional Arguments

- `--templates`: Specify the path to your Nuclei templates. Default is "~/nuclei-templates/".
- `--output`: Specify the output directory for results. Default is the current directory.
- `--no-notify`: Disable Discord notifications.

Example:

```bash
python3 autosubnuclei.py example.com --templates /path/to/nuclei-templates --output results --no-notify
```

## Configuration

On the first run, the script will create a configuration file (`~/.config/scan_notifier/config.ini`) and prompt you to enter your Discord username and webhook URL. This information will be stored for future use.

## How It Works

1. The script checks for and downloads the latest versions of required tools (subfinder, httpx, nuclei, and notify) to the specified output directory.
2. It uses Subfinder to enumerate subdomains of the target domain.
3. httpx is then used to identify live hosts among the discovered subdomains.
4. Nuclei scans the live hosts for potential vulnerabilities using specified templates.
5. Results from each step can optionally be sent as notifications via Discord using the notify tool.

## Output

The script generates the following output files in the specified output directory:

- `<domain>_subfinder.txt`: List of discovered subdomains
- `<domain>_httpx.txt`: List of live hosts
- `<domain>_nuclei.txt`: Detailed vulnerability scan results

## Security Considerations

- This tool should only be used on domains you have permission to scan.
- Be aware of the potential impact of scanning activities on target systems.
- Review and understand the Nuclei templates you're using to avoid unintended consequences.

## Troubleshooting

If you encounter any issues:

1. Ensure you have the latest version of the script and required Python packages.
2. Check your internet connection.
3. Verify that you have the necessary permissions to write to the script's directory and the config directory.
4. If issues persist, check the error messages for more details on the problem.

## Contributing

Contributions to improve the script are welcome. Please feel free to submit pull requests or open issues for bugs and feature requests.

## Disclaimer

This tool is for educational and ethical testing purposes only. The authors are not responsible for any misuse or damage caused by this program. Always ensure you have explicit permission to scan the target domain.

**Changes Made:**

* Added information about the `tqdm` package.
* Included details about the new optional arguments (`--output` and `--no-notify`).
* Explained the configuration file and its location.
* Updated the output file names to include the `.txt` extension.
* Added a note about improved error handling and progress indication.
* Minor formatting and wording improvements.