# Gemini Neural TTS Audio Guardrails

These guidelines apply whenever calling Google Gemini API endpoints for Neural Audio generation (`responseModalities: ["AUDIO"]`).

## 1. Zero Prompt-Prefixing in Spoken Content (Critical)
* **The Failure Mode**: Prepending style instructions, personas, or stage directions inside `contents[0].parts[0].text` (e.g. `f"Speak this warmly as a friendly woman: {script}"`) causes the model to read the prompt out loud into the synthesized audio.
* **The Rule**: The `contents` text payload must contain **strictly and exclusively the exact spoken words**.
* **Persona Configuration**: Governed 100% through the voice preset in `generationConfig`:
  ```json
  "speechConfig": {
    "voiceConfig": {
      "prebuiltVoiceConfig": {
        "voiceName": "Aoede"
      }
    }
  }
  ```
  *(Options: `Aoede` for warm/friendly female, `Kore` for clear female, `Fenrir` for deep male, `Puck` for casual male).*

## 2. Quota & Model Fallback Hierarchy
When synthesizing audio via the Gemini API, respect tier quotas:
1. **Primary**: `gemini-3.8-flash-lite-tts` (fastest, generous RPM/TPM limits, natural conversational pacing).
2. **Secondary Fallback**: `gemini-3.1-flash-tts-preview` (high fidelity, but monitor 429 RPM limits).
3. **Tertiary Fallback**: `gemini-3.8-flash-tts` (strict daily request cap; use sparingly).

## 3. Windows SSL & Network Sockets
* Python HTTP clients (`httpx`, `urllib`) on Windows environments frequently hit `[SSL: CERTIFICATE_VERIFY_FAILED]`.
* Automation scripts must use `httpx.Client(verify=False, timeout=60.0)` or explicitly load the Windows certificate bundle.

## 4. Pacing & Sentence Truncation Guardrail
* Target a cadence of **2.0 to 2.3 words per second**.
* **Never hard-truncate PCM byte buffers** (`padded[:target_bytes]`) as this clips word endings.
* If audio exceeds the target duration, use FFmpeg's `atempo` filter (clamped between `0.95` and `1.08`) rather than cutting samples:
  ```bash
  ffmpeg -y -i input.wav -filter:a "atempo=1.05" output.wav
  ```
