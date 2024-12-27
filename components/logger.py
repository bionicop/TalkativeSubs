import flet as ft
from datetime import datetime

class LoggerComponent:
    def __init__(self, page: ft.Page):
        self.page = page
        self.setup_ui()

    def setup_ui(self):
        self.copy_btn = ft.IconButton(
            icon=ft.icons.COPY,
            icon_size=16,
            tooltip="Copy Logs",
            on_click=self.copy_logs
        )
        
        self.clear_btn = ft.IconButton(
            icon=ft.icons.CLEAR_ALL,
            icon_size=16,
            tooltip="Clear Logs",
            on_click=self.clear_logs
        )

        self.log_text = ft.ListView(
            expand=True,
            spacing=1,
            auto_scroll=True,
            height=200
        )

        self.log_container = ft.Container(
            content=ft.Column([
                ft.Container(
                    content=ft.Row([
                        ft.Text("Logs", size=12, weight=ft.FontWeight.BOLD),
                        ft.Row([self.copy_btn, self.clear_btn], spacing=0)
                    ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
                    border=ft.border.only(bottom=ft.border.BorderSide(1, "#2A2F35")),
                    padding=ft.padding.only(left=10, right=10, bottom=5)
                ),
                ft.Container(
                    content=self.log_text,
                    padding=ft.padding.only(left=10, right=10, top=5),
                    expand=True
                )
            ], spacing=0),
            border=ft.border.all(1, "#2A2F35"),
            border_radius=8,
            bgcolor="#111418",
            expand=True
        )

    def get_log_color(self, level: str) -> str:
        colors = {
            'info': ft.colors.BLUE,
            'error': ft.colors.RED,
            'warning': ft.colors.ORANGE,
            'success': ft.colors.GREEN,
            'debug': ft.colors.GREY
        }
        return colors.get(level, ft.colors.BLACK)

    def log_message(self, message: str, level: str = 'info', details: str = None):
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S.%f')[:-3]
        color = self.get_log_color(level)
        
        log_text = ft.Text(
            f"[{timestamp}] [{level.upper()}] {message}",
            color=color,
            size=14,
            selectable=True
        )
        
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
        
        self.log_text.controls.append(container)
        
        if len(self.log_text.controls) > 1000:
            self.log_text.controls.pop(0)
        
        self.page.update()

    def copy_logs(self, e):
        log_text = "\n".join([
            control.content.value if isinstance(control, ft.Container)
            else "\n".join(t.value for t in control.controls)
            for control in self.log_text.controls
        ])
        self.page.set_clipboard(log_text)
        self.page.show_snack_bar(ft.SnackBar(content=ft.Text("Logs copied to clipboard")))

    def clear_logs(self, e):
        self.log_text.controls = []
        self.page.update()

    def get_container(self):
        return self.log_container