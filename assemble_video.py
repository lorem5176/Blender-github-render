#!/usr/bin/env python3
"""
Intelligent and resilient video assembler for Blender parallel renders.
Handles:
  1. Image sequences (PNG, JPG, EXR, TGA, etc.) across any chunk folder structure.
  2. Reads project metadata (FPS, resolution, project name) without needing Blender.
  3. Natural numerical sorting so frame 2 comes before frame 10.
  4. Missing or skipped frames (renumbers sequence cleanly so ffmpeg never halts).
  5. Automatic padding so odd video dimensions never break libx264.
  6. Creates raw frames zip backup so user never loses rendered work.
"""

import sys
import os
import re
import json
import shutil
import zipfile
import subprocess


def natural_sort_key(s):
    """Sort strings containing numbers in human order: 1, 2, ..., 9, 10."""
    return [int(text) if text.isdigit() else text.lower() for text in re.split(r'(\d+)', s)]


def load_project_metadata(search_dir):
    """Searches for render_metadata.json written by workers."""
    for root, dirs, files in os.walk(search_dir):
        for f in files:
            if f == "render_metadata.json":
                meta_path = os.path.join(root, f)
                try:
                    with open(meta_path, "r") as fp:
                        return json.load(fp)
                except Exception:
                    pass
    return {}


def find_files_by_ext(root_dir, extensions):
    """Recursively find all files matching given extensions."""
    matched = []
    if not os.path.isdir(root_dir):
        return matched
    for root, dirs, files in os.walk(root_dir):
        for f in files:
            ext = os.path.splitext(f)[1].lower()
            if ext in extensions and not f.startswith('.'):
                matched.append(os.path.join(root, f))
    return sorted(matched, key=natural_sort_key)


def assemble_from_images(image_files, output_path, fps):
    """Stitch image sequence into high quality MP4 video."""
    print(f"[Assembler] Assembling {len(image_files)} image frames into MP4 at {fps} fps...")

    staging_dir = "staging_frames"
    if os.path.exists(staging_dir):
        shutil.rmtree(staging_dir)
    os.makedirs(staging_dir, exist_ok=True)

    first_ext = os.path.splitext(image_files[0])[1].lower()

    for idx, src_path in enumerate(image_files, start=1):
        dst_name = f"frame_{idx:06d}{first_ext}"
        dst_path = os.path.join(staging_dir, dst_name)
        try:
            os.link(src_path, dst_path)
        except Exception:
            shutil.copy2(src_path, dst_path)

    cmd = [
        "ffmpeg", "-y",
        "-framerate", str(fps),
        "-i", os.path.join(staging_dir, f"frame_%06d{first_ext}"),
        "-vf", "pad=ceil(iw/2)*2:ceil(ih/2)*2",
        "-c:v", "libx264",
        "-pix_fmt", "yuv420p",
        "-crf", "18",
        "-preset", "medium",
        output_path
    ]
    print(f"Running ffmpeg: {' '.join(cmd)}")
    proc = subprocess.run(cmd)

    # Fallback attempt if libx264 preset or crf caused an issue
    if proc.returncode != 0 or not os.path.exists(output_path) or os.path.getsize(output_path) == 0:
        print("[Assembler] Primary ffmpeg command failed. Retrying with universal compatibility preset...")
        cmd_fallback = [
            "ffmpeg", "-y",
            "-framerate", str(fps),
            "-i", os.path.join(staging_dir, f"frame_%06d{first_ext}"),
            "-vf", "pad=ceil(iw/2)*2:ceil(ih/2)*2",
            "-c:v", "libx264",
            "-pix_fmt", "yuv420p",
            output_path
        ]
        proc = subprocess.run(cmd_fallback)

    # Clean staging directory
    shutil.rmtree(staging_dir, ignore_errors=True)
    return os.path.exists(output_path) and os.path.getsize(output_path) > 0


