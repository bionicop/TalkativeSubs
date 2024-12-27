import os
import whisper
from pathlib import Path

class WhisperModelManager:
    def __init__(self):
        self.model_cache = {}
        self.models_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "models")
        os.makedirs(self.models_dir, exist_ok=True)

    def get_model(self, model_name="base"):
        if model_name in self.model_cache:
            return self.model_cache[model_name]

        model_path = os.path.join(self.models_dir, f"{model_name}.pt")
        if os.path.exists(model_path):
            print(f"Loading {model_name} model from disk...")
            self.model_cache[model_name] = whisper.load_model(model_path)
            return self.model_cache[model_name]

        print(f"Downloading {model_name} model...")
        try:
            self.model_cache[model_name] = whisper.load_model(model_name, download_root=self.models_dir)
            print(f"{model_name} model downloaded successfully.")
            return self.model_cache[model_name]
        except Exception as e:
            print(f"Failed to download {model_name} model: {str(e)}")
            raise

    def is_model_downloaded(self, model_name):
        model_path = os.path.join(self.models_dir, f"{model_name}.pt")
        return os.path.exists(model_path)