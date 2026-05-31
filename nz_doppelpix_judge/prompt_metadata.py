from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping, Protocol

from PIL import Image


@dataclass(frozen=True)
class PromptInfo:
    prompt: str
    source: str
    extractor: str


class PromptExtractor(Protocol):
    name: str

    def extract(self, metadata: Mapping[str, str]) -> PromptInfo | None:
        ...


def _text(value: object) -> str:
    return str(value).replace("\r\n", "\n").replace("\r", "\n").strip()


def _clean_prompt(prompt: str) -> str:
    return "\n".join(line.rstrip() for line in prompt.strip().splitlines()).strip()


class ForgeNeoPromptExtractor:
    name = "forge-neo"

    _prompt_end = re.compile(r"\n(?:Negative prompt:|Steps:)", re.IGNORECASE)

    def extract(self, metadata: Mapping[str, str]) -> PromptInfo | None:
        parameters = _text(metadata.get("parameters", ""))
        if not parameters:
            return None

        prompt = self._prompt_end.split(parameters, maxsplit=1)[0]
        prompt = _clean_prompt(prompt)
        if not prompt:
            return None
        return PromptInfo(prompt=prompt, source="parameters", extractor=self.name)


class GenericPromptExtractor:
    name = "generic"

    def extract(self, metadata: Mapping[str, str]) -> PromptInfo | None:
        for key in ("prompt", "Prompt", "description", "Description"):
            prompt = _clean_prompt(_text(metadata.get(key, "")))
            if prompt:
                return PromptInfo(prompt=prompt, source=key, extractor=self.name)
        return None


DEFAULT_EXTRACTORS: tuple[PromptExtractor, ...] = (
    ForgeNeoPromptExtractor(),
    GenericPromptExtractor(),
)


def read_png_metadata(path: str | Path) -> dict[str, str]:
    with Image.open(path) as image:
        return {str(key): _text(value) for key, value in image.info.items()}


def extract_prompt_from_metadata(
    metadata: Mapping[str, str],
    extractors: tuple[PromptExtractor, ...] = DEFAULT_EXTRACTORS,
) -> PromptInfo:
    for extractor in extractors:
        prompt_info = extractor.extract(metadata)
        if prompt_info is not None:
            return prompt_info
    return PromptInfo(prompt="", source="none", extractor="none")


def extract_prompt(path: str | Path) -> PromptInfo:
    return extract_prompt_from_metadata(read_png_metadata(path))
