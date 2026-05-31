import gradio as gr

from nz_doppelpix_judge.ui import build_demo


if __name__ == "__main__":
    build_demo().launch(server_name="127.0.0.1", theme=gr.themes.Glass())
