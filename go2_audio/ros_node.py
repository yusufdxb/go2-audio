#!/usr/bin/env python3
"""
Go2 WebRTC Audio Capture — ROS 2 Node.

Connects to the Go2 robot via the unitree_webrtc_connect library,
receives audio frames from the WebRTC audio track (48kHz stereo Opus),
optionally applies real-time noise reduction, and publishes decoded
mono PCM on /audio/raw as Int16MultiArray.

Message contract
----------------
Topic: /audio/raw
Type:  std_msgs/Int16MultiArray
Layout:
  dim[0]: label="samples", size=960, stride=960
  dim[1]: label="sample_rate", size=48000, stride=0
  dim[2]: label="channels", size=1, stride=0
  data_offset: frame sequence number (monotonic, wraps at 2^31)

Int16MultiArray is used because there is no standard ROS 2 audio message.
The layout dimensions encode the audio contract so consumers can discover
format without hardcoding assumptions. A future version may migrate to
audio_common_msgs/AudioData if available in the target ROS 2 distribution.

Note: unitree_webrtc_connect drops the very first audio frame internally
(webrtc_driver.py line 166) before entering the callback loop.  Frame
numbering here therefore starts at the first frame *delivered* to us.

Usage:
    go2-audio-node --ros-args -p robot_ip:=192.168.123.161
    go2-audio-node --ros-args -p robot_ip:=192.168.123.161 -p noise_reduce:=true
"""

import asyncio
import logging
import os
import threading
import traceback

import rclpy
from rclpy.executors import SingleThreadedExecutor
from rclpy.node import Node
from std_msgs.msg import Int16MultiArray, MultiArrayDimension, MultiArrayLayout
from unitree_webrtc_connect import UnitreeWebRTCConnection, WebRTCConnectionMethod

from go2_audio.audio_utils import rms_level, stereo_to_mono
from go2_audio.denoise import (
    FRAME_SIZE,
    NOISE_LEARN_FRAMES,
    NOISE_LEARN_SECONDS,
    SAMPLE_RATE,
    NoiseReducer,
)

logging.basicConfig(level=logging.WARN)
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

# Pre-built layout — reused for every published message.
_AUDIO_LAYOUT = MultiArrayLayout(
    dim=[
        MultiArrayDimension(label="samples", size=FRAME_SIZE, stride=FRAME_SIZE),
        MultiArrayDimension(label="sample_rate", size=SAMPLE_RATE, stride=0),
        MultiArrayDimension(label="channels", size=1, stride=0),
    ],
    data_offset=0,
)


class Go2AudioNode(Node):
    """Captures audio from Go2 via WebRTC and publishes to /audio/raw."""

    def __init__(self):
        super().__init__("go2_audio_node")

        self.declare_parameter("robot_ip", os.getenv("ROBOT_IP", "192.168.123.161"))
        self.declare_parameter("noise_reduce", False)

        self._robot_ip = self.get_parameter("robot_ip").value
        self._do_noise_reduce = self.get_parameter("noise_reduce").value
        self._audio_pub = self.create_publisher(Int16MultiArray, "/audio/raw", 10)
        self._frame_count = 0
        self._conn = None

        if self._do_noise_reduce:
            self._denoiser = NoiseReducer()
        else:
            self._denoiser = None

        self.get_logger().info(
            f"Go2 Audio Node — robot_ip={self._robot_ip}, noise_reduce={self._do_noise_reduce}"
        )

    async def _on_audio_frame(self, frame):
        self._frame_count += 1

        mono = stereo_to_mono(frame.to_ndarray())

        if self._denoiser is not None:
            out = self._denoiser.process(mono)
            if self._frame_count == NOISE_LEARN_FRAMES + 1:
                self.get_logger().info(
                    f"Noise profile learned from first {NOISE_LEARN_SECONDS}s — reduction active"
                )
        else:
            out = mono

        audio_msg = Int16MultiArray()
        audio_msg.layout = _AUDIO_LAYOUT
        audio_msg.layout.data_offset = self._frame_count
        audio_msg.data = out.tolist()
        self._audio_pub.publish(audio_msg)

        if self._frame_count == 1:
            rms = rms_level(mono)
            self.get_logger().info(
                f"First audio frame: {len(mono)} samples, rate={frame.sample_rate}Hz, RMS={rms}"
            )
        elif self._frame_count % 500 == 0:
            rms = rms_level(out)
            self.get_logger().info(
                f"Audio frame {self._frame_count}: {len(out)} samples, RMS={rms}"
            )

    async def connect_and_stream(self):
        self.get_logger().info(f"Connecting to Go2 at {self._robot_ip}...")

        self._conn = UnitreeWebRTCConnection(
            WebRTCConnectionMethod.LocalSTA,
            ip=self._robot_ip,
        )

        await self._conn.connect()
        self.get_logger().info("WebRTC connected")

        self._conn.audio.add_track_callback(self._on_audio_frame)
        self._conn.datachannel.switchAudioChannel(True)
        self.get_logger().info("Audio channel enabled — waiting for frames")

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
        node.get_logger().info(f"Shutting down. Audio frames: {node._frame_count}")
    except (RuntimeError, OSError) as e:
        node.get_logger().error(f"Fatal: {e}\n{traceback.format_exc()}")
    finally:
        loop.run_until_complete(node.disconnect())
        loop.close()
        executor.shutdown()
        node.destroy_node()
        rclpy.shutdown()


if __name__ == "__main__":
    main()
