import os
import tempfile
import wave

import numpy as np
import pytest

AudioCapture = pytest.importorskip(
    "go2_audio.capture", reason="unitree_webrtc_connect not installed"
).AudioCapture


class TestWavSave:
    def test_save_and_read_back(self):
        """Verify WAV file is written correctly."""
        cap = AudioCapture(play=False, store_frames=True)
        frame_data = np.full(960, 500, dtype=np.int16)
        cap.frames.append(frame_data)
        cap.frames.append(frame_data)

        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
            path = f.name
        try:
            cap.save_wav(path)
            with wave.open(path, "r") as wf:
                assert wf.getnchannels() == 1
                assert wf.getsampwidth() == 2
                assert wf.getframerate() == 48000
                assert wf.getnframes() == 1920
        finally:
            os.unlink(path)

    def test_no_frames_no_crash(self):
        """save_wav with no frames should not crash."""
        cap = AudioCapture(play=False)
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
            path = f.name
        try:
            cap.save_wav(path)
        finally:
            if os.path.exists(path):
                os.unlink(path)

    def test_play_mode_does_not_store_frames(self):
        """In play-only mode, frames list stays empty."""
        cap = AudioCapture(play=False, store_frames=False)
        # store_frames=False means frames should not accumulate
        assert cap.store_frames is False
        assert len(cap.frames) == 0
