import flet as ft
from pathlib import Path
from googletrans import LANGUAGES
from services.video_service import VideoService
from services.subtitle_service import WhisperSubtitleService
from services.translation_service import TranslationService
from utils.model_manager import WhisperModelManager
from components.file_selection import FileSelectionComponent
from components.progress_bar import ProgressBarComponent
from components.logger import LoggerComponent
from components.buttons import CustomButton
import asyncio
from constants.paths import TEMP_DIR

class AudioToSubScreen:
    def __init__(self, page: ft.Page):
        self.page = page
        self.video_service = VideoService()
        self.subtitle_service = WhisperSubtitleService()
        self.translation_service = TranslationService()
        self.model_manager = WhisperModelManager()
        self.setup_ui()

    def setup_ui(self):
        self.file_selection = FileSelectionComponent(
            self.page,
            ["mp4", "mkv", "avi", "mov", "mp3", "wav"],
            self.on_files_selected
        )

        self.progress_bar = ProgressBarComponent(self.page)
        self.logger = LoggerComponent(self.page)

        self.process_btn = CustomButton(
            "Generate Subtitles",
            ft.icons.CLOSED_CAPTION,
            self.on_process_click,
            disabled=True
        ).get_button()

        self.language_dropdown = ft.Dropdown(
            label="Target Language",
            options=[ft.dropdown.Option(code, f"{name.title()} ({code})") for code, name in LANGUAGES.items()],
            value="en",
            width=300,
        )

        self.controls_container = ft.Container(
            content=ft.Column([
                self.file_selection.get_container(),
                self.language_dropdown,
                self.process_btn,
                self.progress_bar.get_container(),
                self.logger.get_container(),
            ])
        )

    def on_files_selected(self, files):
        self.process_btn.disabled = len(files) == 0
        self.page.update()

    async def on_process_click(self, e):
        try:
            self.process_btn.disabled = True
            self.file_selection.enable_selection(False)
            self.progress_bar.update_progress(progress=0, status="Starting...")

            for file_path in self.file_selection.selected_files:
                self.logger.log_message(f"Processing file: {Path(file_path).name}")

                if Path(file_path).suffix.lower() in ['.mp4', '.mkv', '.avi', '.mov']:
                    self.logger.log_message("Extracting audio from video...")
                    audio_path = await asyncio.to_thread(self.video_service.extract_audio, file_path)
                else:
                    audio_path = file_path

                model = self.model_manager.get_model()
                self.logger.log_message("Generating subtitles...")
                subtitles, detected_language = await asyncio.to_thread(self.subtitle_service.generate_subtitles, model, audio_path)
                self.logger.log_message(f"Detected language: {detected_language}", level="info")

                base_name = Path(file_path).stem
                original_srt = Path(TEMP_DIR) / f"{base_name}_original.srt"
                await asyncio.to_thread(self.subtitle_service.save_subtitles, subtitles, original_srt)
                self.logger.log_message(f"Original subtitles saved to: {original_srt}", level="success")

                target_lang = self.language_dropdown.value
                if target_lang != detected_language:
                    self.logger.log_message(f"Translating subtitles from {detected_language} to {target_lang}...")
                    translated_subtitles = await asyncio.to_thread(
                        self.translation_service.translate_subtitles, subtitles, detected_language, target_lang
                    )
                    translated_srt = Path(file_path).parent / f"{base_name}_{target_lang}.srt"
                    await asyncio.to_thread(self.subtitle_service.save_subtitles, translated_subtitles, translated_srt)
                    self.logger.log_message(f"Translated subtitles saved to: {translated_srt}", level="success")
                else:
                    final_srt = Path(file_path).parent / f"{base_name}_{detected_language}.srt"
                    await asyncio.to_thread(self.subtitle_service.save_subtitles, subtitles, final_srt)
                    self.logger.log_message(f"Subtitles saved to: {final_srt}", level="success")

                self.progress_bar.update_progress(progress=1, status="Completed")
        except Exception as e:
            self.logger.log_message(f"Error processing file: {str(e)}", level="error")
        finally:
            self.process_btn.disabled = False
            self.file_selection.enable_selection(True)
            await self.page.update_async()

    def get_content(self):
        return self.controls_container