"""ImportStep: read a STEP file into the DAG, like any other Python file read.

``ImportStep`` reads its source exactly the way ``open()`` does: a path (``str``
or ``os.PathLike``) is resolved against the current working directory, and an
already-open file object (anything with ``.read()``, text or binary) is read
as is. Getting the file onto disk — a download, an upload, the project files of
a playground — is up to the caller; there is no network, URL or cache logic
here. The file's text is stored in the node (``content``) with its sha256 and a
label (the file name when known), so the DAG is self-contained.
"""

from __future__ import annotations

import hashlib
import os
from pathlib import Path
from typing import Any

#: Every ISO 10303-21 ("STEP physical file") starts with this keyword.
STEP_MAGIC = "ISO-10303-21"
#: Label used when the STEP text has no file name (``ImportStep.from_text``).
INLINE_STEP_LABEL = "inline.step"


class StepFileError(ValueError):
    """The source is not readable STEP (ISO 10303-21) text."""


def _decode(data: bytes | str, label: str) -> str:
    if isinstance(data, str):
        return data
    try:
        return data.decode("utf-8")
    except UnicodeDecodeError:
        # STEP is 7-bit ASCII by the standard; latin-1 never fails and keeps
        # stray 8-bit bytes in string literals (vendor names, comments).
        return data.decode("latin-1")


def validate_step_text(text: str, label: str = INLINE_STEP_LABEL) -> str:
    """Return ``text`` if it looks like an ISO 10303-21 file, else raise.

    The check is structural only (header keyword, HEADER and DATA sections);
    the kernel reads the geometry and reports anything deeper.
    """
    if not isinstance(text, str):
        raise StepFileError(
            f"{label}: STEP content must be text, got {type(text).__name__}"
        )
    head = text.lstrip("﻿ \t\r\n")
    if not head:
        raise StepFileError(f"{label}: the STEP file is empty")
    if not head.startswith(STEP_MAGIC):
        raise StepFileError(
            f"{label}: not a STEP file — it must start with '{STEP_MAGIC};' "
            f"(got {head[:40]!r}). Export the model as STEP (.step/.stp, AP203/AP214/AP242)."
        )
    upper = head.upper()
    if "HEADER;" not in upper or "DATA;" not in upper:
        raise StepFileError(
            f"{label}: truncated STEP file — missing its HEADER or DATA section"
        )
    return text


def read_step_source(source: Any) -> tuple[str, str]:
    """Read ``source`` like ``open()`` would; return ``(text, label)``.

    ``source`` is a path (``str`` / ``os.PathLike``, resolved against the
    current working directory) or a file object with ``.read()``.
    """
    if hasattr(source, "read"):
        label = (
            os.path.basename(str(getattr(source, "name", "") or ""))
            or INLINE_STEP_LABEL
        )
        return _decode(source.read(), label), label
    if isinstance(source, (str, os.PathLike)):
        path = Path(source)
        if isinstance(source, str) and source.lstrip().startswith(STEP_MAGIC):
            raise StepFileError(
                "ImportStep got STEP text where a path was expected — use ImportStep.from_text(text)"
            )
        try:
            data = path.read_bytes()
        except FileNotFoundError:
            raise FileNotFoundError(
                f"ImportStep: no such file {str(path)!r} (resolved like open(), from the "
                f"current directory {os.getcwd()!r})"
            ) from None
        return _decode(data, path.name), path.name
    raise TypeError(
        "ImportStep needs a path (str or os.PathLike) or an open file object; "
        f"got {type(source).__name__}. For STEP text, use ImportStep.from_text(text)."
    )


def _step_fields(text: str, label: str) -> dict[str, Any]:
    from cadbuildr.foundation.gen.models import StringParameter

    validate_step_text(text, label)
    return {
        "content": StringParameter(value=text),
        "sha256": StringParameter(
            value=hashlib.sha256(text.encode("utf-8")).hexdigest()
        ),
        "filename": StringParameter(value=label),
    }


class ImportStepMixin:
    """Constructors for ``ImportStep``: ``ImportStep(path_or_file)``, ``ImportStep.from_text(text)``."""

    def __init__(self, source: Any = None, /, **kwargs: Any) -> None:
        if source is not None:
            if "content" in kwargs:
                raise TypeError(
                    "ImportStep: pass either a file (path / file object) or content=, not both"
                )
            text, label = read_step_source(source)
            fields = _step_fields(text, label)
            if "filename" in kwargs:
                fields.pop("filename")
            kwargs = {**fields, **kwargs}
        elif "content" not in kwargs:
            raise TypeError(
                "ImportStep needs a STEP file: ImportStep('part.step'), ImportStep(open_file) "
                "or ImportStep.from_text(step_text)"
            )
        super().__init__(**kwargs)

    @classmethod
    def from_text(cls, text: str, filename: str = INLINE_STEP_LABEL, **kwargs: Any):
        """An ImportStep from STEP text already in memory (e.g. an inline example)."""
        return cls(**_step_fields(text, filename), **kwargs)


def part_from_step(cls, source: Any, name: str | None = None):
    """``Part.from_step(path_or_file)``: a Part whose only operation is the imported solid."""
    from cadbuildr.foundation.gen.models import ImportStep

    step = source if isinstance(source, ImportStep) else ImportStep(source)
    part = cls()
    part.name.value = name or os.path.splitext(step.filename.value)[0] or "step_part"
    part.add_operation(step)
    return part


def install_part_from_step() -> None:
    """Attach ``Part.from_step`` (called once from ``cadbuildr.foundation``)."""
    from cadbuildr.foundation.gen.models import Part

    Part.from_step = classmethod(part_from_step)
