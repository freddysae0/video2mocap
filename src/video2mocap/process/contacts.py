"""Foot contact detection and ground estimation.

A foot is in contact when it is close to the ground AND (almost) still. We use hysteresis (separate
enter/exit thresholds) and minimum durations so contacts don't flicker - flicker is what produces
the "skating then popping" look of most video mocap.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from ..motion import Motion
from .filters import lowpass


@dataclass
class ContactConfig:
    height_enter_m: float = 0.05  # foot joint height above its own ground level to start a contact
    height_exit_m: float = 0.08
    speed_enter_mps: float = 0.25  # horizontal speed to start a contact
    speed_exit_mps: float = 0.45
    min_contact_frames: int = 4
    max_gap_frames: int = 2  # gaps shorter than this inside a contact are filled
    use_estimator_contacts: bool = True  # if the backend predicted contacts, combine with them
    # contact DECISIONS are made on a heavily low-passed copy of the foot track (the motion itself is
    # untouched); this keeps residual jitter from breaking a stance into flickering pieces
    detect_cutoff_hz: float = 3.0


def estimate_ground_height(heights: np.ndarray, percentile: float = 5.0) -> float:
    """Ground level of one foot joint from its height track (robust low percentile)."""
    return float(np.percentile(heights, percentile))


def _runs(mask: np.ndarray) -> list[tuple[int, int]]:
    """[start, end) of True runs."""
    m = np.concatenate([[False], mask, [False]]).astype(int)
    d = np.diff(m)
    return list(zip(np.where(d == 1)[0], np.where(d == -1)[0]))


def clean_mask(mask: np.ndarray, min_len: int, max_gap: int) -> np.ndarray:
    mask = mask.copy()
    # fill short gaps
    for s, e in _runs(~mask):
        if s > 0 and e < len(mask) and (e - s) <= max_gap:
            mask[s:e] = True
    # drop short contacts
    for s, e in _runs(mask):
        if (e - s) < min_len:
            mask[s:e] = False
    return mask


def detect_contacts(motion: Motion, foot_joints: list[str], cfg: ContactConfig | None = None,
                    up_axis: int = 1) -> dict[str, np.ndarray]:
    cfg = cfg or ContactConfig()
    gpos, _ = motion.fk()
    horiz = [a for a in range(3) if a != up_axis]
    out: dict[str, np.ndarray] = {}
    for name in foot_joints:
        j = motion.skeleton.index(name)
        p = lowpass(gpos[:, j], motion.fps, cfg.detect_cutoff_hz)
        h = p[:, up_axis] - estimate_ground_height(p[:, up_axis])
        v = np.zeros(len(p))
        v[1:] = np.linalg.norm(np.diff(p[:, horiz], axis=0), axis=1) * motion.fps
        v[0] = v[1] if len(v) > 1 else 0.0
        state = False
        mask = np.zeros(len(p), dtype=bool)
        for t in range(len(p)):
            if state:
                state = h[t] < cfg.height_exit_m and v[t] < cfg.speed_exit_mps
            else:
                state = h[t] < cfg.height_enter_m and v[t] < cfg.speed_enter_mps
            mask[t] = state
        if cfg.use_estimator_contacts and name in motion.contacts:
            # estimator says contact and geometry roughly agrees -> contact
            est = motion.contacts[name] & (h < cfg.height_exit_m * 1.5)
            mask = mask | est
        out[name] = clean_mask(mask, cfg.min_contact_frames, cfg.max_gap_frames)
    return out


def contact_runs(mask: np.ndarray) -> list[tuple[int, int]]:
    return _runs(mask)