def assemble_from_videos(video_files, output_path):
    """Losslessly concatenate video segments."""
    print(f"[Assembler] Concatenating {len(video_files)} video segments into single MP4...")
    concat_list_path = "concat_list.txt"
    with open(concat_list_path, "w") as f:
        for v in video_files:
            abs_v = os.path.abspath(v)
            f.write(f"file '{abs_v}'\n")

    cmd = [
        "ffmpeg", "-y",
        "-f", "concat",
        "-safe", "0",
        "-i", concat_list_path,
        "-c", "copy",
        output_path
    ]
    print(f"Running ffmpeg: {' '.join(cmd)}")
    proc = subprocess.run(cmd)

    if os.path.exists(concat_list_path):
        os.remove(concat_list_path)
    return os.path.exists(output_path) and os.path.getsize(output_path) > 0


def main():
    download_dir = sys.argv[1] if len(sys.argv) > 1 else "downloaded_chunks"
    output_dir = sys.argv[2] if len(sys.argv) > 2 else "final_output"
    blend_file = sys.argv[3] if len(sys.argv) > 3 else "AUTO"

    os.makedirs(output_dir, exist_ok=True)
    final_video = os.path.join(output_dir, "rendered_animation.mp4")

    # Load metadata written by workers
    meta = load_project_metadata(download_dir)
    if not meta:
        meta = load_project_metadata(".")

    fps = meta.get("fps", 24)
    if not fps or fps <= 0:
        fps = 24

    project_name = meta.get("project_name", blend_file)
    print(f"[Assembler] Project: {project_name} | Target FPS: {fps}")

    # Forward metadata into final_output for summarize_video.py
    if meta:
        meta_out = os.path.join(output_dir, "render_metadata.json")
        try:
            with open(meta_out, "w") as fp:
                json.dump(meta, fp, indent=2)
        except Exception:
            pass

    # 1. Search for image frames
    image_exts = {".png", ".jpg", ".jpeg", ".exr", ".tga", ".bmp", ".tif", ".tiff"}
    image_files = find_files_by_ext(download_dir, image_exts)

    # Fallback search if downloaded_chunks had no images
    if not image_files:
        image_files = find_files_by_ext("output", image_exts)

    if image_files:
        print(f"[Assembler] Found {len(image_files)} image frames.")
        success = assemble_from_images(image_files, final_video, fps)
        if success and os.path.exists(final_video):
            size_mb = os.path.getsize(final_video) / (1024 * 1024)
            print(f"✅ Video created successfully: {final_video} ({size_mb:.2f} MB)")
        else:
            print("⚠️ Warning: ffmpeg image assembly failed to produce output video.")

        # Always create a zip archive of all raw frames as backup
        zip_path = os.path.join(output_dir, "all_rendered_frames.zip")
        print(f"[Assembler] Creating backup zip of all {len(image_files)} rendered frames...")
        with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
            for idx, img in enumerate(image_files, start=1):
                ext = os.path.splitext(img)[1].lower()
                zf.write(img, f"frame_{idx:06d}{ext}")
        print(f"✅ Frames archive created: {zip_path} ({os.path.getsize(zip_path)} bytes)")
        return

    # 2. If no images found, search for video chunks
    video_exts = {".mp4", ".mkv", ".mov", ".avi"}
    video_files = find_files_by_ext(download_dir, video_exts)

    if video_files:
        print(f"[Assembler] Found {len(video_files)} video chunks.")
        if len(video_files) == 1:
            shutil.copy2(video_files[0], final_video)
            print(f"✅ Single video chunk copied to {final_video}")
        else:
            success = assemble_from_videos(video_files, final_video)
            if success and os.path.exists(final_video):
                print(f"✅ Video concatenated successfully: {final_video}")
        return

    # 3. No render files found at all
    print("❌ Error: No rendered image frames or video chunks found in downloaded_chunks/.")
    print("Directory contents for diagnostics:")
    for root, dirs, files in os.walk("."):
        if ".git" in root or "__pycache__" in root:
            continue
        if files:
            print(f"  {root}: {files[:10]}")
    sys.exit(1)


if __name__ == "__main__":
    main()
