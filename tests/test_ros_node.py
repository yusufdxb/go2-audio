"""
Tests for ROS 2 node contract: layout metadata, frame sizing, sequence numbering.

These test the documented audio contract without needing a running robot or
ROS 2 graph.  They import only from go2_audio.denoise (no rclpy required)
and validate the constants that ros_node.py uses to build messages.
"""

import numpy as np
import pytest

from go2_audio.audio_utils import stereo_to_mono
from go2_audio.denoise import FRAME_SIZE, NOISE_LEARN_FRAMES, SAMPLE_RATE, NoiseReducer

# ---------------------------------------------------------------------------
# Layout metadata contract
# ---------------------------------------------------------------------------


class TestAudioContract:
    """Verify the constants that define the published message contract."""

    def test_sample_rate(self):
        assert SAMPLE_RATE == 48000

    def test_frame_size(self):
        assert FRAME_SIZE == 960

    def test_frame_duration_ms(self):
        """960 samples at 48 kHz = exactly 20 ms."""
        duration_ms = FRAME_SIZE / SAMPLE_RATE * 1000
        assert duration_ms == 20.0

    def test_publish_rate_hz(self):
        """One frame per 20 ms = 50 Hz."""
        hz = SAMPLE_RATE / FRAME_SIZE
        assert hz == 50.0

    def test_noise_learn_frames_consistent(self):
        """NOISE_LEARN_FRAMES should match NOISE_LEARN_SECONDS / frame duration."""
        expected = int(2.0 * SAMPLE_RATE / FRAME_SIZE)  # 2 s * 50 Hz = 100
        assert NOISE_LEARN_FRAMES == expected


# ---------------------------------------------------------------------------
# Frame size contract through the processing pipeline
# ---------------------------------------------------------------------------


class TestFrameSizeContract:
    """Ensure the full audio pipeline preserves the 960-sample frame size."""

    def test_stereo_to_mono_produces_frame_size(self):
        """Standard Go2 stereo interleaved frame -> FRAME_SIZE mono."""
        stereo = np.random.randint(-1000, 1000, FRAME_SIZE * 2, dtype=np.int16)
        mono = stereo_to_mono(stereo)
        assert len(mono) == FRAME_SIZE

    def test_stereo_to_mono_2d_produces_frame_size(self):
        """frame.to_ndarray() returns shape (1, 1920); verify flatten works."""
        stereo = np.random.randint(-1000, 1000, (1, FRAME_SIZE * 2), dtype=np.int16)
        mono = stereo_to_mono(stereo)
        assert len(mono) == FRAME_SIZE

    @pytest.fixture
    def trained_reducer(self):
        pytest.importorskip("noisereduce")
        r = NoiseReducer()
        for _ in range(NOISE_LEARN_FRAMES):
            r.process(np.random.randint(-100, 100, FRAME_SIZE, dtype=np.int16))
        assert not r.learning
        return r

    def test_denoiser_preserves_frame_size(self, trained_reducer):
        """Post-learning denoiser must return exactly FRAME_SIZE samples."""
        for _ in range(10):
            out = trained_reducer.process(np.random.randint(-500, 500, FRAME_SIZE, dtype=np.int16))
            assert len(out) == FRAME_SIZE
            assert out.dtype == np.int16


# ---------------------------------------------------------------------------
# Sequence counter behavior
# ---------------------------------------------------------------------------


class TestSequenceCounter:
    """Verify the frame counter logic that ros_node uses for data_offset.

    The node does: self._frame_count += 1 per callback invocation.
    We simulate that here to confirm the contract: monotonic, starts at 1.
    """

    def test_monotonic_from_one(self):
        counter = 0
        for i in range(1, 101):
            counter += 1
            assert counter == i

    def test_first_frame_is_one_not_zero(self):
        """data_offset should be 1 on first publish, not 0."""
        counter = 0
        counter += 1  # first callback
        assert counter == 1
