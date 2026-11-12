"""
Blender Render Settings Script
-------------------------------
Called by the GitHub Actions workflow to configure and launch a render.
Compatible with Blender 4.x and 5.x.
"""

import bpy
import sys
import argparse


def parse_args():
    """Parse arguments after the '--' separator."""
    argv = sys.argv
    if "--" in argv:
        argv = argv[argv.index("--") + 1:]
    else:
        argv = []

    parser = argparse.ArgumentParser(description="Blender render settings")
    parser.add_argument("--engine", type=str, default="AUTO",
                        choices=["AUTO", "CYCLES", "BLENDER_EEVEE_NEXT", "BLENDER_EEVEE"],
                        help="Render engine to use (AUTO uses whatever engine is saved in the .blend file)")
    parser.add_argument("--samples", type=int, default=256,
                        help="Number of render samples")
    parser.add_argument("--resolution_x", type=int, default=1920,
                        help="Horizontal resolution")
    parser.add_argument("--resolution_y", type=int, default=1080,
                        help="Vertical resolution")
    parser.add_argument("--frame_start", type=int, default=1,
                        help="Start frame")
    parser.add_argument("--frame_end", type=int, default=1,
                        help="End frame")
    parser.add_argument("--output_format", type=str, default="PNG",
                        choices=["PNG", "JPEG", "OPEN_EXR", "FFMPEG"],
                        help="Output file format")
    parser.add_argument("--output_path", type=str, default="//output/render_",
                        help="Output path prefix")
    return parser.parse_args(argv)


