# 🎨 Blender GitHub Render (20x Parallel Cloud Farm)

Render your Blender animations in parallel using 20 simultaneous GitHub Actions cloud runners for free — no local CPU or GPU heat needed.

## How It Works

- **20 Parallel Cloud Workers:** Your total frames are divided equally across 20 runners (e.g. 100 frames = 5 frames/runner; 2,000 frames = 100 frames/runner).
- **Auto Engine Detection:** Automatically uses whatever render engine is saved in your `.blend` file (EEVEE, Cycles), or lets you override it.
- **Auto Frame Range:** Automatically detects the start and end frames from your project file if set to `0`.
- **Automatic MP4 Video:** Once all 20 workers finish rendering, a final job collects all frames and compiles them into a 1080p `rendered_animation.mp4` file.
- **Manual Trigger Only:** Pushing commits will **never** start a render automatically. You trigger renders when you are ready.

---

## Quick Start

### 1. Update / Push your `.blend` file

Save your Blender file as `scene.blend` in this folder:

```bash
git add scene.blend
git commit -m "Update scene"
git push
```
*(Pushing will NOT trigger a build automatically).*

### 2. Launch the 20x Parallel Render

1. Go to your repo on GitHub: **Actions** tab
2. Click **Blender Parallel Render (20x Speed)** on the left sidebar
3. Click **Run workflow**:
   - `frame_end`: Enter `0` to auto-detect full length, or enter any specific number (e.g. `100`, `2000`).
   - `render_engine`: `AUTO` (uses the engine saved in your `.blend` file).
   - `samples`: `48` (clean & fast with denoising).
4. Click **Run workflow**.

### 3. Download Your Video

Once all 20 workers complete:
1. Open the completed run.
2. Scroll to **Artifacts** at the bottom.
3. Download `final-animation-<number>.zip` — inside will be **`rendered_animation.mp4`**!
