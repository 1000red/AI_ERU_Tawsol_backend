"""
Deterministic Audio Ducker
Applies moving-average volume ducking to background music during active voiceover periods.
"""
import os
import sys
import wave
import struct
import math

def read_wav_samples(path):
    with wave.open(path, 'rb') as wf:
        n_channels = wf.getnchannels()
        sampwidth = wf.getsampwidth()
        framerate = wf.getframerate()
        n_frames = wf.getnframes()
        data = wf.readframes(n_frames)
        fmt = f"<{n_frames * n_channels}h"
        samples = list(struct.unpack(fmt, data))
        # Convert stereo to mono if needed
        if n_channels == 2:
            mono = [(samples[i*2] + samples[i*2+1]) // 2 for i in range(n_frames)]
            return mono, framerate
        return samples, framerate

def write_wav(path, samples, framerate=24000, n_channels=2):
    with wave.open(path, 'wb') as wf:
        wf.setnchannels(n_channels)
        wf.setsampwidth(2)
        wf.setframerate(framerate)
        # Duplicate mono to stereo
        if n_channels == 2:
            stereo = []
            for s in samples:
                val = max(-32767, min(32767, int(s)))
                stereo.extend([val, val])
            fmt = f"<{len(stereo)}h"
            wf.writeframes(struct.pack(fmt, *stereo))
        else:
            clamped = [max(-32767, min(32767, int(s))) for s in samples]
            fmt = f"<{len(clamped)}h"
            wf.writeframes(struct.pack(fmt, *clamped))

def duck_audio(voice_wav_path: str, bgm_wav_path: str, output_path: str, duck_gain_db: float = -18.0, ramp_ms: int = 300):
    """
    Mixes voice over background music with smooth ducking.
    """
    voice_samples, rate = read_wav_samples(voice_wav_path)
    bgm_samples, bgm_rate = read_wav_samples(bgm_wav_path)

    # Pad or truncate BGM to match voice length
    target_len = len(voice_samples)
    if len(bgm_samples) < target_len:
        loops = (target_len // len(bgm_samples)) + 1
        bgm_samples = (bgm_samples * loops)[:target_len]
    else:
        bgm_samples = bgm_samples[:target_len]

    # Calculate moving envelope of voice
    window_size = int(rate * 0.05)  # 50ms window
    speech_threshold = 400  # RMS threshold for speech presence
    duck_multiplier = 10 ** (duck_gain_db / 20.0)

    envelope = [0.0] * target_len
    for i in range(0, target_len, window_size):
        chunk = voice_samples[i:i+window_size]
        if not chunk:
            continue
        rms = math.sqrt(sum(s**2 for s in chunk) / len(chunk))
        target_gain = duck_multiplier if rms > speech_threshold else 1.0
        for j in range(i, min(i + window_size, target_len)):
            envelope[j] = target_gain

    # Smooth envelope (linear ramp)
    ramp_samples = int(rate * (ramp_ms / 1000.0))
    smoothed = list(envelope)
    for i in range(1, target_len):
        step = 1.0 / ramp_samples
        if smoothed[i] < smoothed[i-1]:
            smoothed[i] = max(smoothed[i], smoothed[i-1] - step)
        elif smoothed[i] > smoothed[i-1]:
            smoothed[i] = min(smoothed[i], smoothed[i-1] + step)

    # Apply 3-second tail fade out
    tail_fade_samples = int(rate * 3.0)
    for i in range(target_len - tail_fade_samples, target_len):
        factor = (target_len - i) / tail_fade_samples
        smoothed[i] *= factor

    # Mix down
    mixed = []
    for i in range(target_len):
        bgm_val = bgm_samples[i] * smoothed[i] * 0.25  # Base BGM volume at 25%
        voice_val = voice_samples[i] * 1.15            # Voice boost 15%
        mix = int(bgm_val + voice_val)
        mixed.append(max(-32767, min(32767, mix)))

    write_wav(output_path, mixed, framerate=rate, n_channels=2)
    print(f"[SUCCESS] Mixed ducked audio written to {output_path}")

if __name__ == "__main__":
    if len(sys.argv) < 4:
        print("Usage: python audio_ducker.py <voice.wav> <bgm.wav> <output_master.wav>")
        sys.exit(1)
    duck_audio(sys.argv[1], sys.argv[2], sys.argv[3])
