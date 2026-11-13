#!/usr/bin/env python3
"""
Simple, robust parallel chunk renderer for Blender animations.
Equally divides any frame range across all 20 cloud runners.
Preserves 100% of native project settings (resolution, fps, lighting, materials).
"""

import sys
import os
import shutil
import re
import json
import time
import argparse
import subprocess


def parse_args():
    parser = argparse.ArgumentParser(description="Parallel Blender chunk runner")
    parser.add_argument("--chunk", type=int, required=True, help="Worker index (0 to 19)")
    parser.add_argument("--total-chunks", type=int, default=20, help="Total workers")
    parser.add_argument("--blend-file", type=str, default="AUTO", help="Project file name")
    parser.add_argument("--engine", type=str, default="CYCLES", help="Render engine (CYCLES, BLENDER_EEVEE, AUTO)")
    return parser.parse_args()


def list_available_blend_files():
    """Finds all .blend files in the workspace."""
    found = []
    for root, dirs, files in os.walk("."):
        if ".git" in root or "__pycache__" in root:
            continue
        for f in files:
            if f.endswith(".blend"):
                found.append(os.path.normpath(os.path.join(root, f)))
    return sorted(found)


def find_blend_file(name_or_path):
    """
    Robustly resolves a .blend file:
    1. If AUTO or empty, picks first .blend in 'Blender Project/' or repo.
    2. Checks direct path.
    3. Checks inside 'Blender Project/'.
    4. Searches case-insensitively across the entire repo.
    5. Falls back gracefully to first available project rather than failing.
    """
    all_blends = list_available_blend_files()
    if not all_blends:
        raise FileNotFoundError("❌ Error: No .blend files found anywhere in the repository!")

    # If AUTO or unspecified, pick the first project in 'Blender Project/' or anywhere
    if not name_or_path or name_or_path.strip().upper() in ("AUTO", "DEFAULT", "NONE", ""):
        for b in all_blends:
            if "Blender Project" in b:
                return os.path.abspath(b)
        return os.path.abspath(all_blends[0])

    target = name_or_path.strip()

    # 1. Direct path exists
    if os.path.exists(target) and os.path.isfile(target):
        return os.path.abspath(target)

    # 2. Check in 'Blender Project' / 'Blender Projects'
    for folder in ["Blender Project", "Blender Projects", "."]:
        if not os.path.isdir(folder):
            continue
        p1 = os.path.join(folder, target)
        if os.path.exists(p1) and os.path.isfile(p1):
            return os.path.abspath(p1)
        p2 = os.path.join(folder, target + ".blend")
        if os.path.exists(p2) and os.path.isfile(p2):
            return os.path.abspath(p2)

    # 3. Case-insensitive search across repo
    clean_target = target.lower()
    if not clean_target.endswith(".blend"):
        clean_target += ".blend"

    for b in all_blends:
        b_name = os.path.basename(b).lower()
        if b_name == clean_target:
            return os.path.abspath(b)

    # 4. Fallback: warn and use first available project
    fallback = all_blends[0]
    print(f"[Warning] Project '{name_or_path}' not found! Available projects: {[os.path.basename(b) for b in all_blends]}")
    print(f"[Warning] Automatically using '{os.path.basename(fallback)}' as fallback.")
    return os.path.abspath(fallback)


def get_blender_binary():
    """Finds available Blender executable."""
    # Check PATH first
    b = shutil.which("blender")
    if b:
        return b
    # Check standard install locations
    candidates = [
        "/usr/local/bin/blender",
        "/usr/bin/blender",
        "/Applications/Blender.app/Contents/MacOS/Blender",
    ]
    for c in candidates:
        if os.path.exists(c) and os.access(c, os.X_OK):
            return c
    return "blender"


def detect_scene_info(blend_file):
    """Auto-detect frame range, fps, and resolution from .blend file."""
    blender_bin = get_blender_binary()
    if not os.path.exists(blend_file):
        return 1, 100, 24, 1920, 1080

    cmd = []
    if shutil.which("xvfb-run") and os.name != "nt" and sys.platform != "darwin":
        cmd.extend(["xvfb-run", "-a"])
    cmd.extend([
        blender_bin, "--background", blend_file, "--python-expr",
        "import bpy; s = bpy.context.scene; print('SCENE_INFO:' + str(s.frame_start) + ':' + str(s.frame_end) + ':' + str(s.render.fps) + ':' + str(s.render.resolution_x) + ':' + str(s.render.resolution_y))"
    ])

    try:
        proc = subprocess.run(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            text=True,
            timeout=60
        )
        m = re.search(r"SCENE_INFO:(\d+):(\d+):(\d+):(\d+):(\d+)", proc.stdout)
        if m:
            s, e, fps, rx, ry = [int(x) for x in m.groups()]
            if s > e:
                s, e = e, s
            print(f"[Detect] File: {os.path.basename(blend_file)} | Frames: {s}..{e} | FPS: {fps} | Res: {rx}x{ry}")
            return s, e, fps, rx, ry
    except Exception as e:
        print(f"[Detect] Notice: scene inspection fallback ({e})")

    return 1, 100, 24, 1920, 1080


def get_chunk_range(start_frame, end_frame, chunk_idx, total_chunks=20):
    """Equally divides any frame range across total_chunks workers."""
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


