# Unitree Go2 Audio Capture

Capture **real microphone audio** from the Unitree Go2 robot via WebRTC.

> **TL;DR**: The Go2's DDS `/audiosender` topic delivers uninitialized memory (white noise). Real audio comes through the **WebRTC audio track** (Opus codec, 48 kHz stereo). This package provides working code to capture it.

## Why This Exists

The Go2 publishes an `/audiosender` DDS topic that appears to contain audio but actually contains random bytes. Manual spectral analysis confirmed this — see [`docs/dds_audio_analysis.md`](docs/dds_audio_analysis.md) for the full investigation and test results.

The Go2 delivers microphone audio exclusively via its **WebRTC connection** as an Opus-encoded audio track at 48 kHz stereo.

## Compatibility

| Model | Audio | Notes |
|-------|-------|-------|
| Go2 EDU | Yes | Verified on hardware |
| Go2 Pro | Yes | Expected to work (same hardware) |
| Go2 Air | No | No microphone hardware |

## Prerequisites

```bash
# Required for unitree-webrtc-connect (pyaudio dependency)
sudo apt install portaudio19-dev
```

## Install

```bash
pip install -e .                   # core (capture to WAV)
pip install -e ".[playback]"       # + live speaker playback
pip install -e ".[ros]"            # + ROS 2 noise reduction
pip install -e ".[dev]"            # + pytest, ruff
```

## Quick Start

### Standalone capture (no ROS 2)

```bash
# Record 10 seconds to WAV
go2-audio-capture --robot-ip 192.168.123.161 --duration 10 --output audio.wav

# Live playback through speakers
go2-audio-capture --robot-ip 192.168.123.161 --play
```

### ROS 2 node

Publishes `Int16MultiArray` on `/audio/raw` at ~50 Hz (48 kHz mono, 960 samples/frame):

```bash
# Direct
go2-audio-node --ros-args -p robot_ip:=192.168.123.161

# With noise reduction (learns profile from first 2s, then applies)
go2-audio-node --ros-args -p robot_ip:=192.168.123.161 -p noise_reduce:=true

# Via launch file (requires colcon build first — see ROS 2 Package section)
ros2 launch go2_audio audio.launch.py robot_ip:=192.168.123.161 noise_reduce:=true
```

## How It Works

1. **Establish a WebRTC connection** to the robot (SDP offer/answer via HTTP)
2. **Activate the audio channel** by sending `{"type":"aud","data":"on"}` over the SCTP data channel
3. **Receive Opus audio frames** on the WebRTC audio track
4. **Decode to PCM** — 48 kHz stereo, 16-bit signed integers, 960 samples per frame

