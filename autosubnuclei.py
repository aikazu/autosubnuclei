#!/usr/bin/env python3

import os
import sys
import shutil
import requests
import zipfile
import tempfile
import subprocess
import concurrent.futures
import argparse
from pathlib import Path

GITHUB_API_URL = "https://api.github.com/repos/projectdiscovery/{binary}/releases/latest"

def get_amd64_zip_url(release_info):
    """Extracts the download URL for the amd64 zip asset from the release info."""
    for asset in release_info.get("assets", []):
        if "amd64" in asset["name"].lower() and asset["name"].endswith(".zip"):
            return asset["browser_download_url"]
    raise ValueError("No suitable asset found for amd64 architecture.")

def get_latest_release_url(binary):
    """Fetches the latest release info for a given binary from GitHub."""
    response = requests.get(GITHUB_API_URL.format(binary=binary))
    response.raise_for_status()
    return get_amd64_zip_url(response.json())

def run_command(command):
    """Runs a shell command and handles errors."""
    process = subprocess.run(command, capture_output=True, text=True, check=True)
    return process.stdout

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

def send_notification(data):
    """Sends a notification using notify."""
    config_path = create_notify_config()
    notification_data_file = Path("notification_data.txt")
    notification_data_file.write_text(data)

    notify_command = f"./notify -silent -data {notification_data_file} -bulk -config {config_path}"
    run_command(notify_command.split())

def download_and_extract(url, binary_name):
    """Downloads and extracts a binary from a given URL."""
    print(f"{binary_name} not found, downloading...")

    with tempfile.TemporaryDirectory() as temp_dir:
        zip_file_path = Path(temp_dir) / f"{binary_name}.zip"
        
        response = requests.get(url, stream=True)
        response.raise_for_status()
        
        with zip_file_path.open("wb") as zip_file:
            for chunk in response.iter_content(chunk_size=8192):
                zip_file.write(chunk)

        with zipfile.ZipFile(zip_file_path, 'r') as zip_ref:
            zip_ref.extractall(path=temp_dir)

        binary_path = Path(temp_dir) / binary_name
        binary_path.chmod(0o755)
        shutil.move(str(binary_path), f"./{binary_name}")

def download_binaries(binaries):
    """Downloads all required binaries concurrently."""
    with concurrent.futures.ThreadPoolExecutor() as executor:
        futures = []
        for binary, url in binaries.items():
            if not Path(f"./{binary}").exists():
                futures.append(executor.submit(download_and_extract, url, binary))
        concurrent.futures.wait(futures)

def main():
    parser = argparse.ArgumentParser(description="Security scanner for subdomains")
    parser.add_argument("domain", help="Target domain to scan")
    parser.add_argument("--templates", default="~/nuclei-templates/", help="Path to nuclei templates")
    args = parser.parse_args()

    domain = args.domain
    templates_path = Path(args.templates).expanduser()

    binaries = {
        "subfinder": get_latest_release_url("subfinder"),
        "httpx": get_latest_release_url("httpx"),
        "nuclei": get_latest_release_url("nuclei"),
        "notify": get_latest_release_url("notify")
    }

    download_binaries(binaries)

    # Use Subfinder to find subdomains and save them to a file
    subfinder_output = run_command(f"./subfinder -silent -all -d {domain} -o {domain}_subfinder".split())
    send_notification(subfinder_output)

    # Use Httpx to find live subdomains and save them to a file
    httpx_output = run_command(f"./httpx -silent -l {domain}_subfinder -o {domain}_httpx".split())
    send_notification(httpx_output)

    # Use Nuclei to scan the live subdomains with a specific template
    nuclei_output = run_command(f"./nuclei -l {domain}_httpx -t {templates_path} -severity critical,high,medium,low,info -v -me {domain}_nuclei".split())
    send_notification(nuclei_output)

    print("Scan completed successfully!")

if __name__ == "__main__":
    main()
