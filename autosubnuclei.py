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

def get_amd64_zip_url(release_info):
    """Extracts the download URL for the amd64 zip asset from the release info."""
    for asset in release_info.get("assets", []):
        if "amd64" in asset["name"].lower() and asset["name"].endswith(".zip"):
            return asset["browser_download_url"]
    raise ValueError("No suitable asset found for amd64 architecture.")

def get_latest_release_url(binary):
    """Fetches the latest release info for a given binary from GitHub."""
    try:
        response = requests.get(GITHUB_API_URL.format(binary=binary))
        response.raise_for_status()
    except requests.exceptions.RequestException as err:
        print(f"Error fetching release info for {binary}: {err}")
        return None
    return get_amd64_zip_url(response.json())

def run_command(command):
    """Runs a shell command and handles errors."""
    try:
        process = subprocess.run(command, capture_output=True, text=True, check=True)
        return process.stdout
    except subprocess.CalledProcessError as err:
        print(f"Error running command: {err}")
        print(f"Output: {err.stderr}")
        sys.exit(1)

def create_notify_config():
    """Creates a notify configuration file."""
    config_dir = Path.home() / ".config" / "notify"
    config_path = config_dir / "provider-config.yaml"

    if not config_path.exists():
        config_dir.mkdir(parents=True, exist_ok=True)
        username = input("Enter the Discord username: ")
        webhook_url = input("Enter the Discord webhook URL: ")

        config_content = f"""
discord:
  - id: "crawl"
    discord_channel: "notify"
    discord_username: "{username}"
    discord_format: "{{{{data}}}}"
    discord_webhook_url: "{webhook_url}"
"""
        config_path.write_text(config_content)
    return config_path


def send_notification(data, title):  # Add title parameter
    """Sends a notification using notify with a title."""
    try:
        config_path = create_notify_config()
        notification_data_file = Path("notification_data.txt")

        # Add title to the notification data
        notification_data = f"### {title}\n{data}"  
        notification_data_file.write_text(notification_data)

        notify_command = [
            "./notify", "-silent", "-data", str(notification_data_file), 
            "-bulk", "-config", str(config_path)
        ]
        run_command(notify_command)

    except Exception as err:
        print(f"Error sending notification: {err}")

def download_and_extract(url, binary_name, output_dir):
    """Downloads and extracts a binary from a given URL."""
    print(f"Downloading {binary_name}...")
    try:
        response = requests.get(url, stream=True)
        response.raise_for_status()
        total_size = int(response.headers.get('content-length', 0))
        with tempfile.TemporaryDirectory() as temp_dir, tqdm(
            desc=binary_name, total=total_size, unit='iB', unit_scale=True
        ) as pbar:
            zip_file_path = Path(temp_dir) / f"{binary_name}.zip"
            with zip_file_path.open("wb") as zip_file:
                for chunk in response.iter_content(chunk_size=8192):
                    zip_file.write(chunk)
                    pbar.update(len(chunk))
            with zipfile.ZipFile(zip_file_path, 'r') as zip_ref:
                zip_ref.extractall(path=temp_dir)
            binary_path = Path(temp_dir) / binary_name
            binary_path.chmod(0o755)
            shutil.move(str(binary_path), str(output_dir / binary_name))
    except requests.exceptions.RequestException as err:
        print(f"Error downloading {binary_name}: {err}")
    except zipfile.BadZipFile as err:
        print(f"Error extracting {binary_name}: {err}")
    except Exception as err:
        print(f"Error processing {binary_name}: {err}")

def download_binaries(binaries, output_dir):
    """Downloads all required binaries."""
    for binary, url in binaries.items():
        if not (output_dir / binary).exists():
            download_and_extract(url, binary, output_dir)

def main():
    parser = argparse.ArgumentParser(description="Security scanner for subdomains")
    parser.add_argument("domain", help="Target domain to scan")
    parser.add_argument("--templates", default="~/nuclei-templates/", help="Path to nuclei templates")
    parser.add_argument("--output", default=".", help="Output directory for results")
    parser.add_argument("--no-notify", action="store_true", help="Disable notifications")
    args = parser.parse_args()

    domain = args.domain
    templates_path = Path(args.templates).expanduser()
    output_dir = Path(args.output)
    output_dir.mkdir(parents=True, exist_ok=True)

    binaries = {
        "subfinder": get_latest_release_url("subfinder"),
        "httpx": get_latest_release_url("httpx"),
        "nuclei": get_latest_release_url("nuclei"),
        "notify": get_latest_release_url("notify")
    }

    download_binaries(binaries, output_dir)

    # Use Subfinder to find subdomains
    subfinder_output_file = output_dir / f"{domain}_subfinder.txt"
    run_command(["./subfinder", "-silent", "-all", "-d", domain, "-o", str(subfinder_output_file)])
    if not args.no_notify:
        send_notification(subfinder_output_file.read_text(), "Subfinder")  # Add title

    # Use Httpx to find live subdomains
    httpx_output_file = output_dir / f"{domain}_httpx.txt"
    run_command(["./httpx", "-silent", "-l", str(subfinder_output_file), "-o", str(httpx_output_file)])
    if not args.no_notify:
        send_notification(httpx_output_file.read_text(), "Httpx")  # Add title

    # Use Nuclei to scan the live subdomains
    nuclei_output_file = output_dir / f"{domain}_nuclei.txt"
    run_command([
        "./nuclei", "-l", str(httpx_output_file), "-t", str(templates_path), 
        "-severity", "critical,high,medium,low,info", "-v", "-me", str(nuclei_output_file)
    ])
    if not args.no_notify:
        send_notification(nuclei_output_file.read_text(), "Nuclei")  # Add title

    print("Scan completed successfully!")

if __name__ == "__main__":
    main()