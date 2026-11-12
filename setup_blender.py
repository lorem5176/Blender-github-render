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

def find_blend_file(name_or_path):
    """Resolve .blend file path from Blender Project/ folder or anywhere in repo."""
    if not name_or_path or name_or_path.lower() == "auto":
        name_or_path = ""

    if name_or_path and os.path.exists(name_or_path):
        return os.path.abspath(name_or_path)

    for folder in ["Blender Project", "Blender Projects", "."]:
        if not os.path.isdir(folder):
            continue
        if name_or_path:
            p1 = os.path.join(folder, name_or_path)
            if os.path.exists(p1):
                return os.path.abspath(p1)
            p2 = os.path.join(folder, name_or_path + ".blend")
            if os.path.exists(p2):
                return os.path.abspath(p2)
        else:
            files = [os.path.join(folder, f) for f in os.listdir(folder) if f.endswith(".blend")]
            if files:
                return os.path.abspath(files[0])

    for root, dirs, files in os.walk("."):
        if ".git" in root or "__pycache__" in root:
            continue
        for f in files:
            if f.endswith(".blend"):
                if not name_or_path or f.lower() == name_or_path.lower() or f.lower() == (name_or_path + ".blend").lower():
                    return os.path.abspath(os.path.join(root, f))

    return "Blender Project/scene.blend"


def main():
    arg_target = sys.argv[1] if len(sys.argv) > 1 else ""
    blend_path = find_blend_file(arg_target)
    print(f"[Project] Target blend file resolved to: {blend_path}")
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
    blender_bin = os.path.join(blender_dir, "blender")
    print(f"[Success] Blender installed in: {blender_dir}")

    # Symlink to /usr/local/bin so it is immediately on PATH everywhere
    subprocess.run(["sudo", "ln", "-sf", blender_bin, "/usr/local/bin/blender"], check=False)

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
