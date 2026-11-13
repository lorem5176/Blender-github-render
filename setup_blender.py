#!/usr/bin/env python3
"""
Downloads and extracts the appropriate Blender version for Linux x64.
Autodetects the required Blender version from the .blend file header.
Includes multiple mirror fallbacks and download verification.
"""

import sys
import os
import re
import shutil
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

        m = re.search(rb"v0?(\d)(\d{2})", data)
        if m:
            major = int(m.group(1))
            minor = int(m.group(2))
            print(f"[Detect] Found Blender version {major}.{minor} in {blend_path}")
            return f"{major}.{minor}"
    except Exception as e:
        print(f"[Detect] Warning parsing blend header: {e}")
    return "5.2"


def get_candidate_urls(version):
    """Generates a list of download URLs from official release and fast global mirrors."""
    folder = f"Blender{version}"
    mirrors = [
        f"https://download.blender.org/release/{folder}/",
        f"https://mirrors.dotsrc.org/blender/release/{folder}/",
        f"https://mirror.clarkson.edu/blender/release/{folder}/"
    ]
    candidates = []

    # First attempt to scrape the latest patch version from the primary mirror
    try:
        req = urllib.request.Request(mirrors[0], headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=15) as resp:
            html = resp.read().decode("utf-8", errors="ignore")
            matches = re.findall(rf'href="?(blender-{re.escape(version)}\.[0-9]+-linux-x64\.tar\.xz)"?', html)
            if matches:
                best_file = sorted(matches)[-1]
                for m in mirrors:
                    candidates.append((f"{m}{best_file}", best_file))
    except Exception as e:
        print(f"[Download] Note querying primary directory: {e}")

    # Fallbacks for specific known patch releases
    for patch in [4, 3, 2, 1, 0]:
        fn = f"blender-{version}.{patch}-linux-x64.tar.xz"
        for m in mirrors:
            candidates.append((f"{m}{fn}", fn))

    # General 5.2.3 fallback
    default_fn = "blender-5.2.3-linux-x64.tar.xz"
    for m in mirrors:
        candidates.append((f"{m}{default_fn}", default_fn))

    # Deduplicate while preserving order
    seen = set()
    unique = []
    for u, f in candidates:
        if u not in seen:
            seen.add(u)
            unique.append((u, f))
    return unique


def find_blend_file_helper(arg_target):
    try:
        from render_chunk import find_blend_file
        return find_blend_file(arg_target)
    except Exception:
        for folder in ["Blender Project", "Blender Projects", "."]:
            if os.path.isdir(folder):
                files = [os.path.join(folder, f) for f in os.listdir(folder) if f.endswith(".blend")]
                if files:
                    return os.path.abspath(files[0])
    return ""


def main():
    arg_target = sys.argv[1] if len(sys.argv) > 1 else "AUTO"
    blend_path = find_blend_file_helper(arg_target)
    print(f"[Project] Target blend file resolved to: {blend_path}")

    # If Blender already exists and works, verify and reuse
    existing = shutil.which("blender") or "/usr/local/bin/blender"
    if os.path.exists(existing) and os.access(existing, os.X_OK):
        try:
            ver_check = subprocess.run([existing, "--version"], stdout=subprocess.PIPE, text=True, timeout=10)
            if ver_check.returncode == 0:
                print(f"[Setup] Blender is already installed: {ver_check.stdout.splitlines()[0]}")
                return
        except Exception:
            pass

    version = detect_blend_version(blend_path) if (blend_path and os.path.exists(blend_path)) else "5.2"
    candidates = get_candidate_urls(version)

    success = False
    for url, filename in candidates[:6]:
        print(f"[Download] Trying {url}...")
        try:
            # Check availability with HEAD or quick fetch
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"}, method="HEAD")
            with urllib.request.urlopen(req, timeout=10) as resp:
                if resp.status != 200:
                    continue
        except Exception:
            continue

        # Download with wget
        dl_proc = subprocess.run([
            "wget", "-q", "--show-progress", "--retry-connrefused",
            "--tries=3", "--timeout=60", url, "-O", filename
        ])
        if dl_proc.returncode != 0 or not os.path.exists(filename) or os.path.getsize(filename) < 100000000:
            print(f"[Download] Incomplete download from {url}, trying next mirror...")
            if os.path.exists(filename):
                try:
                    os.remove(filename)
                except Exception:
                    pass
            continue

        # Extract
        print(f"[Extract] Extracting {filename}...")
        ext_proc = subprocess.run(["tar", "-xf", filename])
        if ext_proc.returncode == 0:
            success = True
            break
        else:
            print(f"[Extract] Warning extracting {filename}, trying next candidate...")
            if os.path.exists(filename):
                try:
                    os.remove(filename)
                except Exception:
                    pass

    if not success:
        sys.exit(f"❌ Error: Failed to download and extract Blender {version} for Linux x64 from any mirror.")

    # Locate extracted directory
    extracted = [d for d in os.listdir(".") if d.startswith("blender-") and os.path.isdir(d)]
    if not extracted:
        sys.exit("❌ Error: Could not find extracted blender directory")

    blender_dir = os.path.abspath(extracted[0])
    blender_bin = os.path.join(blender_dir, "blender")
    print(f"✅ Blender installed in: {blender_dir}")

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
