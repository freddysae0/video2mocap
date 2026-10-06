import numpy as np

from video2mocap import quat
from video2mocap.face.attach import resample_take
from video2mocap.face.capture import FaceTake, _fill_gaps
from video2mocap.face.sync import ENV_HZ, detect_clap, offset_by_audio


def _env_with_clap(seconds, clap_s, seed):
    rng = np.random.default_rng(seed)
    e = 0.01 + 0.002 * rng.random(int(seconds * ENV_HZ))
    k = int(clap_s * ENV_HZ)
    e[k:k + 6] = [0.9, 0.6, 0.3, 0.15, 0.08, 0.04]
    return e


def test_clap_detection_and_offset():
    a, b = _env_with_clap(8, 1.25, 0), _env_with_clap(8, 2.40, 1)
    assert abs(detect_clap(a) - 1.25) < 0.011 and abs(detect_clap(b) - 2.40) < 0.011


def test_audio_cross_correlation_offset():
    rng = np.random.default_rng(3)
    speech = np.abs(np.convolve(rng.standard_normal(20 * ENV_HZ), np.ones(20) / 20, "same")) + 0.01
    a = speech[200:200 + 10 * ENV_HZ]
    b = speech[200 + int(1.3 * ENV_HZ):200 + int(1.3 * ENV_HZ) + 10 * ENV_HZ]  # B starts 1.3 s later
    off, conf = offset_by_audio(a, b)
    assert abs(off - (-1.3)) < 0.01 and conf > 0.5  # t_B = t_A - 1.3


def test_gap_fill_and_resample():
    T, K = 30, 52
    C = np.tile(np.linspace(0, 1, T)[:, None], (1, K))
    R = quat.identity((T,))
    valid = np.ones(T, bool)
    valid[10:13] = False
    C[10:13] = np.nan
    R[10:13] = np.nan
    C2, R2 = _fill_gaps(C, R, valid, max_gap=5)
    assert np.allclose(C2[10:13, 0], np.linspace(0, 1, T)[10:13])
    take = FaceTake(30.0, [f"b{k}" for k in range(K)], C2, R2, valid)
    curves, rot, ok = resample_take(take, np.array([0.5, 0.5 + 1 / 60, 5.0]))
    assert np.isclose(curves[0, 0], C2[15, 0]) and np.isclose(curves[1, 0], (C2[15, 0] + C2[16, 0]) / 2)
    assert ok[0] and not ok[2] and curves[2].sum() == 0
