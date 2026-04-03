# Unitree Go2 Audio Capture

Get **real microphone audio** from the Unitree Go2 robot.

> **TL;DR**: The Go2's DDS `/audiosender` topic is broken — it sends uninitialized random bytes (white noise). Real audio comes through the **WebRTC audio track** (Opus codec, 48kHz stereo). This repo provides working code to capture it.

## Why This Exists

If you've tried subscribing to `/audiosender` on the Go2 and got noise, you're not alone. We ran 7 independent spectral tests confirming the DDS audio topic is garbage:

| Test | Expected (real audio) | Measured | Verdict |
|------|----------------------|----------|---------|
| Spectral flatness | 0.1–0.5 | 0.994 | White noise |
| Zero-crossing rate | 0.1–0.3 | 0.505 | White noise |
| Dynamic range | 10–20+ dB | 1.8 dB | No signal |
| Byte entropy | < 6 bits | 7.97/8.0 | Uniform random |

The Go2 delivers microphone audio exclusively via its **WebRTC connection** as an Opus-encoded audio track at 48kHz stereo.

## Compatibility

- **Go2 Pro** and **Go2 Edu** — works (has microphone hardware)
- **Go2 Air** — no microphone, audio not available

## Quick Start

### Option 1: Standalone (no ROS 2)

Capture audio to a WAV file with zero ROS dependencies:

```bash
pip install unitree-webrtc-connect numpy sounddevice

python standalone/capture_audio.py --robot-ip 192.168.123.161 --duration 10 --output audio.wav
```

### Option 2: ROS 2 Node

Publishes `Int16MultiArray` on `/audio/raw` at ~50Hz (48kHz mono, 960 samples/frame):

```bash
pip install unitree-webrtc-connect noisereduce

# Run the node
python ros2_node/go2_audio_node.py --ros-args -p robot_ip:=192.168.123.161

# Optional: enable noise reduction
python ros2_node/go2_audio_node.py --ros-args -p robot_ip:=192.168.123.161 -p noise_reduce:=true
```

### Option 3: Shell Scripts

```bash
# Live playback through speakers (with bandpass filter + noise reduction)
./scripts/listen_audio.sh          # default 10x gain
./scripts/listen_audio.sh 20       # 20x gain

# Record to WAV file with spectrum analysis
./scripts/record_audio.sh 10       # record 10 seconds
```

## How It Works

The Go2 runs a WebRTC server. To get audio:

1. **Establish a WebRTC connection** to the robot (SDP offer/answer via HTTP)
2. **Activate the audio channel** by sending `{"type":"aud","data":"on"}` over the SCTP data channel
3. **Receive Opus audio frames** on the WebRTC audio track
4. **Decode to PCM** — 48kHz stereo, 16-bit signed integers, 960 samples per frame

This repo uses the [`unitree-webrtc-connect`](https://github.com/unitreerobotics/unitree_sdk2_python) library which handles the WebRTC negotiation and SCTP data channel correctly.

### Why not just fix the custom WebRTC code?

Many Go2 ROS 2 packages use a custom `go2_connection.py` with a **broken SCTP data channel**. The `{"type":"aud","data":"on"}` message never reaches the robot, so the microphone is never activated. Until that SCTP issue is fixed upstream, using `unitree-webrtc-connect` is the reliable path.

## Audio Format

| Property | Value |
|----------|-------|
| Source codec | Opus (WebRTC) |
| Sample rate | 48,000 Hz |
| Channels | Stereo (mixed to mono in this code) |
| Bit depth | 16-bit signed integer |
| Frame size | 960 samples (~20ms) |
| Publish rate | ~50 Hz |
| ROS 2 topic | `/audio/raw` (Int16MultiArray) |

## Audio Quality Notes

The Go2's internal microphone picks up significant **motor noise** (dominant below 300Hz). For better audio quality:

- **Bandpass filter** (300–3000 Hz) removes motor rumble — included in `listen_audio.sh`
- **Spectral subtraction** learns the noise profile in the first ~1 second, then subtracts it — included in `listen_audio.sh` and optional in the ROS 2 node
- **External USB microphone** on a companion computer (Jetson, etc.) gives much cleaner audio for speech recognition

## Repository Structure

```
go2-audio/
├── README.md
├── standalone/
│   └── capture_audio.py       # No ROS 2 needed — captures to WAV
├── ros2_node/
│   └── go2_audio_node.py      # Full ROS 2 node with noise reduction
├── scripts/
│   ├── listen_audio.sh        # Live playback with filtering
│   └── record_audio.sh        # Record to WAV + spectrum analysis
└── docs/
    └── dds_audio_analysis.md  # Full investigation of why /audiosender is broken
```

## Requirements

- Python 3.8+
- `unitree-webrtc-connect` (pip install)
- `numpy`
- For standalone: `sounddevice`, `scipy` (optional, for WAV recording)
- For ROS 2 node: ROS 2 Humble+, `rclpy`, `std_msgs`
- For noise reduction: `noisereduce`, `scipy`

**numpy version note**: If you also use `cv_bridge`, pin numpy to 1.26.x (`pip install numpy==1.26.4`). The `unitree-webrtc-connect` package pulls in numpy 2.x which is incompatible with `cv_bridge`.

## Troubleshooting

**No audio frames received**
- Verify the robot is powered on and you can ping `192.168.123.161`
- Check you're on the same subnet (192.168.123.x)
- Audio is only available on Go2 **Pro/Edu** models

**Audio is pure noise / white noise**
- You're probably reading from DDS `/audiosender` — that topic is broken
- Use this repo's WebRTC approach instead

**Very quiet audio / only motor noise**
- The internal mic is near the motors — this is expected
- Use the bandpass filter (300–3000Hz) and/or spectral subtraction
- Consider an external USB microphone

## License

MIT

## Acknowledgments

Built on [`unitree-webrtc-connect`](https://github.com/unitreerobotics/unitree_sdk2_python) by Unitree Robotics.
