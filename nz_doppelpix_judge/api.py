from __future__ import annotations

import shutil
import tempfile
import threading
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from fastapi.responses import Response

from nz_doppelpix_judge.compare import compare_images
from nz_doppelpix_judge.config import APP_TITLE
from nz_doppelpix_judge.network_access import NETWORK_ACCESS
from nz_doppelpix_judge.ui import RESULT_METRICS, render_results_csv


TRUE_VALUES = {"1", "true", "yes", "on"}
FALSE_VALUES = {"0", "false", "no", "off", ""}


@dataclass
class CompareJob:
    job_id: str
    mode: str
    status: str = "queued"
    total: int = 0
    completed: int = 0
    current_file: str = ""
    rows: list[dict[str, str]] = field(default_factory=list)
    errors: list[dict[str, str]] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)
    prompt: str = ""
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)


class CompareJobStore:
    def __init__(self) -> None:
        self._jobs: dict[str, CompareJob] = {}
        self._lock = threading.Lock()

    def create(self, mode: str) -> CompareJob:
        job = CompareJob(job_id=_new_job_id(), mode=mode)
        with self._lock:
            self._jobs[job.job_id] = job
        return job

    def get(self, job_id: str) -> CompareJob:
        with self._lock:
            job = self._jobs.get(job_id)
            if job is None:
                raise KeyError(job_id)
            return _copy_job(job)

    def update(self, job_id: str, **changes: Any) -> CompareJob:
        with self._lock:
            job = self._jobs[job_id]
            for key, value in changes.items():
                if key in {"rows", "errors"}:
                    value = [dict(item) for item in value]
                elif key == "notes":
                    value = list(value)
                setattr(job, key, value)
            job.updated_at = time.time()
            return _copy_job(job)

    def delete(self, job_id: str) -> None:
        with self._lock:
            self._jobs.pop(job_id, None)


JOB_STORE = CompareJobStore()


def create_api_router(job_store: CompareJobStore = JOB_STORE) -> APIRouter:
    router = APIRouter(prefix="/api")

    @router.get("/health")
    def health() -> dict[str, Any]:
        return {"ok": True, "app": APP_TITLE}

    @router.get("/capabilities")
    def capabilities() -> dict[str, Any]:
        return {
            "modes": ["manual", "auto"],
            "candidate_inputs": ["candidate_file", "candidate_directory_path"],
            "optional_metrics": ["clip_score", "image_reward"],
            "result_formats": ["json", "csv"],
            "result_columns": _result_columns(),
        }

    @router.post("/compare-jobs")
    async def create_compare_job(
        reference_file: UploadFile = File(...),
        candidate_file: UploadFile | None = File(None),
        candidate_directory_path: str | None = Form(None),
        enable_clip_score: str | bool = Form(False),
        enable_image_reward: str | bool = Form(False),
    ) -> dict[str, Any]:
        enable_clip = _parse_bool(enable_clip_score, "enable_clip_score")
        enable_image_reward_flag = _parse_bool(enable_image_reward, "enable_image_reward")
        directory_path = _clean_optional_text(candidate_directory_path)
        has_candidate_file = candidate_file is not None and bool(candidate_file.filename)
        has_candidate_directory = bool(directory_path)

        if has_candidate_file == has_candidate_directory:
            raise HTTPException(
                status_code=400,
                detail="Provide exactly one of candidate_file or candidate_directory_path.",
            )

        mode = "manual" if has_candidate_file else "auto"
        job = job_store.create(mode)
        temp_dir = Path(tempfile.mkdtemp(prefix=f"nz-doppelpix-job-{job.job_id}-"))

        try:
            reference_path = await _save_png_upload(reference_file, temp_dir, "reference.png")
            candidate_path: Path | None = None
            candidate_paths: list[Path] | None = None

            if has_candidate_file:
                if candidate_file is None:
                    raise HTTPException(status_code=400, detail="Candidate PNG upload is missing.")
                candidate_path = await _save_png_upload(candidate_file, temp_dir, "candidate.png")
                total = 1
            else:
                candidate_paths = _candidate_pngs(_candidate_directory(directory_path or ""))
                total = len(candidate_paths)

            job_store.update(job.job_id, total=total)
        except Exception:
            job_store.delete(job.job_id)
            shutil.rmtree(temp_dir, ignore_errors=True)
            raise

        _log(
            f"queued job={job.job_id} mode={mode} total={total} "
            f"clip={enable_clip} image_reward={enable_image_reward_flag}"
        )
        thread = threading.Thread(
            target=_run_compare_job,
            args=(
                job_store,
                job.job_id,
                reference_path,
                candidate_path,
                candidate_paths,
                enable_clip,
                enable_image_reward_flag,
                temp_dir,
            ),
            daemon=True,
        )
        thread.start()

        return {
            "job_id": job.job_id,
            "status": "queued",
            "mode": mode,
            "local_network_enabled": NETWORK_ACCESS.is_local_network_enabled(),
        }

    @router.get("/compare-jobs/{job_id}")
    def get_compare_job(job_id: str) -> dict[str, Any]:
        return _job_status_response(_get_job_or_404(job_store, job_id))

    @router.get("/compare-jobs/{job_id}/results")
    def get_compare_job_results(job_id: str) -> dict[str, Any]:
        job = _get_completed_job_or_409(job_store, job_id)
        return {
            "job_id": job.job_id,
            "status": job.status,
            "mode": job.mode,
            "columns": _result_columns(),
            "rows": job.rows,
            "notes": job.notes,
            "prompt": job.prompt,
        }

    @router.get("/compare-jobs/{job_id}/results.csv")
    def get_compare_job_results_csv(job_id: str) -> Response:
        job = _get_completed_job_or_409(job_store, job_id)
        filename = f"nz-doppelpix-results-{job.job_id}.csv"
        return Response(
            content=render_results_csv(job.rows).encode("utf-8-sig"),
            media_type="text/csv; charset=utf-8",
            headers={"Content-Disposition": f'attachment; filename="{filename}"'},
        )

    return router


