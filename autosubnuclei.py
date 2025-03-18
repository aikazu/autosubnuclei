#!/usr/bin/env python3

import os
import sys
import shutil
import requests
import zipfile
import tempfile
import subprocess
import argparse
import platform
from pathlib import Path
from tqdm import tqdm

GITHUB_API_URL = "https://api.github.com/repos/projectdiscovery/{binary}/releases/latest"
DISCORD_MESSAGE_LIMIT = 2000  # Discord's message character limit

# Get script directory for binary storage
SCRIPT_DIR = Path(__file__).parent.resolve()
BIN_DIR = SCRIPT_DIR / "bin"

def get_os():
    """Returns the operating system name."""
    return platform.system().lower()

def get_architecture():
    """Returns the system architecture."""
    machine = platform.machine().lower()
    if machine in ("x86_64", "amd64"):
        return "amd64"
    elif machine in ("arm64", "aarch64"):
        return "arm64"
    else:
        sys.exit(f"Unsupported architecture: {machine}")

def get_zip_url(release_info):
    """Extracts the download URL for the appropriate zip asset from the release info."""
    os_name = get_os()
    arch = get_architecture()
    
    for asset in release_info.get("assets", []):
        asset_name = asset["name"].lower()
        if os_name in asset_name and arch in asset_name and asset_name.endswith(".zip"):
            return asset["browser_download_url"]
    raise ValueError(f"No {os_name} {arch} zip asset found in release {release_info['tag_name']}")

def get_latest_release_url(binary):
    """Fetches the latest release info for a given binary from GitHub."""
    try:
        response = requests.get(GITHUB_API_URL.format(binary=binary))
        response.raise_for_status()
        return get_zip_url(response.json())
    except requests.exceptions.RequestException as err:
        sys.exit(f"Error fetching release info for {binary}: {err}")

def run_command(command, timeout=1800):
    """Runs a shell command and handles errors."""
    try:
        process = subprocess.run(
            command,
            capture_output=True,
            text=True,
            check=True,
            timeout=timeout
        )
        return process.stdout
    except subprocess.CalledProcessError as err:
        sys.exit(f"Command failed: {err}\nError output: {err.stderr}")
    except subprocess.TimeoutExpired:
        sys.exit(f"Command timed out: {' '.join(command)}")

def create_notify_config():
    """Creates a notify configuration file with environment variable support."""
    config_dir = Path.home() / ".config" / "notify"
    config_path = config_dir / "provider-config.yaml"

    if config_path.exists():
        return config_path

    config_dir.mkdir(parents=True, exist_ok=True)
    
    # Check environment variables first
    username = os.environ.get("DISCORD_USERNAME")
    webhook_url = os.environ.get("DISCORD_WEBHOOK_URL")
    
    if not (username and webhook_url):
        if not sys.stdin.isatty():
            sys.exit("Discord credentials not found in env and not running interactively")
        username = input("Enter Discord username: ")
        webhook_url = input("Enter Discord webhook URL: ")

    config_content = f"""discord:
  - id: "crawl"
    discord_channel: "notify"
    discord_username: "{username}"
    discord_format: "{{{{data}}}}"
    discord_webhook_url: "{webhook_url}"
"""
    config_path.write_text(config_content)
    config_path.chmod(0o600)  # Restrict permissions
    return config_path

def send_notification(data, title, notify_path, data_type='text'):
    """Sends notifications with format handling per data type."""
    try:
        if data_type == 'markdown':
            print("Debug: Nuclei output data:\n", data)  # Debugging: Print the raw data
            formatted_lines = []
            in_table = False
            for line in data.split('\n'):
                # Detect table start
                if '|' in line and '---' in line:
                    in_table = True
                    continue
                if not in_table or not line.strip():
                    continue

                parts = [p.strip() for p in line.split('|') if p.strip()]
                # Expected columns: [Hostname/IP, Finding, Severity]
                if len(parts) >= 3:  # Ensure there are at least 3 columns
                    hostname_ip = parts[0]
                    finding = parts[1]
                    severity = parts[2]
                    # Extract the actual finding text from the markdown link (if present)
                    if '](' in finding:  # Check if it's a markdown link
                        finding = finding.split('](')[0].replace('[', '').strip()
                    formatted_lines.append(f"• {severity.upper()}: {finding} ({hostname_ip})")
                else:
                    print(f"Debug: Skipping line (unexpected format): {line}")  # Debugging: Log skipped lines
            
            formatted_data = "\n".join(formatted_lines) if formatted_lines else "No significant findings"
        else:
            formatted_data = data.strip()

        max_length = DISCORD_MESSAGE_LIMIT - len(title) - 100
        if len(formatted_data) > max_length:
            formatted_data = formatted_data[:max_length] + "\n... (truncated)"
        
        notification_content = f"## {title}\n{formatted_data}"

        config_path = create_notify_config()

        with tempfile.NamedTemporaryFile(mode='w', delete=False) as temp_file:
            temp_file.write(notification_content)
            temp_file_path = temp_file.name

        notify_command = [
            notify_path, "-silent", "-data", temp_file_path, 
            "-bulk", "-config", str(config_path)
        ]
        run_command(notify_command)
        
        os.unlink(temp_file_path)

    except Exception as err:
        print(f"Notification error: {err}")

