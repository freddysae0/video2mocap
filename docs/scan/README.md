# Scan: photos / video → textured 3D mesh

```bash
v2m scan photos_folder/ --out runs/scan_bench          # or a video file
```
Stages (resumable; each skips if its output exists):
1. **ingest** – sharp, non-redundant images (from photos, or sharpest frame every 0.33 s of a video)
2. **sfm** – camera poses with COLMAP (BSD-3), then gravity alignment (Manhattan world)
3. **mvs** – dense cloud → mesh → refine → texture with OpenMVS (AGPL-3, run as an external program;
   its outputs are not covered by the AGPL)
4. **report** – registered images, reprojection error, triangles, textures (`report.json`)

Output: `model/scene_textured.obj` + texture atlas. Up axis is **−Y** (COLMAP camera convention);
`scripts/blender/render_mesh_preview.py` renders turntable views with the right orientation.

Tools: COLMAP 4.2.1 CUDA build and OpenMVS 2.4.0 (Windows) in `~/tools`, or set `COLMAP` and
`OPENMVS_DIR`. RealityScan (Epic; free under 1 M USD revenue) is planned as the high-quality backend.

Verified on the openMVS sample (11 photos): 11/11 registered, 0.56 px reprojection error, 68 k
triangles, 4.5 min on an RTX 3050. Known issue: OpenMVS 2.4.0 Windows seam levelling blackens
textures, so it is disabled.

Next: people/vehicle masking + face/plate blur, delighting and PBR maps, FBX/glTF export at real
scale with Nanite-ready LODs, review sheets (renders next to the photos), RealityScan backend.
See [CAPTURE.md](CAPTURE.md) for how to shoot.
