# 🎨 Blender GitHub Render (20x Parallel Cloud Farm)

Render your Blender animations across 20 simultaneous GitHub Actions cloud runners for free.

## Folder Structure

Store all your Blender project files directly inside the **`Blender Project/`** folder:

```
├── Blender Project/
│   ├── scene.blend
│   ├── car_animation.blend
│   └── character_walk.blend
├── .github/workflows/
│   └── render-parallel.yml
├── render_chunk.py
└── setup_blender.py
```

You can keep multiple projects here without ever renaming or deleting older projects.

---

## How to Render Any Project

1. **Add your new Blender project:**
   Save or copy your `.blend` file into the `Blender Project/` folder:
   ```bash
   cp /path/to/my_new_project.blend "Blender Project/"
   git add "Blender Project/"
   git commit -m "Add my_new_project.blend"
   git push
   ```
   *(Pushing never triggers a render automatically).*

2. **Run in GitHub Actions:**
   - Go to your repository on GitHub → **Actions** tab.
   - Click **Blender Parallel Render (20x Speed)** on the left.
   - Click **Run workflow**:
     - **`blend_file`**: Type the filename, e.g. `car_animation.blend` (or `auto` to use the first project).
     - **`frame_start`**: `1` (default)
     - **`frame_end`**: `0` (default — auto-detects the full length from your project).
     - **`render_engine`**: `CYCLES` (default for maximum quality) or `BLENDER_EEVEE` or `AUTO`.
   - Click **Run workflow**.

3. **Download Your Video:**
   Once the 20 workers complete, download **`rendered_animation.mp4`** from **Artifacts** at the bottom of the page!
