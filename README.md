# Automated Subdomain Enumeration and Vulnerability Scanning

This script automates the process of subdomain enumeration and vulnerability scanning using `subfinder`, `httpx`, `nuclei`, and `notify`. It fetches the latest binaries from GitHub, executes the necessary commands, and sends notifications via Discord.

## Features

- **Automatic Binary Download**: Fetches the latest versions of required binaries from GitHub.
- **Subdomain Enumeration**: Uses `subfinder` to find subdomains.
- **Live Subdomain Detection**: Uses `httpx` to detect live subdomains.
- **Vulnerability Scanning**: Uses `nuclei` to scan live subdomains for vulnerabilities.
- **Notification**: Sends results to a Discord channel using `notify`.

## Requirements

- Python 3.x
- `requests` library: Install with `pip install requests`
- Discord webhook URL

## Installation

1. Clone the repository:
    ```sh
    git clone https://github.com/yourusername/repo-name.git
    cd repo-name
    ```

2. Install required Python libraries:
    ```sh
    pip install requests
    ```

3. Make the script executable:
    ```sh
    chmod +x script.py
    ```

## Usage

Run the script with the following command:
```sh
./script.py <domain>
```


Example:

sh

Copy code

`./script.py example.com`

The script will:

1. Download and extract the latest binaries for `subfinder`, `httpx`, `nuclei`, and `notify` if they are not already present.
2. Use `subfinder` to enumerate subdomains and save the output to a file.
3. Use `httpx` to find live subdomains and save the output to a file.
4. Use `nuclei` to scan the live subdomains for vulnerabilities.
5. Send the results to a configured Discord channel using `notify`.

## Configuration

During the first run, the script will prompt for Discord configuration details:

- Discord username
- Discord webhook URL

These details will be saved in `~/.config/notify/provider-config.yaml`.

## File Structure

Copy code

`. ├── script.py └── README.md`

## License

This project is licensed under the MIT License. See the LICENSE file for details.

## Contributing

Contributions are welcome! Please fork the repository and create a pull request with your changes.

## Acknowledgements

- [subfinder](https://github.com/projectdiscovery/subfinder)
- [httpx](https://github.com/projectdiscovery/httpx)
- [nuclei](https://github.com/projectdiscovery/nuclei)
- [notify](https://github.com/projectdiscovery/notify)