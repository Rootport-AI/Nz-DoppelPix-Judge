# Nz DoppelPix Judge Specification

## Overview

Nz DoppelPix Judge is a local-only Gradio Web GUI for comparing PNG images with objective similarity and prompt-fidelity metrics.

The primary use case is evaluating image degradation caused by DiT inference acceleration techniques such as TeaCache and Spectrum. The tool is also usable as a generic two-image or one-to-many PNG comparison utility.

## Runtime

- Platform target: local Windows execution
- Web UI: Gradio
- Default host for `python app.py`: `127.0.0.1`
- Listen host for `python app.py --listen`: `0.0.0.0`
- `run.bat` host behavior: always starts `python app.py --listen`
- Port: `7870`
- Public sharing: not used
- License: Apache License 2.0

## Device Selection

The runtime device is selected in `nz_doppelpix_judge/config.py`:

```python
DEVICE = "cuda" if torch.cuda.is_available() else "cpu"
```

Metric device behavior:

- LPIPS - AlexNet uses `DEVICE`.
- LPIPS - VGG uses `DEVICE`.
- Experimental / FID-like uses `DEVICE`.
- CLIP Score uses `DEVICE`.
- SSIM - win size 7 (skimage) runs on CPU through NumPy/scikit-image.
- SSIM - win size 11 (Wang) runs on CPU through NumPy/scikit-image.
- PSNR runs on CPU through NumPy/scikit-image.
- ImageReward is loaded through the ImageReward package and is not explicitly moved by this app.

The app does not install or configure CUDA by itself. GPU use depends on the active virtual environment exposing a CUDA-enabled PyTorch build.

## Entry Points

- `setup.bat`
  - Creates or reuses `.venv`
  - Installs `requirements.txt`
  - Installs `requirements-optional.txt` unless `--core-only` is passed
- `run.bat`
  - Starts the app
  - Passes `--listen`
  - Waits until the local server responds
  - Opens `http://127.0.0.1:7870`
- `app.py`
  - Minimal Python entry point
  - Accepts `--listen` to bind to all network interfaces
  - Installs HTTP API routes into the same FastAPI app as the Gradio UI
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
- `local network` checkbox
  - Off by default
  - When off, requests from machines other than the local machine are rejected
  - When on, requests from other devices on the local network are allowed
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

## Local Network Access

The process can bind to all interfaces through the `--listen` command-line argument. `run.bat` always uses this mode.

Binding to all interfaces does not by itself allow other devices to use the app. Incoming HTTP requests pass through `LocalNetworkAccessMiddleware` in `nz_doppelpix_judge/network_access.py`.

Access behavior:

- The local machine is always allowed.
- The local machine includes loopback addresses and the machine's own resolved interface addresses.
- When the `local network` checkbox is off, other network clients receive HTTP 403.
- When the `local network` checkbox is on, other network clients are allowed.
- The checkbox updates global process state and affects subsequent requests immediately.

## HTTP API

Status: implemented.

Purpose:

- Allow local AI agents, LAN AI agents, and simple scripts to automate image comparison without browser control.
- Preserve the same comparison behavior, metric options, and CSV table shape as the UI.
- Avoid browser-MCP-only automation for routine benchmark workflows.

Security requirement:

- All API routes must run behind the same `LocalNetworkAccessMiddleware` used by the Gradio UI.
- There must not be an API-only bypass for local network access control.
- The planned API must not expose an endpoint that enables `local network` access remotely.
- When `local network` is off, API requests from machines other than the local machine must receive HTTP 403.
- When `local network` is on, API requests from other devices on the local network may proceed.

### Endpoints

```text
GET  /api/health
GET  /api/capabilities
POST /api/compare-jobs
GET  /api/compare-jobs/{job_id}
GET  /api/compare-jobs/{job_id}/results
GET  /api/compare-jobs/{job_id}/results.csv
```

Potential later endpoint:

```text
GET  /api/compare-jobs/{job_id}/events
```

`/events` may provide Server-Sent Events for live progress. The current implementation uses polling through `GET /api/compare-jobs/{job_id}`.

### Health

`GET /api/health` returns a minimal JSON response for automation clients.

Example response:

```json
{
  "ok": true,
  "app": "Nz DoppelPix Judge"
}
```

### Capabilities

`GET /api/capabilities` returns the server's available modes and metric flags.

Example response:

```json
{
  "modes": ["manual", "auto"],
  "candidate_inputs": ["candidate_file", "candidate_directory_path"],
  "optional_metrics": ["clip_score", "image_reward"],
  "result_formats": ["json", "csv"],
  "result_columns": ["File name", "..."]
}
```

### Create Compare Job

`POST /api/compare-jobs` creates and starts a comparison job.

Request format: `multipart/form-data`

Common fields:

