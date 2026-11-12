#!/usr/bin/env python3
"""
Pure parallel chunk renderer for Blender.
Supports multiple projects located in the 'Blender Project' folder.
Runs Blender natively with 0 overrides — your materials, lights, and settings
are preserved exactly as you designed them in Blender.
"""

import sys
import os
import shutil
import re
import argparse
import subprocess


def parse_args():
    parser = argparse.ArgumentParser(description="Parallel Blender chunk runner")
    parser.add_argument("--chunk", type=int, required=True, help="Worker index (0 to 19)")
    parser.add_argument("--total-chunks", type=int, default=20, help="Total workers")
    parser.add_argument("--frame-start", type=int, default=1, help="Start frame")
    parser.add_argument("--frame-end", type=int, default=0, help="End frame (0 = auto-detect from file)")
    parser.add_argument("--blend-file", type=str, default="auto", help="Name or path of .blend project file")
    parser.add_argument("--engine", type=str, default="CYCLES", help="Render engine (CYCLES, BLENDER_EEVEE, AUTO)")
    return parser.parse_args()


def find_blend_file(name_or_path):
    """
    Finds .blend file from 'Blender Project/' folder or anywhere in the repo.
    Accepts:
      - 'car.blend'
      - 'car'
      - 'Blender Project/car.blend'
      - 'auto' or '' (picks first .blend found in Blender Project/)
    """
    if not name_or_path or name_or_path.lower() == "auto":
        name_or_path = ""

    # Direct path
    if name_or_path and os.path.exists(name_or_path):
        return os.path.abspath(name_or_path)

    # Search in 'Blender Project' or 'Blender Projects'
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

    # Recursive search
    for root, dirs, files in os.walk("."):
        if ".git" in root or "__pycache__" in root:
            continue
        for f in files:
            if f.endswith(".blend"):
                if not name_or_path or f.lower() == name_or_path.lower() or f.lower() == (name_or_path + ".blend").lower():
                    return os.path.abspath(os.path.join(root, f))

    return "Blender Project/scene.blend"


def detect_scene_frames(blend_file):
    """Auto-detect frame range from .blend file if not specified."""
    blender_bin = shutil.which("blender") or "/Applications/Blender.app/Contents/MacOS/Blender"
    if not os.path.exists(blend_file):
        return 1, 100
    try:
        proc = subprocess.run(
            [blender_bin, "--background", blend_file, "--python-expr",
             "import bpy; print(f'SCENE_FRAME_RANGE:{bpy.context.scene.frame_start}:{bpy.context.scene.frame_end}')"],
            stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True, timeout=30
        )
        m = re.search(r"SCENE_FRAME_RANGE:(\d+):(\d+)", proc.stdout)
        if m:
            s, e = int(m.group(1)), int(m.group(2))
            print(f"[Detect] Auto-detected frame range: {s} to {e}")
            return s, e
    except Exception as e:
        print(f"[Detect] Note: {e}")
    return 1, 100


def get_chunk_range(start_frame, end_frame, chunk_idx, total_chunks=20):
    """Equally divides any number of frames across 20 workers."""
    total_frames = end_frame - start_frame + 1
    if total_frames <= 0:
        return None, None

    base = total_frames // total_chunks
    rem = total_frames % total_chunks

    count = base + (1 if chunk_idx < rem else 0)
    if count == 0:
        return None, None

    offset = (chunk_idx * (base + 1)) if chunk_idx < rem else (rem * (base + 1) + (chunk_idx - rem) * base)
    c_start = start_frame + offset
    c_end = c_start + count - 1
    return c_start, c_end


def main():
    args = parse_args()

    blend_path = find_blend_file(args.blend_file)
    print(f"[Project] Using Blender file: {blend_path}")

    if args.frame_end <= 0:
        auto_start, auto_end = detect_scene_frames(blend_path)
        if args.frame_start <= 1:
            args.frame_start = auto_start
        args.frame_end = auto_end

    if args.frame_end < args.frame_start:
        print(f"Error: frame_end ({args.frame_end}) < frame_start ({args.frame_start})")
        sys.exit(1)

    chunk_start, chunk_end = get_chunk_range(
        args.frame_start, args.frame_end, args.chunk, args.total_chunks
    )

    if chunk_start is None:
        print(f"[Worker {args.chunk + 1}/{args.total_chunks}] No frames assigned. Exiting.")
        sys.exit(0)

    num_frames = chunk_end - chunk_start + 1
    total_all = args.frame_end - args.frame_start + 1
    print("=" * 60)
    print(f"  Parallel Worker {args.chunk + 1} of {args.total_chunks}")
    print(f"  Rendering frames: {chunk_start} to {chunk_end} ({num_frames} of {total_all} frames)")
    print(f"  File: {os.path.basename(blend_path)} | Engine: {args.engine}")
    print("=" * 60)

    os.makedirs("output", exist_ok=True)

    cmd = [
        "xvfb-run", "-a", "blender",
        "-b", blend_path,
    ]

    # Engine selection (CYCLES is default for maximum quality)
    if args.engine and args.engine.upper() != "AUTO":
        cmd.extend(["-E", args.engine.upper()])

    cmd.extend([
        "-s", str(chunk_start),
        "-e", str(chunk_end),
        "-o", "//output/frame_",
        "-a"
    ])

    print(f"Running: {' '.join(cmd)}")
    result = subprocess.run(cmd)
    sys.exit(result.returncode)


if __name__ == "__main__":
    main()
