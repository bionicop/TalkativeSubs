import flet as ft

class CustomButton:
    def __init__(self, text, icon, on_click, disabled=False):
        self.button = ft.ElevatedButton(
            text=text,
            icon=icon,
            on_click=on_click,
            disabled=disabled,
            style=ft.ButtonStyle(
                shape=ft.RoundedRectangleBorder(radius=8)
            )
        )

    def get_button(self):
        return self.button