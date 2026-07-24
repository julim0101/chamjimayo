"""
참지마요 — 위험도 스코어링 및 사건 요약

3단계 증거 등급
  Tier 1  확정 지표 — 발화 독점률·시간외 주기성·반복성 등 수학적 연산. 반박 불가.
  Tier 2  분류 지표 — 모욕·독성 어휘 밀도. 모델 확률값.
  Tier 3  정황 후보 — 가스라이팅·배제·수동공격. LLM 맥락 추론. **최종 판단은 사람.**

종합 위험도는 3요건 점수의 가중 결합이되,
**요건은 모두 충족되어야 성립**하므로 최소값에 페널티를 준다
(하나라도 현저히 낮으면 종합 점수도 끌어내린다).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional

import numpy as np
import pandas as pd

from .metrics import RequirementBlock, selective_response

# ---------------------------------------------------------------- 등급


RISK_LEVELS = [
    (0.60, "높음", "#C1121F", "3요건 모두에서 강한 지표가 관측됨."),
    (0.38, "중간", "#E36414", "복수 요건에서 유의미한 지표. 추가 확인 필요."),
    (0.20, "낮음", "#5C6B73", "일부 지표만 관측. 맥락 확인 권고."),
    (0.00, "관측 없음", "#8D99AE", "유의미한 지표가 관측되지 않음."),
]


def risk_level(score: float) -> tuple[str, str, str]:
    for th, label, color, desc in RISK_LEVELS:
        if score >= th:
            return label, color, desc
    return RISK_LEVELS[-1][1], RISK_LEVELS[-1][2], RISK_LEVELS[-1][3]


# 부수 법위반 단서의 중대성 가중 — 조사 우선순위 산출에 사용
VIOLATION_SEVERITY = {
    "신고자 불이익 처우": 0.20,          # 근기법 제109조 — 3년 이하 징역 (형사처벌)
    "임금 미지급·감액": 0.12,            # 근기법 제43조 — 형사처벌 대상
    "연장·휴일근로수당 미지급": 0.10,     # 근기법 제56조
    "근로시간 위반": 0.08,               # 근기법 제50·53조
    "직장 내 괴롭힘 조치의무 위반": 0.06,  # 근기법 제76조의3 — 과태료
}


def priority_score(risk: float, law_flags: dict[str, str]) -> tuple[float, list[str]]:
    """조사 우선순위 = 괴롭힘 성립 가능성 + 별건 위반의 중대성.

    괴롭힘 성립 여부와 조사 우선순위는 별개의 판단이다.
    임금 체불이나 신고자 보복처럼 그 자체로 형사처벌 대상인 단서가 있으면
    괴롭힘 점수와 무관하게 먼저 들여다볼 사건이 된다.
    """
    bonus, reasons = 0.0, []
    for name in law_flags:
        w = VIOLATION_SEVERITY.get(name, 0.05)
        bonus += w
        reasons.append(name)
    return float(np.clip(risk + bonus, 0.0, 1.0)), reasons


# ---------------------------------------------------------------- 사건 요약


@dataclass
class CaseSummary:
    case_id: str
    source_name: str
    room: str
    actor: str
    subject: str
    n_messages: int
    n_speakers: int
    period_start: datetime
    period_end: datetime
    span_days: int

    blocks: list[RequirementBlock] = field(default_factory=list)
    risk_score: float = 0.0
    risk_label: str = ""
    risk_color: str = ""
    risk_desc: str = ""

    priority: float = 0.0  # 조사 우선순위 (위험도 + 별건 위반 중대성)
    priority_reasons: list[str] = field(default_factory=list)

    # Tier 3 전용 큐 — 정량 지표는 낮으나 정황 후보가 관측된 사건
    needs_human_review: bool = False
    review_reason: str = ""

    tox_backend: str = "lexicon"
    rag_backend: str = "bm25"

    key_evidence: list[dict] = field(default_factory=list)  # 핵심 증거 발화
    subtle_evidence: list[dict] = field(default_factory=list)  # Tier 3 정황
    law_flags: dict[str, str] = field(default_factory=dict)  # 부수 법위반 단서
    citations: list[dict] = field(default_factory=list)  # RAG 인용
    masking_counts: dict[str, int] = field(default_factory=dict)

    @property
    def block_map(self) -> dict[str, RequirementBlock]:
        return {b.code: b for b in self.blocks}

    @property
    def requirement_scores(self) -> dict[str, float]:
        return {b.code: b.score for b in self.blocks}

    @property
    def all_requirements_met(self) -> bool:
        """3요건 모두 최소 기준(0.35)을 넘는지 — 성립 가능성의 1차 신호."""
        return all(b.score >= 0.35 for b in self.blocks)


# ---------------------------------------------------------------- 종합 점수


def combine(blocks: list[RequirementBlock]) -> float:
    """3요건 점수 → 종합 위험도.

    산술평균만 쓰면 한 요건이 0이어도 나머지가 높으면 점수가 높게 나온다.
    그러나 직장 내 괴롭힘은 3요건 **동시 충족**이 성립 요건이므로,
    산술평균과 기하평균을 절반씩 섞어 '균형'에 보상을 준다.
    """
    s = np.array([b.score for b in blocks], dtype=float)
    if s.size == 0:
        return 0.0
    arith = float(s.mean())
    geo = float(np.prod(np.clip(s, 1e-6, 1.0)) ** (1 / s.size))
    return float(np.clip(0.5 * arith + 0.5 * geo, 0.0, 1.0))


# ---------------------------------------------------------------- 증거 추출


def extract_key_evidence(
    adf: pd.DataFrame,
    actor: str,
    blocks: list[RequirementBlock],
    tox_col: str = "tox_score",
    limit: int = 12,
) -> list[dict]:
    """대시보드 상단에 띄울 '핵심 증거' 발화를 고른다.

    선정 기준 (합산 점수 상위):
      - 독성 점수
      - 근무시간 외 지시 여부
      - 심야 연락 여부
      - 질책성 추궁 여부
      - 부수 법위반 단서 포함 여부
    """
    if adf.empty:
        return []
    col = tox_col if tox_col in adf.columns else "lex_toxicity"
    A = adf[adf["speaker"] == actor].copy()
    if A.empty:
        return []

    A["_w"] = (
        A[col] * 2.0
        + (A["is_offhours"] & A["is_directive"]) * 1.2
        + A["is_night"] * 0.8
        + A["is_holiday"] * 0.5
        + A["is_rebuke_q"] * 0.6
        + A["law_flags"].apply(len) * 1.5
    )
    top = A.nlargest(limit, "_w")
    top = top[top["_w"] > 0.3].sort_values("ts")

    out = []
    for _, r in top.iterrows():
        reasons = []
        if r[col] >= 0.5:
            reasons.append(f"독성 {r[col]:.2f}")
        if r["is_offhours"] and r["is_directive"]:
            reasons.append("근무시간 외 지시")
        if r["is_night"]:
            reasons.append("심야 연락")
        if r["is_holiday"]:
            reasons.append("휴일 연락")
        if r["is_rebuke_q"]:
            reasons.append("질책성 추궁")
        for name, _law in r["law_flags"]:
            reasons.append(f"⚖ {name}")
        out.append(
            {
                "idx": int(r["idx"]),
                "ts": r["ts"],
                "speaker": r["speaker"],
                "text": r["text"],
                "toxicity": float(r[col]),
                "terms": list(r["toxic_terms"]),
                "reasons": reasons,
            }
        )
    return out


def extract_subtle_evidence(adf: pd.DataFrame, actor: str, limit: int = 10) -> list[dict]:
    """Tier 3 정황 후보 — 반드시 '후보'로만 제시한다."""
    if adf.empty:
        return []
    A = adf[(adf["speaker"] == actor) & (adf["subtle_tags"].apply(len) > 0)]
    out = []
    for _, r in A.head(limit).iterrows():
        out.append(
            {
                "idx": int(r["idx"]),
                "ts": r["ts"],
                "speaker": r["speaker"],
                "text": r["text"],
                "tags": list(r["subtle_tags"]),
            }
        )
    return out


def collect_law_flags(adf: pd.DataFrame) -> dict[str, str]:
    """부수 법위반 단서를 유형 → 근거조항으로 집계."""
    flags: dict[str, str] = {}
    for lst in adf["law_flags"]:
        for name, law in lst:
            flags[name] = law
    return flags


# ---------------------------------------------------------------- 조립


def build_case(
    case_id: str,
    source_name: str,
    room: str,
    adf: pd.DataFrame,
    actor: str,
    subject: str,
    blocks: list[RequirementBlock],
    tox_backend: str = "lexicon",
    rag_backend: str = "bm25",
    masking_counts: Optional[dict] = None,
    tox_col: str = "tox_score",
) -> CaseSummary:
    score = combine(blocks)
    label, color, desc = risk_level(score)
    flags = collect_law_flags(adf)
    prio, prio_reasons = priority_score(score, flags)

    subtle = extract_subtle_evidence(adf, actor)
    sel = selective_response(adf, actor, subject)

    # Tier 3 정황은 **점수에 섞지 않는다.**
    # 확률적 추론을 확정 지표와 합산하면 "반박 불가능한 숫자"라는 Tier 1의 강점이 무너진다.
    # 대신 별도의 '사람 검토 필요' 큐로 올린다.
    needs_review, reason = False, ""
    if score < 0.38 and len(subtle) >= 3:
        needs_review = True
        tags = sorted({t for e in subtle for t in e["tags"]})
        reason = (
            f"정량 지표는 낮으나({score:.2f}) 정황 후보 {len(subtle)}건 관측 — {', '.join(tags)}"
        )
        if sel.get("applicable") and sel["gap"] >= 0.15:
            reason += (
                f" / 선택적 무응답 격차 {sel['gap']*100:.0f}%p"
                f"(대상자 {sel['subject_rate']*100:.0f}% vs 동료 {sel['peer_rate']*100:.0f}%)"
            )

    return CaseSummary(
        case_id=case_id,
        source_name=source_name,
        room=room,
        actor=actor,
        subject=subject,
        n_messages=len(adf),
        n_speakers=int(adf["speaker"].nunique()) if not adf.empty else 0,
        period_start=adf["ts"].min() if not adf.empty else datetime.now(),
        period_end=adf["ts"].max() if not adf.empty else datetime.now(),
        span_days=int((adf["ts"].max() - adf["ts"].min()).days + 1) if not adf.empty else 0,
        blocks=blocks,
        risk_score=score,
        risk_label=label,
        risk_color=color,
        risk_desc=desc,
        priority=prio,
        priority_reasons=prio_reasons,
        tox_backend=tox_backend,
        rag_backend=rag_backend,
        needs_human_review=needs_review,
        review_reason=reason,
        key_evidence=extract_key_evidence(adf, actor, blocks, tox_col),
        subtle_evidence=subtle,
        law_flags=flags,
        masking_counts=masking_counts or {},
    )


def attach_citations(case: CaseSummary, retriever, top_k: int = 3) -> CaseSummary:
    """3요건별 근거 조항·판단기준을 RAG로 붙인다. 폐쇄형 코퍼스 밖은 인용하지 않는다."""
    cites: list[dict] = []
    seen: set[str] = set()

    for b in case.blocks:
        # 해당 요건에서 실제로 관측된 지표를 질의로 사용 (근거 없는 검색 방지)
        observed = [m.label for m in b.metrics if m.value > 0]
        q = " ".join(observed[:4])
        for h in retriever.for_requirement(b.code, q, top_k=top_k):
            if h.doc.id in seen:
                continue
            seen.add(h.doc.id)
            cites.append(
                {
                    "req": b.code,
                    "id": h.doc.id,
                    "citation": h.doc.citation,
                    "title": h.doc.title,
                    "text": h.doc.text,
                    "verified": h.doc.verified,
                    "score": h.score,
                }
            )

    # 부수 법위반 단서에 대한 조항도 함께 인용
    for name, law in case.law_flags.items():
        for h in retriever.search(f"{name} {law}", top_k=1, doc_types={"법령"}):
            if h.doc.id in seen:
                continue
            seen.add(h.doc.id)
            cites.append(
                {
                    "req": "부수위반",
                    "id": h.doc.id,
                    "citation": h.doc.citation,
                    "title": h.doc.title,
                    "text": h.doc.text,
                    "verified": h.doc.verified,
                    "score": h.score,
                }
            )

    case.citations = cites
    return case
