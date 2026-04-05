"""Smoke tests for package imports and metadata.

These catch packaging regressions (e.g., missing __version__, broken imports)
without needing hardware or ROS 2.
"""


class TestImportSurface:
    def test_version_is_set(self):
        from go2_audio import __version__

        assert __version__
        assert __version__ != "0.0.0"
        assert "UNKNOWN" not in __version__

    def test_audio_utils_importable(self):
        from go2_audio.audio_utils import rms_level, stereo_to_mono

        assert callable(stereo_to_mono)
        assert callable(rms_level)

    def test_denoise_importable(self):
        from go2_audio.denoise import FRAME_SIZE, SAMPLE_RATE, NoiseReducer

        assert SAMPLE_RATE == 48000
        assert FRAME_SIZE == 960
        assert callable(NoiseReducer)

    def test_capture_importable(self):
        """capture module requires unitree_webrtc_connect at import time."""
        import importlib

        spec = importlib.util.find_spec("go2_audio.capture")
        assert spec is not None, "go2_audio.capture module not found"

    def test_ros_node_module_exists(self):
        """ros_node module spec should be findable even if rclpy is missing."""
        import importlib

        spec = importlib.util.find_spec("go2_audio.ros_node")
        assert spec is not None, "go2_audio.ros_node module not found"
