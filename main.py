import flet as ft
from subtitle_processor import SubtitleProcessor
from audio_utils import AudioProcessor
import asyncio
import os
from pathlib import Path
from typing import Optional, Dict, List, Set
import time
import json
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor

def main(page: ft.Page):
    page.title = "SubtitleToAudio"
    page.theme_mode = ft.ThemeMode.SYSTEM
    page.window.width = 1000
    page.window.height = 800
    page.padding = 20
    page.bgcolor = ft.colors.BACKGROUND
    
    # Initialize processors
    subtitle_processor = SubtitleProcessor()
    audio_processor = AudioProcessor(max_workers=15)
    
    # State variables
    is_converting = False
    is_paused = False
    selected_files = []
    current_batch_start = 0
    current_file = None
    failed_segments: Dict[str, Set[int]] = {}
    
    # Settings dialog
    def show_settings(e):
        # Update fields with current settings
        workers_field.value = str(audio_processor.settings.get("max_workers", 15))
        batch_field.value = str(audio_processor.settings.get("batch_size", 10))
        retry_field.value = str(audio_processor.settings.get("retry_attempts", 3))
        voice_dropdown.value = audio_processor.settings.get("voice", "en-US-EmmaNeural")
        auto_cleanup_switch.value = audio_processor.settings.get("auto_cleanup", True)
        
        # Update sliders
        rate_slider.value = float(audio_processor.settings.get("rate", "+0%").rstrip("%")) / 100 * 50
        volume_slider.value = float(audio_processor.settings.get("volume", "+0%").rstrip("%")) / 100 * 50
        pitch_slider.value = float(audio_processor.settings.get("pitch", "+0Hz").rstrip("Hz"))
        wpm_field.value = str(audio_processor.settings.get("words_per_minute", "")) if audio_processor.settings.get("words_per_minute") else ""
        settings_dialog.open = True
        page.update()

    def close_settings(e=None):
        settings_dialog.open = False
        page.update()

    def reset_to_defaults(e):
        # Default values
        workers_field.value = "15"
        batch_field.value = "10"
        retry_field.value = "3"
        voice_dropdown.value = "en-US-EmmaNeural"
        auto_cleanup_switch.value = True
        rate_slider.value = 0
        volume_slider.value = 0
        pitch_slider.value = 0
        wpm_field.value = ""
        page.update()

    def save_settings(e):
        try:
            new_workers = int(workers_field.value)
            new_batch = int(batch_field.value)
            new_retry = int(retry_field.value)
            new_wpm = int(wpm_field.value) if wpm_field.value.strip() else None
            new_auto_cleanup = auto_cleanup_switch.value

            if not (1 <= new_workers <= 50):
                raise ValueError("Max workers must be between 1 and 50")
            if not (1 <= new_batch <= 100):
                raise ValueError("Batch size must be between 1 and 100")
            if not (1 <= new_retry <= 10):
                raise ValueError("Retry attempts must be between 1 and 10")
            if new_wpm is not None and not (50 <= new_wpm <= 600):
                raise ValueError("Words per minute must be between 50 and 600")

            # Format voice settings with proper signs
            rate_val = float(rate_slider.value)
            volume_val = float(volume_slider.value)
            pitch_val = float(pitch_slider.value)

            settings = {
                "max_workers": new_workers,
                "batch_size": new_batch,
                "retry_attempts": new_retry,
                "voice": voice_dropdown.value,
                "rate": f"{int((rate_val / 50) * 100):+d}%",
                "volume": f"{int((volume_val / 50) * 100):+d}%",
                "pitch": f"{int(pitch_val):+d}Hz",
                "words_per_minute": new_wpm,
                "auto_cleanup": new_auto_cleanup,
            }
            
            with open("app_settings.json", "w") as f:
                json.dump(settings, f)
            
            audio_processor.settings = settings
            audio_processor.executor = ThreadPoolExecutor(max_workers=new_workers)
            
            close_settings()
            page.show_snack_bar(ft.SnackBar(content=ft.Text("Settings saved successfully!")))
        except ValueError as e:
            page.show_snack_bar(ft.SnackBar(content=ft.Text(str(e)), bgcolor=ft.colors.ERROR))
        page.update()

    # Settings fields with descriptions
    workers_field = ft.TextField(
        label="Max Workers (1-50)",
        value="15",
        width=300,
        helper_text="Number of parallel processing threads",
        text_size=14,
        border_color=ft.colors.BLUE_200,
        height=65,
    )
    
    batch_field = ft.TextField(
        label="Batch Size (1-100)",
        value="10",
        width=300,
        helper_text="Number of segments to process at once",
        text_size=14,
        border_color=ft.colors.BLUE_200,
        height=65,
    )
    
    retry_field = ft.TextField(
        label="Retry Attempts (1-10)",
        value="3",
        width=300,
        helper_text="Number of retries on failure",
        text_size=14,
        border_color=ft.colors.BLUE_200,
        height=65,
    )

    auto_cleanup_switch = ft.Switch(
        label="Auto Cleanup Temporary Files",
        value=True,
        label_position=ft.LabelPosition.LEFT,
        active_color=ft.colors.BLUE_700,
        active_track_color=ft.colors.BLUE_200,
    )

    # Voice settings
    voices = audio_processor.voice_manager.voices.get('voices', [])
    voice_dropdown = ft.Dropdown(
        label="Voice",
        options=[ft.dropdown.Option(voice) for voice in voices],
        value=audio_processor.settings.get("voice", "en-US-EmmaNeural"),
        width=300,
        helper_text="Select voice for text-to-speech conversion",
        border_color=ft.colors.BLUE_200,
        height=65,
    )

    # Sliders for voice adjustments with better value ranges
    rate_slider = ft.Slider(
        min=-50,
        max=50,
        value=0,
        label="{value}",
        divisions=20,
        width=300,
    )
    rate_label = ft.Text("Speech Rate:", size=14, weight=ft.FontWeight.BOLD)
    rate_value = ft.Text("+0%", size=14, color=ft.colors.BLUE)
    
    def on_rate_change(e):
        try:
            if e.data and e.data.strip():
                val = float(e.data)
                # Convert -50 to +50 range to -100% to +100%
                percentage = int((val / 50) * 100)
                rate_value.value = f"{percentage:+d}%"
                page.update()
        except ValueError:
            pass

    rate_slider.on_change = on_rate_change

    volume_slider = ft.Slider(
        min=-50,
        max=50,
        value=0,
        label="{value}",
        divisions=20,
        width=300,
    )
    volume_label = ft.Text("Volume:", size=14, weight=ft.FontWeight.BOLD)
    volume_value = ft.Text("+0%", size=14, color=ft.colors.BLUE)
    
    def on_volume_change(e):
        try:
            if e.data and e.data.strip():
                val = float(e.data)
                # Convert -50 to +50 range to -100% to +100%
                percentage = int((val / 50) * 100)
                volume_value.value = f"{percentage:+d}%"
                page.update()
        except ValueError:
            pass

    volume_slider.on_change = on_volume_change

    pitch_slider = ft.Slider(
        min=-50,
        max=50,
        value=0,
        label="{value}",
        divisions=20,
        width=300,
    )
    pitch_label = ft.Text("Pitch:", size=14, weight=ft.FontWeight.BOLD)
    pitch_value = ft.Text("+0Hz", size=14, color=ft.colors.BLUE)
    
    def on_pitch_change(e):
        try:
            if e.data and e.data.strip():
                val = float(e.data)
                # Keep the Hz range as is
                pitch_value.value = f"{int(val):+d}Hz"
                page.update()
        except ValueError:
            pass

    pitch_slider.on_change = on_pitch_change

    wpm_field = ft.TextField(
        label="Words per Minute",
        value="",
        width=300,
        helper_text="Optional: 50-600 WPM (leave empty for default)",
        text_size=14,
        border_color=ft.colors.BLUE_200,
        height=65,
    )

    # Create tabs for settings
    processing_tab = ft.Tab(
        text="Processing",
        content=ft.Container(
            content=ft.Column([
                ft.Container(
                    content=ft.Column([
                        ft.Container(
                            content=workers_field,
                            padding=ft.padding.only(bottom=15)
                        ),
                        ft.Container(
                            content=batch_field,
                            padding=ft.padding.only(bottom=15)
                        ),
                        ft.Container(
                            content=retry_field,
                            padding=ft.padding.only(bottom=15)
                        ),
                        ft.Container(
                            content=auto_cleanup_switch,
                            padding=ft.padding.only(bottom=10)
                        ),
                    ]),
                    padding=20
                ),
            ]),
            padding=10,
        ),
    )

    voice_tab = ft.Tab(
        text="Voice",
        content=ft.Container(
            content=ft.Column([
                ft.Container(
                    content=ft.Column([
                        voice_dropdown,
                        ft.Container(height=20),
                        ft.Container(
                            content=ft.Column([
                                rate_label,
                                ft.Row([rate_slider, rate_value], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
                                ft.Container(height=10),
                                volume_label,
                                ft.Row([volume_slider, volume_value], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
                                ft.Container(height=10),
                                pitch_label,
                                ft.Row([pitch_slider, pitch_value], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
                            ], spacing=10),
                        ),
                        ft.Container(height=20),
                        wpm_field,
                    ], spacing=10),
                    padding=20
                ),
            ]),
            padding=10,
        ),
    )

    settings_dialog = ft.AlertDialog(
        modal=True,
        title=ft.Text("Settings", size=20, weight=ft.FontWeight.BOLD, color=ft.colors.BLUE_700),
        content=ft.Container(
            content=ft.Column([
                ft.Tabs(
                    selected_index=0,
                    animation_duration=300,
                    tabs=[
                        ft.Tab(
                            text="Processing",
                            content=ft.Container(
                                content=ft.Column([
                                    ft.Container(
                                        content=workers_field,
                                        padding=ft.padding.only(bottom=15)
                                    ),
                                    ft.Container(
                                        content=batch_field,
                                        padding=ft.padding.only(bottom=15)
                                    ),
                                    ft.Container(
                                        content=retry_field,
                                        padding=ft.padding.only(bottom=15)
                                    ),
                                    ft.Container(
                                        content=auto_cleanup_switch,
                                        padding=ft.padding.only(bottom=10)
                                    ),
                                ]),
                                padding=20
                            ),
                        ),
                        ft.Tab(
                            text="Voice",
                            content=ft.Container(
                                content=ft.Column([
                                    voice_dropdown,
                                    ft.Row([rate_label, rate_slider, rate_value], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
                                    ft.Row([volume_label, volume_slider, volume_value], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
                                    ft.Row([pitch_label, pitch_slider, pitch_value], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
                                    wpm_field,
                                ], spacing=10),
                                padding=20
                            ),
                        ),
                    ],
                    expand=True,
                ),
            ]),
            width=450,
            height=400,
        ),
        actions=[
            ft.Row([
                ft.TextButton(
                    "Reset to Defaults",
                    on_click=reset_to_defaults,
                    style=ft.ButtonStyle(color=ft.colors.BLUE_700)
                ),
                ft.Row([
                    ft.TextButton(
                        "Cancel",
                        on_click=close_settings,
                        style=ft.ButtonStyle(color=ft.colors.GREY_700)
                    ),
                    ft.TextButton(
                        "Save",
                        on_click=save_settings,
                        style=ft.ButtonStyle(color=ft.colors.BLUE_700)
                    ),
                ]),
            ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
        ],
        actions_alignment=ft.MainAxisAlignment.END,
        on_dismiss=close_settings,
    )
    
    # Settings button (keep it in the original position)
    settings_btn = ft.IconButton(
        icon=ft.icons.SETTINGS,
        tooltip="Settings",
        on_click=show_settings
    )
    
    # File picker
    file_picker = ft.FilePicker(
        on_result=lambda e: handle_file_picked(e)
    )
    page.overlay.append(file_picker)
    
    # Controls
    select_file_btn = ft.ElevatedButton(
        "Select Subtitles",
        icon=ft.icons.FILE_UPLOAD,
        on_click=lambda _: file_picker.pick_files(
            allowed_extensions=["srt"],
            allow_multiple=True
        ),
        style=ft.ButtonStyle(
            shape=ft.RoundedRectangleBorder(radius=8),
        ),
    )
    
    # Progress indicators
    progress_bar = ft.ProgressBar(width=400, color="primary", value=0)
    status_text = ft.Text("Ready", size=16)
    network_status = ft.Text("", size=14, color=ft.colors.ERROR)
    
    # Control buttons
    convert_btn = ft.ElevatedButton(
        "Convert",
        icon=ft.icons.PLAY_ARROW,
        on_click=lambda _: asyncio.run(start_conversion()),
        disabled=True,
        style=ft.ButtonStyle(
            shape=ft.RoundedRectangleBorder(radius=8),
        ),
    )
    
    pause_btn = ft.ElevatedButton(
        "Pause",
        icon=ft.icons.PAUSE,
        on_click=lambda _: toggle_pause(),
        disabled=True,
        style=ft.ButtonStyle(
            shape=ft.RoundedRectangleBorder(radius=8),
        ),
    )
    
    cancel_btn = ft.ElevatedButton(
        "Cancel",
        icon=ft.icons.CANCEL,
        on_click=lambda _: cancel_conversion(),
        disabled=True,
        style=ft.ButtonStyle(
            shape=ft.RoundedRectangleBorder(radius=8),
        ),
    )
    
    # Enhanced log view with colors and scrolling
    log_list = ft.ListView(
        expand=True,
        spacing=2,
        auto_scroll=True,
        height=400
    )
    
    def get_log_color(level: str) -> str:
        """Get color for log level"""
        colors = {
            'info': ft.colors.BLUE,
            'error': ft.colors.RED,
            'warning': ft.colors.ORANGE,
            'success': ft.colors.GREEN,
            'debug': ft.colors.GREY
        }
        return colors.get(level, ft.colors.BLACK)
    
    def log_message(message: str, level: str = 'info', details: str = None):
        """Enhanced logging with colors and details"""
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S.%f')[:-3]
        color = get_log_color(level)
        
        # Create main log message
        log_text = ft.Text(
            f"[{timestamp}] [{level.upper()}] {message}",
            color=color,
            size=14,
            selectable=True
        )
        
        # Add details if provided
        if details:
            detail_text = ft.Text(
                f"    ↳ {details}",
                color=ft.colors.with_opacity(0.7, color),
                size=12,
                selectable=True
            )
            container = ft.Column([log_text, detail_text], spacing=2)
        else:
            container = ft.Container(content=log_text)
        
        log_list.controls.append(container)
        
        # Keep only last 1000 log entries to prevent memory issues
        if len(log_list.controls) > 1000:
            log_list.controls.pop(0)
        
        page.update()
    
    def copy_logs():
        """Copy all logs to clipboard"""
        log_text = "\n".join([
            control.content.value if isinstance(control, ft.Container)
            else "\n".join(t.value for t in control.controls)
            for control in log_list.controls
        ])
        page.set_clipboard(log_text)
        page.show_snack_bar(ft.SnackBar(content=ft.Text("Logs copied to clipboard")))
    
    copy_log_btn = ft.IconButton(
        icon=ft.icons.COPY,
        tooltip="Copy logs",
        on_click=lambda _: copy_logs()
    )
    
    def handle_file_picked(e: ft.FilePickerResultEvent):
        nonlocal selected_files
        if e.files:
            selected_files = [file.path for file in e.files]
            file_names = ", ".join(Path(f).name for f in selected_files)
            log_message(
                f"Selected {len(selected_files)} file(s)",
                details=f"Files: {file_names}"
            )
            convert_btn.disabled = False
            page.update()
    
    def toggle_pause():
        nonlocal is_paused
        is_paused = not is_paused
        pause_btn.text = "Resume" if is_paused else "Pause"
        log_message(
            "Conversion paused" if is_paused else "Conversion resumed",
            level='warning' if is_paused else 'info'
        )
        page.update()
    
    def cancel_conversion():
        nonlocal is_converting, current_batch_start, current_file
        is_converting = False
        is_paused = False
        current_batch_start = 0
        current_file = None
        log_message("Conversion cancelled", level='warning')
        convert_btn.disabled = False
        pause_btn.disabled = True
        cancel_btn.disabled = True
        progress_bar.value = 0
        page.update()
    
    async def process_subtitle_file(file: str, output_folder: Path) -> bool:
        nonlocal current_batch_start, current_file, failed_segments
        log_message(f"Starting subtitle file processing.", level='info', details=f"Processing file: {file}")
        current_file = file

        try:
            # Parse subtitles from file
            subtitles = subtitle_processor.parse_subtitle_file(file)
            total_segments = len(subtitles)
            batch_size = int(batch_field.value)

            log_message(
                "Parsed subtitle file successfully.",
                level='info',
                details=f"Total segments parsed: {total_segments}, Batch size configured: {batch_size}"
            )

            # Initialize failed segments for retry logic
            if file not in failed_segments:
                failed_segments[file] = set()
                log_message(
                    "Initialized failed segments tracking.",
                    level='debug',
                    details=f"No previously failed segments found."
                )

            processed_segments = 0

            while failed_segments[file] or current_batch_start < total_segments:
                if not is_converting:
                    log_message(
                        "Conversion interrupted by user.",
                        level='warning',
                        details=f"Processing terminated early."
                    )
                    return False

                while is_paused:
                    log_message(
                        "Processing paused.",
                        level='warning',
                        details=f"Awaiting resume."
                    )
                    await asyncio.sleep(0.1)

                if failed_segments[file]:
                    failed_batch = list(failed_segments[file])[:batch_size]
                    segments_to_process = [(i, *subtitles[i-1][1:]) for i in failed_batch]
                    failed_segments[file] -= set(failed_batch)
                    log_message(
                        "Retrying failed segments.",
                        level='warning',
                        details=f"Retrying {len(failed_batch)} failed segments."
                    )
                else:
                    end_idx = min(current_batch_start + batch_size, total_segments)
                    segments_to_process = subtitles[current_batch_start:end_idx]
                    log_message(
                        "Processing new segment batch.",
                        level='debug',
                        details=f"Processing segments {current_batch_start+1} to {end_idx} of {total_segments}"
                    )

                try:
                    results = await audio_processor.process_batch(
                        segments_to_process,
                        voice_dropdown.value,
                        output_folder,
                        current_batch_start,
                        batch_size
                    )

                    success_count = 0
                    for idx, (output_file, success, error) in enumerate(results):
                        if not success:
                            segment_idx = segments_to_process[idx][0]
                            failed_segments[file].add(segment_idx)

                            if "Internet connection lost" in error:
                                log_message(
                                    "Internet connection lost during processing.",
                                    level='error',
                                    details=f"Segment index {segment_idx}: {error}"
                                )
                                network_status.value = "⚠️ Internet connection lost. Will retry failed segments..."
                                page.update()
                                await asyncio.sleep(2)
                            else:
                                log_message(
                                    "Error processing segment.",
                                    level='error',
                                    details=f"Segment index {segment_idx}: {error}"
                                )
                        else:
                            success_count += 1
                            processed_segments += 1

                    if success_count > 0:
                        log_message(
                            "Successfully processed batch.",
                            level='success',
                            details=f"Successfully processed {success_count}/{len(results)} segments."
                        )

                    # Update progress bar after each successful batch
                    if not failed_segments[file]:
                        current_batch_start = min(current_batch_start + batch_size, total_segments)
                        progress = processed_segments / total_segments
                        progress_bar.value = progress
                        status_text.value = f"Converting: {int(progress * 100)}%"
                        page.update()

                        log_message(
                            "Progress updated.",
                            level='debug',
                            details=f"Progress: {int(progress * 100)}%"
                        )

                except Exception as e:
                    log_message(
                        "Unexpected error occurred during batch processing.",
                        level='error',
                        details=f"Error: {str(e)}"
                    )
                    for segment in segments_to_process:
                        failed_segments[file].add(segment[0])
                    await asyncio.sleep(1)
                    continue

            if not failed_segments[file]:
                output_file = Path(file).parent / f"{Path(file).stem}_audio.mp3"
                audio_files = list(output_folder.glob("*.mp3"))
                log_message(
                    "Combining audio files.",
                    level='info',
                    details=f"Combining {len(audio_files)} audio files with timing adjustments."
                )
                audio_processor.combine_audio_files(subtitles, audio_files, output_file)
                log_message(
                    "Audio combination completed successfully.",
                    level='success',
                    details=f"Output file: {output_file.name}, Size: {output_file.stat().st_size / (1024 * 1024):.2f} MB"
                )
                return True
            else:
                log_message(
                    "Failed segments remain after processing.",
                    level='error',
                    details=f"Total failed segments: {len(failed_segments[file])}"
                )
                return False

        except Exception as e:
            log_message(
                "Unexpected exception during subtitle file processing.",
                level='error',
                details=f"Error: {str(e)}"
            )
            return False
        finally:
            current_file = None
            current_batch_start = 0
            log_message(
                "Final cleanup complete.",
                level='debug',
                details="Resetting internal state after subtitle processing attempt."
            )


    async def start_conversion():
        nonlocal is_converting, failed_segments
        convert_btn.disabled = True
        pause_btn.disabled = False
        cancel_btn.disabled = False
        is_converting = True
        failed_segments = {}
        network_status.value = ""
        page.update()
        
        try:
            total_files = len(selected_files)
            for file_idx, file in enumerate(selected_files):
                if not is_converting:
                    break
                
                output_folder = subtitle_processor.create_subtitle_folder(file)
                log_message(
                    f"Starting file {file_idx + 1}/{total_files}",
                    details=f"File: {Path(file).name}"
                )
                
                while is_converting:
                    if await process_subtitle_file(file, output_folder):
                        break
                    if not is_converting:
                        break
                    log_message(
                        f"Retrying failed segments",
                        level='warning',
                        details=f"File: {Path(file).name}"
                    )
                    await asyncio.sleep(1)
                
                progress_bar.value = (file_idx + 1) / total_files
                page.update()
            
        except Exception as e:
            log_message(
                "Conversion error",
                level='error',
                details=f"Error: {str(e)}"
            )
        finally:
            convert_btn.disabled = False
            pause_btn.disabled = True
            cancel_btn.disabled = True
            is_converting = False
            progress_bar.value = 0
            page.update()
    
    def on_exit(e):
        audio_processor.shutdown_executor()
        
    page.on_close = on_exit
    
    # Main layout
    main_content = ft.Column([
        ft.Container(
            content=ft.Column([
                ft.Row([
                    select_file_btn,
                    settings_btn
                ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
                ft.Row([
                    convert_btn,
                    pause_btn,
                    cancel_btn,
                ]),
                ft.Column([
                    progress_bar,
                    status_text,
                    network_status,
                ]),
            ]),
            padding=20,
            border_radius=10,
            bgcolor=ft.colors.SURFACE_VARIANT,
        ),
        ft.Container(
            content=ft.Column([
                ft.Row([
                    ft.Text("Logs", size=16, weight=ft.FontWeight.BOLD),
                    copy_log_btn,
                ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
                log_list,
            ]),
            padding=20,
            border_radius=10,
            bgcolor=ft.colors.SURFACE_VARIANT,
            margin=ft.margin.only(top=20),
            expand=True
        ),
    ], expand=True)
    
    # Footer with divider
    footer = ft.Container(
        content=ft.Column([
            ft.Divider(
                height=1,
                color=ft.colors.with_opacity(0.2, ft.colors.ON_SURFACE_VARIANT)
            ),
            ft.Row([
                ft.Text("Created by "),
                ft.TextButton(
                    "bionicop",
                    url="https://github.com/bionicop",
                    tooltip="Visit GitHub Profile"
                ),
            ], alignment=ft.MainAxisAlignment.CENTER),
        ]),
        margin=ft.margin.only(top=20),
    )
    
    # Add everything to the page
    page.add(
        ft.Column([
            main_content,
            footer,
            settings_dialog
        ], expand=True)
    )

if __name__ == "__main__":
    ft.app(target=main)