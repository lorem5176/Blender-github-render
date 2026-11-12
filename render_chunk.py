#!/usr/bin/env python3
"""
Pure parallel chunk renderer for Blender.
Runs Blender natively with 0 overrides — 100% of your scene settings,
engine, materials, lights, samples, and resolution are preserved as-is.
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
    parser.add_argument("--frame-end", type=int, default=0, help="End frame (0 = auto-detect)")
    parser.add_argument("--blend-file", type=str, default="scene.blend", help="Path to .blend file")
    return parser.parse_args()


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
            return int(m.group(1)), int(m.group(2))
    except Exception as e:
        print(f"[Detect] Note: {e}")
    return 1, 100


def get_chunk_range(start_frame, end_frame, chunk_idx, total_chunks=20):
    """Divide total frames equally across 20 workers."""
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

    if args.frame_end <= 0:
        auto_start, auto_end = detect_scene_frames(args.blend_file)
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
    print(f"  File: {args.blend_file} (100% native Blender settings preserved)")
    print("=" * 60)

    os.makedirs("output", exist_ok=True)

    # Pure standard Blender CLI render - NO SETTINGS OVERRIDDEN
    cmd = [
        "xvfb-run", "-a", "blender",
        "-b", args.blend_file,
        "-s", str(chunk_start),
        "-e", str(chunk_end),
        "-o", "//output/frame_",
        "-a"
    ]

    print(f"Running: {' '.join(cmd)}")
    result = subprocess.run(cmd)
    sys.exit(result.returncode)


if __name__ == "__main__":
    main()
