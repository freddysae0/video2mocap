"""v2m command line.

  v2m run      VIDEO --out DIR [--fast] [--fbx] [--max-people N] full pipeline (backend + post + review)
  v2m post     RAW.npz --rig NAME --out CLEAN.npz                post-process one motion
  v2m review   MOTION.npz --out SHEET.png [--track-dir DIR]      key-frame contact sheet for review
  v2m edit     MOTION.npz EDITS.json --out EDITED.npz            apply reviewer edits (then re-run post)
  v2m export   MOTION.npz --bvh OUT.bvh [--fbx OUT.fbx]          BVH (and FBX through Blender)
  v2m metrics  MOTION.npz                                        quality numbers as JSON
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .io.bvh import write_bvh
from .motion import Motion
from .pipeline import postprocess
from .process.edit import apply_edits, load_edits
from .qa.metrics import report
from .qa.review import render_contact_sheet, select_keyframes
from .rigs import PROFILES


def _rig(name: str):
    if name not in PROFILES:
        sys.exit(f"unknown rig '{name}'. known: {', '.join(PROFILES)}")
    return PROFILES[name]


def cmd_post(a) -> None:
    raw = Motion.load(a.motion)
    out, metrics = postprocess(raw, _rig(a.rig))
    out.save(a.out)
    Path(a.out).with_suffix(".metrics.json").write_text(json.dumps(metrics, indent=2))
    print(json.dumps(metrics["final"], indent=2))


def cmd_review(a) -> None:
    m = Motion.load(a.motion)
    frames = select_keyframes(m, max_frames=a.max_frames)
    video_frames, camera, kp2d = None, None, None
    if a.track_dir:
        from .review_io import load_review_inputs

        video_frames, camera, kp2d = load_review_inputs(a.track_dir, frames)
    path = render_contact_sheet(m, frames, a.out, video_frames, camera, kp2d, title=Path(a.motion).name)
    print(json.dumps({"sheet": str(path), "frames": frames}))


def cmd_edit(a) -> None:
    m = apply_edits(Motion.load(a.motion), load_edits(a.edits))
    m.save(a.out)
    print(f"wrote {a.out}")


def cmd_export(a) -> None:
    m = Motion.load(a.motion)
    if a.bvh:
        write_bvh(m, a.bvh)
        print(f"wrote {a.bvh}")
    if a.fbx:
        from .blender import bvh_to_fbx

        src = a.bvh or str(Path(a.fbx).with_suffix(".bvh"))
        if not a.bvh:
            write_bvh(m, src)
        bvh_to_fbx(src, a.fbx, blender=a.blender)
        print(f"wrote {a.fbx}")


def cmd_metrics(a) -> None:
    print(json.dumps(report(Motion.load(a.motion)), indent=2))


def cmd_run(a) -> None:
    from .run import run_video

    extra = ["--no_imgfeat"] if a.fast else []
    run_video(a.video, a.out, static_cam=not a.moving_cam, max_people=a.max_people, backend=a.backend,
              extra=extra, fbx=a.fbx)


def main(argv: list[str] | None = None) -> None:
    p = argparse.ArgumentParser(prog="v2m", description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd", required=True)

    s = sub.add_parser("run")
    s.add_argument("video")
    s.add_argument("--out", required=True)
    s.add_argument("--moving-cam", action="store_true",
                   help="camera moves (needs visual odometry; not supported yet - static is assumed)")
    s.add_argument("--fbx", action="store_true", help="also export FBX through Blender")
    s.add_argument("--fast", action="store_true", help="GEM-X keypoints-only mode: less memory, lower quality")
    s.add_argument("--max-people", type=int, default=8)
    s.add_argument("--backend", default="gemx")
    s.set_defaults(fn=cmd_run)

    s = sub.add_parser("post")
    s.add_argument("motion")
    s.add_argument("--rig", default="soma77")
    s.add_argument("--out", required=True)
    s.set_defaults(fn=cmd_post)

    s = sub.add_parser("review")
    s.add_argument("motion")
    s.add_argument("--out", required=True)
    s.add_argument("--track-dir", help="track folder with video frames/camera/2D keypoints for overlays")
    s.add_argument("--max-frames", type=int, default=16)
    s.set_defaults(fn=cmd_review)

    s = sub.add_parser("edit")
    s.add_argument("motion")
    s.add_argument("edits")
    s.add_argument("--out", required=True)
    s.set_defaults(fn=cmd_edit)

    s = sub.add_parser("export")
    s.add_argument("motion")
    s.add_argument("--bvh")
    s.add_argument("--fbx")
    s.add_argument("--blender", help="path to blender executable (auto-detected if omitted)")
    s.set_defaults(fn=cmd_export)

    s = sub.add_parser("metrics")
    s.add_argument("motion")
    s.set_defaults(fn=cmd_metrics)

    a = p.parse_args(argv)
    a.fn(a)


if __name__ == "__main__":
    main()
