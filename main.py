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

def main(page: ft.Page):
    page.title = "SubtitleToAudio"
    page.theme_mode = ft.ThemeMode.SYSTEM
    page.window_width = 1000
    page.window_height = 800
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
    
    # Voice selection
    voices = audio_processor.voice_manager.voices.get('voices', [])
    last_voice = audio_processor.voice_manager.voices.get('last_used_voice', 'en-US-EmmaNeural')
    
    voice_dropdown = ft.Dropdown(
        label="Voice",
        options=[ft.dropdown.Option(voice) for voice in voices],
        value=last_voice,
        width=200,
        on_change=lambda e: on_voice_change(e)
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
    
    def on_voice_change(e):
        with open('config.json', 'r+') as f:
            config = json.load(f)
            config['last_used_voice'] = e.data
            f.seek(0)
            json.dump(config, f)
            f.truncate()
        log_message(f"Voice changed to: {e.data}", level='info')
    
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
        current_file = file
        
        try:
            subtitles = subtitle_processor.parse_subtitle_file(file)
            total_segments = len(subtitles)
            batch_size = 15
            
            log_message(
                f"Processing file: {Path(file).name}",
                details=f"Total segments: {total_segments}, Batch size: {batch_size}"
            )
            
            if file not in failed_segments:
                failed_segments[file] = set()
            
            while failed_segments[file] or current_batch_start < total_segments:
                if not is_converting:
                    return False
                
                while is_paused:
                    await asyncio.sleep(0.1)
                
                if failed_segments[file]:
                    failed_batch = list(failed_segments[file])[:batch_size]
                    segments_to_process = [(i, *subtitles[i-1][1:]) for i in failed_batch]
                    failed_segments[file] -= set(failed_batch)
                    log_message(
                        f"Retrying failed segments",
                        details=f"Processing {len(failed_batch)} failed segments"
                    )
                else:
                    end_idx = min(current_batch_start + batch_size, total_segments)
                    segments_to_process = subtitles[current_batch_start:end_idx]
                    log_message(
                        f"Processing batch {current_batch_start//batch_size + 1}",
                        level='debug',
                        details=f"Segments {current_batch_start+1} to {end_idx} of {total_segments}"
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
                                network_status.value = "⚠️ Internet connection lost. Will retry failed segments..."
                                log_message(
                                    f"Internet connection lost at segment {segment_idx}",
                                    level='error',
                                    details=f"Error: {error}"
                                )
                                page.update()
                                await asyncio.sleep(2)
                            else:
                                log_message(
                                    f"Error processing segment {segment_idx}",
                                    level='error',
                                    details=f"Error: {error}"
                                )
                        else:
                            success_count += 1
                    
                    if success_count > 0:
                        log_message(
                            f"Batch completed",
                            level='success',
                            details=f"Successfully processed {success_count}/{len(results)} segments"
                        )
                    
                    if not failed_segments[file]:
                        current_batch_start = min(current_batch_start + batch_size, total_segments)
                        progress = min(current_batch_start / total_segments, 1.0)
                        status_text.value = f"Converting: {int(progress * 100)}%"
                        network_status.value = ""
                        page.update()
                    
                except Exception as e:
                    log_message(
                        f"Batch processing error",
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
                    "Combining audio files",
                    details=f"Combining {len(audio_files)} segments with timing"
                )
                audio_processor.combine_audio_files(subtitles, audio_files, output_file)
                log_message(
                    f"Created combined audio: {output_file.name}",
                    level='success',
                    details=f"Output size: {output_file.stat().st_size / (1024*1024):.2f} MB"
                )
                return True
            else:
                log_message(
                    f"Cannot complete file {Path(file).name}",
                    level='error',
                    details=f"Failed segments: {len(failed_segments[file])}"
                )
                return False
            
        except Exception as e:
            log_message(
                f"Failed to process {Path(file).name}",
                level='error',
                details=f"Error: {str(e)}"
            )
            return False
        finally:
            current_file = None
            current_batch_start = 0
    
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
    
    # Main layout
    main_content = ft.Column([
        ft.Container(
            content=ft.Column([
                ft.Row([
                    select_file_btn,
                    voice_dropdown,
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
            footer
        ], expand=True)
    )

if __name__ == "__main__":
    ft.app(target=main)