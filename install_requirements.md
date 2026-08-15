# Jarvis Environment Setup

## Python Requirements

- `.`
- `.summarize`
- `collections`
- `datetime`
- `difflib`
- `glob`
- `json`
- `lib`
- `matplotlib.pyplot`
- `modules.input_processing`
- `modules.load_notes`
- `modules.memory`
- `os`
- `pathlib`
- `platform`
- `psutil`
- `re`
- `requests`
- `rich.console`
- `rich.panel`
- `rich.table`
- `rich>=13.0.0`
- `subprocess`
- `sys`
- `threading`
- `time`
- `typer`
- `typer[all]>=0.9.0`
- `wordcloud`

## System Dependencies

- **Ollama**: Local LLM runner (https://ollama.com/)
- **Git**: Version control and backup
- **FFmpeg**: Audio/video processing (optional)
- **WSL2**: Linux subsystem for Windows (if on Windows)
- **Whisper/Vosk**: Speech recognition (Python package or binary)
- **TTS (Coqui/pyttsx3)**: Text-to-speech (Python package)

---
Run the following to install Python packages:

    pip install -r requirements.txt

Install system tools using your OS package manager.
