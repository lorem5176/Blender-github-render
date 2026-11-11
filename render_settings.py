"""
Blender Render Settings Script
-------------------------------
Called by the GitHub Actions workflow to configure and launch a render.
Applies high-quality settings based on CLI arguments.

Usage (called automatically by the workflow):
  blender --background scene.blend --python render_settings.py -- [options]
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
    parser.add_argument("--engine", type=str, default="CYCLES",
                        choices=["CYCLES", "BLENDER_EEVEE_NEXT"],
                        help="Render engine to use")
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
    """Apply high-quality render settings."""

    # --- Render engine ---
    scene.render.engine = args.engine
    print(f"[Config] Engine: {args.engine}")

    # --- Resolution ---
    scene.render.resolution_x = args.resolution_x
    scene.render.resolution_y = args.resolution_y
    scene.render.resolution_percentage = 100  # full resolution, no downscaling
    print(f"[Config] Resolution: {args.resolution_x}x{args.resolution_y} @ 100%")

    # --- Output ---
    scene.render.filepath = args.output_path
    scene.render.image_settings.file_format = args.output_format
    if args.output_format == "PNG":
        scene.render.image_settings.color_mode = "RGBA"
        scene.render.image_settings.color_depth = "16"  # 16-bit for quality
        scene.render.image_settings.compression = 15
    elif args.output_format == "JPEG":
        scene.render.image_settings.quality = 95
    elif args.output_format == "OPEN_EXR":
        scene.render.image_settings.color_depth = "32"
        scene.render.image_settings.exr_codec = "ZIP"
    elif args.output_format == "FFMPEG":
        scene.render.image_settings.file_format = "FFMPEG"
        scene.render.ffmpeg.format = "MPEG4"
        scene.render.ffmpeg.codec = "H264"
        scene.render.ffmpeg.constant_rate_factor = "HIGH"
        scene.render.ffmpeg.ffmpeg_preset = "GOOD"
    print(f"[Config] Format: {args.output_format}")

    # --- Frame range ---
    scene.frame_start = args.frame_start
    scene.frame_end = args.frame_end
    print(f"[Config] Frames: {args.frame_start} - {args.frame_end}")

    # --- Engine-specific high quality settings ---
    if args.engine == "CYCLES":
        cycles = scene.cycles

        # Samples
        cycles.samples = args.samples
        cycles.preview_samples = 32
        print(f"[Config] Cycles samples: {args.samples}")

        # Denoising (built-in OpenImageDenoise for CPU)
        cycles.use_denoising = True
        cycles.denoiser = "OPENIMAGEDENOISE"
        cycles.denoising_input_passes = "RGB_ALBEDO_NORMAL"
        print("[Config] Denoising: OpenImageDenoise (RGB+Albedo+Normal)")

        # Light paths — high quality bounces
        cycles.max_bounces = 12
        cycles.diffuse_bounces = 8
        cycles.glossy_bounces = 8
        cycles.transmission_bounces = 12
        cycles.volume_bounces = 4
        cycles.transparent_max_bounces = 16
        print("[Config] Light paths: High quality (12 max bounces)")

        # Use CPU (GitHub Actions runners don't have GPUs)
        cycles.device = "CPU"
        # Optimize tile size for CPU rendering
        scene.render.tile_x = 64 if hasattr(scene.render, 'tile_x') else 64
        scene.render.tile_y = 64 if hasattr(scene.render, 'tile_y') else 64
        print("[Config] Device: CPU")

        # Adaptive sampling for efficiency
        cycles.use_adaptive_sampling = True
        cycles.adaptive_threshold = 0.01  # low threshold = high quality
        cycles.adaptive_min_samples = 64
        print("[Config] Adaptive sampling: ON (threshold 0.01)")

        # Clamp for firefly reduction
        cycles.sample_clamp_indirect = 10.0
        print("[Config] Indirect clamp: 10.0")

    elif args.engine == "BLENDER_EEVEE_NEXT":
        eevee = scene.eevee

        # Samples
        eevee.taa_render_samples = args.samples
        print(f"[Config] EEVEE samples: {args.samples}")

        # Shadows — high quality
        eevee.shadow_cube_size = "2048"
        eevee.shadow_cascade_size = "2048"
        eevee.use_shadow_high_bitdepth = True
        eevee.use_soft_shadows = True
        print("[Config] EEVEE shadows: High quality (2048)")

        # Ambient Occlusion
        eevee.use_gtao = True
        eevee.gtao_distance = 1.0
        eevee.gtao_quality = 1.0
        print("[Config] EEVEE AO: Enabled")

        # Screen Space Reflections
        eevee.use_ssr = True
        eevee.use_ssr_halfres = False  # full resolution
        eevee.ssr_quality = 1.0
        eevee.ssr_max_roughness = 0.5
        print("[Config] EEVEE SSR: Full resolution")

    # --- Color management ---
    scene.display_settings.display_device = "sRGB"
    scene.view_settings.view_transform = "Filmic"
    scene.view_settings.look = "None"
    print("[Config] Color: Filmic / sRGB")

    # --- Performance (optimize for CI runner: ~4 CPU cores) ---
    scene.render.threads_mode = "AUTO"
    print("[Config] Threads: Auto")


def main():
    args = parse_args()
    scene = bpy.context.scene

    print("\n" + "=" * 50)
    print("  Applying High-Quality Render Settings")
    print("=" * 50)

    configure_high_quality(scene, args)

    print("\n" + "=" * 50)
    print("  Starting Render...")
    print("=" * 50 + "\n")

    # Render
    if args.frame_start == args.frame_end:
        # Single frame
        scene.frame_set(args.frame_start)
        bpy.ops.render.render(write_still=True)
        print(f"\n✅ Frame {args.frame_start} rendered successfully!")
    else:
        # Animation
        bpy.ops.render.render(animation=True)
        print(f"\n✅ Animation (frames {args.frame_start}-{args.frame_end}) rendered!")


if __name__ == "__main__":
    main()
