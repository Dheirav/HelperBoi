"""
Voice Activation Module for HelperBoi / Jarvis
Provides:
- 100% Offline Speech-to-Text (STT) via SpeechRecognition
- 100% Offline Text-to-Speech (TTS) via pyttsx3 (Windows SAPI5)
- Wake-word listener ("Jarvis", "Hey Jarvis")
- Interactive Voice Shell Mode
"""

import sys
import os
import re
import time
import logging
import threading

logger = logging.getLogger("jarvis.voice")

# Try importing pyttsx3 for TTS
_TTS_ENGINE = None
try:
    import pyttsx3
    _TTS_ENGINE = pyttsx3.init()
    # Configure voice properties
    voices = _TTS_ENGINE.getProperty('voices')
    if voices:
        _TTS_ENGINE.setProperty('voice', voices[0].id)  # Default male/female system voice
    _TTS_ENGINE.setProperty('rate', 185)               # Words per minute
except Exception as e:
    logger.warning(f"pyttsx3 initialization failed: {e}")

# Try importing SpeechRecognition for STT
_SR_AVAILABLE = False
try:
    import speech_recognition as sr
    _SR_AVAILABLE = True
except Exception as e:
    logger.warning(f"SpeechRecognition initialization failed: {e}")


_tts_lock = threading.Lock()

def speak(text, block=True, timeout_sec=None):
    """
    Synthesize and speak text out loud using offline Windows SAPI5 engine.
    Uses dynamic timeout scaling based on text length so long responses are never cut off prematurely.
    """
    if not text or not str(text).strip():
        return

    # Strip markdown and clean text for speech synthesis
    clean_text = re.sub(r"\[.*?\]\(.*?\)", "", str(text))
    clean_text = re.sub(r"[*`#_]", "", clean_text)
    clean_text = " ".join(clean_text.split()).strip()

    # Extract punchy 1-2 sentence spoken summary if long
    sentences = re.split(r'(?<=[.!?]) +', clean_text)
    if len(sentences) > 2 and len(clean_text) > 250:
        clean_text = " ".join(sentences[:2])

    if len(clean_text) > 300:
        clean_text = clean_text[:300] + "..."

    # Dynamic timeout calculation: ~15 chars per sec + 4s buffer
    if timeout_sec is None:
        timeout_sec = max(8.0, len(clean_text) * 0.08 + 4.0)

    def _do_speak():
        with _tts_lock:
            try:
                try:
                    import pythoncom
                    pythoncom.CoInitialize()
                except Exception:
                    pass

                engine = pyttsx3.init()
                engine.setProperty('rate', 185)
                voices = engine.getProperty('voices')
                if voices:
                    engine.setProperty('voice', voices[0].id)

                engine.say(clean_text)
                engine.runAndWait()
                try:
                    engine.stop()
                except Exception:
                    pass
            except Exception as e:
                logger.warning(f"TTS Speech output error: {e}")

    t = threading.Thread(target=_do_speak, daemon=True)
    t.start()

    if block:
        t.join(timeout=timeout_sec)
        if t.is_alive():
            logger.warning(f"TTS speech reached timeout of {timeout_sec:.1f}s - proceeding to listen.")


def listen_for_speech(timeout=4, phrase_time_limit=6, prompt_msg="🎤 Listening..."):
    """
    Listen for voice input from default microphone and convert speech to text.
    Non-blocking with strict timeouts to prevent terminal freezes.
    """
    if not _SR_AVAILABLE:
        print("[⚠️ Voice Input Warning]: SpeechRecognition package is not available.")
        return None

    r = sr.Recognizer()
    r.energy_threshold = 300
    r.dynamic_energy_threshold = True

    try:
        with sr.Microphone() as source:
            print(f"\n[🎤 Voice Input]: {prompt_msg}")
            r.adjust_for_ambient_noise(source, duration=0.2)
            audio = r.listen(source, timeout=timeout, phrase_time_limit=phrase_time_limit)
            print("[⏳ Speech Captured]: Processing audio...")

            text = r.recognize_google(audio)
            print(f"[🗣️ You Said]: \"{text}\"")
            return text
    except sr.WaitTimeoutError:
        print("[⏱️ Voice Timeout]: No speech detected.")
        return None
    except sr.UnknownValueError:
        print("[❓ Voice Error]: Could not understand speech audio.")
        return None
    except Exception as e:
        print(f"[❌ Voice Microphone Error]: {e}")
        return None


def listen_for_wake_word(wake_words=("jarvis", "hey jarvis", "hi jarvis"), timeout=10):
    """
    Listen continuously for a wake-word phrase. Returns True if heard.
    """
    print(f"[👂 Wake-Word Listener Active]: Say '{', '.join(wake_words)}' to wake Jarvis...")
    text = listen_for_speech(timeout=timeout, phrase_time_limit=4, prompt_msg="Listening for wake-word...")
    if text:
        text_lower = text.lower()
        for ww in wake_words:
            if ww in text_lower:
                print(f"[⚡ Wake-Word Detected!]: '{ww}' heard!")
                speak("Yes? I am listening.", block=True)
                return True
    return False


def start_voice_mode(on_command_callback=None):
    """
    Launch interactive voice assistant shell.
    """
    speak("Voice mode activated. How can I help you?", block=False)
    print("\n==================== JARVIS VOICE MODE ====================")
    print("🎤 Say 'Jarvis' or speak a command directly.")
    print("Type 'exit' or press Ctrl+C to return to text mode.")
    print("===========================================================\n")

    while True:
        try:
            command_text = listen_for_speech(timeout=6, phrase_time_limit=8, prompt_msg="Listening for command...")
            if not command_text:
                continue

            if command_text.lower() in ("exit", "quit", "stop", "goodbye"):
                speak("Goodbye! Exiting voice mode.", block=True)
                print("[Voice Mode Ended]")
                break

            if on_command_callback:
                print(f"[🤖 Executing Command]: {command_text}")
                response = on_command_callback(command_text)
                if response:
                    print(f"\n[🤖 Jarvis Response]: {response}\n")
                    speak(response, block=True)
        except KeyboardInterrupt:
            speak("Exiting voice mode.", block=True)
            break
