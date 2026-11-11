# 🎨 Blender GitHub Render

Render Blender projects for free using GitHub Actions — no GPU or local compute needed.

## Quick Start

### 1. Push your `.blend` file

Copy your Blender project file into this repo root (name it `scene.blend` or update the workflow):

```bash
cp /path/to/your/project.blend scene.blend
git add .
git commit -m "Add scene"
git push
```

### 2. Trigger a render

**Option A — Automatic:** Every push to `main` triggers a render of `scene.blend` with default settings.

**Option B — Manual (recommended):** Go to your repo → **Actions** → **Blender Render** → **Run workflow**, and configure:

| Parameter      | Default          | Description                              |
| -------------- | ---------------- | ---------------------------------------- |
| `blend_file`   | `scene.blend`    | Path to your `.blend` file               |
| `render_engine`| `CYCLES`         | `CYCLES` or `BLENDER_EEVEE_NEXT`        |
| `samples`      | `256`            | Render samples (higher = better)         |
| `resolution_x` | `1920`           | Width in pixels                          |
| `resolution_y` | `1080`           | Height in pixels                         |
| `frame_start`  | `1`              | First frame to render                    |
| `frame_end`    | `1`              | Last frame (same as start = single image)|
| `output_format`| `PNG`            | `PNG`, `JPEG`, `OPEN_EXR`, or `FFMPEG`  |

### 3. Download your render

Once the workflow finishes:
1. Go to **Actions** → click the completed run
2. Scroll to **Artifacts**
3. Download `blender-render-<run-number>.zip`

## High-Quality Settings Applied Automatically

The render script (`render_settings.py`) applies these high-quality defaults:

- **Full resolution** (100%, no downscaling)
- **16-bit PNG** output with RGBA
- **Cycles:** OpenImageDenoise, 12 max bounces, adaptive sampling (0.01 threshold), firefly clamping
- **EEVEE:** High-res shadows (2048), full-res SSR, ambient occlusion
- **Filmic** color management

## Limits & Tips

| Aspect               | Limit                                      |
| --------------------- | ------------------------------------------ |
| **Max run time**      | ~6 hours per job                           |
| **CPU**               | 4 cores (GitHub-hosted runner)             |
| **RAM**               | ~16 GB                                     |
| **GPU**               | ❌ None (CPU rendering only)              |
| **File size**         | Use Git LFS for files > 50 MB             |
| **Free tier (public)**| 2,000 minutes/month                        |
| **Free tier (private)**| 500 minutes/month                         |

### Tips for faster renders
- Use **EEVEE** instead of Cycles for faster (but less realistic) renders
- Lower samples to `128` for test renders, increase to `512+` for final
- Enable **adaptive sampling** (already configured) to skip converged pixels
- Reduce resolution for previews
- For animations, split frame ranges across multiple workflow runs

## File Structure

```
├── .github/workflows/
│   └── render.yml          # GitHub Actions workflow
├── render_settings.py      # Blender Python render config
├── scene.blend             # ← Your Blender file goes here
├── .gitattributes          # Git LFS tracking rules
├── .gitignore
└── README.md
```

## Large Files (Git LFS)

`.blend` files are often large. This repo is pre-configured with Git LFS. Set it up:

```bash
# Install Git LFS (one-time)
brew install git-lfs     # macOS
git lfs install

# Then just commit normally — .blend files auto-tracked via .gitattributes
git add scene.blend
git commit -m "Add scene"
git push
```

> **Note:** GitHub free accounts get 1 GB of LFS storage and 1 GB/month bandwidth.
> For larger projects, consider compressing textures or packing them into the `.blend` file.
