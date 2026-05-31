from __future__ import annotations

import torch


APP_TITLE = "Nz DoppelPix Judge"
DEVICE = "cuda" if torch.cuda.is_available() else "cpu"
