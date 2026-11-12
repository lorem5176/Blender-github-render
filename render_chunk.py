#!/usr/bin/env python3
"""
Helper script to calculate frame slice for a parallel matrix worker
and execute Blender for that specific slice.
"""

import sys
import os
import math
import argparse
import subprocess

def parse_args():
    parser = argparse.ArgumentParser(description="Parallel Blender chunk renderer")
    parser.add_argument("--chunk", type=int, required=True, help="Current worker index (0-based)")
    parser.add_argument("--total-chunks", type=int, default=10, help="Total number of parallel workers")
    parser.add_argument("--frame-start", type=int, default=1, help="Global start frame")
    parser.add_argument("--frame-end", type=int, default=1, help="Global end frame")
    parser.add_argument("--blend-file", type=str, default="scene.blend", help="Path to .blend file")
    parser.add_argument("--engine", type=str, default="CYCLES", help="Render engine")
    parser.add_argument("--samples", type=int, default=48, help="Sample count")
    parser.add_argument("--resolution-x", type=int, default=1920, help="Resolution width")
    parser.add_argument("--resolution-y", type=int, default=1080, help="Resolution height")
    return parser.parse_args()

def main():
    args = parse_args()

    if args.frame_end < args.frame_start:
        print(f"Error: frame_end ({args.frame_end}) < frame_start ({args.frame_start})")
        sys.exit(1)

    total_frames = args.frame_end - args.frame_start + 1
    frames_per_chunk = math.ceil(total_frames / args.total_chunks)

    chunk_start = args.frame_start + (args.chunk * frames_per_chunk)
    chunk_end = min(chunk_start + frames_per_chunk - 1, args.frame_end)

    if chunk_start > args.frame_end:
        print(f"[Worker {args.chunk}] No frames to render (chunk_start {chunk_start} > frame_end {args.frame_end}). Exiting.")
        sys.exit(0)

    print("=" * 60)
    print(f"  Parallel Worker {args.chunk + 1} / {args.total_chunks}")
    print(f"  Rendering frames: {chunk_start} to {chunk_end} ({chunk_end - chunk_start + 1} frames)")
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
