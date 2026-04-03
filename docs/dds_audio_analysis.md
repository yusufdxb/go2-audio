# Why Go2's DDS `/audiosender` Topic Is Broken

> **Reproducibility note**: The spectral tests described below were performed
> manually during initial investigation. The analysis scripts are not included
> in this repository. The results are documented here for reference but should
> be treated as one-time empirical findings, not automated reproducible tests.

## Summary

The Unitree Go2 robot publishes an `/audiosender` topic via DDS that appears to contain audio data. **It does not.** The topic contains uninitialized random bytes — effectively white noise. Real microphone audio is only available through the robot's WebRTC interface.

## Evidence

We captured 10 seconds of data from `/audiosender` and ran 7 independent statistical tests. Every test confirms the data is random noise, not audio:

### Test Results

| # | Test | What It Measures | Expected (Real Audio) | Measured | Interpretation |
|---|------|------------------|-----------------------|----------|----------------|
| 1 | **Spectral flatness** | How "white" the spectrum is (1.0 = perfectly flat) | 0.1–0.5 | **0.994** | Near-perfect white noise |
| 2 | **Zero-crossing rate** | How often the signal crosses zero | 0.1–0.3 | **0.505** | Maximum randomness (coin flip) |
| 3 | **Dynamic range** | Difference between loudest and quietest moments | 10–20+ dB | **1.8 dB** | No variation — no signal |
| 4 | **Byte entropy** | Randomness of raw byte values | < 6 bits/byte | **7.97/8.0** | All bytes equally likely |
| 5 | **Unique byte values** | How many of 256 possible values appear | Small subset | **255/256** | Nearly all values used |
| 6 | **Crest factor** | Peak-to-RMS ratio | 1.4–8.0 | **3.12** | Matches Gaussian noise |
| 7 | **Spectral stationarity** | How much the spectrum changes over time | Variable | **0.55 dB** | Nothing changes — static noise |

### What This Means

- The data has maximum entropy — it's indistinguishable from `urandom`
- There is zero temporal structure (no speech, no motor hum, no anything)
- The spectral flatness of 0.994 means the "audio" has equal energy at all frequencies
- A real microphone signal — even in a noisy environment — would show dominant frequency bands, time-varying energy, and much lower entropy

## Root Cause

The Go2's audio pipeline works as follows:

1. The robot's internal microphone feeds into the **WebRTC server** running on the robot
2. Audio is encoded as **Opus** (48kHz stereo) and delivered via WebRTC audio tracks
3. The DDS `/audiosender` topic exists but is **never populated with real data** — it contains whatever was in that memory buffer at allocation time

### Why does `/audiosender` exist?

Likely a placeholder or legacy topic from an earlier firmware version. The Unitree SDK2 documentation does not reference it for audio capture — only the WebRTC interface is documented for media streaming.

## The Fix

To get real audio from the Go2:

1. Establish a WebRTC connection to the robot
2. Send `{"type":"aud","data":"on"}` via the SCTP data channel to activate the microphone
3. Receive Opus audio frames on the WebRTC audio track
4. Decode to PCM: 48kHz stereo, 16-bit signed integers

The [`unitree-webrtc-connect`](https://github.com/unitreerobotics/unitree_sdk2_python) library handles all of this. See the main [README](../README.md) for usage.

### Verified Real Audio

After switching to WebRTC:

```
First audio frame: 960 samples, rate=48000Hz, RMS=780
Spectral flatness: 0.009 (highly tonal — real audio!)
Dominant frequencies: 208Hz, 648Hz, 906Hz, 1296Hz
```

Spectral flatness dropped from 0.994 (white noise) to 0.009 (structured audio) — confirming real microphone data.

## Common Pitfall: Broken SCTP in Custom WebRTC Code

Many Go2 ROS 2 packages include a custom `go2_connection.py` that handles WebRTC. These implementations typically have a **broken SCTP data channel** — the `{"type":"aud","data":"on"}` activation message is never delivered to the robot, so the microphone stays off even when WebRTC video works.

Symptoms:
- WebRTC video works fine
- Audio track exists but receives silence or no frames
- No error messages — it just silently fails

Solution: Use the official `unitree-webrtc-connect` library, which has a working SCTP implementation.
