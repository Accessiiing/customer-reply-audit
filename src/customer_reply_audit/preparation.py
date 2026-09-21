from __future__ import annotations

import json
from pathlib import Path

from pydantic import TypeAdapter

from .io import sha256_bytes, sha256_file, write_json
from .models import ReplyRecord


def prepare_replies(source: Path, output_dir: Path) -> tuple[Path, Path]:
    raw = source.read_bytes()
    text = raw.decode("utf-8-sig")
    stripped = text.lstrip()
    prefix_chars = len(text) - len(stripped)
    payload, end = json.JSONDecoder().raw_decode(stripped)
    records = TypeAdapter(list[ReplyRecord]).validate_python(payload)
    trailing = stripped[end:]
    if not trailing.strip():
        raise ValueError("source is already valid JSON; no derived cleanup is required")

    output_dir.mkdir(parents=True, exist_ok=True)
    clean_path = output_dir / "replies.cleaned.json"
    manifest_path = output_dir / "replies.cleaned.manifest.json"
    write_json(clean_path, [record.model_dump() for record in records])
    manifest = {
        "source_path": str(source.resolve()),
        "source_sha256": sha256_file(source),
        "derived_path": str(clean_path.resolve()),
        "derived_sha256": sha256_file(clean_path),
        "record_count": len(records),
        "leading_whitespace_chars": prefix_chars,
        "trailing_chars": len(trailing),
        "trailing_sha256": sha256_bytes(trailing.encode("utf-8")),
        "policy": "The original attachment was not modified. Non-JSON trailing content was excluded explicitly.",
    }
    write_json(manifest_path, manifest)
    return clean_path, manifest_path
