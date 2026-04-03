"""
Noise reduction for Go2 audio frames.

Separated from ros_node.py so it can be tested without rclpy or
unitree_webrtc_connect installed.
"""

import numpy as np

SAMPLE_RATE = 48000
FRAME_SIZE = 960
NOISE_LEARN_SECONDS = 2.0
NOISE_LEARN_FRAMES = int(NOISE_LEARN_SECONDS * SAMPLE_RATE / FRAME_SIZE)


class NoiseReducer:
    """Real-time noise reducer using noisereduce (stationary mode).

    Learns the noise profile from the first few seconds of audio,
    then applies per-frame stationary noise reduction.  Helps remove
    the Go2's motor noise (dominant below 300 Hz).

    Frame contract: one FRAME_SIZE-sample input always produces one
    FRAME_SIZE-sample output.
    """

    def __init__(self):
        import noisereduce  # noqa: F401 — import check

        self._noise_frames = []
        self._noise_clip = None
        self._learning = True

    def _learn_noise(self, mono: np.ndarray):
        self._noise_frames.append(mono.copy())
        if len(self._noise_frames) >= NOISE_LEARN_FRAMES:
            self._noise_clip = np.concatenate(self._noise_frames).astype(np.float32)
            self._learning = False
            self._noise_frames = []

    @property
    def learning(self) -> bool:
        return self._learning

    def process(self, mono: np.ndarray) -> np.ndarray:
        import noisereduce as nr

        if self._learning:
            self._learn_noise(mono)
            return mono

        reduced = nr.reduce_noise(
            y=mono.astype(np.float32),
            sr=SAMPLE_RATE,
            y_noise=self._noise_clip,
            stationary=True,
            prop_decrease=0.6,
            n_fft=min(len(mono), 1024),
            freq_mask_smooth_hz=500,
        )
        return np.clip(reduced, -32768, 32767).astype(np.int16)
