# 🎨 Blender GitHub Render (20x Parallel Cloud Farm)

Render your Blender animations across 20 simultaneous GitHub Actions cloud runners for free.

## Folder Structure

Store all your Blender project files inside the **`Blender Project/`** folder:

```
├── Blender Project/
│   ├── one.blend
│   ├── two.blend
│   └── 3.blend
├── .github/workflows/
│   └── render-parallel.yml
├── render_chunk.py
├── setup_blender.py
└── summarize_video.py
```

---

## How to Render

1. **Add your `.blend` file:**
   Save or copy your `.blend` file into the `Blender Project/` folder (e.g. `one.blend`).
   Push to GitHub:
   ```bash
   git add "Blender Project/"
   git commit -m "Add project"
   git push
   ```

2. **Start the Render on GitHub:**
   - Go to your repository on GitHub → **Actions** tab.
   - Click **Blender Parallel Render (20x Speed)** on the left.
   - Click **Run workflow**:
     - **`blend_file`**: Type the filename (e.g. `one.blend`, `two.blend`, `3.blend`).
     - **`render_engine`**: `CYCLES` (default for maximum quality).
   - Click **Run workflow**.

3. **Check Specifications & Download:**
   When the run completes, GitHub will display the **Video Information Card**:
   - 📐 **Resolution** (e.g. 1920×1080)
   - ⏱️ **Duration** (e.g. 10 sec, 1 min 30 sec)
   - 🎞️ **Frame Rate** (e.g. 24 fps)
   - 💾 **File Size** (e.g. 14 MB)
   - Download the `.mp4` file directly under the **Artifacts** section!
