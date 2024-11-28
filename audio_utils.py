from pydub import AudioSegment
import edge_tts
import asyncio
from pathlib import Path
from typing import List, Tuple, Optional
from concurrent.futures import ThreadPoolExecutor
import time
import subprocess
import re
import json

class VoiceManager:
    def __init__(self):
        self.config_file = Path("config.json")
        self.voices = self.load_config()

    def load_config(self) -> dict:
        if self.config_file.exists():
            with open(self.config_file, 'r') as f:
                config = json.load(f)
                if time.time() - config.get('last_updated', 0) > 86400:
                    return self.fetch_and_save_voices()
                return config
        return self.fetch_and_save_voices()

    def fetch_and_save_voices(self) -> dict:
        try:
            command = ['edge-tts', '--list-voices']
            result = subprocess.run(command, capture_output=True, text=True)
            
            voices = []
            for line in result.stdout.strip().splitlines():
                match = re.match(r'Name:\s*(.+)', line)
                if match:
                    voices.append(match.group(1).strip())
            
            if not voices:
                # Fallback to default voice if no voices found
                voices = ['en-US-EmmaNeural']
            
            config = {
                'voices': voices,
                'last_used_voice': 'en-US-EmmaNeural',
                'last_updated': time.time()
            }
            
            with open(self.config_file, 'w') as f:
                json.dump(config, f)
            
            return config
        except FileNotFoundError:
            # Fallback configuration if edge-tts is not found
            config = {
                'voices': ['en-US-EmmaNeural'],
                'last_used_voice': 'en-US-EmmaNeural',
                'last_updated': time.time()
            }
            with open(self.config_file, 'w') as f:
                json.dump(config, f)
            return config

class AudioProcessor:
    def __init__(self, max_workers: int = 15):
        self.max_workers = max_workers
        self.executor = ThreadPoolExecutor(max_workers=max_workers)
        self.voice_manager = VoiceManager()
        self.settings = self._load_settings()

    def shutdown_executor(self):
        self.executor.shutdown(wait=True)

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

    async def convert_text_to_speech(self, text: str, voice: str, output_file: Path, retries: Optional[int] = None) -> Tuple[Path, bool, str]:
        """Convert text to speech with enhanced retry mechanism and error handling"""
        retry_count = retries if retries is not None else self.settings.get("retry_attempts", 3)
        
        # Cache voice settings to avoid repeated dictionary lookups
        rate = self.settings.get("rate", "+0%")
        volume = self.settings.get("volume", "+0%")
        pitch = self.settings.get("pitch", "+0Hz")
        
        # Initialize communicator once
        communicate = edge_tts.Communicate(
            text,
            voice,
            rate=rate,
            volume=volume,
            pitch=pitch
        )
        
        for attempt in range(retry_count):
            try:
                await communicate.save(str(output_file))
                return output_file, True, ""
            except Exception as e:
                error_msg = str(e)
                if "Unable to connect" in error_msg:
                    # Reduce wait time for connection errors
                    await asyncio.sleep(1)
                    return output_file, False, "Internet connection lost"
                if attempt == retry_count - 1:
                    return output_file, False, f"Failed after {retry_count} attempts: {error_msg}"
                # Use shorter exponential backoff
                await asyncio.sleep(min(1 * attempt, 2))
        return output_file, False, "Failed after retries"

    async def process_batch(self, subtitles: List[tuple], voice: str, output_folder: Path, 
                          start_idx: int, batch_size: int) -> List[Tuple[Path, bool, str]]:
        """Process a batch of subtitles with parallel execution"""
        # Create all tasks at once for better concurrency
        tasks = []
        semaphore = asyncio.Semaphore(self.max_workers)  # Control concurrent connections
        
        async def process_subtitle(subtitle):
            async with semaphore:
                index, start_time, end_time, text = subtitle
                output_file = output_folder / f"{index}.mp3"
                return await self.convert_text_to_speech(text, voice, output_file)
        
        # Create tasks for all subtitles in the batch
        tasks = [process_subtitle(subtitle) for subtitle in subtitles]
        
        # Execute all tasks concurrently
        return await asyncio.gather(*tasks)

    def combine_audio_files(self, subtitles: List[Tuple], audio_files: List[Path], output_file: Path):
        """Combine multiple audio files with precise timing and silence gaps"""
        try:
            # Pre-load all audio segments to avoid repeated disk I/O
            audio_segments = {}
            for audio_file in audio_files:
                try:
                    audio_segments[int(audio_file.stem)] = AudioSegment.from_file(str(audio_file))
                except Exception as e:
                    print(f"Error loading audio file {audio_file}: {e}")
            
            # Initialize combined audio
            combined = AudioSegment.empty()
            current_position = 0
            
            for index, start_time, end_time, _ in subtitles:
                start_ms = self._time_to_ms(start_time)
                end_ms = self._time_to_ms(end_time)
                
                # Add silence if needed
                if start_ms > current_position:
                    silence_duration = start_ms - current_position
                    combined += AudioSegment.silent(duration=silence_duration)
                
                # Add audio segment if exists
                if index in audio_segments:
                    segment = audio_segments[index]
                    segment_duration = end_ms - start_ms
                    
                    # Adjust segment duration to match subtitle timing
                    if len(segment) > segment_duration:
                        segment = segment[:segment_duration]
                    elif len(segment) < segment_duration:
                        segment += AudioSegment.silent(duration=segment_duration - len(segment))
                    
                    combined += segment
                    current_position = end_ms
                else:
                    # If audio file missing, add silence for the duration
                    silence_duration = end_ms - start_ms
                    combined += AudioSegment.silent(duration=silence_duration)
                    current_position = end_ms
            
            # Export with optimized settings
            combined.export(
                str(output_file),
                format="mp3",
                bitrate="192k",
                codec="libmp3lame",
                parameters=["-q:a", "0"]  # Use highest quality setting
            )
            
            # Cleanup temporary files after successful export
            for audio_file in audio_files:
                try:
                    if audio_file.exists():
                        audio_file.unlink()
                except Exception as e:
                    print(f"Error deleting temporary file {audio_file}: {e}")
            
            # Try to remove the temp directory if it's empty
            try:
                audio_files[0].parent.rmdir()
            except Exception:
                pass  # Ignore if directory is not empty or other errors
                
        except Exception as e:
            print(f"Error combining audio files: {e}")
            raise

    def _time_to_ms(self, time_str: str) -> int:
        """Convert SRT time format to milliseconds"""
        hours, minutes, seconds = time_str.split(':')
        seconds, milliseconds = seconds.split(',')
        return (int(hours) * 3600000 + 
                int(minutes) * 60000 + 
                int(seconds) * 1000 + 
                int(milliseconds))

    def cleanup_old_files(self, temp_dir: Path):
        """Clean up old temporary files"""
        try:
            cleanup_days = self.settings.get("cleanup_days", 7)
            current_time = time.time()
            max_age = cleanup_days * 24 * 60 * 60  # Convert days to seconds
            
            for file_path in temp_dir.rglob("*.mp3"):
                if file_path.is_file():
                    file_age = current_time - file_path.stat().st_mtime
                    if file_age > max_age:
                        try:
                            file_path.unlink()
                        except Exception:
                            pass
        except Exception:
            pass