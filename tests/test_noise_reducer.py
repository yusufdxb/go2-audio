import numpy as np
import pytest

pytest.importorskip("noisereduce")

from go2_audio.denoise import FRAME_SIZE, NOISE_LEARN_FRAMES, NoiseReducer  # noqa: E402


class TestNoiseReducer:
    """Test NoiseReducer frame cadence contract."""

    @pytest.fixture
    def reducer(self):
        return NoiseReducer()

    def test_learning_phase_passthrough(self, reducer):
        """During learning, output equals input."""
        frame = np.random.randint(-1000, 1000, FRAME_SIZE, dtype=np.int16)
        out = reducer.process(frame)
        np.testing.assert_array_equal(out, frame)
        assert out.dtype == np.int16

    def test_learning_flag(self, reducer):
        """learning property reflects internal state."""
        assert reducer.learning is True
        for _ in range(NOISE_LEARN_FRAMES):
            reducer.process(np.random.randint(-100, 100, FRAME_SIZE, dtype=np.int16))
        assert reducer.learning is False

    def test_output_frame_size_matches_input(self, reducer):
        """After learning, output must be same size as input."""
        for _ in range(NOISE_LEARN_FRAMES + 50):
            frame = np.random.randint(-100, 100, FRAME_SIZE, dtype=np.int16)
            out = reducer.process(frame)
            assert len(out) == FRAME_SIZE, f"Expected {FRAME_SIZE} samples, got {len(out)}"
            assert out.dtype == np.int16
