#!/usr/bin/env python3

import os
import sys
import shutil
import requests
import zipfile
import tempfile
import subprocess

GITHUB_API_URL = "https://api.github.com/repos/projectdiscovery/{binary}/releases/latest"

def get_amd64_zip_url(release_info):
    """Extracts the download URL for the amd64 zip asset from the release info."""
    for asset in release_info.get("assets", []):
        if "amd64" in asset["name"].lower() and asset["name"].endswith(".zip"):
            return asset["browser_download_url"]
    sys.exit("No suitable asset found for amd64 architecture.")

def get_latest_release_url(binary):
    """Fetches the latest release info for a given binary from GitHub."""
    response = requests.get(GITHUB_API_URL.format(binary=binary))
    if response.status_code != 200:
        sys.exit(f"Failed to fetch release info for {binary}.")
    return get_amd64_zip_url(response.json())

def run_command(command, step_name):
    """Runs a shell command and handles errors."""
    process = subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, shell=True, text=True)
    if process.returncode != 0:
        sys.exit(f"Error at step '{step_name}': {process.stderr}")
    return process.stdout

def create_notify_config():
    """Creates a notify configuration file."""
    config_dir = os.path.expanduser("~/.config/notify")
    config_path = os.path.join(config_dir, "provider-config.yaml")

    if not os.path.exists(config_path):
        os.makedirs(config_dir, exist_ok=True)
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

        with open(config_path, "w") as config_file:
            config_file.write(config_content)

    return config_path

def send_notification(data):
    """Sends a notification using notify."""
    config_path = create_notify_config()
    notification_data_file = "notification_data.txt"

    with open(notification_data_file, "w") as f:
        f.write(data)

    notify_command = f"./notify -silent -data {notification_data_file} -bulk -config {config_path}"
    run_command(notify_command, "Notify")

def download_and_extract(url, binary_name):
    """Downloads and extracts a binary from a given URL."""
    print(f"{binary_name} not found, downloading...")

    response = requests.get(url, stream=True)
    temp_dir = tempfile.mkdtemp()
    zip_file_path = os.path.join(temp_dir, binary_name + ".zip")

    with open(zip_file_path, "wb") as zip_file:
        for chunk in response.iter_content(chunk_size=128):
            zip_file.write(chunk)

    with zipfile.ZipFile(zip_file_path, 'r') as zip_ref:
        zip_ref.extractall(path=temp_dir)

    binary_path = os.path.join(temp_dir, binary_name)
    os.chmod(binary_path, 0o755)
    shutil.move(binary_path, f"./{binary_name}")
    shutil.rmtree(temp_dir)

def main():
    if len(sys.argv) != 2:
        sys.exit("Usage: python3 script.py <domain>")

    domain = sys.argv[1]
    binaries = {
        "subfinder": get_latest_release_url("subfinder"),
        "httpx": get_latest_release_url("httpx"),
        "nuclei": get_latest_release_url("nuclei"),
        "notify": get_latest_release_url("notify")
    }

    for binary, url in binaries.items():
        if not os.path.exists(f"./{binary}"):
            download_and_extract(url, binary)

    # Use Subfinder to find subdomains and save them to a file
    subfinder_output = run_command(f"./subfinder -silent -all -d {domain} -o {domain}_subfinder", "Subfinder")
    send_notification(subfinder_output)

    # Use Httpx to find live subdomains and save them to a file
    httpx_output = run_command(f"./httpx -silent -l {domain}_subfinder -o {domain}_httpx", "Httpx")
    send_notification(httpx_output)

    # Use Nuclei to scan the live subdomains with a specific template
    nuclei_output = run_command(f"./nuclei -l {domain}_httpx -t ~/nuclei-templates/ -severity critical,high,medium,low,info -v -me {domain}_nuclei", "Nuclei")
    send_notification(nuclei_output)

    print("Done!")

if __name__ == "__main__":
    main()
