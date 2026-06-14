# Nz DoppelPix Judge Specification

## Overview

Nz DoppelPix Judge is a local-only Gradio Web GUI for comparing PNG images with objective similarity and prompt-fidelity metrics.

The primary use case is evaluating image degradation caused by DiT inference acceleration techniques such as TeaCache and Spectrum. The tool is also usable as a generic two-image or one-to-many PNG comparison utility.

## Runtime

- Platform target: local Windows execution
- Web UI: Gradio
- Host: `127.0.0.1`
- Port: `7870`
- Public sharing: not used
- License: Apache License 2.0

## Entry Points

- `setup.bat`
  - Creates or reuses `.venv`
  - Installs `requirements.txt`
  - Installs `requirements-optional.txt` unless `--core-only` is passed
- `run.bat`
  - Starts the app
  - Waits until the local server responds
  - Opens `http://127.0.0.1:7870`
- `app.py`
  - Minimal Python entry point
  - Launches Gradio with the Monochrome theme

## UI Layout

The first view contains:

- Reference PNG path (Coming soon) textbox
  - Disabled
  - Reserved for future use
- Reference PNG upload area
  - Required for both modes
  - Accepts PNG files
- Reference preview
  - Rendered as HTML from a Base64 PNG thumbnail
- Candidate PNG directory path textbox
  - Enables Auto Compare mode when non-empty
  - Directory path is manually pasted by the user
- Candidate PNG upload area
  - Used by Manual Compare mode
  - Hidden/disabled when Candidate PNG directory path is non-empty
- Candidate preview
  - Manual mode: shows uploaded Candidate PNG
  - Auto mode: shows the PNG currently being processed
- Prompt fidelity metrics group
  - `Enable CLIP Score`
  - `Enable ImageReward`
- `Compare` button
- Result table
- `Copy table` button
- `Download CSV` button
- Notes textbox
- Extracted prompt textbox

## Modes

### Manual Compare Mode

Manual Compare mode is active when `Candidate PNG directory path` is empty.

Requirements:

- Reference PNG must be uploaded.
- Candidate PNG must be uploaded.

Behavior:

- Compares the uploaded Reference PNG and Candidate PNG once.
- Clears the existing result table when Compare is pressed.
- Writes one result row.
- `File name` contains the Candidate PNG filename.

### Auto Compare Mode

Auto Compare mode is active when `Candidate PNG directory path` is non-empty.

Requirements:

- Reference PNG must be uploaded.
- Candidate PNG directory path must point to an existing directory.

Behavior:

- Candidate PNG upload area is hidden/disabled.
- Reads only `.png` files directly under the specified directory.
- Does not recurse into subdirectories.
- Sorts files by filename ascending, case-insensitive.
- Clears the existing result table when Compare is pressed.
- Compares each Candidate PNG against the uploaded Reference PNG.
- Appends one result row per Candidate PNG.
- Updates Candidate preview to the PNG currently being processed.
- Prints console progress with a text progress bar and percentage.

Error behavior:

- If a Candidate PNG fails during processing, its filename is still added.
- Metric score cells for that row are set to `error`.
- Processing continues to the next file.

## Mode Exclusivity

Manual and Auto modes are mutually exclusive through UI behavior:

- If a Candidate PNG is uploaded, the Candidate PNG directory path textbox becomes non-interactive.
- If Candidate PNG directory path is non-empty, the Candidate PNG upload area becomes non-interactive and hidden.
- The user must clear the uploaded Candidate PNG or clear the Candidate PNG directory path to switch modes.

## Result Table

The result table is rendered as custom HTML rather than Gradio Dataframe. This is used because Gradio Dataframe headers did not reliably preserve line breaks.

Columns:

- `File name`
- `LPIPS - AlexNet`
- `LPIPS - VGG`
- `SSIM - win size 7 (skimage)`
- `SSIM - win size 11 (Wang)`
- `PSNR`
- `Experimental / FID-like`
- `CLIP Score (reference)`
- `CLIP Score (candidate)`
- `ImageReward (reference)`
- `ImageReward (candidate)`

Display behavior:

- Table headers use line breaks for readability.
- The table may scroll horizontally.
- On initial load, scores are `-`.
- Optional prompt-fidelity metric columns remain visible, but values are `-` unless enabled.

## Copy Table

The `Copy table` button copies the latest result table as TSV.

TSV format:

- First row: column headers
- Columns: tab-separated
- Rows: newline-separated
- Cell tabs and line breaks are replaced with spaces

Copy feedback:

- The button text temporarily changes to `Copied`.
- A short button animation is applied.
- No separate clipboard message textbox is shown.

## Download CSV

The `Download CSV` button downloads the latest result table as CSV.

CSV format:

