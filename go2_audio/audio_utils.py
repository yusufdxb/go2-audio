"""
Shared audio utility functions for go2_audio.

These are used by both the standalone capture module and the ROS 2 node.
"""

import numpy as np


def stereo_to_mono(interleaved: np.ndarray) -> np.ndarray:
    """Deinterleave stereo int16 samples to mono by averaging channels."""
    flat = interleaved.flatten()
    if flat.shape[0] % 2 == 0:
        left = flat[0::2]
        right = flat[1::2]
        return ((left.astype(np.int32) + right.astype(np.int32)) // 2).astype(np.int16)
    return flat.astype(np.int16)


def rms_level(samples: np.ndarray) -> int:
    return int(np.sqrt(np.mean(samples.astype(np.float64) ** 2)))
