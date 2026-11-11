#!/usr/bin/env python3
"""
Downloads and extracts the appropriate Blender version for Linux x64.
Autodetects the required Blender version from the .blend file.
"""

import sys
import os
import re
import subprocess
import urllib.request
import tarfile

def detect_blend_version(blend_path):
    """Detect Blender major.minor version from blend file header."""
    try:
        # scene.blend can be zstd compressed
        proc = subprocess.run(
            ["zstd", "-d", "-c", blend_path],
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL
        )
        data = proc.stdout[:64]
        if not data.startswith(b"BLENDER"):
            with open(blend_path, "rb") as f:
                data = f.read(64)
        
        # Match v0502 or v502 or v402
        m = re.search(rb"v0?(\d)(\d{2})", data)
        if m:
            major = int(m.group(1))
            minor = int(m.group(2))
            print(f"[Detect] Found Blender version {major}.{minor} in {blend_path}")
            return f"{major}.{minor}"
    except Exception as e:
        print(f"[Detect] Warning: could not parse blend header: {e}")
    return "5.2"

def find_download_url(version):
    """Find valid linux-x64 download URL on download.blender.org."""
    folder = f"Blender{version}"
    dir_url = f"https://download.blender.org/release/{folder}/"
    print(f"[Download] Checking {dir_url}...")
    
    try:
        req = urllib.request.Request(dir_url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=30) as resp:
            html = resp.read().decode("utf-8", errors="ignore")
            matches = re.findall(rf'href="?(blender-{re.escape(version)}\.[0-9]+-linux-x64\.tar\.xz)"?', html)
            if matches:
                # Pick the latest patch version
                best_file = sorted(matches)[-1]
                return f"{dir_url}{best_file}", best_file
    except Exception as e:
        print(f"[Download] Could not query {dir_url}: {e}")

    # Direct fallback attempts
    for patch in [3, 2, 1, 0]:
        filename = f"blender-{version}.{patch}-linux-x64.tar.xz"
        candidate_url = f"https://download.blender.org/release/{folder}/{filename}"
        try:
            req = urllib.request.Request(candidate_url, headers={"User-Agent": "Mozilla/5.0"}, method="HEAD")
            with urllib.request.urlopen(req, timeout=15) as resp:
                if resp.status == 200:
                    return candidate_url, filename
        except Exception:
            continue

    # Fallback to 5.2.3
    return "https://download.blender.org/release/Blender5.2/blender-5.2.3-linux-x64.tar.xz", "blender-5.2.3-linux-x64.tar.xz"

def main():
    blend_path = sys.argv[1] if len(sys.argv) > 1 else "scene.blend"
    version = detect_blend_version(blend_path) if os.path.exists(blend_path) else "5.2"
    url, filename = find_download_url(version)
    
    print(f"[Download] Downloading from: {url}")
    subprocess.run(["wget", "-q", "--show-progress", "--retry-connrefused", "--tries=3", url, "-O", filename], check=True)
    
    print("[Extract] Extracting Blender archive...")
    subprocess.run(["tar", "-xf", filename], check=True)
    
    # Locate extracted directory
    extracted = [d for d in os.listdir(".") if d.startswith("blender-") and os.path.isdir(d)]
    if not extracted:
        sys.exit("Error: Could not find extracted blender directory")
    
    blender_dir = os.path.abspath(extracted[0])
    print(f"[Success] Blender installed in: {blender_dir}")
    
    # Export to GitHub Actions environment
    github_path = os.environ.get("GITHUB_PATH")
    if github_path:
        with open(github_path, "a") as f:
            f.write(f"{blender_dir}\n")
    
    github_env = os.environ.get("GITHUB_ENV")
    if github_env:
        with open(github_env, "a") as f:
            f.write(f"BLENDER_DIR={blender_dir}\n")

if __name__ == "__main__":
    main()
