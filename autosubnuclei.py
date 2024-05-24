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

def send_notification(data, title="Notification"):
    """Sends a notification using notify."""
    config_path = "notify.yaml"
    with open("notification_data.txt", "w") as f:
        f.write(data)
    
    run_command(f"notify -silent -data notification_data.txt -bulk -config {config_path} -title \"{title}\"", "Notify")

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

    # Move the binary to /usr/bin/
    sudo_move_command = f"sudo mv {binary_path} /usr/bin/{binary_name}"
    run_command(sudo_move_command, f"Move {binary_name} to /usr/bin/")

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
        if shutil.which(binary) is None:
            if os.geteuid() != 0:
                print(f"The binary '{binary}' is not available. Please run the script with sudo to download and install it.")
                sys.exit(1)
            download_and_extract(url, binary)

    # Use Subfinder to find subdomains and save them to a file
    print(f"Finding subdomains with Subfinder for {domain}...")
    subfinder_output = run_command(f"subfinder -silent -all -d {domain} -o {domain}_subfinder", "Subfinder")
    send_notification(subfinder_output, f"Subfinder Results for {domain}")

    # Use Httpx to find live subdomains and save them to a file
    print(f"Finding live subdomains with Httpx for {domain}...")
    httpx_output = run_command(f"httpx -silent -l {domain}_subfinder -o {domain}_httpx", "Httpx")
    send_notification(httpx_output, f"Httpx Results for {domain}")

    # Use Nuclei to scan the live subdomains with a specific template
    print(f"Scanning live subdomains with Nuclei for {domain}...")
    nuclei_output = run_command(f"nuclei -l {domain}_httpx -t ~/nuclei-templates/ -severity critical,high,medium,low,info -v -me {domain}_nuclei", "Nuclei")
    send_notification(nuclei_output, f"Nuclei Results for {domain}")

    print("Done!")

if __name__ == "__main__":
    main()
