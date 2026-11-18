# Portfolio

Source for https://olegna27.github.io

- `src/pages/*.html`: page bodies with a JSON header
- `src/media/`: images, video, figures, 3D model
- `build.py`: builds `docs/` (what GitHub Pages serves)

```
python3 -I build.py
python3 -m http.server 8000 --directory docs
```

`tools/` converts a STEP assembly to the GLB used by the 3D viewer (`uv run --python 3.12 --with "cadquery-ocp==7.7.2" python tools/step2glb.py in.step out.glb 3.0 1.2`, then `tools/patch_glb.py`).