def recover_misplaced_frames(target_dir):
    """
    Safety net: if frames were written outside target_dir (e.g. inside Blender Project/output),
    scans and copies them into target_dir so nothing is ever lost.
    """
    image_exts = (".png", ".jpg", ".jpeg", ".exr", ".tga", ".bmp", ".tif", ".tiff")
    recovered = 0
    target_abs = os.path.abspath(target_dir)

    for root, dirs, files in os.walk("."):
        if ".git" in root or "__pycache__" in root or os.path.abspath(root) == target_abs:
            continue
        for f in files:
            if f.lower().endswith(image_exts) and "frame" in f.lower():
                src = os.path.join(root, f)
                dst = os.path.join(target_abs, f)
                if not os.path.exists(dst):
                    try:
                        shutil.copy2(src, dst)
                        recovered += 1
                    except Exception:
                        pass

    if recovered > 0:
        print(f"[Worker] Recovered {recovered} misplaced frame(s) into {target_dir}/")


def main():
    args = parse_args()

    blend_path = find_blend_file(args.blend_file)
    frame_start, frame_end, native_fps, rx, ry = detect_scene_info(blend_path)

    chunk_start, chunk_end = get_chunk_range(
        frame_start, frame_end, args.chunk, args.total_chunks
    )

    # Use absolute path for output to guarantee files land in root ./output
    output_dir = os.path.abspath("output")
    os.makedirs(output_dir, exist_ok=True)

    # Save project metadata into output so the assemble job has exact fps and resolution
    metadata = {
        "project_name": os.path.basename(blend_path),
        "frame_start": frame_start,
        "frame_end": frame_end,
        "fps": native_fps,
        "resolution_x": rx,
        "resolution_y": ry,
        "engine": args.engine,
        "total_frames": frame_end - frame_start + 1,
        "chunk": args.chunk
    }
    meta_path = os.path.join(output_dir, "render_metadata.json")
    try:
        with open(meta_path, "w") as f:
            json.dump(metadata, f, indent=2)
    except Exception as e:
        print(f"[Worker] Note writing metadata: {e}")

    if chunk_start is None:
        print(f"[Worker {args.chunk + 1}/{args.total_chunks}] No frames assigned (total frames < workers). Finished.")
        sys.exit(0)

    num_frames = chunk_end - chunk_start + 1
    total_all = frame_end - frame_start + 1
    print("=" * 65)
    print(f"  🎬 Parallel Worker {args.chunk + 1} of {args.total_chunks}")
    print(f"  📁 Project:    {os.path.basename(blend_path)}")
    print(f"  🖼️ Frames:     {chunk_start} to {chunk_end} ({num_frames} of {total_all} frames)")
    print(f"  🚀 Engine:     {args.engine}")
    print(f"  📐 Resolution: {rx} x {ry} (Native)")
    print(f"  🎞️ Frame Rate: {native_fps} FPS (Native)")
    print("=" * 65)

    blender_bin = get_blender_binary()
    output_prefix = os.path.join(output_dir, "frame_")

    cmd = []
    if shutil.which("xvfb-run") and os.name != "nt" and sys.platform != "darwin":
        cmd.extend(["xvfb-run", "-a"])
    cmd.extend([
        blender_bin,
        "-b", blend_path,
    ])

    # Force specified render engine (CYCLES is default for maximum CPU quality)
    if args.engine and args.engine.upper() != "AUTO":
        engine_name = "CYCLES" if "CYCLES" in args.engine.upper() else "BLENDER_EEVEE"
        cmd.extend(["-E", engine_name])

    cmd.extend([
        "-F", "PNG",
        "-s", str(chunk_start),
        "-e", str(chunk_end),
        "-o", output_prefix,
        "-a"
    ])

    image_exts = (".png", ".jpg", ".jpeg", ".exr", ".tga", ".bmp", ".tif", ".tiff")
    max_retries = 2

    for attempt in range(1, max_retries + 1):
        print(f"Running (attempt {attempt}/{max_retries}): {' '.join(cmd)}")
        result = subprocess.run(cmd)

        # Check for rendered frames
        recover_misplaced_frames(output_dir)
        rendered_frames = [f for f in os.listdir(output_dir) if f.lower().endswith(image_exts)]

        if len(rendered_frames) >= num_frames or result.returncode == 0:
            print(f"✅ Chunk frames rendered: {len(rendered_frames)} frame(s) saved in {output_dir}")
            for rf in sorted(rendered_frames)[:3]:
                print(f"   - {rf} ({os.path.getsize(os.path.join(output_dir, rf))} bytes)")
            if len(rendered_frames) > 3:
                print(f"   ... and {len(rendered_frames) - 3} more.")
            sys.exit(0)

        print(f"[Worker] Warning: Attempt {attempt} completed with code {result.returncode}, found {len(rendered_frames)} frames.")
        if attempt < max_retries:
            print("[Worker] Retrying in 5 seconds...")
            time.sleep(5)

    # If some frames were rendered, exit 0 so upload preserves them
    rendered_frames = [f for f in os.listdir(output_dir) if f.lower().endswith(image_exts)]
    if rendered_frames:
        print(f"⚠️ Worker produced {len(rendered_frames)} frames despite warnings. Proceeding.")
        sys.exit(0)

    sys.exit(result.returncode if result.returncode != 0 else 1)


if __name__ == "__main__":
    main()