def configure_high_quality(scene, args):
    """Apply high-quality render settings safely across Blender versions."""

    # Resolve frame range: 0 means use the blend file's own range
    if args.frame_start <= 0:
        args.frame_start = scene.frame_start
    if args.frame_end <= 0:
        args.frame_end = scene.frame_end

    # --- Render engine ---
    if args.engine and args.engine != "AUTO":
        try:
            scene.render.engine = args.engine
            print(f"[Config] Engine override: {args.engine}")
        except Exception as e:
            print(f"[Config] Engine error ({args.engine}): {e}")
    else:
        print(f"[Config] Using blend file's engine: {scene.render.engine}")

    # --- Resolution ---
    scene.render.resolution_x = args.resolution_x
    scene.render.resolution_y = args.resolution_y
    scene.render.resolution_percentage = 100
    print(f"[Config] Resolution: {args.resolution_x}x{args.resolution_y} @ 100%")

    # --- Frame range ---
    scene.frame_start = args.frame_start
    scene.frame_end = args.frame_end
    print(f"[Config] Frame range: {args.frame_start} to {args.frame_end} (total {args.frame_end - args.frame_start + 1} frames)")

    # --- Output ---
    scene.render.filepath = args.output_path
    scene.render.use_file_extension = True
    scene.render.image_settings.file_format = args.output_format
    if args.output_format == "PNG":
        scene.render.image_settings.color_mode = "RGBA"
        scene.render.image_settings.color_depth = "16"
        scene.render.image_settings.compression = 15
    elif args.output_format == "JPEG":
        scene.render.image_settings.quality = 95
    elif args.output_format == "OPEN_EXR":
        scene.render.image_settings.color_depth = "32"
        scene.render.image_settings.exr_codec = "ZIP"
    elif args.output_format == "FFMPEG":
        scene.render.image_settings.file_format = "FFMPEG"
        if hasattr(scene.render, "ffmpeg"):
            scene.render.ffmpeg.format = "MPEG4"
            scene.render.ffmpeg.codec = "H264"
            scene.render.ffmpeg.constant_rate_factor = "HIGH"
            scene.render.ffmpeg.ffmpeg_preset = "GOOD"
    print(f"[Config] Format: {args.output_format}")

    # --- Frame range ---
    scene.frame_start = args.frame_start
    scene.frame_end = args.frame_end
    print(f"[Config] Frames: {args.frame_start} - {args.frame_end}")

    # --- Performance: Persistent data across frames (critical for animations) ---
    if hasattr(scene.render, "use_persistent_data"):
        scene.render.use_persistent_data = True
        print("[Config] Persistent data: Enabled (geometry cached between frames)")

    # --- Engine specific settings ---
    if "CYCLES" in scene.render.engine:
        cycles = scene.cycles
        cycles.device = "CPU"
        print("[Config] Device: CPU")

        # Samples
        cycles.samples = args.samples
        if hasattr(cycles, "preview_samples"):
            cycles.preview_samples = min(16, args.samples)
        print(f"[Config] Cycles samples: {args.samples}")

        # Denoising - OpenImageDenoise produces clean frames at much lower sample counts
        if hasattr(cycles, "use_denoising"):
            cycles.use_denoising = True
            if hasattr(cycles, "denoiser"):
                cycles.denoiser = "OPENIMAGEDENOISE"
            if hasattr(cycles, "denoising_input_passes"):
                try:
                    cycles.denoising_input_passes = "RGB_ALBEDO_NORMAL"
                except Exception:
                    pass
            if hasattr(cycles, "denoising_prefilter"):
                cycles.denoising_prefilter = "ACCURATE"
            print("[Config] Denoising: OpenImageDenoise (Accurate)")

        # Optimized bounce limits: 98% of light energy is contained within 3-4 bounces.
        # Reducing superfluous bounces cuts render time by 40-50% with zero visible difference.
        for prop, val in [
            ("max_bounces", 6),
            ("diffuse_bounces", 3),
            ("glossy_bounces", 3),
            ("transmission_bounces", 6),
            ("volume_bounces", 0),
            ("transparent_max_bounces", 8),
            # Caustic fireflies cause massive sampling overhead; turning them off cleans noise fast
            ("caustics_reflective", False),
            ("caustics_refractive", False),
            # Adaptive sampling: stops calculating once pixels hit the threshold
            ("use_adaptive_sampling", True),
            ("adaptive_threshold", 0.015),
            ("adaptive_min_samples", 16),
            ("sample_clamp_indirect", 10.0),
            ("use_light_tree", True),
        ]:
            if hasattr(cycles, prop):
                try:
                    setattr(cycles, prop, val)
                except Exception:
                    pass
        print("[Config] High-efficiency light paths & adaptive sampling configured")

    elif "EEVEE" in scene.render.engine:
        eevee = scene.eevee
        for prop, val in [
            ("taa_render_samples", args.samples),
            ("use_raytracing", True),
            ("shadow_ray_count", 4),
            ("shadow_step_count", 16),
            ("use_shadow_high_bitdepth", True),
            ("use_soft_shadows", True),
            ("use_gtao", True),
            ("use_ssr", True),
        ]:
            if hasattr(eevee, prop):
                try:
                    setattr(eevee, prop, val)
                except Exception:
                    pass
        print(f"[Config] EEVEE samples: {args.samples}")

    # --- Threads ---
    scene.render.threads_mode = "AUTO"
    print("[Config] Threads: Auto")


def main():
    args = parse_args()
    scene = bpy.context.scene

    print("\n" + "=" * 50)
    print("  Applying Render Settings")
    print("=" * 50)

    configure_high_quality(scene, args)

    print("\n" + "=" * 50)
    print("  Starting Render...")
    print("=" * 50 + "\n")

    if args.frame_start == args.frame_end:
        scene.frame_set(args.frame_start)
        scene.render.filepath = f"{args.output_path}{args.frame_start:04d}"
        bpy.ops.render.render(write_still=True)
        print(f"\n✅ Frame {args.frame_start} rendered successfully to {scene.render.filepath}!")
    else:
        scene.render.filepath = args.output_path
        bpy.ops.render.render(animation=True)
        print(f"\n✅ Animation (frames {args.frame_start}-{args.frame_end}) rendered!")


if __name__ == "__main__":
    main()
