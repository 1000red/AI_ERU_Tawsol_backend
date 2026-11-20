"""
Two-Stage FFmpeg Video Assembler
Assembles 1080p master video using pre-rendered bokeh loop and transparent slide concat demuxer.
"""
import os
import sys
import subprocess

def run_cmd(cmd):
    print(f"[EXEC] {' '.join(cmd)}")
    res = subprocess.run(cmd, capture_output=True, text=True)
    if res.returncode != 0:
        print(f"[ERROR] Command failed with return code {res.returncode}")
        print(res.stderr)
        raise RuntimeError(f"Command failed: {res.stderr}")
    return res.stdout

def assemble_pitch_video(bg_video: str, concat_file: str, audio_file: str, output_file: str, target_seconds: float = 300.0):
    """
    Two-stage assembly pipeline.
    """
    bokeh_temp = "temp_bg_bokeh_loop.mp4"

    print("=== Stage 1: Pre-rendering Bokeh Background Loop ===")
    stage1_cmd = [
        "ffmpeg", "-y",
        "-stream_loop", "30",
        "-i", bg_video,
        "-t", str(target_seconds),
        "-vf", "scale=384:216,scale=1920:1080:flags=bilinear,colorchannelmixer=aa=0.45",
        "-c:v", "libx264",
        "-preset", "veryfast",
        "-crf", "22",
        bokeh_temp
    ]
    run_cmd(stage1_cmd)

    print("=== Stage 2: Final Overlay Compositing & Audio Concat ===")
    stage2_cmd = [
        "ffmpeg", "-y",
        "-i", bokeh_temp,
        "-f", "concat", "-safe", "0", "-i", concat_file,
        "-i", audio_file,
        "-filter_complex", "[0:v][1:v]overlay=0:0:shortest=1[outv]",
        "-map", "[outv]",
        "-map", "2:a",
        "-c:v", "libx264",
        "-preset", "veryfast",
        "-crf", "20",
        "-pix_fmt", "yuv420p",
        "-c:a", "aac",
        "-b:a", "320k",
        "-t", str(target_seconds),
        output_file
    ]
    run_cmd(stage2_cmd)

    if os.path.exists(bokeh_temp):
        os.remove(bokeh_temp)

    print(f"=== Assembly Complete: {output_file} ===")

if __name__ == "__main__":
    if len(sys.argv) < 5:
        print("Usage: python video_assembler.py <bg_raw.mp4> <concat_slides.txt> <master_audio.wav> <output_master.mp4> [duration_seconds]")
        sys.exit(1)
    duration = float(sys.argv[5]) if len(sys.argv) > 5 else 300.0
    assemble_pitch_video(sys.argv[1], sys.argv[2], sys.argv[3], sys.argv[4], duration)