def install_api_routes(app, job_store: CompareJobStore = JOB_STORE) -> None:
    app.include_router(create_api_router(job_store))


def _log(message: str) -> None:
    print(f"API Compare {message}", flush=True)


def _console_progress(job_id: str, done: int, total: int, label: str, finished: bool = False) -> None:
    percent = int(done * 100 / total) if total else 100
    width = 28
    filled = round(width * done / total) if total else width
    bar = "#" * filled + "-" * (width - filled)
    suffix = label[:90]
    print(
        f"API Auto Compare {job_id} [{bar}] {percent:3d}% ({done}/{total}) {suffix}",
        end="\n" if finished else "\r",
        flush=True,
    )


def _copy_job(job: CompareJob) -> CompareJob:
    return CompareJob(
        job_id=job.job_id,
        mode=job.mode,
        status=job.status,
        total=job.total,
        completed=job.completed,
        current_file=job.current_file,
        rows=[dict(row) for row in job.rows],
        errors=[dict(error) for error in job.errors],
        notes=list(job.notes),
        prompt=job.prompt,
        created_at=job.created_at,
        updated_at=job.updated_at,
    )


def _new_job_id() -> str:
    timestamp = time.strftime("%Y%m%d-%H%M%S")
    return f"{timestamp}-{uuid.uuid4().hex[:8]}"


def _clean_optional_text(value: str | None) -> str:
    return (value or "").strip()


def _parse_bool(value: str | bool, field_name: str) -> bool:
    if isinstance(value, bool):
        return value
    normalized = str(value).strip().lower()
    if normalized in TRUE_VALUES:
        return True
    if normalized in FALSE_VALUES:
        return False
    raise HTTPException(status_code=400, detail=f"{field_name} must be true or false.")


def _candidate_directory(path: str) -> Path:
    cleaned = path.strip().strip('"').strip("'")
    directory = Path(cleaned).expanduser()
    if not directory.is_dir():
        raise HTTPException(status_code=400, detail="candidate_directory_path must be a directory.")
    return directory


def _candidate_pngs(directory: Path) -> list[Path]:
    files = sorted(
        (path for path in directory.iterdir() if path.is_file() and path.suffix.lower() == ".png"),
        key=lambda path: path.name.lower(),
    )
    if not files:
        raise HTTPException(status_code=400, detail="candidate_directory_path does not contain PNG files.")
    return files


async def _save_png_upload(upload: UploadFile, directory: Path, fallback_name: str) -> Path:
    filename = Path(upload.filename or fallback_name).name
    if Path(filename).suffix.lower() != ".png":
        raise HTTPException(status_code=400, detail=f"{filename} must be a PNG file.")

    target = directory / filename
    if target.exists():
        target = directory / f"{Path(filename).stem}-{uuid.uuid4().hex[:8]}.png"

    content = await upload.read()
    if not content:
        raise HTTPException(status_code=400, detail=f"{filename} is empty.")
    target.write_bytes(content)
    return target


def _run_compare_job(
    job_store: CompareJobStore,
    job_id: str,
    reference_path: Path,
    candidate_path: Path | None,
    candidate_paths: list[Path] | None,
    enable_clip: bool,
    enable_image_reward: bool,
    temp_dir: Path,
) -> None:
    try:
        if candidate_path is not None:
            _run_manual_job(job_store, job_id, reference_path, candidate_path, enable_clip, enable_image_reward)
        else:
            _run_auto_job(job_store, job_id, reference_path, candidate_paths or [], enable_clip, enable_image_reward)
    except Exception as exc:
        job_store.update(
            job_id,
            status="failed",
            current_file="",
            errors=[{"file": "", "error": str(exc)}],
            notes=[f"Unexpected API job failure: {exc}"],
        )
        _log(f"failed job={job_id} error={exc}")
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)


