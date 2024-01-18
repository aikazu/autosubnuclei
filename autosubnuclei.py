#!/usr/bin/env python3
import subprocess
import sys
import os
import shutil
import requests
import zipfile
import tempfile

GITHUB_API_URL = "https://api.github.com/repos/projectdiscovery/{binary}/releases/latest"

def get_amd64_zip_url(release_info):
    assets = release_info.get("assets", [])
    for asset in assets:
        if "amd64" in asset["name"].lower() and asset["name"].endswith(".zip"):
            return asset["browser_download_url"]

    sys.exit(1)

def get_latest_release_url(binary):
    url = GITHUB_API_URL.format(binary=binary)
    response = requests.get(url)
    if response.status_code != 200:
        sys.exit(1)

    release_info = response.json()
    return get_amd64_zip_url(release_info)

def run_command(command, step_name):
    process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, shell=True)
    output, error = process.communicate()

    if process.returncode != 0:
        print(f"Error at step '{step_name}': {error.decode('utf-8')}")
        sys.exit(1)

    return output.decode('utf-8')

def download_and_extract(url, binary_name):
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

    # Move the binary to the script directory
    shutil.move(binary_path, os.path.dirname(os.path.realpath(__file__)))

    shutil.rmtree(temp_dir)

def main():
    if len(sys.argv) != 2:
        print("Usage: python3 script.py <domain>")
        sys.exit(1)

    domain = sys.argv[1]

    binaries = {
        "subfinder": get_latest_release_url("subfinder"),
        "httpx": get_latest_release_url("httpx"),
        "nuclei": get_latest_release_url("nuclei")
    }

    for binary, url in binaries.items():
        if shutil.which(binary) is None:
            download_and_extract(url, binary)

    # Use Subfinder to find subdomains and save them to a file
    print("Finding subdomains with Subfinder...")
    run_command(f"subfinder -silent -all -d {domain} -o {domain}_subfinder", "Subfinder")

    # Use Httpx to find live subdomains and save them to a file
    print("Finding live subdomains with Httpx...")
    run_command(f"httpx -silent -l {domain}_subfinder -o {domain}_httpx", "Httpx")

    # Use Nuclei to scan the live subdomains with a specific template
    print("Scanning live subdomains with Nuclei...")
    run_command(f"nuclei -l {domain}_httpx -t ~/nuclei-templates/ -me {domain}_nuclei", "Nuclei")

    print("Done!")

if __name__ == "__main__":
    main()
