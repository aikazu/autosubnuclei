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
    assets = release_info.get("assets", [])
    for asset in assets:
        if "amd64" in asset["name"].lower() and asset["name"].endswith(".zip"):
            return asset["browser_download_url"]
    print("No suitable asset found for amd64 architecture.")
    sys.exit(1)

def get_latest_release_url(binary):
    """Fetches the latest release info for a given binary from GitHub."""
    url = GITHUB_API_URL.format(binary=binary)
    response = requests.get(url)
    if response.status_code != 200:
        print(f"Failed to fetch release info for {binary}.")
        sys.exit(1)

    release_info = response.json()
    return get_amd64_zip_url(release_info)

def run_command(command, step_name):
    """Runs a shell command and handles errors."""
    process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, shell=True)
    output, error = process.communicate()

    if process.returncode != 0:
        print(f"Error at step '{step_name}': {error.decode('utf-8')}")
        sys.exit(1)

    return output.decode('utf-8')

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

    # Write notification data to file
    try:
        with open(notification_data_file, "w") as f:
            f.write(data)
    except Exception as e:
        print(f"Failed to write notification data: {str(e)}")
        sys.exit(1)

    # Confirm that the notification data file exists
    if not os.path.exists(notification_data_file):
        print(f"Error: {notification_data_file} file not found after writing.")
        sys.exit(1)

    # Construct and run the notify command
    notify_command = f"./notify -silent -data {notification_data_file} -bulk -config {config_path}"
    
    try:
        output = run_command(notify_command, "Notify")
    except Exception as e:
        print(f"Failed to send notification: {str(e)}")
        sys.exit(1)

def download_and_extract(url, binary_name):
    """Downloads and extracts a binary from a given URL."""
    print(f"{binary_name} not found, downloading...")

    response = requests.get(url, stream=True)
    temp_dir = tempfile.mkdtemp()
    zip_file_path = os.path.join(temp_dir, binary_name + ".zip")

    with open(zip_file_path, "wb") as zip_file:
        for chunk in response.iter_content(chunk_size=128):
            zip_file.write(chunk)

    try:
        with zipfile.ZipFile(zip_file_path, 'r') as zip_ref:
            zip_ref.extractall(path=temp_dir)
    except zipfile.BadZipFile:
        print(f"Error: {binary_name} download failed. The file is not a valid zip file.")
        shutil.rmtree(temp_dir)
        sys.exit(1)

    binary_path = os.path.join(temp_dir, binary_name)

    # Make the binary executable
    os.chmod(binary_path, 0o755)

    # Move the binary to the current directory
    shutil.move(binary_path, f"./{binary_name}")

    shutil.rmtree(temp_dir)

def main():
    if len(sys.argv) != 2:
        print("Usage: python3 script.py <domain>")
        sys.exit(1)

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
    print(f"Finding subdomains with Subfinder for {domain}...")
    subfinder_output = run_command(f"./subfinder -silent -all -d {domain} -o {domain}_subfinder", "Subfinder")
    send_notification(subfinder_output)

    # Use Httpx to find live subdomains and save them to a file
    print(f"Finding live subdomains with Httpx for {domain}...")
    httpx_output = run_command(f"./httpx -silent -l {domain}_subfinder -o {domain}_httpx", "Httpx")
    send_notification(httpx_output)

    # Use Nuclei to scan the live subdomains with a specific template
    print(f"Scanning live subdomains with Nuclei for {domain}...")
    nuclei_output = run_command(f"./nuclei -l {domain}_httpx -t ~/nuclei-templates/ -severity critical,high,medium,low,info -v -me {domain}_nuclei", "Nuclei")
    send_notification(nuclei_output)

    print("Done!")

if __name__ == "__main__":
    main()
