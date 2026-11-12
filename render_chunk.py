#!/usr/bin/env python3
"""
Pure parallel chunk renderer for Blender.
Supports multiple projects located in the 'Blender Project' folder.
Runs Blender with custom resolution, fps, and engine settings if specified,
or uses 100% native project settings.
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
    parser.add_argument("--resolution", type=str, default="AUTO", help="Resolution preset (e.g. 1920x1080, 1080x1920, AUTO)")
    parser.add_argument("--fps", type=str, default="AUTO", help="FPS preset (e.g. 24 fps, 30 fps, AUTO)")
    return parser.parse_args()


def find_blend_file(name_or_path):
    """
    Finds .blend file from 'Blender Project/' folder or anywhere in the repo.
    Accepts:
      - 'one.blend' or 'one'
      - 'two.blend' or 'two'
      - '3.blend' or '3'
      - 'Blender Project/one.blend'
      - 'auto' (picks first .blend found in Blender Project/)
    """
    if not name_or_path or name_or_path.lower() == "auto":
        name_or_path = ""

    # 1. Direct path
    if name_or_path and os.path.exists(name_or_path):
        return os.path.abspath(name_or_path)

    # 2. Search in 'Blender Project' or 'Blender Projects'
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
            files = sorted([os.path.join(folder, f) for f in os.listdir(folder) if f.endswith(".blend")])
            if files:
                return os.path.abspath(files[0])

    # 3. Recursive search
    for root, dirs, files in os.walk("."):
        if ".git" in root or "__pycache__" in root:
            continue
        for f in sorted(files):
            if f.endswith(".blend"):
                if not name_or_path or f.lower() == name_or_path.lower() or f.lower() == (name_or_path + ".blend").lower():
                    return os.path.abspath(os.path.join(root, f))

    return "Blender Project/one.blend"


def detect_scene_info(blend_file):
    """Auto-detect frame range, fps, and resolution from .blend file."""
    blender_bin = shutil.which("blender") or "/Applications/Blender.app/Contents/MacOS/Blender"
    if not os.path.exists(blend_file):
        return 1, 100, 24, 1920, 1080
    try:
        proc = subprocess.run(
            [blender_bin, "--background", blend_file, "--python-expr",
             "import bpy; s = bpy.context.scene; print('SCENE_INFO:' + str(s.frame_start) + ':' + str(s.frame_end) + ':' + str(s.render.fps) + ':' + str(s.render.resolution_x) + ':' + str(s.render.resolution_y))"],
            stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True, timeout=30
        )
        m = re.search(r"SCENE_INFO:(\d+):(\d+):(\d+):(\d+):(\d+)", proc.stdout)
        if m:
            s, e, fps, rx, ry = [int(x) for x in m.groups()]
            print(f"[Detect] File: {os.path.basename(blend_file)} | Frames: {s}..{e} | FPS: {fps} | Res: {rx}x{ry}")
            return s, e, fps, rx, ry
    except Exception as e:
        print(f"[Detect] Note: {e}")
    return 1, 100, 24, 1920, 1080


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
    auto_start, auto_end, native_fps, native_rx, native_ry = detect_scene_info(blend_path)

    # Frame range resolution
    if args.frame_end <= 0:
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

    # Resolution resolution
    res_match = re.search(r"(\d+)x(\d+)", args.resolution)
    if res_match:
        target_rx = int(res_match.group(1))
        target_ry = int(res_match.group(2))
    else:
        target_rx = native_rx
        target_ry = native_ry

    # FPS resolution
    fps_match = re.search(r"(\d+)", args.fps)
    target_fps = int(fps_match.group(1)) if fps_match else native_fps

    # Calculated duration
    duration_sec = total_all / target_fps
    dur_min = int(duration_sec // 60)
    dur_sec = int(duration_sec % 60)
    dur_str = f"{dur_min}m {dur_sec}s" if dur_min > 0 else f"{dur_sec}s"

    print("=" * 65)
    print(f"  🎬 Parallel Worker {args.chunk + 1} of {args.total_chunks}")
    print(f"  Project:    {os.path.basename(blend_path)}")
    print(f"  Resolution: {target_rx} x {target_ry}")
    print(f"  FPS:        {target_fps} fps")
    print(f"  Total Video Length: {dur_str} ({total_all} frames)")
    print(f"  This Worker: Frames {chunk_start} to {chunk_end} ({num_frames} frames)")
    print(f"  Engine:     {args.engine}")
    print("=" * 65)

    os.makedirs("output", exist_ok=True)

    # Prepare python snippet for overrides (if needed)
    py_overrides = []
    if res_match:
        py_overrides.append(f"bpy.context.scene.render.resolution_x = {target_rx}")
        py_overrides.append(f"bpy.context.scene.render.resolution_y = {target_ry}")
        py_overrides.append("bpy.context.scene.render.resolution_percentage = 100")
    if fps_match:
        py_overrides.append(f"bpy.context.scene.render.fps = {target_fps}")

    cmd = [
        "xvfb-run", "-a", "blender",
        "-b", blend_path,
    ]

    # Engine selection (CYCLES is default for maximum quality)
    if args.engine and args.engine.upper() != "AUTO":
        engine_name = "CYCLES" if "CYCLES" in args.engine.upper() else "BLENDER_EEVEE"
        cmd.extend(["-E", engine_name])

    if py_overrides:
        cmd.extend(["--python-expr", "import bpy; " + "; ".join(py_overrides)])

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