- `reference_file`: PNG upload. Required.
- `enable_clip_score`: boolean-like string. Optional. Default: `false`.
- `enable_image_reward`: boolean-like string. Optional. Default: `false`.

Manual Compare fields:

- `candidate_file`: PNG upload. Required for Manual Compare.

Auto Compare fields:

- `candidate_directory_path`: server-local directory path. Required for Auto Compare.

Input rules:

- Exactly one of `candidate_file` or `candidate_directory_path` must be provided.
- `candidate_directory_path` is resolved on the machine running the server, not on the client machine.
- Auto Compare reads only direct child `.png` files, matching UI behavior.
- Optional metric flags default to off, matching UI behavior.

Example response:

```json
{
  "job_id": "20260614-abc123",
  "status": "queued",
  "mode": "auto",
  "local_network_enabled": true
}
```

### Job Status

`GET /api/compare-jobs/{job_id}` returns job metadata and progress.

Status values:

- `queued`
- `running`
- `completed`
- `failed`

Running response example:

```json
{
  "job_id": "20260614-abc123",
  "status": "running",
  "mode": "auto",
  "total": 42,
  "completed": 17,
  "current_file": "sample_017.png",
  "errors": []
}
```

Completed response example:

```json
{
  "job_id": "20260614-abc123",
  "status": "completed",
  "mode": "auto",
  "total": 42,
  "completed": 42,
  "csv_url": "/api/compare-jobs/20260614-abc123/results.csv"
}
```

### API Console Output

API compare jobs write progress to the server console.

Manual Compare logs:

- Queued job ID, mode, total count, and optional metric flags.
- Started job ID and candidate filename.
- Completed or failed job ID and candidate filename.

Auto Compare logs:

- Queued job ID, mode, total count, and optional metric flags.
- Started job ID and total count.
- Text progress bar with percentage, completed count, total count, and current filename.
- Completed job ID, total count, and error count.

Example:

```text
API Compare queued job=20260614-153025-8e981651 mode=auto total=2 clip=False image_reward=False
API Compare started job=20260614-153025-8e981651 mode=auto total=2
API Auto Compare 20260614-153025-8e981651 [##############--------------]  50% (1/2) completed a.png
API Auto Compare 20260614-153025-8e981651 [############################] 100% (2/2) completed b.png
API Compare completed job=20260614-153025-8e981651 mode=auto total=2 errors=0
```

### JSON Results

`GET /api/compare-jobs/{job_id}/results` returns the latest completed result rows as JSON.

The response includes the same metric columns as the result table. Notes and extracted prompt are returned as separate metadata fields, not mixed into result rows.

If the job is not `completed`, the endpoint returns HTTP 409.

### CSV Results

`GET /api/compare-jobs/{job_id}/results.csv` downloads CSV for a completed job.

CSV behavior:

- Same columns as the UI `Download CSV` button.
- Same rows as the UI `Download CSV` button.
- Does not include Notes, extracted prompt, preview state, or extra internal job metadata.
- Uses UTF-8 with BOM for Windows spreadsheet compatibility.

If the job is not `completed`, the endpoint returns HTTP 409.

### UI Workflow Mapping

The API replaces browser automation steps as follows:

| UI automation step | API equivalent |
| --- | --- |
| Upload Reference PNG | `reference_file` in `POST /api/compare-jobs` |
| Enter Candidate PNG directory path | `candidate_directory_path` in `POST /api/compare-jobs` |
| Upload Candidate PNG | `candidate_file` in `POST /api/compare-jobs` |
| Toggle `Enable CLIP Score` | `enable_clip_score` in `POST /api/compare-jobs` |
| Toggle `Enable ImageReward` | `enable_image_reward` in `POST /api/compare-jobs` |
| Press `Compare` | `POST /api/compare-jobs` |
| Watch console until complete | Poll `GET /api/compare-jobs/{job_id}` until `status` is `completed` |
| Press `Download CSV` | `GET /api/compare-jobs/{job_id}/results.csv` |

### Error Behavior

Manual Compare:

- Request validation errors return HTTP 400.
- Comparison failures mark the job as `failed`.
- `GET /api/compare-jobs/{job_id}` exposes the failure state and error details.
- Result JSON and CSV endpoints return HTTP 409 for failed jobs.

Auto Compare:

- Directory validation errors return HTTP 400.
- Per-candidate processing errors are recorded in the result row as `error`, matching UI behavior.
- Processing continues to the next candidate when possible.

Unknown job IDs return HTTP 404.

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

The CSV is generated from the same in-memory result rows as the TSV used by `Copy table`. It does not include Notes, extracted prompts, preview state, image paths beyond the displayed `File name`, or other UI-only data.

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
  api.py
  config.py
  image_io.py
  network_access.py
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
  test_api.py
  test_network_access.py
  test_prompt_metadata.py
  test_ui_results.py
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
