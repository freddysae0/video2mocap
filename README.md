# video2mocap

**Video → production-quality skeletal animation for Blender and Unreal Engine.**
Multi-person, world-grounded, foot-locked, and reviewable by a human *or an AI agent* that can look at
key frames and correct the motion with precise, declarative edits.

> Status: **early (v0.1)**. The post-processing core, BVH/FBX export and the review/edit loop are
> implemented and tested. The first estimator backend (NVIDIA GEM-X) is being integrated.

## Why another one?

Video mocap tools exist (Move.ai, QuickMagic, DeepMotion, Rokoko Vision, FreeMoCap, …) but either
they are closed/cloud, or the open research models behind them (WHAM, GVHMR, TRAM, PromptHMR…) are
built on the SMPL body model and research datasets whose licenses **forbid commercial use**. Games
need motion they can ship. Our goals, in order:

1. **Faithful.** The animation must be what the video shows: no foot skating, no jitter, correct
   world trajectory and root motion. Quality is measured, not eyeballed (see *Metrics*).
2. **License-clean by default.** The default pipeline only uses code and weights that allow
   commercial use. Research-only backends can be plugged in, but are clearly marked.
3. **Multi-person.** Every person in the video gets their own track and animation, in one shared
   world frame.
4. **Correctable.** Every result comes with key-frame review sheets and can be fixed with a JSON list
   of edits that is applied deterministically and recorded in the file's history.
5. **Engine-ready.** BVH and FBX that import cleanly in Blender and Unreal (verified by an automated
   round-trip test), plus Unreal retargeting helpers.

## Pipeline

```
video ─► detect + track people ─► per-person 3D estimator (backend) ─► raw motion (.npz)
                                                                          │
           ┌──────────────────────────────────────────────────────────────┘
           ▼
   smooth (zero-phase) ─► contacts ─► ground ─► foot lock (IK) ─► metrics
           │
           ▼
   key-frame review sheet (video + skeleton overlay, front/side views)
           │            ▲
           ▼            │  edits.json  (human or AI reviewer)
       apply edits ─────┘
           │
           ▼
   BVH ─► Blender ─► FBX ─► Unreal (IK Retargeter → your skeleton)
```

The estimator always sees **every** frame (temporal models need dense input; that is what keeps the
motion faithful). *Key frames* are chosen for **review**: extreme poses, low-confidence frames and
frames with high reprojection error.

## Backends

| Backend | Code / weights / body model | Commercial use | Notes |
|---|---|---|---|
| **GEM-X** (NVIDIA, default) | Apache-2.0 / NVIDIA Open Model License / SOMA (Apache-2.0) | ✅ | 77 joints incl. hands & face, world-space, moving camera. Its image-feature stage uses SAM-3D-Body weights (SAM License — read the note in [docs/LICENSES.md](docs/LICENSES.md)); a keypoint-only mode avoids them. |
| research backends (planned: GVHMR, PromptHMR) | SMPL/SMPL-X based | ❌ research only | For comparison and prototyping. Outputs are tagged `license: research-only`. |

See [docs/RESEARCH.md](docs/RESEARCH.md) for the full survey (2024–2026) and why we chose this.

## Quick start

```bash
# core (Windows / Linux / macOS)
uv venv && uv pip install -e ".[dev]"
pytest

# post-process, review, edit, export a motion
v2m post   raw.npz --rig soma77 --out clean.npz
v2m review clean.npz --out sheet.png
v2m edit   clean.npz edits.json --out fixed.npz
v2m export fixed.npz --bvh fixed.bvh --fbx fixed.fbx     # FBX through headless Blender

# GEM-X backend (Linux or WSL2 with an NVIDIA GPU)
bash backends/gemx/install_wsl.sh
v2m run video.mp4 --out runs/clip01
```

## Metrics

Every run writes `metrics.json` (raw → before foot-lock → final):

| metric | meaning |
|---|---|
| `foot_skate_cm_s` | horizontal speed of feet while in contact (0 = perfect) |
| `jitter_m_s3` | mean jerk of all joints (compare runs; lower = smoother) |
| `hf_energy_ratio` | share of motion energy above 12 Hz (estimator noise lives there) |
| `penetration_ratio` | frames with a foot more than 1 cm under the ground |
| `reproj_px` | 2D reprojection error against detected keypoints (faithfulness to the video) |

Tests use synthetic motions with known ground truth, e.g. a clean motion must come out of the
filters essentially unchanged (< 1.5 cm anywhere), and foot locking must reduce skating by > 10× on a
drifting stance.

## The review loop (human or AI)

`v2m review` renders a contact sheet of key frames. A reviewer compares them with the video and
writes edits:

```json
[
  {"op": "rotate", "joint": "LeftForeArm", "frames": [118, 126], "euler_deg": [0, 0, -12], "falloff": 6,
   "note": "elbow over-bent vs video at f120"},
  {"op": "set_contact", "joint": "LeftToeBase", "frames": [200, 231], "value": true},
  {"op": "trim", "frames": [12, 640]}
]
```

Edits ease in/out (`falloff`) so they never pop, and each one is stored in the motion's history.
See [docs/REVIEW_LOOP.md](docs/REVIEW_LOOP.md).

## Repository layout

```
src/video2mocap/   core library (motion format, filters, contacts, IK, foot lock, edits, QA, BVH, CLI)
backends/gemx/     installer + runner for NVIDIA GEM-X (runs in its own venv, Linux/WSL2)
scripts/blender/   headless Blender scripts (BVH→FBX, verification)
scripts/unreal/    Unreal Editor Python helpers (import + retarget)
tests/             unit + integration tests (synthetic ground truth, Blender round-trip)
docs/              research survey, architecture, licenses, review loop
```

## License

Apache-2.0 for this repository. Backends and model weights keep their own licenses — see
[docs/LICENSES.md](docs/LICENSES.md). You are responsible for checking them for your use.
