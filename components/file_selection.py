import flet as ft
from pathlib import Path

class FileSelectionComponent:
    def __init__(self, page: ft.Page, allowed_extensions: list, on_files_selected=None):
        self.page = page
        self.allowed_extensions = allowed_extensions
        self.on_files_selected = on_files_selected
        self.selected_files = []
        self.setup_component()

    def setup_component(self):
        self.file_picker = ft.FilePicker(
            on_result=self.handle_file_selected
        )
        self.page.overlay.append(self.file_picker)

        self.select_file_btn = ft.ElevatedButton(
            "Select Files",
            icon=ft.icons.FILE_UPLOAD,
            on_click=lambda _: self.file_picker.pick_files(
                allowed_extensions=self.allowed_extensions,
                allow_multiple=True
            )
        )

        self.files_list = ft.ListView(
            expand=True,
            spacing=1,
            height=150,
            auto_scroll=True
        )

        self.container = ft.Container(
            content=ft.Column([
                ft.Row([self.select_file_btn], alignment=ft.MainAxisAlignment.START),
                ft.Container(
                    content=ft.Column([
                        ft.Text("Selected Files:", size=14, weight=ft.FontWeight.BOLD),
                        self.files_list
                    ]),
                    padding=10,
                    border=ft.border.all(1, ft.colors.with_opacity(0.1, ft.colors.ON_SURFACE)),
                    border_radius=8
                )
            ])
        )

    def handle_file_selected(self, e: ft.FilePickerResultEvent):
        if e.files:
            new_files = [file.path for file in e.files]
            self.selected_files.extend(new_files)
            self.update_files_list()
            if self.on_files_selected:
                self.on_files_selected(self.selected_files)

    def update_files_list(self):
        self.files_list.controls = [
            self.create_file_item(f, i)
            for i, f in enumerate(self.selected_files)
        ]
        self.page.update()

    def create_file_item(self, file_path: str, index: int):
        return ft.Container(
            content=ft.Row([
                ft.Icon(ft.icons.VIDEO_FILE),
                ft.Text(Path(file_path).name),
                ft.IconButton(
                    icon=ft.icons.DELETE,
                    on_click=lambda e, idx=index: self.remove_file(idx)
                )
            ]),
            border=ft.border.all(1, ft.colors.with_opacity(0.1, ft.colors.ON_SURFACE)),
            border_radius=4,
            padding=5
        )

    def remove_file(self, index: int):
        removed_file = self.selected_files.pop(index)
        self.update_files_list()
        if self.on_files_selected:
            self.on_files_selected(self.selected_files)
        return removed_file

    def get_container(self):
        return self.container

    def enable_selection(self, enabled: bool):
        self.select_file_btn.disabled = not enabled
        self.page.update()