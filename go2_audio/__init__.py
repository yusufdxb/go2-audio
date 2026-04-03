"""
go2_audio — Capture real microphone audio from the Unitree Go2 robot via WebRTC.

The Go2's DDS /audiosender topic delivers uninitialized noise; real audio is
available exclusively through the WebRTC audio track (Opus, 48 kHz stereo).
This package provides both a standalone capture tool and a ROS 2 node.
"""

__version__ = "0.1.0"
__author__ = "Yusuf Guenena"
__email__ = "yusuf.a.guenena@gmail.com"

__all__ = ["__version__"]
