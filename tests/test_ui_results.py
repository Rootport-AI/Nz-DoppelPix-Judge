import csv
from io import StringIO
import unittest

from nz_doppelpix_judge.ui import RESULT_METRICS, render_results_csv, render_results_tsv


def _parse_tsv(text: str) -> list[list[str]]:
    return [line.split("\t") for line in text.splitlines()]


class UiResultsTests(unittest.TestCase):
    def test_results_csv_matches_copy_table_columns_and_cells(self) -> None:
        row = {
            "File name": "candidate, one.png",
            "LPIPS - AlexNet": "0.123456",
            "PSNR": "line\nbreak",
            "ImageReward (candidate)": "tab\tvalue",
        }

        csv_rows = list(csv.reader(StringIO(render_results_csv([row]))))
        tsv_rows = _parse_tsv(render_results_tsv([row]))

        self.assertEqual(csv_rows, tsv_rows)
        self.assertEqual(csv_rows[0], ["File name", *[metric_name for metric_name, _ in RESULT_METRICS]])
        self.assertEqual(csv_rows[1][0], "candidate, one.png")
        self.assertEqual(csv_rows[1][csv_rows[0].index("PSNR")], "line break")
        self.assertEqual(csv_rows[1][csv_rows[0].index("ImageReward (candidate)")], "tab value")


if __name__ == "__main__":
    unittest.main()