def download_and_extract(url, binary_name):
    """Downloads and extracts a binary to the script's bin directory."""
    try:
        BIN_DIR.mkdir(parents=True, exist_ok=True)
        
        with requests.get(url, stream=True) as response:
            response.raise_for_status()
            total_size = int(response.headers.get('content-length', 0))
            
            with tempfile.TemporaryDirectory() as temp_dir:
                zip_path = Path(temp_dir) / f"{binary_name}.zip"
                with open(zip_path, 'wb') as f, tqdm(
                    desc=binary_name,
                    total=total_size,
                    unit='iB',
                    unit_scale=True
                ) as pbar:
                    for chunk in response.iter_content(chunk_size=8192):
                        f.write(chunk)
                        pbar.update(len(chunk))

                with zipfile.ZipFile(zip_path, 'r') as zip_ref:
                    zip_ref.extractall(temp_dir)
                
                # Search for binary in extracted files
                extracted_files = list(Path(temp_dir).rglob('*'))
                binary_found = False
                for file in extracted_files:
                    # Handle Windows binaries (e.g., subfinder.exe)
                    if file.is_file() and (file.name == binary_name or file.name == f"{binary_name}.exe"):
                        # Ensure the binary is executable
                        file.chmod(0o755)
                        # Move the binary to the bin directory
                        shutil.move(str(file), str(BIN_DIR / file.name))
                        binary_found = True
                        break
                
                if not binary_found:
                    raise FileNotFoundError(f"Binary {binary_name} (or {binary_name}.exe) not found in archive")

    except Exception as err:
        sys.exit(f"Failed processing {binary_name}: {err}")

def download_binaries(binaries, force=False):
    """Downloads all required binaries with optional force update."""
    for binary, url in binaries.items():
        bin_path = BIN_DIR / binary
        if force or not bin_path.exists():
            print(f"Downloading {binary}...")
            download_and_extract(url, binary)

def validate_file(file_path, step_name):
    """Validates if output file exists and has content."""
    if not file_path.exists():
        sys.exit(f"{step_name} failed to create output file")
    if file_path.stat().st_size == 0:
        sys.exit(f"{step_name} produced empty results")

def main():
    parser = argparse.ArgumentParser(description="Automated Security Scanning Pipeline")
    parser.add_argument("domain", help="Target domain to scan")
    parser.add_argument("--templates", default="~/nuclei-templates/",
                      help="Path to nuclei templates")
    parser.add_argument("--output", type=Path, default=Path("output"),
                      help="Output directory for results")
    parser.add_argument("--no-notify", action="store_true",
                      help="Disable notifications")
    parser.add_argument("--force", action="store_true",
                      help="Force re-download of binaries")
    parser.add_argument("--severities", default="critical,high,medium,low",
                      help="Comma-separated Nuclei severity levels")
    args = parser.parse_args()

    # Prepare output directories
    domain_output_dir = args.output / args.domain
    domain_output_dir.mkdir(parents=True, exist_ok=True)
    templates_path = Path(args.templates).expanduser()

    # Get binary URLs and download
    binaries = {
        "subfinder": get_latest_release_url("subfinder"),
        "httpx": get_latest_release_url("httpx"),
        "nuclei": get_latest_release_url("nuclei"),
        "notify": get_latest_release_url("notify")
    }
    download_binaries(binaries, args.force)

    # Build paths to binaries
    bin_paths = {name: str(BIN_DIR / name) for name in binaries}

    # Subfinder execution
    sub_output = domain_output_dir / "subfinder.txt"
    print("Running subfinder...")
    run_command([bin_paths["subfinder"], "-silent", "-d", args.domain, "-o", str(sub_output)])
    validate_file(sub_output, "Subfinder")
    if not args.no_notify:
        send_notification(sub_output.read_text(), "Subfinder Results", bin_paths["notify"])

    # Httpx execution
    httpx_output = domain_output_dir / "httpx.txt"
    print("Running httpx...")
    run_command([bin_paths["httpx"], "-silent", "-l", str(sub_output), "-o", str(httpx_output)])
    validate_file(httpx_output, "Httpx")
    if not args.no_notify:
        send_notification(httpx_output.read_text(), "Httpx Results", bin_paths["notify"])
    # Nuclei execution with web vulnerability focus
    nuclei_output_dir = domain_output_dir / "nuclei"
    nuclei_output_dir.mkdir(parents=True, exist_ok=True)

    print("Running nuclei...")
    run_command([
        bin_paths["nuclei"],
        "-l", str(httpx_output),
        "-t", str(templates_path),
        "-severity", args.severities,
        "-tags", "dast,cve,misconfig,oast,xss",  # Web vulnerability tags
        "-me", str(nuclei_output_dir)
    ])

    # Look for index.md specifically
    index_md = nuclei_output_dir / "index.md"
    if not index_md.exists():
        sys.exit("Nuclei index.md not found in output directory")

    if not args.no_notify:
        send_notification(index_md.read_text(), "Nuclei Results", bin_paths["notify"], data_type='markdown')

    print(f"Scan completed successfully. Results saved to: {domain_output_dir}")

if __name__ == "__main__":
    main()
