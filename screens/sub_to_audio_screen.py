import flet as ft
from pathlib import Path
from services.audio_processor import AudioProcessor
from services.subtitle_service import SubtitleProcessor
from components.file_selection import FileSelectionComponent
from components.progress_bar import ProgressBarComponent
from components.logger import LoggerComponent
from components.buttons import CustomButton
import asyncio
import json
from typing import Dict, Set
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor

class SubToAudioScreen:
    def __init__(self, page: ft.Page, audio_processor: AudioProcessor):
        self.page = page
        self.audio_processor = audio_processor
        self.subtitle_processor = SubtitleProcessor()
        self.is_converting = False
        self.is_paused = False
        self.is_cancelled = False
        self.selected_files = []
        self.current_batch_start = 0
        self.current_file = None
        self.failed_segments: Dict[str, Set[int]] = {}
        self.setup_ui()

    def setup_ui(self):
        self.file_selection = FileSelectionComponent(
            self.page,
            ["srt"],
            self.on_files_selected
        )

        self.progress_bar = ProgressBarComponent(self.page)
        self.logger = LoggerComponent(self.page)

        self.convert_btn = CustomButton(
            "Convert",
            ft.icons.PLAY_ARROW,
            self.on_convert_click,
            disabled=True
        ).get_button()

        self.pause_btn = CustomButton(
            "Pause",
            ft.icons.PAUSE,
            self.on_pause_click,
            disabled=True
        ).get_button()

        self.cancel_btn = CustomButton(
            "Cancel",
            ft.icons.CANCEL,
            self.on_cancel_click,
            disabled=True
        ).get_button()

        self.controls_container = ft.Container(
            content=ft.Column([
                ft.Row([self.convert_btn, self.pause_btn, self.cancel_btn]),
                self.file_selection.get_container(),
                self.progress_bar.get_container(),
                self.logger.get_container()
            ])
        )

    def on_files_selected(self, files):
        self.selected_files = files
        self.convert_btn.disabled = len(self.selected_files) == 0
        self.logger.log_message(
            f"Selected {len(self.selected_files)} file(s)",
            level='info',
            details=f"Files: {', '.join(Path(f).name for f in self.selected_files)}"
        )
        self.page.update()

    def on_convert_click(self, e):
        self.page.run_task(self.convert_subtitles_to_audio)

    def on_pause_click(self, e):
        self.is_paused = not self.is_paused
        self.pause_btn.text = "Resume" if self.is_paused else "Pause"
        self.pause_btn.icon = ft.icons.PLAY_ARROW if self.is_paused else ft.icons.PAUSE
        self.logger.log_message(
            "Conversion paused" if self.is_paused else "Conversion resumed",
            level='warning' if self.is_paused else 'info'
        )
        self.page.update()

    def on_cancel_click(self, e):
        self.is_cancelled = True
        self.is_converting = False
        self.is_paused = False
        self.logger.log_message("Conversion cancelled", level='warning')
        self.progress_bar.reset()
        self.reset_buttons()
        self.page.update()

    def reset_buttons(self):
        self.convert_btn.disabled = False
        self.pause_btn.disabled = True
        self.cancel_btn.disabled = True
        self.pause_btn.text = "Pause"
        self.pause_btn.icon = ft.icons.PAUSE

    async def convert_subtitles_to_audio(self):
        self.is_converting = True
        self.is_paused = False
        self.is_cancelled = False
        self.convert_btn.disabled = True
        self.pause_btn.disabled = False
        self.cancel_btn.disabled = False
        self.progress_bar.update_progress(progress=0, status="Starting...")
        self.logger.log_message("Conversion started", level='info')

        try:
            total_files = len(self.selected_files)
            for file_idx, file in enumerate(self.selected_files):
                if self.is_cancelled:
                    self.logger.log_message("Conversion cancelled by user", level='warning')
                    break

                output_folder = self.subtitle_processor.create_subtitle_folder(file)
                self.logger.log_message(
                    f"Starting file {file_idx + 1}/{total_files}",
                    level='info',
                    details=f"File: {Path(file).name}"
                )

                while self.is_converting:
                    if await self.process_subtitle_file(file, output_folder):
                        break
                    if not self.is_converting:
                        break
                    self.logger.log_message(
                        "Retrying failed segments",
                        level='warning',
                        details=f"File: {Path(file).name}"
                    )
                    await asyncio.sleep(1)

                progress = (file_idx + 1) / total_files
                self.progress_bar.update_progress(progress=progress, status=f"Processing file {file_idx + 1}/{total_files}")
                self.page.update()

        except Exception as e:
            self.logger.log_message(
                "Conversion error",
                level='error',
                details=f"Error: {str(e)}"
            )
        finally:
            self.reset_buttons()
            self.is_converting = False
            self.progress_bar.update_progress(progress=1, status="Completed")
            self.logger.log_message("Conversion process finished.", level='info')

    async def process_subtitle_file(self, file: str, output_folder: Path) -> bool:
        self.current_file = file
        self.logger.log_message(f"Starting subtitle file processing.", level='info', details=f"Processing file: {file}")

        try:
            subtitles = self.subtitle_processor.parse_subtitle_file(file)
            total_segments = len(subtitles)
            batch_size = int(self.audio_processor.settings.get("batch_size", 10))

            self.logger.log_message(
                "Parsed subtitle file successfully.",
                level='info',
                details=f"Total segments parsed: {total_segments}, Batch size configured: {batch_size}"
            )

            if file not in self.failed_segments:
                self.failed_segments[file] = set()
                self.logger.log_message(
                    "Initialized failed segments tracking.",
                    level='debug',
                    details=f"No previously failed segments found."
                )

            processed_segments = 0

            while self.failed_segments[file] or self.current_batch_start < total_segments:
                if self.is_cancelled:
                    self.logger.log_message(
                        "Conversion cancelled by user.",
                        level='warning',
                        details=f"Processing terminated early."
                    )
                    return False

                while self.is_paused:
                    await asyncio.sleep(0.1)

                if self.failed_segments[file]:
                    failed_batch = list(self.failed_segments[file])[:batch_size]
                    segments_to_process = [(i, *subtitles[i-1][1:]) for i in failed_batch]
                    self.failed_segments[file] -= set(failed_batch)
                    self.logger.log_message(
                        "Retrying failed segments.",
                        level='warning',
                        details=f"Retrying {len(failed_batch)} failed segments."
                    )
                else:
                    end_idx = min(self.current_batch_start + batch_size, total_segments)
                    segments_to_process = subtitles[self.current_batch_start:end_idx]
                    self.logger.log_message(
                        "Processing new segment batch.",
                        level='debug',
                        details=f"Processing segments {self.current_batch_start+1} to {end_idx} of {total_segments}"
                    )

                try:
                    results = await self.audio_processor.process_batch(
                        segments_to_process,
                        self.audio_processor.settings.get("voice", "en-US-EmmaNeural"),
                        output_folder,
                        self.current_batch_start,
                        batch_size
                    )

                    success_count = 0
                    for idx, (output_file, success, error) in enumerate(results):
                        if not success:
                            segment_idx = segments_to_process[idx][0]
                            self.failed_segments[file].add(segment_idx)

                            if "Internet connection lost" in error:
                                self.logger.log_message(
                                    "Internet connection lost during processing.",
                                    level='error',
                                    details=f"Segment index {segment_idx}: {error}"
                                )
                                await asyncio.sleep(2)
                            else:
                                self.logger.log_message(
                                    "Error processing segment.",
                                    level='error',
                                    details=f"Segment index {segment_idx}: {error}"
                                )
                        else:
                            success_count += 1
                            processed_segments += 1

                    if success_count > 0:
                        self.logger.log_message(
                            "Successfully processed batch.",
                            level='success',
                            details=f"Successfully processed {success_count}/{len(results)} segments."
                        )

                    if not self.failed_segments[file]:
                        self.current_batch_start = min(self.current_batch_start + batch_size, total_segments)
                        progress = processed_segments / total_segments
                        self.progress_bar.update_progress(progress=progress, status=f"Converting: {int(progress * 100)}%")
                        self.page.update()

                except Exception as e:
                    self.logger.log_message(
                        "Unexpected error occurred during batch processing.",
                        level='error',
                        details=f"Error: {str(e)}"
                    )
                    for segment in segments_to_process:
                        self.failed_segments[file].add(segment[0])
                    await asyncio.sleep(1)
                    continue

            if not self.failed_segments[file]:
                output_file = Path(file).parent / f"{Path(file).stem}_audio.mp3"
                audio_files = list(output_folder.glob("*.mp3"))
                self.logger.log_message(
                    "Combining audio files.",
                    level='info',
                    details=f"Combining {len(audio_files)} audio files with timing adjustments."
                )
                self.audio_processor.combine_audio_files(subtitles, audio_files, output_file)
                self.logger.log_message(
                    "Audio combination completed successfully.",
                    level='success',
                    details=f"Output file: {output_file.name}, Size: {output_file.stat().st_size / (1024 * 1024):.2f} MB"
                )
                return True
            else:
                self.logger.log_message(
                    "Failed segments remain after processing.",
                    level='error',
                    details=f"Total failed segments: {len(self.failed_segments[file])}"
                )
                return False

        except Exception as e:
            self.logger.log_message(
                "Unexpected exception during subtitle file processing.",
                level='error',
                details=f"Error: {str(e)}"
            )
            return False
        finally:
            self.current_file = None
            self.current_batch_start = 0
            self.logger.log_message(
                "Final cleanup complete.",
                level='debug',
                details="Resetting internal state after subtitle processing attempt."
            )

    def get_content(self):
        return self.controls_container