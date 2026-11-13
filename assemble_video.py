#!/usr/bin/env python3
"""
Intelligent and resilient video assembler for Blender parallel renders.
Handles:
  1. Image sequences (PNG, JPG, EXR, TGA) even if scattered across subdirectories.
  2. Video chunks (MP4, MKV, MOV) via lossless concat demuxer if Blender rendered in FFMPEG mode.
  3. Natural numerical sorting so frame 2 comes before frame 10.
  4. Missing or skipped frames (renumbers sequence cleanly so ffmpeg never halts).
  5. Raw frames zip backup so user never loses rendered work.
"""

import sys
import os
import re
import shutil
import zipfile
import subprocess


def natural_sort_key(s):
    """Sort strings containing numbers in human order: 1, 2, ..., 9, 10."""
    return [int(text) if text.isdigit() else text.lower() for text in re.split(r'(\d+)', s)]


def get_fps(blend_file_arg, default_fps=24):
    """Detect native FPS from .blend file or return default."""
    try:
        from render_chunk import find_blend_file, detect_scene_info
        bp = find_blend_file(blend_file_arg)
        s, e, native_fps, rx, ry = detect_scene_info(bp)
        if native_fps and native_fps > 0:
            return native_fps
    except Exception as e:
        print(f"[Assembler] Note detecting FPS: {e}")
    return default_fps


def find_files_by_ext(root_dir, extensions):
    """Recursively find all files matching given extensions."""
    matched = []
    for root, dirs, files in os.walk(root_dir):
        for f in files:
            ext = os.path.splitext(f)[1].lower()
            if ext in extensions and not f.startswith('.'):
                matched.append(os.path.join(root, f))
    return sorted(matched, key=natural_sort_key)


def assemble_from_images(image_files, output_path, fps):
    """Stitch image sequence into high quality MP4 video."""
    print(f"[Assembler] Assembling {len(image_files)} image frames into MP4 at {fps} fps...")
    
    # Staging directory with clean consecutive names (frame_000001.png, ...)
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
        "-c:v", "libx264",
        "-pix_fmt", "yuv420p",
        "-crf", "18",
        "-preset", "medium",
        output_path
    ]
    print(f"Running ffmpeg: {' '.join(cmd)}")
    proc = subprocess.run(cmd)
    
    # Clean staging directory
    shutil.rmtree(staging_dir, ignore_errors=True)
    return proc.returncode == 0


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
    return proc.returncode == 0


def main():
    download_dir = sys.argv[1] if len(sys.argv) > 1 else "downloaded_chunks"
    output_dir = sys.argv[2] if len(sys.argv) > 2 else "final_output"
    blend_file = sys.argv[3] if len(sys.argv) > 3 else "one.blend"
    
    os.makedirs(output_dir, exist_ok=True)
    final_video = os.path.join(output_dir, "rendered_animation.mp4")
    fps = get_fps(blend_file, default_fps=24)

    # 1. Search for image frames
    image_exts = {".png", ".jpg", ".jpeg", ".exr", ".tga", ".bmp", ".tif", ".tiff"}
    image_files = find_files_by_ext(download_dir, image_exts)

    if image_files:
        print(f"[Assembler] Found {len(image_files)} image frames in {download_dir}.")
        success = assemble_from_images(image_files, final_video, fps)
        if success and os.path.exists(final_video):
            print(f"✅ Video created successfully: {final_video} ({os.path.getsize(final_video)} bytes)")
        else:
            print("⚠️ Warning: ffmpeg image assembly failed, checking fallback...")

        # Also create a zip archive of all raw frames as backup
        zip_path = os.path.join(output_dir, "all_rendered_frames.zip")
        print(f"[Assembler] Creating backup zip of all {len(image_files)} rendered frames...")
        with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
            for idx, img in enumerate(image_files, start=1):
                ext = os.path.splitext(img)[1].lower()
                zf.write(img, f"frame_{idx:06d}{ext}")
        print(f"✅ Frames archive created: {zip_path}")
        return

    # 2. If no images found, search for video chunks
    video_exts = {".mp4", ".mkv", ".mov", ".avi"}
    video_files = find_files_by_ext(download_dir, video_exts)

    if video_files:
        print(f"[Assembler] Found {len(video_files)} video chunks in {download_dir}.")
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
    print("Listing downloaded_chunks contents for debugging:")
    for root, dirs, files in os.walk(download_dir):
        print(f"  {root}: {files}")


if __name__ == "__main__":
    main()
