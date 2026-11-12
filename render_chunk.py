#!/usr/bin/env python3
"""
Helper script to calculate equal frame slices for 20 parallel matrix workers
and execute Blender for that specific slice.
Works dynamically for ANY number of frames (100, 105, 500, 1440, 2000, etc.)
always distributing workload evenly across all 20 workers.
"""

import sys
import os
import shutil
import re
import argparse
import subprocess


def parse_args():
    parser = argparse.ArgumentParser(description="Parallel Blender chunk renderer")
    parser.add_argument("--chunk", type=int, required=True, help="Current worker index (0-based, 0 to 19)")
    parser.add_argument("--total-chunks", type=int, default=20, help="Total number of parallel workers")
    parser.add_argument("--frame-start", type=int, default=1, help="Global start frame")
    parser.add_argument("--frame-end", type=int, default=0, help="Global end frame (0 = auto-detect from .blend)")
    parser.add_argument("--blend-file", type=str, default="scene.blend", help="Path to .blend file")
    parser.add_argument("--engine", type=str, default="AUTO", help="Render engine (AUTO, CYCLES, BLENDER_EEVEE)")
    parser.add_argument("--samples", type=int, default=48, help="Sample count")
    parser.add_argument("--resolution-x", type=int, default=1920, help="Resolution width")
    parser.add_argument("--resolution-y", type=int, default=1080, help="Resolution height")
    return parser.parse_args()


def detect_scene_frames(blend_file):
    """Auto-detect frame range from .blend file if frame_end is 0 or not provided."""
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
            print(f"[Detect] Auto-detected frame range from {blend_file}: {s} to {e}")
            return s, e
    except Exception as e:
        print(f"[Detect] Notice: could not auto-detect frame range: {e}")
    return 1, 100


def get_chunk_range(start_frame, end_frame, chunk_idx, total_chunks=20):
    """
    Equally distributes ANY number of frames across total_chunks workers.
    - 100 frames across 20 workers -> exactly 5 frames each.
    - 2000 frames across 20 workers -> exactly 100 frames each.
    - 105 frames across 20 workers -> 5 workers get 6, 15 workers get 5.
    Guarantees no overlaps and every single frame is rendered once.
    """
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

    # If frame_end is 0, auto-detect from .blend file
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
        print(f"[Worker {args.chunk + 1}/{args.total_chunks}] No frames assigned (total frames < total workers). Exiting.")
        sys.exit(0)

    num_frames = chunk_end - chunk_start + 1
    total_all = args.frame_end - args.frame_start + 1
    print("=" * 60)
    print(f"  Parallel Worker {args.chunk + 1} of {args.total_chunks}")
    print(f"  Rendering frames: {chunk_start} to {chunk_end} ({num_frames} frames out of {total_all})")
    print(f"  File: {args.blend_file} | Engine: {args.engine} | Samples: {args.samples}")
    print("=" * 60)

    os.makedirs("output", exist_ok=True)

    cmd = [
        "xvfb-run", "-a", "blender",
        "--background", args.blend_file,
        "--python", "render_settings.py",
        "--",
        "--engine", args.engine,
        "--samples", str(args.samples),
        "--resolution_x", str(args.resolution_x),
        "--resolution_y", str(args.resolution_y),
        "--frame_start", str(chunk_start),
        "--frame_end", str(chunk_end),
        "--output_format", "PNG",
        "--output_path", "//output/frame_"
    ]

    print(f"Running: {' '.join(cmd)}")
    result = subprocess.run(cmd)
    sys.exit(result.returncode)


if __name__ == "__main__":
    main()
