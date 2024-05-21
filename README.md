# autosubnuclei
# Subdomain Discovery and Vulnerability Scanning Script

This script automates the process of discovering subdomains and scanning them for vulnerabilities using `subfinder`, `httpx`, and `nuclei`. It dynamically checks for and installs these tools if they are not already present on the system.

## Prerequisites

- Python 3.x
- `requests` module

## Usage
```sh
python3 autosubnuclei.py <domain>
```

## How It Works
1. Checks for Necessary Binaries:
- subfinder
- httpx
- nuclei
If any of these binaries are not found, they are downloaded and installed automatically from their latest releases on GitHub.

2. Subdomain Discovery:
- Uses subfinder to find subdomains of the given domain and saves the results to <domain>_subfinder.

3. Finding Live Subdomains:
- Uses httpx to check which subdomains are live and saves the results to <domain>_httpx.

4. Vulnerability Scanning:
- Uses nuclei to scan the live subdomains for vulnerabilities using templates specified in ~/nuclei-templates/, and saves the results to <domain>_nuclei.
