from __future__ import annotations

import hashlib
import json
import unicodedata
from pathlib import Path
from typing import TypeVar

from pydantic import BaseModel, TypeAdapter

from .models import ReplyRecord, TruthRecord

T = TypeVar("T", bound=BaseModel)


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    return sha256_bytes(path.read_bytes())


def load_records(path: Path, model: type[T]) -> list[T]:
    raw = json.loads(path.read_text(encoding="utf-8-sig"))
    records = TypeAdapter(list[model]).validate_python(raw)
    ids = [record.id for record in records]
    if len(ids) != len(set(ids)):
        raise ValueError(f"{path}: ID must be unique")
    return records


def load_replies(path: Path) -> list[ReplyRecord]:
    return load_records(path, ReplyRecord)


def load_truth(path: Path) -> list[TruthRecord]:
    return load_records(path, TruthRecord)


def write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if isinstance(payload, BaseModel):
        text = payload.model_dump_json(indent=2)
    else:
        text = json.dumps(payload, ensure_ascii=False, indent=2)
    path.write_text(text + "\n", encoding="utf-8")


def normalize_for_quote(value: str) -> str:
    return "".join(unicodedata.normalize("NFKC", value).split())


def quote_exists(quote: str, source: str) -> bool:
    return bool(quote) and normalize_for_quote(quote) in normalize_for_quote(source)

