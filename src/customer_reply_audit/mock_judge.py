"""Deterministic demonstration judge.

This module is intentionally labelled mock.  It uses public, general relation
rules and never reads ground truth.  It proves the pipeline, not semantic
generalisation.
"""
from __future__ import annotations

import re

from .models import Claim, EvidenceRelation, IssueType, JudgeOutput, ReplyRecord, Severity


def _sentence(text: str, needle: str) -> str:
    for part in re.split(r"(?<=[。！？；])", text):
        if needle in part:
            return part.strip()
    return text.strip()


def _claim(
    record: ReplyRecord,
    *,
    reply_needle: str,
    evidence_needle: str = "",
    subject: str,
    predicate: str,
    value: str,
    relation: EvidenceRelation,
    issue: IssueType | None,
    severity: Severity,
    reason: str,
    tags: list[str],
) -> Claim:
    reply_quote = _sentence(record.system_reply, reply_needle) if reply_needle else ""
    evidence_quote = _sentence(record.knowledge_base, evidence_needle) if evidence_needle else ""
    return Claim(
        reply_quote=reply_quote,
        subject=subject,
        predicate=predicate,
        value=value,
        relation=relation,
        evidence_quote=evidence_quote,
        issue_types=[issue] if issue else [],
        business_tags=tags,
        severity=severity,
        reason=reason,
    )


def _match_group(pattern: str, text: str) -> str | None:
    match = re.search(pattern, text, re.I)
    return match.group(1) if match else None