def _run_manual_job(
    job_store: CompareJobStore,
    job_id: str,
    reference_path: Path,
    candidate_path: Path,
    enable_clip: bool,
    enable_image_reward: bool,
) -> None:
    job_store.update(job_id, status="running", total=1, completed=0, current_file=candidate_path.name)
    _log(f"started job={job_id} mode=manual candidate={candidate_path.name}")
    try:
        result = compare_images(str(reference_path), str(candidate_path), enable_clip, enable_image_reward)
        row = _result_row(candidate_path, {row.name: row.score for row in result.rows}, auto_mode=False)
        prompt = result.prompt_info.prompt if enable_clip or enable_image_reward else ""
        job_store.update(
            job_id,
            status="completed",
            completed=1,
            current_file="",
            rows=[row],
            notes=result.notes,
            prompt=prompt,
        )
        _log(f"completed job={job_id} mode=manual candidate={candidate_path.name}")
    except Exception as exc:
        job_store.update(
            job_id,
            status="failed",
            current_file="",
            errors=[{"file": candidate_path.name, "error": str(exc)}],
            notes=[f"Error while processing {candidate_path.name}: {exc}"],
        )
        _log(f"failed job={job_id} mode=manual candidate={candidate_path.name} error={exc}")


def _run_auto_job(
    job_store: CompareJobStore,
    job_id: str,
    reference_path: Path,
    candidate_paths: list[Path],
    enable_clip: bool,
    enable_image_reward: bool,
) -> None:
    rows: list[dict[str, str]] = []
    errors: list[dict[str, str]] = []
    notes: list[str] = []
    prompt = ""
    total = len(candidate_paths)
    job_store.update(job_id, status="running", total=total, completed=0)
    _log(f"started job={job_id} mode=auto total={total}")
    _console_progress(job_id, 0, total, "starting")

    for index, png_path in enumerate(candidate_paths, start=1):
        _console_progress(job_id, index - 1, total, f"processing {png_path.name}")
        job_store.update(job_id, current_file=png_path.name)
        try:
            result = compare_images(str(reference_path), str(png_path), enable_clip, enable_image_reward)
            rows.append(_result_row(png_path, {row.name: row.score for row in result.rows}, auto_mode=True))
            if enable_clip or enable_image_reward:
                prompt = result.prompt_info.prompt
            notes = [
                f"Auto Compare complete: {index}/{total} files processed."
                if index == total
                else f"Auto Compare progress: {index}/{total} files processed.",
                *result.notes,
            ]
            progress_label = f"completed {png_path.name}"
        except Exception as exc:
            rows.append(_error_row(png_path))
            errors.append({"file": png_path.name, "error": str(exc)})
            notes = [
                f"Auto Compare progress: {index}/{total} files processed.",
                f"Error while processing {png_path.name}: {exc}",
            ]
            progress_label = f"error {png_path.name}"

        job_store.update(
            job_id,
            completed=index,
            rows=rows,
            errors=errors,
            notes=notes,
            prompt=prompt,
        )
        _console_progress(job_id, index, total, progress_label, finished=index == total)

    job_store.update(job_id, status="completed", current_file="")
    _log(f"completed job={job_id} mode=auto total={total} errors={len(errors)}")


def _result_row(candidate_path: str | Path, scores_by_metric: dict[str, str], auto_mode: bool) -> dict[str, str]:
    row = {"File name": Path(candidate_path).name}
    for metric_name, _ in RESULT_METRICS:
        score = scores_by_metric.get(metric_name, "-")
        row[metric_name] = "error" if auto_mode and score.startswith("error:") else score
    return row


def _error_row(candidate_path: str | Path) -> dict[str, str]:
    return {"File name": Path(candidate_path).name, **{metric_name: "error" for metric_name, _ in RESULT_METRICS}}


def _result_columns() -> list[str]:
    return ["File name", *[metric_name for metric_name, _ in RESULT_METRICS]]


def _get_job_or_404(job_store: CompareJobStore, job_id: str) -> CompareJob:
    try:
        return job_store.get(job_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="Job not found.") from None


def _get_completed_job_or_409(job_store: CompareJobStore, job_id: str) -> CompareJob:
    job = _get_job_or_404(job_store, job_id)
    if job.status != "completed":
        raise HTTPException(status_code=409, detail=f"Job is {job.status}.")
    return job


def _job_status_response(job: CompareJob) -> dict[str, Any]:
    response: dict[str, Any] = {
        "job_id": job.job_id,
        "status": job.status,
        "mode": job.mode,
        "total": job.total,
        "completed": job.completed,
        "current_file": job.current_file,
        "errors": job.errors,
    }
    if job.status == "completed":
        response["csv_url"] = f"/api/compare-jobs/{job.job_id}/results.csv"
    return response
