import flet as ft
import json
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
from services.audio_processor import AudioProcessor
from utils.model_manager import WhisperModelManager

def show_settings(page, audio_processor: AudioProcessor):
    model_manager = WhisperModelManager()

    # Load settings
    def load_settings():
        try:
            if Path("app_settings.json").exists():
                with open("app_settings.json", "r") as f:
                    return json.load(f)
            else:
                # Return default settings if the file doesn't exist
                return {
                    "max_workers": 15,
                    "batch_size": 10,
                    "retry_attempts": 3,
                    "auto_cleanup": True,
                    "voice": "en-US-EmmaNeural",
                    "rate": "+0%",
                    "volume": "+0%",
                    "pitch": "+0Hz",
                    "words_per_minute": None,
                    "whisper_model": "base",
                }
        except (FileNotFoundError, json.JSONDecodeError):
            # Return default settings if there's an error reading the file
            return {
                "max_workers": 15,
                "batch_size": 10,
                "retry_attempts": 3,
                "auto_cleanup": True,
                "voice": "en-US-EmmaNeural",
                "rate": "+0%",
                "volume": "+0%",
                "pitch": "+0Hz",
                "words_per_minute": None,
                "whisper_model": "base",
            }

    settings = load_settings()

    # Settings fields with descriptions
    workers_field = ft.TextField(
        label="Max Workers (1-50)",
        value=str(settings.get("max_workers", 15)),
        width=300,
        helper_text="Number of parallel processing threads",
        text_size=14,
        border_color=ft.colors.BLUE_200,
        height=65,
    )
    
    batch_field = ft.TextField(
        label="Batch Size (1-100)",
        value=str(settings.get("batch_size", 10)),
        width=300,
        helper_text="Number of segments to process at once",
        text_size=14,
        border_color=ft.colors.BLUE_200,
        height=65,
    )
    
    retry_field = ft.TextField(
        label="Retry Attempts (1-10)",
        value=str(settings.get("retry_attempts", 3)),
        width=300,
        helper_text="Number of retries on failure",
        text_size=14,
        border_color=ft.colors.BLUE_200,
        height=65,
    )

    auto_cleanup_switch = ft.Switch(
        label="Auto Cleanup Temporary Files",
        value=settings.get("auto_cleanup", True),
        label_position=ft.LabelPosition.LEFT,
        active_color=ft.colors.BLUE_700,
        active_track_color=ft.colors.BLUE_200,
    )

    # Voice settings
    voices = audio_processor.voice_manager.voices.get('voices', [])
    voice_dropdown = ft.Dropdown(
        label="Voice",
        options=[ft.dropdown.Option(voice) for voice in voices],
        value=settings.get("voice", "en-US-EmmaNeural"),
        width=300,
        helper_text="Select voice for text-to-speech conversion",
        border_color=ft.colors.BLUE_200,
        height=65,
    )

    # Sliders for voice adjustments
    rate_slider = ft.Slider(
        min=-50,
        max=50,
        value=float(settings.get("rate", "+0%").rstrip("%")) / 100 * 50,
        label="{value}",
        divisions=20,
        width=300,
    )
    rate_label = ft.Text("Speech Rate:", size=14, weight=ft.FontWeight.BOLD)
    rate_value = ft.Text(settings.get("rate", "+0%"), size=14, color=ft.colors.BLUE)
    
    def on_rate_change(e):
        try:
            if e.data and e.data.strip():
                val = float(e.data)
                percentage = int((val / 50) * 100)
                rate_value.value = f"{percentage:+d}%"
                page.update()
        except ValueError:
            pass

    rate_slider.on_change = on_rate_change

    volume_slider = ft.Slider(
        min=-50,
        max=50,
        value=float(settings.get("volume", "+0%").rstrip("%")) / 100 * 50,
        label="{value}",
        divisions=20,
        width=300,
    )
    volume_label = ft.Text("Volume:", size=14, weight=ft.FontWeight.BOLD)
    volume_value = ft.Text(settings.get("volume", "+0%"), size=14, color=ft.colors.BLUE)
    
    def on_volume_change(e):
        try:
            if e.data and e.data.strip():
                val = float(e.data)
                percentage = int((val / 50) * 100)
                volume_value.value = f"{percentage:+d}%"
                page.update()
        except ValueError:
            pass

    volume_slider.on_change = on_volume_change

    pitch_slider = ft.Slider(
        min=-50,
        max=50,
        value=float(settings.get("pitch", "+0Hz").rstrip("Hz")),
        label="{value}",
        divisions=20,
        width=300,
    )
    pitch_label = ft.Text("Pitch:", size=14, weight=ft.FontWeight.BOLD)
    pitch_value = ft.Text(settings.get("pitch", "+0Hz"), size=14, color=ft.colors.BLUE)
    
    def on_pitch_change(e):
        try:
            if e.data and e.data.strip():
                val = float(e.data)
                pitch_value.value = f"{int(val):+d}Hz"
                page.update()
        except ValueError:
            pass

    pitch_slider.on_change = on_pitch_change

    wpm_field = ft.TextField(
        label="Words per Minute",
        value=str(settings.get("words_per_minute", "")) if settings.get("words_per_minute") else "",
        width=300,
        helper_text="Optional: 50-600 WPM (leave empty for default)",
        text_size=14,
        border_color=ft.colors.BLUE_200,
        height=65,
    )

    # Whisper Model settings
    whisper_model_dropdown = ft.Dropdown(
        label="Whisper Model",
        options=[
            ft.dropdown.Option("tiny", text="Tiny (Fastest)"),
            ft.dropdown.Option("base", text="Base (Fast)"),
            ft.dropdown.Option("small", text="Small (Balanced)"),
            ft.dropdown.Option("medium", text="Medium (Accurate)"),
            ft.dropdown.Option("large", text="Large (Most Accurate)"),
        ],
        value=settings.get("whisper_model", "base"),
        width=300,
    )

    download_progress = ft.ProgressBar(width=300, visible=False)
    model_status_text = ft.Text("", size=14)

    def update_model_status():
        model_name = whisper_model_dropdown.value
        is_downloaded = model_manager.is_model_downloaded(model_name)
        if is_downloaded:
            model_status_text.value = "Model already downloaded"
            model_status_text.color = ft.colors.GREEN
        else:
            model_status_text.value = "Model not downloaded"
            model_status_text.color = ft.colors.RED
        page.update()

    def handle_download_click(e):
        def download_model():
            try:
                download_progress.visible = True
                model_status_text.value = "Downloading model..."
                page.update()
                
                model_name = whisper_model_dropdown.value
                model_manager.get_model(model_name)
                
                model_status_text.value = "Model downloaded successfully!"
                model_status_text.color = ft.colors.GREEN
            except Exception as ex:
                model_status_text.value = f"Error downloading model: {str(ex)}"
                model_status_text.color = ft.colors.RED
            finally:
                download_progress.visible = False
                page.update()

        # Run the download in a separate thread
        import threading
        threading.Thread(target=download_model).start()

    # Update model status on dropdown change
    def on_model_selection_change(e):
        update_model_status()

    whisper_model_dropdown.on_change = on_model_selection_change

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

    whisper_tab = ft.Tab(
        text="Whisper",
        content=ft.Container(
            content=ft.Column([
                whisper_model_dropdown,
                ft.ElevatedButton(
                    "Download Selected Model",
                    on_click=handle_download_click,
                ),
                download_progress,
                model_status_text,
            ], spacing=20),
            padding=30
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
                        processing_tab,
                        voice_tab,
                        whisper_tab,
                    ],
                    expand=True,
                ),
            ]),
            width=600,
            height=500,
        ),
        actions=[
            ft.Row([
                ft.TextButton(
                    "Reset to Defaults",
                    on_click=lambda e: reset_to_defaults(),
                    style=ft.ButtonStyle(color=ft.colors.BLUE_700)
                ),
                ft.Row([
                    ft.TextButton(
                        "Cancel",
                        on_click=lambda e: close_settings(),
                        style=ft.ButtonStyle(color=ft.colors.GREY_700)
                    ),
                    ft.TextButton(
                        "Save",
                        on_click=lambda e: save_settings(),
                        style=ft.ButtonStyle(color=ft.colors.BLUE_700)
                    ),
                ]),
            ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
        ],
        actions_alignment=ft.MainAxisAlignment.END,
        on_dismiss=lambda e: close_settings(),
    )

    def close_settings():
        settings_dialog.open = False
        page.update()

    def reset_to_defaults():
        workers_field.value = "15"
        batch_field.value = "10"
        retry_field.value = "3"
        voice_dropdown.value = "en-US-EmmaNeural"
        auto_cleanup_switch.value = True
        rate_slider.value = 0
        volume_slider.value = 0
        pitch_slider.value = 0
        wpm_field.value = ""
        whisper_model_dropdown.value = "base"
        page.update()

    def save_settings():
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
                "whisper_model": whisper_model_dropdown.value,
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

    # Add the dialog to the page
    page.dialog = settings_dialog
    settings_dialog.open = True
    page.update()