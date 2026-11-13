#!/usr/bin/env python3
"""
Inspects the final rendered MP4 video and writes a clean, detailed
specification summary for the user in GitHub Actions.
"""

import sys
import os
import re
import json
import subprocess


def format_duration(seconds):
    if seconds <= 0:
        return "0s"
    mins = int(seconds // 60)
    secs = int(seconds % 60)
    millis = int((seconds - int(seconds)) * 10)
    if mins > 0:
        return f"{mins} min {secs} sec"
    if secs > 0:
        return f"{secs}.{millis} sec" if millis > 0 else f"{secs} sec"
    return f"{seconds:.2f} sec"


def load_metadata(final_output_dir):
    for candidate in [
        os.path.join(final_output_dir, "render_metadata.json"),
        "downloaded_chunks/render_metadata.json",
        "output/render_metadata.json",
        "render_metadata.json"
    ]:
        if os.path.exists(candidate):
            try:
                with open(candidate, "r") as fp:
                    return json.load(fp)
            except Exception:
                pass
    return {}


def main():
    video_path = sys.argv[1] if len(sys.argv) > 1 else "final_output/rendered_animation.mp4"
    project_arg = sys.argv[2] if len(sys.argv) > 2 else "AUTO"
    engine_arg = sys.argv[3] if len(sys.argv) > 3 else "CYCLES"

    final_dir = os.path.dirname(video_path) or "final_output"
    meta = load_metadata(final_dir)

    project_name = meta.get("project_name") or (os.path.basename(project_arg) if project_arg != "AUTO" else "Blender Animation")
    engine_name = meta.get("engine") or engine_arg
    meta_fps = meta.get("fps") or 24
    meta_w = meta.get("resolution_x") or 1920
    meta_h = meta.get("resolution_y") or 1080
    meta_frames = meta.get("total_frames") or 0

    if not os.path.exists(video_path):
        print(f"Notice: Video {video_path} not found. Checking for rendered frames archive...")
        zip_path = os.path.join(final_dir, "all_rendered_frames.zip")
        if os.path.exists(zip_path):
            size_mb = os.path.getsize(zip_path) / (1024 * 1024)
            print(f"Frames archive found: {zip_path} ({size_mb:.2f} MB)")
            summary_env = os.environ.get("GITHUB_STEP_SUMMARY")
            if summary_env:
                with open(summary_env, "a") as f:
                    f.write(f"""# 🎨 Render Complete: Frames Archive

Your rendered frames have been preserved in **all_rendered_frames.zip** ({size_mb:.2f} MB).
Download it from the **Artifacts** section above!
""")
        else:
            print("Notice: No final video or frames archive found.")
        sys.exit(0)

    # File size in MB
    size_bytes = os.path.getsize(video_path)
    size_mb = size_bytes / (1024 * 1024)

    # Use ffprobe to get exact video specs
    width = meta_w
    height = meta_h
    fps = str(meta_fps)
    duration = 0.0
    frames = meta_frames

    try:
        proc = subprocess.run([
            "ffprobe", "-v", "error",
            "-select_streams", "v:0",
            "-show_entries", "stream=width,height,r_frame_rate,nb_frames,duration",
            "-of", "default=noprint_wrappers=1",
            video_path
        ], stdout=subprocess.PIPE, text=True, timeout=15)

        for line in proc.stdout.splitlines():
            if line.startswith("width="):
                width = int(line.split("=")[1])
            elif line.startswith("height="):
                height = int(line.split("=")[1])
            elif line.startswith("r_frame_rate="):
                raw_fps = line.split("=")[1]
                if "/" in raw_fps:
                    num, den = raw_fps.split("/")
                    if float(den) > 0:
                        fps = str(round(float(num) / float(den)))
                else:
                    fps = raw_fps
            elif line.startswith("duration="):
                try:
                    duration = float(line.split("=")[1])
                except Exception:
                    pass
            elif line.startswith("nb_frames="):
                try:
                    frames = int(line.split("=")[1])
                except Exception:
                    pass
    except Exception as e:
        print(f"Notice: ffprobe inspection ({e})")

    # Fallback duration calculation
    fps_float = float(fps) if fps and float(fps) > 0 else 24.0
    if duration <= 0 and frames > 0:
        duration = frames / fps_float
    elif frames <= 0 and duration > 0:
        frames = int(round(duration * fps_float))

    dur_str = format_duration(duration)

    summary_text = f"""
======================================================================
  🎬 RENDER COMPLETE: OUTPUT VIDEO SPECIFICATIONS
======================================================================
  📁 Project File:         {project_name}
  📁 Video Output File:    {os.path.basename(video_path)}
  📐 Resolution:           {width} x {height}
  ⏱️ Duration:             {dur_str} ({duration:.2f}s)
  🎞️ Frame Rate:           {fps} fps
  🖼️ Total Frames:         {frames} frames rendered
  💾 Download File Size:   {size_mb:.2f} MB
  🚀 Render Engine:        {engine_name} (rendered across 20 parallel cloud runners)
======================================================================
"""
    print(summary_text)

    # Markdown output for GitHub Actions summary page
    md_summary = f"""# 🎬 Render Complete: Video Information

Here are the exact specifications of the video file you are downloading to your Mac:

| Specification | Output Video Detail |
| :--- | :--- |
| 📁 **File Name** | `{os.path.basename(video_path)}` |
| 📁 **Source Project** | `{project_name}` |
| 📐 **Video Resolution** | **{width} × {height}** |
| ⏱️ **Video Duration** | **{dur_str}** ({duration:.1f}s) |
| 🎞️ **Frame Rate** | **{fps} fps** |
| 🖼️ **Total Frames Rendered** | **{frames} frames** |
| 💾 **Video File Size** | **{size_mb:.2f} MB** |
| 🚀 **Render Engine** | **{engine_name}** (20 parallel cloud runners) |

---
### ⬇️ How to Download:
Scroll to the **Artifacts** section at the top of this run and download **`final-animation`**. Inside will be **`{os.path.basename(video_path)}`** ready to play!
"""

    summary_env = os.environ.get("GITHUB_STEP_SUMMARY")
    if summary_env:
        with open(summary_env, "a") as f:
            f.write(md_summary)


if __name__ == "__main__":
    main()
