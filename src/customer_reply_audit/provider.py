from __future__ import annotations

import json
import os
from pathlib import Path

import httpx

from .models import JudgeOutput, ReplyRecord


class ProviderError(RuntimeError):
    pass


class OpenAICompatibleJudge:
    def __init__(self, *, prompt_path: Path, timeout: float | None = None):
        self.api_key = os.getenv("AUDIT_API_KEY") or os.getenv("OPENAI_API_KEY")
        self.base_url = (os.getenv("AUDIT_BASE_URL") or os.getenv("OPENAI_BASE_URL") or "https://api.openai.com/v1").rstrip("/")
        self.model = os.getenv("AUDIT_MODEL") or os.getenv("OPENAI_MODEL") or ""
        self.timeout = timeout or float(os.getenv("AUDIT_TIMEOUT_SECONDS", "60"))
        self.prompt = prompt_path.read_text(encoding="utf-8")
        if not self.api_key or not self.model:
            raise ProviderError("real mode requires AUDIT_API_KEY and AUDIT_MODEL")

    def judge(self, record: ReplyRecord) -> tuple[JudgeOutput, dict[str, int | float | str]]:
        schema = JudgeOutput.model_json_schema()
        payload = {
            "model": self.model,
            "temperature": 0,
            "response_format": {"type": "json_object"},
            "messages": [
                {"role": "system", "content": self.prompt + "\nJSON Schema:\n" + json.dumps(schema, ensure_ascii=False)},
                {"role": "user", "content": json.dumps(record.model_dump(), ensure_ascii=False)},
            ],
        }
        try:
            with httpx.Client(timeout=self.timeout) as client:
                response = client.post(
                    f"{self.base_url}/chat/completions",
                    headers={"Authorization": f"Bearer {self.api_key}"},
                    json=payload,
                )
                response.raise_for_status()
                body = response.json()
                content = body["choices"][0]["message"]["content"]
                usage = body.get("usage") or {"tokens": "unavailable", "cost": "unavailable"}
                try:
                    return JudgeOutput.model_validate_json(content), usage
                except ValueError as first_error:
                    # One bounded format-only repair.  The prior content is data to
                    # re-serialize, not an independent semantic authority.
                    repair_payload = {
                        "model": self.model,
                        "temperature": 0,
                        "response_format": {"type": "json_object"},
                        "messages": [
                            {"role": "system", "content": "只修复 JSON 格式和 schema，不改变语义。只返回 JSON。Schema:\n" + json.dumps(schema, ensure_ascii=False)},
                            {"role": "user", "content": content},
                        ],
                    }
                    repaired = client.post(
                        f"{self.base_url}/chat/completions",
                        headers={"Authorization": f"Bearer {self.api_key}"},
                        json=repair_payload,
                    )
                    repaired.raise_for_status()
                    repaired_body = repaired.json()
                    repaired_content = repaired_body["choices"][0]["message"]["content"]
                    try:
                        return JudgeOutput.model_validate_json(repaired_content), repaired_body.get("usage") or usage
                    except ValueError as repair_error:
                        raise ProviderError(f"format repair failed: {repair_error}") from first_error
        except ProviderError:
            raise
        except (httpx.HTTPError, KeyError, ValueError, json.JSONDecodeError) as exc:
            raise ProviderError(f"provider call failed: {type(exc).__name__}: {exc}") from exc