def judge(record: ReplyRecord) -> JudgeOutput:
    """Apply bounded generic cues without any ID or label lookup."""
    reply, kb, question = record.system_reply, record.knowledge_base, record.user_question
    claims: list[Claim] = []

    # Safety restrictions override unconditional reassurance.
    if re.search(r"注意事项|建议咨询医生|安全|禁用|慎用", kb) and re.search(r"放心|绝对安全|无需.*咨询", reply):
        claims.append(_claim(
            record, reply_needle="放心", evidence_needle="建议咨询医生",
            subject="使用人群", predicate="安全限制", value="无条件可用",
            relation=EvidenceRelation.CONTRADICTED, issue=IssueType.SAFETY_DENIAL,
            severity=Severity.CRITICAL, reason="回复把知识库中的安全限制改成无条件安全承诺。",
            tags=["safety", "product_parameter"],
        ))

    # Capability and completed-operation claims require an explicit capability/receipt.
    capability_limit = re.search(r"(?:未接入|不具备|不可口头告知|需人工后台操作)[^。；]*", kb)
    operation_claim = re.search(r"(?:我帮您查|已经?帮您|已帮您|已升级|直接发到|会有专属客服|具体地址)", reply)
    if capability_limit and operation_claim:
        claims.append(_claim(
            record, reply_needle=operation_claim.group(0), evidence_needle=capability_limit.group(0),
            subject="客服系统", predicate="已执行或已查询", value=operation_claim.group(0),
            relation=EvidenceRelation.CONTRADICTED, issue=IssueType.FABRICATED_CAPABILITY,
            severity=Severity.HIGH, reason="知识库声明能力受限，回复却声称已完成查询、修改或升级。",
            tags=["capability", "commitment"],
        ))

    # Unknown evidence is not a contradiction; a definite answer is unsupported.
    unknown = re.search(r"(?:未标注|未提及)[^。；]*", kb)
    definite = re.search(r"(?:支持的|是的|我们是|可以用于)", reply)
    if unknown and definite:
        claims.append(_claim(
            record, reply_needle=definite.group(0), subject=question.rstrip("？?"),
            predicate="确定断言", value=definite.group(0),
            relation=EvidenceRelation.UNSUPPORTED, issue=IssueType.UNSUPPORTED_ASSERTION,
            severity=Severity.MEDIUM, reason="知识库没有提供支持该确定断言的证据；这不等于已证明现实中为假。",
            tags=["product_parameter" if "参数" in kb else "brand"],
        ))

    # Explicit positive/negative conflicts for policies, discounts, channels and stores.
    polarity_pairs = [
        ("暂不支持纸质发票", "支持电子发票和纸质发票", "发票类型", "paper_invoice"),
        ("无满", "有一张满", "优惠活动", "discount"),
        ("无线下门店", "有的，我们在", "线下门店", "store"),
        ("当前无学生优惠", "有的，凭学生证", "学生优惠", "discount"),
    ]
    for kb_needle, reply_needle, subject, tag in polarity_pairs:
        if kb_needle in kb and reply_needle in reply:
            claims.append(_claim(
                record, reply_needle=reply_needle, evidence_needle=kb_needle,
                subject=subject, predicate="可用性", value="回复肯定、知识库否定",
                relation=EvidenceRelation.CONTRADICTED, issue=IssueType.FACTUAL_CONTRADICTION,
                severity=Severity.HIGH if tag == "discount" else Severity.MEDIUM,
                reason="回复的肯定结论与知识库的明确否定相冲突。", tags=[tag, "rights"],
            ))

    # Compare values only within named properties; never compare bare numbers globally.
    comparisons = [
        (r"蓝牙\s*(\d+(?:\.\d+)?)", "蓝牙版本", "product_parameter", Severity.HIGH),
        (r"延迟(?:低至|约)?\s*(\d+)\s*ms", "延迟", "product_parameter", Severity.MEDIUM),
        (r"(?:下单后)?\s*(\d+)\s*小时内发货", "发货时限", "shipping", Severity.MEDIUM),
        (r"(?:接口类型：|充电头是)(USB-A|Type-C)", "充电头输出接口", "product_parameter", Severity.HIGH),
    ]
    for pattern, subject, tag, severity in comparisons:
        reply_value, kb_value = _match_group(pattern, reply), _match_group(pattern, kb)
        if reply_value and kb_value and reply_value.casefold() != kb_value.casefold():
            claims.append(_claim(
                record, reply_needle=reply_value, evidence_needle=kb_value,
                subject=subject, predicate="参数值", value=reply_value,
                relation=EvidenceRelation.CONTRADICTED, issue=IssueType.FACTUAL_CONTRADICTION,
                severity=severity, reason=f"同一主体和属性的值不一致：回复为 {reply_value}，知识库为 {kb_value}。",
                tags=[tag],
            ))

    # Policy values with units and conditions.
    reply_return = _match_group(r"(\d+)\s*天无理由退货", reply)
    kb_return = _match_group(r"(\d+)\s*天无理由退货", kb)
    if reply_return and kb_return and reply_return != kb_return:
        claims.append(_claim(
            record, reply_needle=f"{reply_return}天无理由退货", evidence_needle=f"{kb_return}天无理由退货",
            subject="普通商品", predicate="无理由退货期限", value=f"{reply_return}天",
            relation=EvidenceRelation.CONTRADICTED, issue=IssueType.FACTUAL_CONTRADICTION,
            severity=Severity.HIGH, reason="同为无理由退货条件，回复期限与知识库不一致。", tags=["policy", "rights"],
        ))

    warranty_reply = re.search(r"保修期为(\d+)(年|个月)", reply)
    warranty_kb = re.search(r"保修期[：:]\s*(\d+)(年|个月)", kb)
    if warranty_reply and warranty_kb and warranty_reply.groups() != warranty_kb.groups():
        claims.append(_claim(
            record, reply_needle=warranty_reply.group(0), evidence_needle=warranty_kb.group(0),
            subject="商品", predicate="保修期", value="".join(warranty_reply.groups()),
            relation=EvidenceRelation.CONTRADICTED, issue=IssueType.FACTUAL_CONTRADICTION,
            severity=Severity.HIGH, reason="保修期的数值或单位与知识库不一致。", tags=["policy", "rights"],
        ))

    material_reply = _match_group(r"采用([^，。]+?)(?:制作|，)", reply)
    material_kb = _match_group(r"材质[：:]\s*([^。；]+)", kb)
    if material_reply and material_kb and material_reply not in material_kb and material_kb not in material_reply:
        claims.append(_claim(
            record, reply_needle=material_reply, evidence_needle=material_kb,
            subject="商品", predicate="材质", value=material_reply,
            relation=EvidenceRelation.CONTRADICTED, issue=IssueType.FACTUAL_CONTRADICTION,
            severity=Severity.HIGH, reason="商品材质与知识库明确参数不一致。", tags=["product_parameter"],
        ))

    if "合作快递" in kb and "顺丰" in reply and "顺丰" not in kb:
        claims.append(_claim(
            record, reply_needle="顺丰", evidence_needle="合作快递",
            subject="订单", predicate="合作快递", value="顺丰",
            relation=EvidenceRelation.CONTRADICTED, issue=IssueType.FACTUAL_CONTRADICTION,
            severity=Severity.MEDIUM, reason="回复指定的快递不在知识库列出的合作快递中。", tags=["shipping"],
        ))

    if "运费由买家承担" in kb and re.search(r"运费.*(?:我们|商家)承担", reply):
        claims.append(_claim(
            record, reply_needle="运费", evidence_needle="运费由买家承担",
            subject="非质量问题退货", predicate="运费承担方", value="商家",
            relation=EvidenceRelation.CONTRADICTED, issue=IssueType.FACTUAL_CONTRADICTION,
            severity=Severity.HIGH, reason="回复改变了非质量问题退货的运费承担方。", tags=["policy", "rights"],
        ))

    # Absolute sizing advice suppresses decision-relevant feedback.
    if re.search(r"用户反馈.*偏大", kb) and re.search(r"不偏大也不偏小|尺码标准", reply):
        claims.append(_claim(
            record, reply_needle="不偏大也不偏小", evidence_needle="用户反馈",
            subject="鞋码", predicate="尺码倾向", value="绝对标准",
            relation=EvidenceRelation.CONTRADICTED, issue=IssueType.MATERIAL_OMISSION,
            severity=Severity.MEDIUM,
            reason="回复绝对化否定了知识库中的偏大反馈，并遗漏会影响选码的条件。",
            tags=["product_parameter", "purchase_decision"],
        ))

    if not claims:
        claims.append(Claim(
            reply_quote=reply,
            subject=question.rstrip("？?"), predicate="整体回答", value=reply,
            relation=EvidenceRelation.SUPPORTED, evidence_quote=kb,
            issue_types=[], business_tags=[], severity=Severity.NONE,
            reason="受限 mock 规则未发现矛盾、无依据确定断言或关键遗漏；这不是完整语义证明。",
        ))
    return JudgeOutput(claims=claims)

