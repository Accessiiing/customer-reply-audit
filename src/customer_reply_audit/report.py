from __future__ import annotations

import html
import json
from pathlib import Path
from typing import Any

from .models import DetectionRun, ReplyRecord


def _pct(value: float | None) -> str:
    return "N/A" if value is None else f"{value:.1%}"


def render_html(run: DetectionRun, evaluation: dict[str, Any], records: list[ReplyRecord], output: Path) -> None:
    by_id = {record.id: record for record in records}
    cm = evaluation["confusion_matrix"]
    metrics = evaluation["metrics_on_valid_decisions"]
    cards: list[str] = []
    for item in run.items:
        record = by_id[item.id]
        issue_labels = ", ".join(issue.value for issue in item.issue_types) or "无"
        claims = "".join(
            f"<li><span class='rel {html.escape(claim.relation.value)}'>{html.escape(claim.relation.value)}</span> "
            f"<b>{html.escape(claim.subject)} · {html.escape(claim.predicate)}</b>：{html.escape(claim.reason)}"
            f"<blockquote>回复：{html.escape(claim.reply_quote or '（关键遗漏）')}<br>证据：{html.escape(claim.evidence_quote or '（无支持证据）')}</blockquote></li>"
            for claim in item.claims
        )
        cards.append(f"""
        <article class="card severity-{html.escape(item.severity.value)}">
          <header><b>{html.escape(item.id)}</b><span>{html.escape(item.status)} / {html.escape(str(item.is_hallucination))}</span><span>{html.escape(item.severity.value)}</span></header>
          <p><strong>用户：</strong>{html.escape(record.user_question)}</p>
          <p><strong>回复：</strong>{html.escape(record.system_reply)}</p>
          <details><summary>知识库与逐项证据</summary><p>{html.escape(record.knowledge_base)}</p><ul>{claims}</ul></details>
          <p class="reason"><strong>类型：</strong>{html.escape(issue_labels)}<br><strong>结论：</strong>{html.escape(item.reason)}</p>
        </article>""")
    mode_warning = "真实模型运行" if run.metadata.mode == "real" else "显式 MOCK：仅验证流程与受限规则，不代表真实模型效果"
    payload = json.dumps(evaluation, ensure_ascii=False, indent=2)
    document = f"""<!doctype html>
<html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>客服回复幻觉检测报告</title>
<style>
:root{{--bg:#f5f3ee;--ink:#17211f;--muted:#65716d;--line:#d8d4ca;--accent:#bb4d2c;--ok:#2c6e5a}}
*{{box-sizing:border-box}}body{{margin:0;background:var(--bg);color:var(--ink);font:15px/1.65 system-ui,"Microsoft YaHei",sans-serif}}
main{{max-width:1120px;margin:auto;padding:36px 20px 80px}}h1{{font-size:34px;margin:0 0 4px}}.eyebrow{{letter-spacing:.12em;color:var(--accent);font-weight:700}}
.notice{{background:#fff4da;border:1px solid #e5c675;padding:12px 16px;margin:20px 0}}.metrics{{display:grid;grid-template-columns:repeat(6,1fr);gap:10px;margin:24px 0}}
.metric,.card{{background:#fff;border:1px solid var(--line);box-shadow:0 7px 22px #302a1f0d}}.metric{{padding:14px}}.metric b{{display:block;font-size:24px}}.metric span{{color:var(--muted)}}
.toolbar{{display:flex;gap:8px;flex-wrap:wrap;margin:20px 0}}button{{border:1px solid var(--line);background:#fff;padding:7px 12px;cursor:pointer}}button.active{{background:var(--ink);color:#fff}}
.card{{padding:18px;margin:12px 0;border-left:5px solid #9ba19f}}.severity-high{{border-left-color:#d36a31}}.severity-critical{{border-left-color:#9d2430}}.severity-medium{{border-left-color:#d2a52f}}
.card header{{display:flex;gap:14px;align-items:center}}.card header b{{font-size:20px;margin-right:auto}}blockquote{{margin:8px 0;padding:8px 12px;border-left:3px solid var(--line);background:#f7f7f4}}
.rel{{font:12px ui-monospace,monospace;padding:2px 6px;background:#eceae4}}.contradicted{{color:#a02b2b}}.unsupported{{color:#8a5316}}.supported{{color:var(--ok)}}
details summary{{cursor:pointer;font-weight:700}}pre{{white-space:pre-wrap;background:#17211f;color:#dfe8e4;padding:16px;overflow:auto}}@media(max-width:760px){{.metrics{{grid-template-columns:repeat(2,1fr)}}}}
</style></head><body><main>
<div class="eyebrow">EVIDENCE-GROUNDED AUDIT</div><h1>客服回复幻觉检测</h1>
<p>run_id：<code>{html.escape(run.metadata.run_id)}</code> · 模型：<code>{html.escape(run.metadata.model)}</code></p>
<div class="notice">{html.escape(mode_warning)}</div>
<section class="metrics">
<div class="metric"><b>{cm['TP']}</b><span>TP</span></div><div class="metric"><b>{cm['FP']}</b><span>FP</span></div><div class="metric"><b>{cm['TN']}</b><span>TN</span></div><div class="metric"><b>{cm['FN']}</b><span>FN</span></div>
<div class="metric"><b>{_pct(metrics['f1'])}</b><span>F1</span></div><div class="metric"><b>{_pct(metrics['balanced_accuracy'])}</b><span>Balanced Accuracy</span></div>
</section>
<div class="toolbar"><button class="active" data-filter="all">全部</button><button data-filter="critical">Critical</button><button data-filter="high">High</button><button data-filter="medium">Medium</button><button data-filter="none">正常</button></div>
<section>{''.join(cards)}</section><details><summary>机器可读评估 JSON</summary><pre>{html.escape(payload)}</pre></details>
</main><script>
document.querySelectorAll('button[data-filter]').forEach(b=>b.addEventListener('click',()=>{{document.querySelectorAll('button').forEach(x=>x.classList.remove('active'));b.classList.add('active');const f=b.dataset.filter;document.querySelectorAll('.card').forEach(c=>c.hidden=f!=='all'&&!c.classList.contains('severity-'+f));}}));
</script></body></html>"""
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(document, encoding="utf-8")