This package uses [`unitree-webrtc-connect`](https://github.com/unitreerobotics/unitree_sdk2_python) which handles WebRTC negotiation and SCTP correctly. Many community Go2 packages use a custom `go2_connection.py` with a broken SCTP data channel where the audio activation message never reaches the robot.

## Audio Format

| Property | Value |
|----------|-------|
| Source codec | Opus (WebRTC) |
| Sample rate | 48,000 Hz |
| Channels | Stereo (mixed to mono) |
| Bit depth | 16-bit signed integer |
| Frame size | 960 samples (~20 ms) |
| Publish rate | ~50 Hz |
| ROS 2 topic | `/audio/raw` (`Int16MultiArray`) |

### Message metadata

The `Int16MultiArray.layout` encodes the audio contract so consumers can discover the format programmatically:

```
layout.dim[0]: label="samples",    size=960,   stride=960   # frame size
layout.dim[1]: label="sample_rate", size=48000, stride=0     # Hz
layout.dim[2]: label="channels",   size=1,     stride=0     # mono
layout.data_offset: <frame_sequence_number>                  # monotonic counter
```

## Audio Quality Notes

The Go2's internal microphone sits inside the robot body, close to the motors. **Significant motor and mechanical noise is expected and very difficult to fully eliminate.** This is a hardware limitation, not a software bug. Do not expect clean, studio-quality audio from the onboard mic.

What to expect:

- **Motor noise** dominates below ~300 Hz and varies with gait/movement
- **Environmental noise** (fans, wind, footsteps) is also picked up
- Even with noise reduction, residual noise will be audible in most conditions
- Speech recognition accuracy depends heavily on the speaker's distance from the robot and ambient noise level

The built-in noise reduction (`noise_reduce:=true`) uses stationary spectral subtraction, learning the noise profile from the first ~2 seconds of audio. It **reduces** motor hum but **cannot fully remove** it, especially during active locomotion when the noise profile changes.

**For high-quality speech capture, use an external USB microphone** mounted on a companion computer (Jetson, etc.). This physically separates the mic from the motor noise source and produces significantly cleaner audio for ASR pipelines.

## Development

```bash
pip install -e ".[dev,ros]"
make test        # runs pytest (handles ROS plugin conflicts automatically)
make lint        # ruff check + format check
```

To use a specific Python interpreter: `make test PYTHON=python3.11`

**Why `make test` instead of `pytest` directly?** On machines with ROS 2 installed, system-wide pytest plugins (`launch_testing`, `ament_*`) auto-load and crash pytest due to hook incompatibilities. The Makefile sets `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1` to block them. On non-ROS machines or in CI, bare `python3 -m pytest` works fine.

## ROS 2 Package

This repo is structured as both a pip-installable Python package and a ROS 2 `ament_python` package. To build with colcon:

```bash
cd ~/ros2_ws/src
ln -s /path/to/go2-audio .
cd ~/ros2_ws
colcon build --packages-select go2_audio
source install/setup.bash
ros2 launch go2_audio audio.launch.py
```

## Repository Structure

```
go2-audio/
├── go2_audio/              # Python package
│   ├── __init__.py
│   ├── audio_utils.py      # Shared stereo-to-mono, RMS utilities
│   ├── capture.py          # Standalone capture (no ROS 2)
│   ├── denoise.py          # NoiseReducer + audio constants (no ROS deps)
│   └── ros_node.py         # ROS 2 node
├── launch/
│   └── audio.launch.py     # ROS 2 launch file
├── tests/
│   ├── test_audio_utils.py
│   ├── test_capture.py
│   ├── test_noise_reducer.py
│   └── test_ros_node.py    # Layout, frame contract, sequence tests
├── docs/
│   └── dds_audio_analysis.md
├── conftest.py             # ROS plugin conflict warning
├── setup.py                # Shim for colcon/ament_python
├── pyproject.toml
├── package.xml
├── Makefile
└── LICENSE
```

## Requirements

See `pyproject.toml` for the full dependency list.

**System dependency**: `portaudio19-dev` (for `pyaudio`, pulled in by `unitree-webrtc-connect`).

**numpy version note**: If you also use `cv_bridge`, pin numpy to 1.26.x (`pip install numpy==1.26.4`). The `unitree-webrtc-connect` package may pull in numpy 2.x which is incompatible with `cv_bridge`.

## Troubleshooting

**No audio frames received**
- Verify the robot is powered on and you can ping `192.168.123.161`
- Check you're on the same subnet (192.168.123.x)
- Audio is only available on Go2 **Pro/Edu** models

**Audio is pure noise / white noise**
- You're probably reading from DDS `/audiosender` — that topic is broken
- Use this package's WebRTC approach instead

**Very quiet audio / only motor noise**
- The internal mic is inside the robot body near the motors — significant noise is expected and cannot be fully eliminated
- Enable noise reduction (`noise_reduce:=true`) to reduce steady-state motor hum
- For speech recognition or other quality-sensitive use cases, use an external USB microphone on a companion computer

**pytest crashes on ROS 2 machine**
- Use `make test` instead of bare `pytest`
- Or: `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 python3 -m pytest tests/ -v`

## License

MIT
