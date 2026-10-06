"""Headless Blender bridge: BVH -> FBX ready for Unreal (Blender imports BVH natively)."""
from __future__ import annotations

import glob
import os
import shutil
import subprocess
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "blender" / "bvh_to_fbx.py"


def find_blender(explicit: str | None = None) -> str:
    if explicit:
        return explicit
    if os.environ.get("BLENDER"):
        return os.environ["BLENDER"]
    found = shutil.which("blender")
    if found:
        return found
    candidates = sorted(glob.glob(r"C:\Program Files\Blender Foundation\Blender *\blender.exe"), reverse=True)
    candidates += ["/Applications/Blender.app/Contents/MacOS/Blender"]
    for c in candidates:
        if Path(c).exists():
            return c
    raise FileNotFoundError("Blender not found: pass --blender or set BLENDER")


def bvh_to_fbx(bvh: str, fbx: str, blender: str | None = None, fps: float | None = None) -> None:
    exe = find_blender(blender)
    cmd = [exe, "--background", "--factory-startup", "--python", str(SCRIPT), "--", str(Path(bvh).resolve()),
           str(Path(fbx).resolve())]
    if fps:
        cmd += ["--fps", str(fps)]
    res = subprocess.run(cmd, capture_output=True, text=True)
    if res.returncode != 0 or not Path(fbx).exists():
        raise RuntimeError(f"Blender export failed:\n{res.stdout[-3000:]}\n{res.stderr[-3000:]}")
