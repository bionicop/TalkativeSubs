from pydub import AudioSegment
import edge_tts
import asyncio
from pathlib import Path
from typing import List, Tuple
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
        command = ['edge-tts', '--list-voices']
        result = subprocess.run(command, capture_output=True, text=True)
        
        voices = []
        for line in result.stdout.strip().splitlines():
            match = re.match(r'Name:\s*(.+)', line)
            if match:
                voices.append(match.group(1).strip())
        
        config = {
            'voices': voices,
            'last_used_voice': 'en-US-EmmaNeural',
            'last_updated': time.time()
        }
        
        with open(self.config_file, 'w') as f:
            json.dump(config, f)
        
        return config

class AudioProcessor:
    def __init__(self, max_workers: int = 30):
        self.max_workers = max_workers
        self.executor = ThreadPoolExecutor(max_workers=max_workers)
        self.voice_manager = VoiceManager()

    async def convert_text_to_speech(self, text: str, voice: str, output_file: Path, retries: int = 3) -> Tuple[Path, bool, str]:
        """Convert text to speech with enhanced retry mechanism and error handling"""
        for attempt in range(retries):
            try:
                communicate = edge_tts.Communicate(text, voice)
                await communicate.save(str(output_file))
                return output_file, True, ""
            except Exception as e:
                error_msg = str(e)
                if "Unable to connect" in error_msg:
                    return output_file, False, "Internet connection lost"
                if attempt == retries - 1:
                    return output_file, False, f"Failed after {retries} attempts: {error_msg}"
                await asyncio.sleep(2 ** attempt)
        return output_file, False, "Failed after retries"

    async def process_batch(self, subtitles: List[tuple], voice: str, output_folder: Path, 
                          start_idx: int, batch_size: int) -> List[Tuple[Path, bool, str]]:
        """Process a batch of subtitles with parallel execution"""
        tasks = []
        for subtitle in subtitles:
            index, start_time, end_time, text = subtitle
            output_file = output_folder / f"{index}.mp3"
            task = self.convert_text_to_speech(text, voice, output_file)
            tasks.append(task)
        
        return await asyncio.gather(*tasks)

    def combine_audio_files(self, subtitles: List[Tuple], audio_files: List[Path], output_file: Path):
        """Combine multiple audio files with precise timing and silence gaps"""
        combined = AudioSegment.empty()
        current_position = 0
        
        # Sort audio files by index
        audio_files_dict = {int(f.stem): f for f in audio_files}
        
        for index, start_time, end_time, _ in subtitles:
            start_ms = self._time_to_ms(start_time)
            end_ms = self._time_to_ms(end_time)
            
            # Add silence if needed
            if start_ms > current_position:
                silence_duration = start_ms - current_position
                silence = AudioSegment.silent(duration=silence_duration)
                combined += silence
            
            # Add audio segment if exists
            if index in audio_files_dict and audio_files_dict[index].exists():
                segment = AudioSegment.from_file(str(audio_files_dict[index]))
                
                # Adjust segment duration to match subtitle timing
                segment_duration = end_ms - start_ms
                if len(segment) > segment_duration:
                    segment = segment[:segment_duration]
                elif len(segment) < segment_duration:
                    segment += AudioSegment.silent(duration=segment_duration - len(segment))
                
                combined += segment
                current_position = end_ms
            else:
                # If audio file missing, add silence for the duration
                silence_duration = end_ms - start_ms
                silence = AudioSegment.silent(duration=silence_duration)
                combined += silence
                current_position = end_ms
        
        # Export with high quality
        combined.export(str(output_file), format="mp3", bitrate="192k")

    def _time_to_ms(self, time_str: str) -> int:
        """Convert SRT time format to milliseconds"""
        hours, minutes, seconds = time_str.split(':')
        seconds, milliseconds = seconds.split(',')
        return (int(hours) * 3600000 + 
                int(minutes) * 60000 + 
                int(seconds) * 1000 + 
                int(milliseconds))