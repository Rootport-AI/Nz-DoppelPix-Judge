from __future__ import annotations

import torch


APP_TITLE = "Nz DoppelPix Judge"
APP_HOST = "127.0.0.1"
APP_PORT = 7870
APP_URL = f"http://{APP_HOST}:{APP_PORT}"
DEVICE = "cuda" if torch.cuda.is_available() else "cpu"
