import flet as ft

class ProgressBarComponent:
    def __init__(self, page: ft.Page):
        self.page = page
        self.setup_ui()

    def setup_ui(self):
        self.progress_bar = ft.ProgressBar(width=400, color="primary", value=0)
        self.status_text = ft.Text("Ready", size=16)
        self.network_status = ft.Text("", size=14, color=ft.colors.ERROR)

        self.progress_container = ft.Column([
            self.progress_bar,
            self.status_text,
            self.network_status,
        ])

    def show_progress(self, show=True):
        self.progress_bar.visible = show
        self.status_text.visible = show
        self.page.update()

    def update_progress(self, progress=None, status=None, network_status=None):
        if progress is not None:
            self.progress_bar.value = progress
        if status is not None:
            self.status_text.value = status
        if network_status is not None:
            self.network_status.value = network_status
        self.page.update()

    def reset(self):
        self.progress_bar.value = 0
        self.status_text.value = "Ready"
        self.network_status.value = ""
        self.page.update()

    def get_container(self):
        return self.progress_container