- Same columns as `Copy table`
- Same rows as `Copy table`
- Columns: comma-separated with standard CSV quoting
- Cell tabs and line breaks are replaced with spaces
- Encoded as UTF-8 with BOM for Windows spreadsheet compatibility

## Image Preprocessing

For metric computation:

- PNGs are opened with Pillow.
- Images are converted to RGB.
- If Reference and Candidate sizes differ, both are resized to the smaller shared width and height.
- Resize method: PIL Lanczos

For preview:

- PNGs are opened with Pillow.
- Images are converted to RGB.
- A thumbnail is generated with max size `640x640`.
- The thumbnail is embedded in the UI as a Base64 PNG inside HTML.

## Metrics

### LPIPS - AlexNet

- Library: `lpips`
- Model: `lpips.LPIPS(net="alex")`
- Input conversion:
  - RGB `[0,255]`
  - converted to `[0,1]`
  - converted to `[-1,1]`
- Direction: lower is more similar

### LPIPS - VGG

- Library: `lpips`
- Model: `lpips.LPIPS(net="vgg")`
- Input conversion:
  - RGB `[0,255]`
  - converted to `[0,1]`
  - converted to `[-1,1]`
- Direction: lower is more similar

### SSIM - win size 7 (skimage)

- Library: `skimage.metrics.structural_similarity`
- Parameters:
  - `channel_axis=2`
  - `data_range=255`
  - `win_size=7`
- Direction: higher is more similar

### SSIM - win size 11 (Wang)

- Library: `skimage.metrics.structural_similarity`
- Parameters:
  - `channel_axis=2`
  - `data_range=255`
  - `gaussian_weights=True`
  - `sigma=1.5`
  - `use_sample_covariance=False`
- Direction: higher is more similar

### PSNR

- Library: `skimage.metrics.peak_signal_noise_ratio`
- Parameters:
  - `data_range=255`
- Direction: higher is more similar

### Experimental / FID-like

- Library: `torchvision`
- Model: `Inception_V3_Weights.DEFAULT`
- Feature extractor:
  - Inception V3
  - `fc` replaced with `torch.nn.Identity()`
- For a single image pair, the score is the squared L2 distance between Inception features.
- This is not dataset-level FID.
- Direction: lower is more similar

### CLIP Score

- Optional
- Enabled only when `Enable CLIP Score` is checked
- Library: `open_clip`
- Model: `ViT-B-32`
- Pretrained weights: `openai`
- Score: `100 * cosine(image_features, text_features)`
- Evaluated for both Reference and Candidate images
- Direction: higher is more prompt-aligned

### ImageReward

- Optional
- Enabled only when `Enable ImageReward` is checked
- Library: `ImageReward`
- Model: `ImageReward-v1.0`
- Evaluated for both Reference and Candidate images
- Direction: higher is more preferred/aligned

## Prompt Extraction

Prompt extraction is implemented in:

- `nz_doppelpix_judge/prompt_metadata.py`

This module is intentionally independent from UI and metric code so that metadata formats can be added later.

Current extractors:

- `ForgeNeoPromptExtractor`
- `GenericPromptExtractor`

Forge neo behavior:

- Reads PNG metadata key: `parameters`
- Treats the text before `Negative prompt:` or `Steps:` as the positive prompt
- Ignores negative prompt and generation settings

Prompt priority:

- Reference PNG metadata is preferred.
- Candidate PNG metadata is used only if Reference PNG has no prompt.

Prompt use:

- CLIP Score and ImageReward use the extracted prompt.
- The extracted prompt is shown in the UI only when CLIP Score or ImageReward is enabled.

## Notes Output

The Notes textbox includes:

- Current mode
- Direction guide
- Prompt source
- Single-pair FID-like warning
- Metric settings
- Auto Compare progress information when applicable
- Error information when applicable

## Console Output

Auto Compare mode writes progress to the console.

Example:

```text
Auto Compare [#######---------------------]  25% (1/4) sample.png
```

## Project Layout

```text
app.py
setup.bat
run.bat
requirements.txt
requirements-optional.txt
nz_doppelpix_judge/
  __init__.py
  config.py
  image_io.py
  prompt_metadata.py
  compare.py
  ui.py
  metrics/
    __init__.py
    basic.py
    fid.py
    perceptual.py
    prompt_alignment.py
tests/
  test_prompt_metadata.py
sample-images/
doc/
  specification.md
```

## Limitations

- The app currently targets PNG input.
- Auto Compare reads only direct child PNG files, not subdirectories.
- Reference path textbox is disabled and reserved for future use.
- Experimental / FID-like is not true dataset-level FID.
- Optional metrics may require downloading model weights on first use.
- CLIP Score and ImageReward can be slow in Auto Compare mode.
