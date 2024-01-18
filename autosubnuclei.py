#!/usr/bin/env python3
import subprocess
import sys
import os
import shutil
import urllib.request
import zipfile
import tempfile

def run_command(command):
    process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, shell=True)
    output, error = process.communicate()

    if process.returncode != 0:
        print(f"Error: {error.decode('utf-8')}")
        sys.exit(1)

    return output.decode('utf-8')

def download_and_extract(url, binary_name):
    print(f"{binary_name} not found, downloading...")
    file_name = url.split("/")[-1]
    urllib.request.urlretrieve(url, file_name)

    print(f"Extracting {binary_name}...")
    temp_dir = tempfile.mkdtemp()
    with zipfile.ZipFile(file_name, 'r') as zip_ref:
        members = [member for member in zip_ref.namelist() if member.endswith(binary_name)]
        if not members:
            print(f"Error: {binary_name} not found in the zip file.")
            sys.exit(1)

        zip_ref.extractall(path=temp_dir)

    bin_directory = "/bin/"
    binary_path = os.path.join(temp_dir, members[0])

    if not os.path.exists(binary_path):
        print(f"Error: {binary_name} not found after extraction.")
        sys.exit(1)

    if not os.access(bin_directory, os.W_OK):
        if os.geteuid() != 0:
            print(f"Please run the script with sudo to move {binary_name} to {bin_directory}")
            sys.exit(1)
        else:
            print(f"Warning: {bin_directory} is not writable, attempting to move with sudo...")

    # Mark the binary as executable
    os.chmod(binary_path, 0o755)

    print(f"Moving {binary_name} to {bin_directory}...")
    shutil.move(binary_path, os.path.join(bin_directory, binary_name))

    # Clean up: remove the downloaded zip file and temporary folder after extraction
    os.remove(file_name)
    shutil.rmtree(temp_dir)

def main():
    if len(sys.argv) != 2:
        print("Usage: python3 script.py <domain>")
        sys.exit(1)

    domain = sys.argv[1]

    binaries = {
        "subfinder": "https://github.com/projectdiscovery/subfinder/releases/download/v2.6.4/subfinder_2.6.4_linux_amd64.zip",
        "httpx": "https://github.com/projectdiscovery/httpx/releases/download/v1.3.8/httpx_1.3.8_linux_amd64.zip",
        "nuclei": "https://github.com/projectdiscovery/nuclei/releases/download/v3.1.5/nuclei_3.1.5_linux_amd64.zip"
    }

    for binary, url in binaries.items():
        if shutil.which(binary) is None:
            download_and_extract(url, binary)

    # Use Subfinder to find subdomains and save them to a file
    print("Finding subdomains with Subfinder...")
    run_command(f"subfinder -silent -all -d {domain} -o {domain}_subfinder")

    # Use Httpx to find live subdomains and save them to a file
    print("Finding live subdomains with Httpx...")
    run_command(f"httpx -silent -l {domain}_subfinder -o {domain}_httpx")

    # Use Nuclei to scan the live subdomains with a specific template
    print("Scanning live subdomains with Nuclei...")
    run_command(f"nuclei -l {domain}_httpx -t ~/nuclei-templates/ -me {domain}_nuclei")

    print("Done!")

if __name__ == "__main__":
    main()
