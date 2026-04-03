#!/bin/bash
# Record Go2 audio to WAV file with spectrum analysis.
#
# Usage:
#   ./record_audio.sh          # default 5 seconds
#   ./record_audio.sh 10       # record 10 seconds
#
# Prerequisites:
#   pip install numpy scipy
#   The go2_audio_node must be running and publishing on /audio/raw
#
# Output: /tmp/go2_audio_sample.wav + spectrum analysis printed to terminal

# Source your ROS 2 environment (adjust paths as needed)
if [ -f /opt/ros/humble/setup.bash ]; then
    source /opt/ros/humble/setup.bash
fi

SECS=${1:-5}
echo "Recording ${SECS}s of audio from /audio/raw — make noise near the robot!"

python3 -c "
import rclpy, numpy as np, wave, sys, time
from std_msgs.msg import Int16MultiArray

SECS = $SECS
rclpy.init()
node = rclpy.create_node('audio_recorder')
all_samples = []
rate = [48000]
count = [0]

def cb(msg):
    count[0] += 1
    samples = np.array(msg.data, dtype=np.int16)
    all_samples.append(samples)
    if count[0] == 1:
        n = len(samples)
        rate[0] = 48000 if n >= 480 else 8000
        print(f'Receiving: {n} samples/frame, rate={rate[0]}Hz', flush=True)

node.create_subscription(Int16MultiArray, '/audio/raw', cb, 10)

t0 = time.time()
print(f'Recording for {SECS}s...', flush=True)
while rclpy.ok() and (time.time() - t0) < SECS:
    rclpy.spin_once(node, timeout_sec=0.01)

if not all_samples:
    print('No audio received! Is go2_audio_node running?')
    sys.exit(1)

pcm = np.concatenate(all_samples)
fname = '/tmp/go2_audio_sample.wav'
with wave.open(fname, 'w') as wf:
    wf.setnchannels(1)
    wf.setsampwidth(2)
    wf.setframerate(rate[0])
    wf.writeframes(pcm.tobytes())
print(f'Saved {len(pcm)} samples ({len(pcm)/rate[0]:.1f}s) to {fname}', flush=True)

# Spectrum analysis
from scipy.signal import welch
f, psd = welch(pcm.astype(np.float64), fs=rate[0], nperseg=4096)
rms = np.sqrt(np.mean(pcm.astype(np.float64)**2))
peak = int(np.max(np.abs(pcm)))
motor_band = psd[(f >= 20) & (f < 300)]
speech_band = psd[(f >= 300) & (f <= 3000)]
high_band = psd[(f >= 3000) & (f <= 8000)]
print(f'RMS: {rms:.1f}, Peak: {peak}', flush=True)
print(f'Power — motor(<300Hz): {np.mean(motor_band):.1f}, speech(300-3k): {np.mean(speech_band):.1f}, high(3k-8k): {np.mean(high_band):.1f}', flush=True)
if np.mean(speech_band) < np.mean(motor_band) * 0.1:
    print('WARNING: Speech band has <10% of motor band power — voice likely not captured', flush=True)
else:
    print('Speech band has signal — filtering + gain should help', flush=True)

rclpy.shutdown()
"
