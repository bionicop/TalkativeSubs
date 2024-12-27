# TalkativeSubs

A powerful tool to convert subtitle files (SRT) to audio using Microsoft Edge's text-to-speech service, and to generate subtitles from audio files using OpenAI Whisper.

## Features

- **Subtitle to Audio Conversion**:
  - Convert single SRT files or entire folders.
  - Multiple voice options with customizable settings (rate, volume, pitch, words per minute).
  - Progress tracking and continuation support.
  - Batch processing with parallel execution.

- **Audio to Subtitle Translation**:
  - Generate subtitles from audio files (MP3, WAV, etc.) using OpenAI Whisper.
  - Translate subtitles into user-defined languages using `Googletrans`.
  - Save subtitles in SRT format.

- **Modular Design**:
  - Clean and modular codebase for easy maintenance and extensibility.
  - Separate components for file selection, progress tracking, logging, and processing.

## Special Thanks

- Special thanks to [rany2](https://github.com/rany2) for creating [edge-tts](https://github.com/rany2/edge-tts), which enables us to use Microsoft Edge's online text-to-speech service from Python without needing Microsoft Edge, Windows, or an API key.
- Thanks to OpenAI for the Whisper model, which powers the **Audio to Subtitle Translation** feature.
- Thanks to [ssut](https://github.com/ssut) for creating [Googletrans](https://github.com/ssut/py-googletrans), which enables subtitle translation into multiple languages.

## Requirements

- **Python 3.11 or 3.12** (I am using 3.12.6)
- **FFmpeg** (for audio processing)
- **Whisper Model** (automatically downloaded on first use)

## Installation

**If you prefer a video, here you go [Installation Video](https://youtu.be/AUX5jpSFRhY)**

1. Clone the repository:
   ```bash
   git clone https://github.com/bionicop/TalkativeSubs.git
   ```

2. Navigate to the `TalkativeSubs` folder and install the required packages:
   ```bash
   pip install -r requirements.txt
   ```

3. Install FFmpeg:
   - **Windows**: Download from [FFmpeg website](https://ffmpeg.org/download.html)
   - **Linux**: `sudo apt-get install ffmpeg`
   - **macOS**: `brew install ffmpeg`

## Usage

1. Run the application:
   ```bash
   python main.py
   ```

2. Use the UI to:
   - **Subtitle to Audio**:
     - Select individual SRT files (single or multiple).
     - Choose a voice and customize settings.
     - Start, pause, resume, or cancel the conversion.
     - Monitor progress in real-time.
   - **Audio to Subtitle**:
     - Select audio files (MP3, WAV, etc.).
     - Choose a target language for subtitles.
     - Generate subtitles and translate them if needed.
     - Save subtitles in SRT format.

## Future Iterations

- [x] Processing options like max workers, batch size, and retry attempts.
- [x] Voice customization like rate, volume, pitch, and words per minute.
- [x] **Audio to Subtitle Translation** via OpenAI Whisper.
- [x] **Subtitle Translation** via `Googletrans`.
- [ ] Add support for non-SRT subtitle formats (e.g., VTT, ASS).
- [ ] Add compatibility with more TTS engines (free ones).
- [ ] Add offline TTS options for users without internet access.