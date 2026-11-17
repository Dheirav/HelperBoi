#!/bin/bash
# Jarvis environment setup for Linux and WSL2.
#
# Dependencies go in .venv and nowhere else. Run the program with
# .venv/bin/python, not a bare python3, so it cannot fall back to the system one.
set -euo pipefail
cd "$(dirname "$0")"

# uv would otherwise pick its own managed Python; the code needs 3.12 (backslashes
# inside f-string expressions), which is what Ubuntu 24.04 ships.
python3 --version
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt

# Ollama server: https://ollama.com/download . Under WSL install it inside WSL so
# that http://localhost:11434 (the default here) reaches it. If it runs on Windows
# instead, point OLLAMA_HOST at it.
# Speech: the Windows voice is used through powershell.exe, so nothing to install.
# Microphone input needs PulseAudio from WSLg plus: sudo apt-get install -y portaudio19-dev
#   and .venv/bin/python -m pip install SpeechRecognition pyaudio
sudo apt-get install -y git ffmpeg
