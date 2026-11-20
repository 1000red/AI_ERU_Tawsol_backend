"""
Gemini Neural Text-to-Speech Synthesizer
Synthesizes speech cleanly using Gemini models with Aoede voice preset.
"""
import os
import sys
import json
import base64
import httpx

# Voice and model defaults
DEFAULT_VOICE = "Aoede"  # Warm, professional female voice
FALLBACK_MODELS = [
    "gemini-3.8-flash-lite-tts",
    "gemini-3.1-flash-tts-preview",
    "gemini-3.8-flash-tts"
]

def synthesize_slide_speech(text: str, output_path: str, api_key: str = None) -> bool:
    """
    Synthesize audio for a given text script.
    Guarantees zero prompt-prefix leakage and handles SSL & fallback tiers.
    """
    if not api_key:
        api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        raise ValueError("GEMINI_API_KEY is not set.")

    # CRITICAL: Send only clean text to prevent model speaking the prompt
    clean_text = text.strip()

    payload = {
        "contents": [
            {
                "parts": [{"text": clean_text}]
            }
        ],
        "generationConfig": {
            "responseModalities": ["AUDIO"],
            "speechConfig": {
                "voiceConfig": {
                    "prebuiltVoiceConfig": {
                        "voiceName": DEFAULT_VOICE
                    }
                }
            }
        }
    }

    # Use verify=False on Windows to prevent SSL certificate authority handshake failures
    with httpx.Client(verify=False, timeout=60.0) as client:
        for model in FALLBACK_MODELS:
            url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={api_key}"
            try:
                response = client.post(url, json=payload, headers={"Content-Type": "application/json"})
                if response.status_code == 200:
                    data = response.json()
                    candidates = data.get("candidates", [])
                    if candidates:
                        parts = candidates[0].get("content", {}).get("parts", [])
                        for part in parts:
                            inline_data = part.get("inlineData", {})
                            if inline_data.get("mimeType", "").startswith("audio/"):
                                audio_bytes = base64.b64decode(inline_data["data"])
                                with open(output_path, "wb") as f:
                                    f.write(audio_bytes)
                                print(f"[SUCCESS] Synthesized via {model} -> {output_path}")
                                return True
                elif response.status_code == 429:
                    print(f"[WARN] Quota limit on {model} (429), trying fallback...")
                    continue
                else:
                    print(f"[WARN] Model {model} returned status {response.status_code}: {response.text[:120]}")
            except Exception as e:
                print(f"[ERROR] Exception calling {model}: {e}")
                continue

    return False

if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Usage: python tts_synthesizer.py <output_file.wav> <spoken_text>")
        sys.exit(1)
    out_file = sys.argv[1]
    speech_text = " ".join(sys.argv[2:])
    success = synthesize_slide_speech(speech_text, out_file)
    sys.exit(0 if success else 1)
