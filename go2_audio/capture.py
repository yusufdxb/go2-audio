#!/usr/bin/env python3
"""
Standalone Go2 audio capture — no ROS 2 required.

Connects to the Unitree Go2 via WebRTC, captures microphone audio,
and saves to a WAV file. Optionally plays through speakers in real-time.

Usage:
    python -m go2_audio.capture --robot-ip 192.168.123.161 --duration 10 --output audio.wav
    python -m go2_audio.capture --robot-ip 192.168.123.161 --play  # live playback, Ctrl+C to stop
"""

import argparse
import asyncio
import queue
import signal
import wave

import numpy as np
from unitree_webrtc_connect import UnitreeWebRTCConnection, WebRTCConnectionMethod

from go2_audio.audio_utils import rms_level, stereo_to_mono


class AudioCapture:
    def __init__(self, play=False, store_frames=False):
        self.frames = []
        self.frame_count = 0
        self.sample_rate = 48000
        self.play = play
        self.store_frames = store_frames
        self._stream = None
        self._play_queue = None

        if self.play:
            import sounddevice as sd

            self._play_queue = queue.Queue(maxsize=100)
            self._stream = sd.OutputStream(
                samplerate=self.sample_rate,
                channels=1,
                dtype="int16",
                blocksize=960,
                callback=self._play_callback,
            )
            self._stream.start()

    def _play_callback(self, outdata, frames, time_info, status):
        try:
            chunk = self._play_queue.get_nowait()
            n = min(len(chunk), frames)
            outdata[:n, 0] = chunk[:n]
            if n < frames:
                outdata[n:, 0] = 0
        except queue.Empty:
            outdata[:, 0] = 0

    async def on_audio_frame(self, frame):
        self.frame_count += 1
        mono = stereo_to_mono(frame.to_ndarray())

        if self.store_frames:
            self.frames.append(mono)

        if self.play and self._play_queue is not None:
            try:
                self._play_queue.put_nowait(mono)
            except queue.Full:
                pass

        if self.frame_count == 1:
            rms = rms_level(mono)
            print(f"First audio frame: {len(mono)} samples, rate={frame.sample_rate}Hz, RMS={rms}")

    def save_wav(self, path):
        if not self.frames:
            print("No audio frames captured!")
            return
        pcm = np.concatenate(self.frames)
        with wave.open(path, "w") as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)
            wf.setframerate(self.sample_rate)
            wf.writeframes(pcm.tobytes())
        duration = len(pcm) / self.sample_rate
        print(f"Saved {len(pcm)} samples ({duration:.1f}s) to {path}")

    def stop_playback(self):
        if self._stream:
            self._stream.stop()
            self._stream.close()


async def run(args):
    # Only buffer frames in memory when we need to write them to disk.
    store = bool(args.output)
    capture = AudioCapture(play=args.play, store_frames=store)

    print(f"Connecting to Go2 at {args.robot_ip}...")
    conn = UnitreeWebRTCConnection(
        WebRTCConnectionMethod.LocalSTA,
        ip=args.robot_ip,
    )
    await conn.connect()
    print("WebRTC connected")

    conn.audio.add_track_callback(capture.on_audio_frame)
    conn.datachannel.switchAudioChannel(True)
    print("Audio channel enabled — waiting for frames...")

    if args.duration:
        print(f"Recording for {args.duration}s...")
        await asyncio.sleep(args.duration)
    else:
        print("Streaming live — press Ctrl+C to stop")
        stop = asyncio.Event()
        loop = asyncio.get_event_loop()
        loop.add_signal_handler(signal.SIGINT, stop.set)
        await stop.wait()

    await conn.disconnect()
    capture.stop_playback()

    print(f"Captured {capture.frame_count} frames")

    if args.output:
        capture.save_wav(args.output)


def main():
    parser = argparse.ArgumentParser(description="Capture audio from Unitree Go2")
    parser.add_argument(
        "--robot-ip", default="192.168.123.161", help="Robot IP address (default: 192.168.123.161)"
    )
    parser.add_argument(
        "--duration",
        type=float,
        default=None,
        help="Recording duration in seconds (omit for continuous)",
    )
    parser.add_argument("--output", "-o", default=None, help="Output WAV file path")
    parser.add_argument(
        "--play", action="store_true", help="Play audio through speakers in real-time"
    )
    args = parser.parse_args()

    if not args.output and not args.play:
        args.output = "go2_audio.wav"
        print(f"No --output or --play specified, saving to {args.output}")

    asyncio.run(run(args))


if __name__ == "__main__":
    main()
