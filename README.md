# Subtitle to Audio Converter

A powerful tool to convert subtitle files (SRT) to audio using Microsoft Edge's text-to-speech service.

## Features

- Convert single SRT files or entire folders
- Multiple voice options with customizable settings
- Progress tracking and continuation support
- Batch processing with parallel execution

## Special Thanks

Special thanks to [rany2](https://github.com/rany2) for creating [edge-tts](https://github.com/rany2/edge-tts), which enables us to use Microsoft Edge's online text-to-speech service from Python without needing Microsoft Edge, Windows, or an API key.

## Requirements

- Python 3.11 or 3.12 (I am using 3.12.6)
- FFmpeg (for audio processing)

## Installation
**If you prefer a video, here you go [Installation Video](https://youtu.be/AUX5jpSFRhY)**

1. Clone the repository:
```bash
git clone https://github.com/bionicop/TalkativeSubs.git
```

2. Then cd into `TalkativeSubs` folder and install the required packages:
```bash
pip install -r requirements.txt
```

3. Install FFmpeg:
- Windows: Download from [FFmpeg website](https://ffmpeg.org/download.html)
- Linux: `sudo apt-get install ffmpeg`
- macOS: `brew install ffmpeg`

## Usage

1. Run the application:
```bash
python main.py
```

2. Use the UI to:
   - Select individual SRT files(single or multiple)
   - Choose voice
   - Start/pause/resume conversion
   - Monitor progress


## Future Iterations
- [x] Processing option like Max workers, batch size and retry attempts.
- [x] Voice customization like rate, volume, pitch, word per minute.
- [ ] Subtitle Translation
- [ ] Add support for non-SRT subtitle formats (e.g., VTT, ASS).  
- [ ] Add compatibility with more TTS engines (free ones)
- [ ] Add Offline TTS options for users without internet access.
