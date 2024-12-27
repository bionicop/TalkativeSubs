import subprocess
from pathlib import Path

class VideoService:
    def extract_audio(self, video_path: str) -> str:
        """
        Extracts audio from a video file and saves it as an MP3 file.
        Returns the path to the extracted audio file.
        """
        try:
            video_path = Path(video_path)
            audio_path = video_path.with_suffix(".mp3")
            
            # Use ffmpeg to extract audio
            command = [
                "ffmpeg",
                "-i", str(video_path),  # Input video file
                "-q:a", "0",            # Best audio quality
                "-map", "a",            # Extract only audio
                str(audio_path)         # Output audio file
            ]
            
            subprocess.run(command, check=True)
            return str(audio_path)
        except subprocess.CalledProcessError as e:
            raise Exception(f"Failed to extract audio from video: {e}")
        except Exception as e:
            raise Exception(f"An error occurred while extracting audio: {e}")