from pathlib import Path
import re
import json
import time
from typing import List, Tuple
from utils.subtitle_formatter import SubtitleFormatter

class WhisperSubtitleService:
    def __init__(self):
        self.formatter = SubtitleFormatter()

    def generate_subtitles(self, model, audio_path):
        try:
            print(f"Transcribing audio with Whisper model: {model}...")
            result = model.transcribe(audio_path)
            subtitles = self._format_segments(result["segments"])
            detected_language = result.get("language", "en")
            return subtitles, detected_language
        except Exception as e:
            print(f"Error generating subtitles: {str(e)}")
            raise

    def _format_segments(self, segments):
        srt_content = ""
        for i, segment in enumerate(segments, 1):
            start_time = self.formatter.format_timestamp(segment['start'])
            end_time = self.formatter.format_timestamp(segment['end'])
            text = segment['text'].strip()
            srt_content += self.formatter.format_subtitle_segment(i, start_time, end_time, text)
        return srt_content

    def save_subtitles(self, subtitles, output_path):
        try:
            with open(output_path, 'w', encoding='utf-8') as f:
                f.write(subtitles)
            print(f"Subtitles saved to: {output_path}")
        except Exception as e:
            print(f"Error saving subtitles: {str(e)}")
            raise

class SubtitleProcessor:
    def __init__(self):
        self.temp_dir = Path("temp/temp_subtitles")
        self.progress_file = self.temp_dir / "progress.json"
        self.settings = self._load_settings()
        self.setup_temp_directory()

    def _load_settings(self) -> dict:
        try:
            if Path("app_settings.json").exists():
                with open("app_settings.json", "r") as f:
                    return json.load(f)
        except Exception:
            pass
        return {
            "max_workers": 15,
            "batch_size": 10,
            "retry_attempts": 3,
            "cleanup_days": 7
        }

    def setup_temp_directory(self):
        # Ensure the parent 'temp' directory exists
        self.temp_dir.parent.mkdir(parents=True, exist_ok=True)
        # Create the 'temp_subtitles' directory
        self.temp_dir.mkdir(exist_ok=True)
        self._cleanup_old_files()

    def _cleanup_old_files(self):
        try:
            cleanup_days = self.settings.get("cleanup_days", 7)
            current_time = time.time()
            max_age = cleanup_days * 24 * 60 * 60
            if self.progress_file.exists():
                file_age = current_time - self.progress_file.stat().st_mtime
                if file_age > max_age:
                    self.progress_file.unlink()
            for dir_path in self.temp_dir.iterdir():
                if dir_path.is_dir():
                    dir_age = current_time - dir_path.stat().st_mtime
                    if dir_age > max_age:
                        try:
                            for file in dir_path.glob("*"):
                                file.unlink()
                            dir_path.rmdir()
                        except Exception as e:
                            print(f"Error cleaning up old files: {e}")
        except Exception as e:
            print(f"Error cleaning up old files: {e}")

    def save_progress(self, file_id: str, completed_segments: List[int]):
        progress_data = {
            "file_id": file_id,
            "completed_segments": completed_segments,
            "timestamp": time.time()
        }
        with open(self.progress_file, 'w') as f:
            json.dump(progress_data, f)

    def load_progress(self, file_id: str) -> List[int]:
        try:
            if self.progress_file.exists():
                with open(self.progress_file, 'r') as f:
                    data = json.load(f)
                    if data["file_id"] == file_id:
                        return data["completed_segments"]
        except Exception as e:
            print(f"Error loading progress: {e}")
        return []

    def create_subtitle_folder(self, subtitle_file: str) -> Path:
        folder_name = Path(subtitle_file).stem
        folder_path = self.temp_dir / folder_name
        folder_path.mkdir(exist_ok=True)
        return folder_path

    def parse_subtitle_file(self, file_path: str) -> List[Tuple[int, str, str, str]]:
        with open(file_path, 'r', encoding='utf-8-sig') as f:
            content = f.read()
        blocks = re.split(r'\n\n+', content.strip())
        subtitles = []
        for block in blocks:
            lines = block.splitlines()
            if len(lines) >= 3:
                try:
                    index = int(lines[0].strip())
                    timing = lines[1]
                    text = ' '.join(lines[2:])
                    start_time, end_time = timing.split(' --> ')
                    subtitles.append((index, start_time, end_time, text))
                except ValueError as e:
                    print(f"Error parsing block: {block}, Error: {e}")
                    continue
        return subtitles

    def clean_temp_files(self, folder: Path):
        if folder.exists():
            for file in folder.glob("*.mp3"):
                file.unlink()
            folder.rmdir()