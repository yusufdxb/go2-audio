#!/bin/bash
# Live Go2 audio playback through PC speakers.
#
# Subscribes to /audio/raw, applies bandpass filter (300-3000Hz) to remove
# motor noise, learns noise spectrum from first ~1s, then applies spectral
# subtraction for cleaner audio.
#
# Usage:
#   ./listen_audio.sh         # default 10x gain
#   ./listen_audio.sh 20      # 20x gain
#
# Prerequisites:
#   pip install numpy sounddevice scipy
#   The go2_audio_node must be running and publishing on /audio/raw
#
# Press Ctrl+C to stop.

# Source your ROS 2 environment (adjust paths as needed)
if [ -f /opt/ros/humble/setup.bash ]; then
    source /opt/ros/humble/setup.bash
fi

GAIN=${1:-10}
echo "Gain: ${GAIN}x  (pass a number as arg to change, e.g. ./listen_audio.sh 20)"

python3 -c "
import rclpy, numpy as np, sounddevice as sd, queue, collections
from scipy.signal import butter, sosfilt
from std_msgs.msg import Int16MultiArray

GAIN = $GAIN

audio_q = queue.Queue(maxsize=50)
rclpy.init()
node = rclpy.create_node('audio_listener')
count = [0]
detected_rate = [0]

# Bandpass 300-3000Hz — speech frequencies only, removes motor rumble
bp_sos = butter(4, [300, 3000], btype='band', fs=48000, output='sos')
bp_zi = [np.zeros(2) for _ in range(bp_sos.shape[0])]

# Spectral subtraction: learn noise spectrum from first 50 frames (~1s), then subtract
NFFT = 1024
noise_frames = []
noise_spectrum = [None]
NOISE_LEARN = 50

def spectral_subtract(signal):
    if noise_spectrum[0] is None:
        return signal
    n = len(signal)
    padded = np.zeros(NFFT)
    padded[:min(n, NFFT)] = signal[:min(n, NFFT)]
    spec = np.fft.rfft(padded)
    mag = np.abs(spec)
    phase = np.angle(spec)
    clean_mag = np.maximum(mag - noise_spectrum[0] * 1.5, 0.0)
    clean = np.fft.irfft(clean_mag * np.exp(1j * phase))
    return clean[:n]

def cb(msg):
    global bp_zi
    count[0] += 1
    samples = np.array(msg.data, dtype=np.int16)
    if len(samples) < 2000 and np.max(np.abs(samples)) == 0:
        return

    filtered, bp_zi = sosfilt(bp_sos, samples.astype(np.float64), zi=bp_zi)

    if len(noise_frames) < NOISE_LEARN:
        padded = np.zeros(NFFT)
        n = min(len(filtered), NFFT)
        padded[:n] = filtered[:n]
        noise_frames.append(np.abs(np.fft.rfft(padded)))
        if len(noise_frames) == NOISE_LEARN:
            noise_spectrum[0] = np.mean(noise_frames, axis=0)
            print(f'Noise spectrum learned — subtraction active', flush=True)

    cleaned = spectral_subtract(filtered)
    amplified = np.clip(cleaned * GAIN, -32768, 32767).astype(np.int16)

    try:
        audio_q.put_nowait(amplified)
    except queue.Full:
        try: audio_q.get_nowait()
        except queue.Empty: pass
        try: audio_q.put_nowait(amplified)
        except queue.Full: pass

    if count[0] == 1:
        n = len(samples)
        detected_rate[0] = 48000 if n >= 480 else 8000
        rms = int(np.sqrt(np.mean(samples.astype(np.float64)**2)))
        print(f'Receiving audio! {n} samples/frame, rate={detected_rate[0]}Hz, raw RMS={rms}', flush=True)

node.create_subscription(Int16MultiArray, '/audio/raw', cb, 10)

MAX_BUF_SAMPLES = 48000 * 4 // 10  # 400ms buffer
buf = collections.deque()
buf_samples = [0]

def audio_cb(outdata, frames, time_info, status):
    while not audio_q.empty():
        try:
            chunk = audio_q.get_nowait()
            buf.append(chunk)
            buf_samples[0] += len(chunk)
        except queue.Empty:
            break
    while buf_samples[0] > MAX_BUF_SAMPLES and len(buf) > 1:
        dropped = buf.popleft()
        buf_samples[0] -= len(dropped)
    filled = 0
    while filled < frames and buf:
        chunk = buf[0]
        need = frames - filled
        if len(chunk) <= need:
            outdata[filled:filled+len(chunk), 0] = chunk
            filled += len(chunk)
            buf_samples[0] -= len(chunk)
            buf.popleft()
        else:
            outdata[filled:frames, 0] = chunk[:need]
            buf[0] = chunk[need:]
            buf_samples[0] -= need
            filled = frames
    if filled < frames:
        outdata[filled:, 0] = 0

print('Waiting for audio on /audio/raw...', flush=True)
while rclpy.ok() and detected_rate[0] == 0:
    rclpy.spin_once(node, timeout_sec=0.1)

rate = detected_rate[0] if detected_rate[0] > 0 else 48000
blocksize = rate // 50

print(f'Playing Go2 audio ({rate}Hz mono, {GAIN}x gain, bandpass + spectral subtraction)', flush=True)
print(f\"Don't talk for the first 1 second — learning noise profile...\", flush=True)
stream = sd.OutputStream(samplerate=rate, channels=1, dtype='int16', blocksize=blocksize, callback=audio_cb)
stream.start()
try:
    while rclpy.ok():
        rclpy.spin_once(node, timeout_sec=0.005)
except KeyboardInterrupt:
    pass
stream.stop()
stream.close()
print(f'Played {count[0]} audio frames.', flush=True)
rclpy.shutdown()
"
