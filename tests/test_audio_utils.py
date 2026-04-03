import numpy as np

from go2_audio.audio_utils import rms_level, stereo_to_mono


class TestStereoToMono:
    def test_basic_stereo(self):
        # L=100, R=200 -> mono=150
        stereo = np.array([100, 200, 300, 400], dtype=np.int16)
        mono = stereo_to_mono(stereo)
        assert mono.dtype == np.int16
        assert len(mono) == 2
        assert mono[0] == 150
        assert mono[1] == 350

    def test_960_frame(self):
        """Standard Go2 frame: 1920 interleaved -> 960 mono."""
        stereo = np.zeros(1920, dtype=np.int16)
        mono = stereo_to_mono(stereo)
        assert len(mono) == 960
        assert mono.dtype == np.int16

    def test_odd_length_passthrough(self):
        """Odd-length input treated as already mono."""
        data = np.array([1, 2, 3], dtype=np.int16)
        mono = stereo_to_mono(data)
        np.testing.assert_array_equal(mono, data)

    def test_clipping_behavior(self):
        """int32 intermediate prevents int16 overflow during averaging."""
        stereo = np.array([32000, 32000], dtype=np.int16)
        mono = stereo_to_mono(stereo)
        assert mono[0] == 32000  # (32000+32000)//2 = 32000

    def test_negative_values(self):
        stereo = np.array([-1000, 1000], dtype=np.int16)
        mono = stereo_to_mono(stereo)
        assert mono[0] == 0

    def test_2d_input(self):
        """Handles 2D array input (frame.to_ndarray() shape)."""
        stereo = np.array([[100, 200, 300, 400]], dtype=np.int16)
        mono = stereo_to_mono(stereo)
        assert len(mono) == 2


class TestRmsLevel:
    def test_silence(self):
        assert rms_level(np.zeros(960, dtype=np.int16)) == 0

    def test_known_rms(self):
        samples = np.full(960, 1000, dtype=np.int16)
        assert rms_level(samples) == 1000

    def test_positive_result(self):
        samples = np.array([100, -100, 100, -100], dtype=np.int16)
        assert rms_level(samples) == 100
