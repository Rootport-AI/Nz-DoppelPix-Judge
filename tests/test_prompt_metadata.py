from pathlib import Path
import unittest

from nz_doppelpix_judge.prompt_metadata import extract_prompt, extract_prompt_from_metadata


class PromptMetadataTests(unittest.TestCase):
    def test_forge_neo_parameters_extracts_positive_prompt_only(self) -> None:
        info = extract_prompt_from_metadata(
            {
                "parameters": (
                    "masterpiece, best quality\n"
                    "Negative prompt: low quality\n"
                    "Steps: 32, Sampler: ER SDE, Seed: 1"
                )
            }
        )

        self.assertEqual(info.extractor, "forge-neo")
        self.assertEqual(info.source, "parameters")
        self.assertEqual(info.prompt, "masterpiece, best quality")

    def test_sample_images_have_prompt_without_generation_settings(self) -> None:
        sample_dir = Path("sample-images")
        if not sample_dir.exists():
            self.skipTest("sample-images directory is not available")

        images = sorted(sample_dir.glob("*.png"))
        self.assertEqual(len(images), 6)
        for image_path in images:
            with self.subTest(image=image_path.name):
                info = extract_prompt(image_path)
                self.assertEqual(info.extractor, "forge-neo")
                self.assertEqual(info.source, "parameters")
                self.assertTrue(info.prompt)
                self.assertNotIn("Negative prompt:", info.prompt)
                self.assertNotIn("Steps:", info.prompt)
                self.assertNotIn("Sampler:", info.prompt)
                self.assertNotIn("Seed:", info.prompt)


if __name__ == "__main__":
    unittest.main()
