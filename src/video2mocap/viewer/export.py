"""Build viewer data (viewer.json) for a run folder produced by `v2m run`."""
from __future__ import annotations

import json
import shutil
from pathlib import Path

import numpy as np

from ..backends.gemx import load_track
from ..motion import Motion

COLORS = ["#ff5a4e", "#3fa2ff", "#ffc23d", "#53d18b", "#c27dff", "#ff8fd0", "#5ee0e0", "#c9c9c9"]


def _clean_to_track_world(clean: Motion, gpos: np.ndarray) -> np.ndarray:
    """Undo the rigid ops applied after estimation so the track's camera can project the clean motion:
    clean = ground_shift(shared_world(raw))  ->  x_track = M^T (x_clean - shift - b)."""
    shift = np.zeros(3)
    for h in clean.meta.get("history", []):
        if h.get("op") == "place_on_ground":
            shift += np.asarray(h["shift"], float)
    sw = clean.meta.get("shared_world", {"M": np.eye(3).tolist(), "b": [0, 0, 0]})
    M, b = np.asarray(sw["M"], float), np.asarray(sw["b"], float)
    return (gpos - shift - b) @ M


def build_viewer_data(run_dir: str | Path) -> Path:
    run_dir = Path(run_dir).resolve()
    run = json.loads((run_dir / "run.json").read_text())
    src = Path(run["video"]) if Path(run["video"]).exists() else None
    if src is None:  # path recorded inside WSL (/mnt/c/...)
        v = run["video"]
        if v.startswith("/mnt/"):
            src = Path(f"{v[5].upper()}:/{v[7:]}")
    video_name = "source" + (src.suffix if src else ".mp4")
    if src and src.exists() and not (run_dir / video_name).exists():
        shutil.copy2(src, run_dir / video_name)

    people = []
    for i, tr in enumerate(run["tracks"]):
        tdir = run_dir / tr["dir"]
        clean = Motion.load(tdir / "clean.npz")
        _, cam, _ = load_track(tdir)
        gpos, _ = clean.fk()
        uv, z = cam.project(_clean_to_track_world(clean, gpos))
        uv = np.where((z > 0)[..., None], uv, np.nan)
        contacts = {k: v.astype(int).tolist() for k, v in clean.contacts.items()}
        people.append({
            "id": i, "name": f"Persona {i + 1}", "color": COLORS[i % len(COLORS)],
            "frame_start": tr["start"], "frame_end": tr["end"],
            "parents": clean.skeleton.parents.tolist(), "names": clean.skeleton.names,
            # mm / px integers keep the file small
            "pos": np.round(gpos * 1000).astype(int).tolist(),
            "uv": np.nan_to_num(np.round(uv), nan=-99999).astype(int).tolist(),
            "contacts": contacts,
            "metrics": json.loads((tdir / "metrics.json").read_text())["final"] if (tdir / "metrics.json").exists() else {},
        })
    data = {"video": video_name, "fps": run["fps"], "frames": run["frames"], "width": run["width"],
            "height": run["height"], "people": people}
    out = run_dir / "viewer.json"
    out.write_text(json.dumps(data, separators=(",", ":")))
    shutil.copy2(Path(__file__).with_name("index.html"), run_dir / "index.html")
    return out


def serve(run_dir: str | Path, port: int = 8765, open_browser: bool = True) -> None:
    import functools
    import http.server
    import webbrowser

    build_viewer_data(run_dir)
    handler = functools.partial(http.server.SimpleHTTPRequestHandler, directory=str(Path(run_dir).resolve()))
    with http.server.ThreadingHTTPServer(("127.0.0.1", port), handler) as httpd:
        url = f"http://127.0.0.1:{port}/index.html"
        print(f"[v2m] viewer at {url}  (Ctrl+C to stop)")
        if open_browser:
            webbrowser.open(url)
        httpd.serve_forever()
