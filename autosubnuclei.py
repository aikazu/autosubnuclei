#!/usr/bin/env python3

import os
import sys
import shutil
import requests
import zipfile
import tempfile
import subprocess
import argparse
from pathlib import Path
from tqdm import tqdm

GITHUB_API_URL = "https://api.github.com/repos/projectdiscovery/{binary}/releases/latest"
DISCORD_MESSAGE_LIMIT = 2000  # Discord's message character limit

def get_amd64_zip_url(release_info):
    """Extracts the download URL for the amd64 zip asset from the release info."""
    for asset in release_info.get("assets", []):
        asset_name = asset["name"].lower()
        if "amd64" in asset_name and asset_name.endswith(".zip"):
            return asset["browser_download_url"]
    raise ValueError(f"No amd64 zip asset found in release {release_info['tag_name']}")

def get_latest_release_url(binary):
    """Fetches the latest release info for a given binary from GitHub."""
    try:
        response = requests.get(GITHUB_API_URL.format(binary=binary))
        response.raise_for_status()
        return get_amd64_zip_url(response.json())
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

def send_notification(data, title):
    """Sends a notification using notify with proper data handling."""
    try:
        # Truncate data to Discord's limits
        if len(data) > DISCORD_MESSAGE_LIMIT:
            data = data[:DISCORD_MESSAGE_LIMIT - 100] + "\n... (truncated)"
        
        notification_data = f"### {title}\n{data}"
        config_path = create_notify_config()

        with tempfile.NamedTemporaryFile(mode='w', delete=False) as temp_file:
            temp_file.write(notification_data)
            temp_file_path = temp_file.name

        notify_command = [
            "notify", "-silent", "-data", temp_file_path, 
            "-bulk", "-config", str(config_path)
        ]
        run_command(notify_command)
        
        os.unlink(temp_file_path)  # Clean up temp file

    except Exception as err:
        print(f"Notification error: {err}")

def download_and_extract(url, binary_name, output_dir):
    """Downloads and extracts a binary with proper error handling."""
    try:
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
                for file in extracted_files:
                    if file.is_file() and file.name == binary_name:
                        file.chmod(0o755)
                        shutil.move(str(file), str(output_dir / binary_name))
                        return
                
                raise FileNotFoundError(f"Binary {binary_name} not found in archive")

    except Exception as err:
        sys.exit(f"Failed processing {binary_name}: {err}")

def download_binaries(binaries, output_dir, force=False):
    """Downloads all required binaries with optional force update."""
    for binary, url in binaries.items():
        if force or not (output_dir / binary).exists():
            print(f"Downloading {binary}...")
            download_and_extract(url, binary, output_dir)

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
    parser.add_argument("--output", type=Path, default=Path.cwd(),
                      help="Output directory for results")
    parser.add_argument("--no-notify", action="store_true",
                      help="Disable notifications")
    parser.add_argument("--force", action="store_true",
                      help="Force re-download of binaries")
    parser.add_argument("--severities", default="critical,high,medium,low,info",
                      help="Comma-separated Nuclei severity levels")
    args = parser.parse_args()

    # Prepare environment
    args.output.mkdir(parents=True, exist_ok=True)
    templates_path = Path(args.templates).expanduser()

    # Get binary URLs and download
    binaries = {
        "subfinder": get_latest_release_url("subfinder"),
        "httpx": get_latest_release_url("httpx"),
        "nuclei": get_latest_release_url("nuclei"),
        "notify": get_latest_release_url("notify")
    }
    download_binaries(binaries, args.output, args.force)

    # Build absolute paths to binaries
    bin_paths = {name: str(args.output / name) for name in binaries}

    # Subfinder execution
    sub_output = args.output / f"{args.domain}_subfinder.txt"
    print("Running subfinder...")
    run_command([bin_paths["subfinder"], "-silent", "-d", args.domain, "-o", str(sub_output)])
    validate_file(sub_output, "Subfinder")
    if not args.no_notify:
        send_notification(sub_output.read_text(), "Subfinder Results")

    # Httpx execution
    httpx_output = args.output / f"{args.domain}_httpx.txt"
    print("Running httpx...")
    run_command([bin_paths["httpx"], "-silent", "-l", str(sub_output), "-o", str(httpx_output)])
    validate_file(httpx_output, "Httpx")
    if not args.no_notify:
        send_notification(httpx_output.read_text(), "Httpx Results")

    # Nuclei execution
    nuclei_output = args.output / f"{args.domain}_nuclei.txt"
    print("Running nuclei...")
    run_command([
        bin_paths["nuclei"],
        "-l", str(httpx_output),
        "-t", str(templates_path),
        "-severity", args.severities,
        "-me", str(nuclei_output)
    ])
    validate_file(nuclei_output, "Nuclei")
    if not args.no_notify:
        send_notification(nuclei_output.read_text(), "Nuclei Results")

    print("Scan completed successfully")

if __name__ == "__main__":
    main()
