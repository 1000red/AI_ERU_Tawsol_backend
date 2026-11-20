# High-Performance FFmpeg Recipes for Pitch Videos

## 1. Fast Bokeh Background Pre-Processing
Instead of real-time Gaussian or Box blurs during multi-layer compositing, use hardware-friendly bilinear downscaling and upscaling:

```bash
ffmpeg -y -stream_loop 30 -i input_bg.mp4 -t 300 \
  -vf "scale=384:216,scale=1920:1080:flags=bilinear,eq=brightness=-0.08:contrast=1.1,format=yuv420p" \
  -c:v libx264 -preset veryfast -crf 22 bg_loop_bokeh.mp4
```
* **Performance Gain**: Runs at **12x-18x realtime** (finishes in ~20-30 seconds for 5 minutes of footage), compared to 0.015x for `boxblur=20:5`.

## 2. Audio Time-Compression with `atempo`
When synthesized speech exceeds its budgeted timeline slice by 1-2 seconds, adjust speed smoothly without pitch shifting:

```bash
ffmpeg -y -i raw_speech.wav -filter:a "atempo=1.05" compressed_speech.wav
```
*(Keep factor strictly within `0.95` to `1.08` to preserve natural vocal cadence).*

## 3. Demuxer Slide Concat File Format
The FFmpeg `concat` demuxer requires explicit durations. Note: the last item must repeat or be extended to hold the final frame:

```text
file 'slide_01.png'
duration 20.0
file 'slide_02.png'
duration 20.0
file 'slide_03.png'
duration 25.0
file 'slide_03.png'
```

## 4. Final Master Assembly Command
```bash
ffmpeg -y \
  -i bg_loop_bokeh.mp4 \
  -f concat -safe 0 -i concat_slides.txt \
  -i master_audio.wav \
  -filter_complex "[0:v][1:v]overlay=0:0:shortest=1[v]" \
  -map "[v]" -map 2:a \
  -c:v libx264 -preset veryfast -crf 20 -pix_fmt yuv420p \
  -c:a aac -b:a 320k \
  -t 300.0 output_presentation_1080p.mp4
```
