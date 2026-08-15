#!/bin/bash
# Jarvis environment setup script

pip install -r requirements.txt
# See https://ollama.com/download for platform-specific install
sudo apt-get install -y git
sudo apt-get install -y ffmpeg
# WSL2: See https://learn.microsoft.com/en-us/windows/wsl/install
# Whisper/Vosk/TTS: install via pip if needed
# e.g. pip install openai-whisper vosk pyttsx3 coqui-ai TTS
