import csv
from io import BytesIO, StringIO
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi import FastAPI
from PIL import Image
from starlette.testclient import TestClient

from nz_doppelpix_judge.api import CompareJobStore, create_api_router
from nz_doppelpix_judge.compare import ComparisonResult, MetricRow
from nz_doppelpix_judge.network_access import LocalNetworkAccessMiddleware, NetworkAccessControl
from nz_doppelpix_judge.prompt_metadata import PromptInfo


def _png_bytes(color: tuple[int, int, int] = (16, 32, 48)) -> bytes:
    buffer = BytesIO()
    Image.new("RGB", (8, 8), color).save(buffer, format="PNG")
    return buffer.getvalue()


def _client(store: CompareJobStore | None = None) -> TestClient:
    app = FastAPI()
    app.include_router(create_api_router(store or CompareJobStore()))
    return TestClient(app)


def _wait_for_status(client: TestClient, job_id: str, status: str) -> dict:
    deadline = time.time() + 3.0
    last_response = {}
    while time.time() < deadline:
        response = client.get(f"/api/compare-jobs/{job_id}")
        response.raise_for_status()
        last_response = response.json()
        if last_response["status"] == status:
            return last_response
        time.sleep(0.02)
    raise AssertionError(f"Job did not reach {status}: {last_response}")


def _fake_result(score: str = "0.123456") -> ComparisonResult:
    return ComparisonResult(
        rows=[MetricRow("LPIPS - AlexNet", score, "lower is more similar")],
        notes=["note"],
        prompt_info=PromptInfo(prompt="prompt", source="parameters", extractor="fake"),
    )


class ApiTests(unittest.TestCase):
    def test_health_and_capabilities(self) -> None:
        client = _client()

        self.assertEqual(client.get("/api/health").json()["ok"], True)
        capabilities = client.get("/api/capabilities").json()
        self.assertIn("manual", capabilities["modes"])
        self.assertIn("auto", capabilities["modes"])
        self.assertIn("File name", capabilities["result_columns"])

    def test_manual_compare_job_returns_json_and_csv_results(self) -> None:
        client = _client()
        files = {
            "reference_file": ("reference.png", _png_bytes(), "image/png"),
            "candidate_file": ("candidate.png", _png_bytes((64, 80, 96)), "image/png"),
        }

        with patch("nz_doppelpix_judge.api.compare_images", return_value=_fake_result()) as compare:
            response = client.post("/api/compare-jobs", files=files)
            self.assertEqual(response.status_code, 200)
            job_id = response.json()["job_id"]
            status = _wait_for_status(client, job_id, "completed")

        self.assertEqual(status["mode"], "manual")
        self.assertEqual(status["completed"], 1)
        compare.assert_called_once()

        result = client.get(f"/api/compare-jobs/{job_id}/results").json()
        self.assertEqual(result["rows"][0]["File name"], "candidate.png")
        self.assertEqual(result["rows"][0]["LPIPS - AlexNet"], "0.123456")

        csv_response = client.get(f"/api/compare-jobs/{job_id}/results.csv")
        self.assertEqual(csv_response.status_code, 200)
        csv_rows = list(csv.reader(StringIO(csv_response.content.decode("utf-8-sig"))))
        self.assertEqual(csv_rows[1][0], "candidate.png")
        self.assertEqual(csv_rows[1][csv_rows[0].index("LPIPS - AlexNet")], "0.123456")

    def test_auto_compare_job_uses_directory_order_and_keeps_error_rows(self) -> None:
        client = _client()

        with tempfile.TemporaryDirectory() as temp_dir:
            directory = Path(temp_dir)
            (directory / "b.png").write_bytes(_png_bytes((128, 0, 0)))
            (directory / "a.png").write_bytes(_png_bytes((0, 128, 0)))

            def fake_compare(reference_path: str, candidate_path: str, enable_clip: bool, enable_image_reward: bool):
                if Path(candidate_path).name == "b.png":
                    raise RuntimeError("boom")
                return _fake_result("0.010000")

            with patch("nz_doppelpix_judge.api.compare_images", side_effect=fake_compare):
                response = client.post(
                    "/api/compare-jobs",
                    files={"reference_file": ("reference.png", _png_bytes(), "image/png")},
                    data={"candidate_directory_path": str(directory)},
                )
                self.assertEqual(response.status_code, 200)
                job_id = response.json()["job_id"]
                status = _wait_for_status(client, job_id, "completed")

        self.assertEqual(status["mode"], "auto")
        self.assertEqual(status["completed"], 2)
        self.assertEqual(len(status["errors"]), 1)

        result = client.get(f"/api/compare-jobs/{job_id}/results").json()
        self.assertEqual([row["File name"] for row in result["rows"]], ["a.png", "b.png"])
        self.assertEqual(result["rows"][0]["LPIPS - AlexNet"], "0.010000")
        self.assertEqual(result["rows"][1]["LPIPS - AlexNet"], "error")

    def test_local_network_middleware_protects_api_routes(self) -> None:
        access_control = NetworkAccessControl(local_network_enabled=False)
        app = FastAPI()
        app.include_router(create_api_router(CompareJobStore()))
        app.add_middleware(LocalNetworkAccessMiddleware, access_control=access_control)

        remote_client = TestClient(app, client=("203.0.113.10", 12345))
        self.assertEqual(remote_client.get("/api/health").status_code, 403)

        access_control.set_local_network_enabled(True)
        response = remote_client.get("/api/health")
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()["ok"])

    def test_candidate_input_is_exclusive(self) -> None:
        client = _client()
        response = client.post(
            "/api/compare-jobs",
            files={
                "reference_file": ("reference.png", _png_bytes(), "image/png"),
                "candidate_file": ("candidate.png", _png_bytes(), "image/png"),
            },
            data={"candidate_directory_path": "."},
        )

        self.assertEqual(response.status_code, 400)


if __name__ == "__main__":
    unittest.main()
