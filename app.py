import gradio as gr

from nz_doppelpix_judge.config import APP_HOST, APP_PORT
from nz_doppelpix_judge.ui import UI_CSS, build_demo


if __name__ == "__main__":
    build_demo().launch(server_name=APP_HOST, server_port=APP_PORT, theme=gr.themes.Monochrome(), css=UI_CSS)
