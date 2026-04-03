#!/usr/bin/env python3
"""
Go2 WebRTC Audio Capture — ROS 2 Node.

Connects to the Go2 robot via the unitree_webrtc_connect library,
receives audio frames from the WebRTC audio track (48kHz stereo Opus),
optionally applies real-time noise reduction, and publishes decoded
mono PCM on /audio/raw as Int16MultiArray.

Usage:
    python go2_audio_node.py --ros-args -p robot_ip:=192.168.123.161
    python go2_audio_node.py --ros-args -p robot_ip:=192.168.123.161 -p noise_reduce:=true
"""

import asyncio
import logging
import os
import threading

import numpy as np

import rclpy
from rclpy.node import Node
from rclpy.executors import SingleThreadedExecutor
from std_msgs.msg import Int16MultiArray

from unitree_webrtc_connect import UnitreeWebRTCConnection, WebRTCConnectionMethod

logging.basicConfig(level=logging.WARN)
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

SAMPLE_RATE = 48000
NOISE_LEARN_SECONDS = 2.0
NOISE_LEARN_FRAMES = int(NOISE_LEARN_SECONDS * SAMPLE_RATE / 960)


class NoiseReducer:
    """Real-time noise reducer using noisereduce (stationary mode).

    Learns the noise profile from the first few seconds of audio,
    then applies per-chunk stationary noise reduction. This helps
    remove the Go2's motor noise (dominant below 300Hz).
    """

    def __init__(self):
        import noisereduce  # noqa: F401 — import check
        self._noise_frames = []
        self._noise_clip = None
        self._learning = True
        self._buffer = np.array([], dtype=np.int16)
        self._chunk_size = SAMPLE_RATE // 5  # 200ms chunks

    def _learn_noise(self, mono: np.ndarray):
        self._noise_frames.append(mono.copy())
        if len(self._noise_frames) >= NOISE_LEARN_FRAMES:
            self._noise_clip = np.concatenate(self._noise_frames).astype(np.float32)
            self._learning = False
            self._noise_frames = []

    def process(self, mono: np.ndarray) -> np.ndarray:
        import noisereduce as nr

        if self._learning:
            self._learn_noise(mono)
            return mono

        self._buffer = np.concatenate([self._buffer, mono])
        if len(self._buffer) < self._chunk_size:
            return np.zeros(len(mono), dtype=np.int16)

        chunk = self._buffer[:self._chunk_size].astype(np.float32)
        self._buffer = self._buffer[self._chunk_size:]

        reduced = nr.reduce_noise(
            y=chunk,
            sr=SAMPLE_RATE,
            y_noise=self._noise_clip,
            stationary=True,
            prop_decrease=0.6,
            n_fft=2048,
            freq_mask_smooth_hz=500,
        )
        return np.clip(reduced, -32768, 32767).astype(np.int16)


class Go2AudioNode(Node):
    """Captures audio from Go2 via WebRTC and publishes to /audio/raw."""

    def __init__(self):
        super().__init__('go2_audio_node')

        self.declare_parameter('robot_ip', os.getenv('ROBOT_IP', '192.168.123.161'))
        self.declare_parameter('noise_reduce', False)

        self._robot_ip = self.get_parameter('robot_ip').value
        self._do_noise_reduce = self.get_parameter('noise_reduce').value
        self._audio_pub = self.create_publisher(Int16MultiArray, '/audio/raw', 10)
        self._frame_count = 0
        self._conn = None

        if self._do_noise_reduce:
            self._denoiser = NoiseReducer()
        else:
            self._denoiser = None

        self.get_logger().info(
            f'Go2 Audio Node — robot_ip={self._robot_ip}, '
            f'noise_reduce={self._do_noise_reduce}')

    async def _on_audio_frame(self, frame):
        self._frame_count += 1

        # frame.to_ndarray() → shape (1, 1920) for 48kHz stereo interleaved
        audio_data = frame.to_ndarray()

        # Deinterleave stereo → mono
        flat = audio_data.flatten()
        if flat.shape[0] % 2 == 0:
            left = flat[0::2]
            right = flat[1::2]
            mono = ((left.astype(np.int32) + right.astype(np.int32)) // 2).astype(np.int16)
        else:
            mono = flat.astype(np.int16)

        if self._denoiser is not None:
            out = self._denoiser.process(mono)
            if self._frame_count == NOISE_LEARN_FRAMES + 1:
                self.get_logger().info(
                    f'Noise profile learned from first {NOISE_LEARN_SECONDS}s — '
                    f'reduction active')
        else:
            out = mono

        if len(out) > 0 and np.any(out != 0):
            audio_msg = Int16MultiArray()
            audio_msg.data = out.tolist()
            self._audio_pub.publish(audio_msg)

        if self._frame_count == 1:
            rms = int(np.sqrt(np.mean(mono.astype(np.float64) ** 2)))
            self.get_logger().info(
                f'First audio frame: {len(mono)} samples, '
                f'rate={frame.sample_rate}Hz, RMS={rms}')
        elif self._frame_count % 500 == 0:
            rms = int(np.sqrt(np.mean(out.astype(np.float64) ** 2)))
            self.get_logger().info(
                f'Audio frame {self._frame_count}: '
                f'{len(out)} samples, RMS={rms}')

    async def connect_and_stream(self):
        self.get_logger().info(f'Connecting to Go2 at {self._robot_ip}...')

        self._conn = UnitreeWebRTCConnection(
            WebRTCConnectionMethod.LocalSTA,
            ip=self._robot_ip,
        )

        await self._conn.connect()
        self.get_logger().info('WebRTC connected')

        self._conn.audio.add_track_callback(self._on_audio_frame)
        self._conn.datachannel.switchAudioChannel(True)
        self.get_logger().info('Audio channel enabled — waiting for frames')

        while rclpy.ok():
            await asyncio.sleep(1.0)

    async def disconnect(self):
        if self._conn:
            await self._conn.disconnect()


def main():
    rclpy.init()
    node = Go2AudioNode()

    executor = SingleThreadedExecutor()
    executor.add_node(node)
    spin_thread = threading.Thread(target=executor.spin, daemon=True)
    spin_thread.start()

    loop = asyncio.new_event_loop()
    try:
        loop.run_until_complete(node.connect_and_stream())
    except KeyboardInterrupt:
        node.get_logger().info(
            f'Shutting down. Audio frames: {node._frame_count}')
    except Exception as e:
        node.get_logger().error(f'Fatal: {e}')
    finally:
        loop.run_until_complete(node.disconnect())
        loop.close()
        executor.shutdown()
        node.destroy_node()
        rclpy.shutdown()


if __name__ == '__main__':
    main()
