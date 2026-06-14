import argparse

import gradio as gr
from gradio.routes import App

from nz_doppelpix_judge.api import install_api_routes
from nz_doppelpix_judge.config import APP_HOST, APP_LISTEN_HOST, APP_PORT
from nz_doppelpix_judge.network_access import LocalNetworkAccessMiddleware
from nz_doppelpix_judge.ui import UI_CSS, build_demo


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run Nz DoppelPix Judge.")
    parser.add_argument(
        "--listen",
        action="store_true",
        help="Bind to all network interfaces. Remote access is still controlled by the local network checkbox.",
    )
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    server_name = APP_LISTEN_HOST if args.listen else APP_HOST
    server_app = App()
    install_api_routes(server_app)
    server_app.add_middleware(LocalNetworkAccessMiddleware)
    build_demo().launch(
        server_name=server_name,
        server_port=APP_PORT,
        theme=gr.themes.Monochrome(),
        css=UI_CSS,
        _app=server_app,
    )
