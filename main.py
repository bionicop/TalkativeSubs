from utils import temporary_cgi_fix
import sys
sys.modules['cgi'] = temporary_cgi_fix

import flet as ft
from screens.audio_to_sub_screen import AudioToSubScreen
from screens.sub_to_audio_screen import SubToAudioScreen
from services.audio_processor import AudioProcessor
from settings import show_settings

# Customizable GUI dimensions
GUI_WIDTH = 1000
GUI_HEIGHT = 900
PADDING = 20
FOOTER_MARGIN_TOP = 20
TAB_PADDING = 10

def main(page: ft.Page):
    page.title = "TalkativeSubs"
    page.vertical_alignment = ft.MainAxisAlignment.CENTER
    page.horizontal_alignment = ft.CrossAxisAlignment.CENTER
    page.padding = ft.padding.all(PADDING)
    page.window_width = GUI_WIDTH
    page.window_height = GUI_HEIGHT
    audio_processor = AudioProcessor()

    audio_to_sub_screen = AudioToSubScreen(page)
    sub_to_audio_screen = SubToAudioScreen(page, audio_processor)

    # Settings button
    settings_button = ft.IconButton(
        icon=ft.icons.SETTINGS,
        on_click=lambda e: show_settings(page, audio_processor),
        tooltip="Open Settings",
    )

    # Footer
    footer = ft.Container(
        content=ft.Column([
            ft.Divider(height=1, color=ft.colors.with_opacity(0.2, ft.colors.ON_SURFACE_VARIANT)),
            ft.Row([
                ft.Text("Made by "),
                ft.TextButton(
                    "bionicop",
                    url="https://github.com/bionicop",
                    tooltip="Visit GitHub Profile"
                ),
            ], alignment=ft.MainAxisAlignment.CENTER),
        ]),
        margin=ft.margin.only(top=FOOTER_MARGIN_TOP),
    )

    # Main layout
    tabs = ft.Tabs(
        selected_index=0,
        animation_duration=300,
        tabs=[
            ft.Tab(
                text="Audio to Subtitle",
                content=ft.Container(
                    content=ft.Column([
                        audio_to_sub_screen.get_content(),
                        footer
                    ]),
                    padding=ft.padding.all(TAB_PADDING)
                )
            ),
            ft.Tab(
                text="Subtitle to Audio",
                content=ft.Container(
                    content=ft.Column([
                        sub_to_audio_screen.get_content(),
                        footer
                    ]),
                    padding=ft.padding.all(TAB_PADDING)
                )
            ),
        ],
        expand=True,
    )

    tabs_and_settings = ft.Row(
        [
            tabs,
            settings_button,
        ],
        alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
        vertical_alignment=ft.CrossAxisAlignment.START,
    )

    page.add(tabs_and_settings)

ft.app(target=main)