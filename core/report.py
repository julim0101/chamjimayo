"""
참지마요 — 리포트 생성

두 종류의 산출물을 만든다.

  1. 감독관용 **증거 분석 보고서** — 위험도, 3요건별 지표, 핵심 증거, 근거 조항
  2. 피해자용 **진정서 초안**       — 육하원칙 정리, 피해 사실, 요청 사항

설계 원칙
  · **템플릿이 기본, LLM은 선택.** API 키가 없거나 호출이 실패해도
    리포트는 반드시 나온다. 시연 중 네트워크 문제로 산출물이 안 나오는 일은 없어야 한다.
  · **LLM은 문장을 다듬을 뿐, 숫자와 인용은 건드리지 않는다.**
    지표는 파이썬 연산 결과를, 조항은 RAG 검색 결과를 그대로 넣는다.
  · 모든 문서 말미에 한계와 면책을 명시한다.
"""

from __future__ import annotations

import textwrap
from datetime import datetime
from typing import Optional

from .scoring import CaseSummary

DISCLAIMER = (
    "본 문서는 대화 로그의 통계적 분석 결과이며, 직장 내 괴롭힘의 성립 여부를 "
    "판정하는 문서가 아닙니다. 사실관계의 진위 판별과 법적 판단은 근로감독관·"
    "노무사·변호사 등 권한 있는 전문가가 수행합니다. 분석은 제출된 대화 기록에 "
    "한정되며, 기록 외의 정황(대면 발언, 업무 배경, 당사자 관계 등)은 반영되지 "
    "않았습니다."
)


def _fmt_dt(dt: datetime) -> str:
    return dt.strftime("%Y-%m-%d %H:%M")


def _fmt_d(dt: datetime) -> str:
    return dt.strftime("%Y-%m-%d")


# ================================================================ 감독관 보고서


def inspector_report(case: CaseSummary, include_full_evidence: bool = True) -> str:
    """근로감독관 제출용 증거 분석 보고서 (Markdown)."""
    c = case
    L: list[str] = []

    L.append(f"# 직장 내 괴롭힘 정량 분석 보고서")
    L.append("")
    L.append(f"**사건번호** `{c.case_id}`  ·  **생성일시** {_fmt_dt(datetime.now())}")
    L.append("")
    L.append("| 항목 | 내용 |")
    L.append("|------|------|")
    L.append(f"| 분석 대상 | {c.room} |")
    L.append(f"| 관찰 기간 | {_fmt_d(c.period_start)} ~ {_fmt_d(c.period_end)} ({c.span_days}일) |")
    L.append(f"| 총 메시지 | {c.n_messages:,}건 · 참여자 {c.n_speakers}명 |")
    L.append(f"| 행위 의심자 | {c.actor} |")
    L.append(f"| 피해 의심 대상자 | {c.subject or '—'} |")
    L.append(f"| **종합 위험도** | **{c.risk_score:.2f} / 1.00 — {c.risk_label}** |")
    L.append(f"| 조사 우선순위 | {c.priority:.2f} |")
    L.append(f"| 3요건 동시 충족 | {'예' if c.all_requirements_met else '아니오'} |")
    L.append("")

    # --- 요약 판단
    L.append("## 1. 분석 요약")
    L.append("")
    L.append(_summary_paragraph(c))
    L.append("")

    # --- 3요건
    L.append("## 2. 근로기준법 제76조의2 성립요건별 지표")
    L.append("")
    for b in c.blocks:
        L.append(f"### {b.code}. {b.title} — {b.score:.2f}")
        L.append("")
        L.append(f"> {b.legal_basis}")
        L.append("")
        L.append("| 지표 | 값 | 산출 근거 |")
        L.append("|------|-----|-----------|")
        for m in b.metrics:
            note = m.note or "—"
            ev = f" (증거 {len(m.evidence_idx)}건)" if m.evidence_idx else ""
            L.append(f"| {m.label} | **{m.display}** | {note}{ev} |")
        L.append("")

    # --- 핵심 증거
    L.append("## 3. 핵심 증거 발화")
    L.append("")
    if not c.key_evidence:
        L.append("_임계치를 초과하는 발화가 관측되지 않았습니다._")
    else:
        L.append("Tier 1(확정 지표)·Tier 2(분류 지표) 기준 상위 발화입니다.")
        L.append("")
        L.append("| # | 일시 | 발화자 | 내용 | 판정 근거 |")
        L.append("|---|------|--------|------|-----------|")
        for e in (c.key_evidence if include_full_evidence else c.key_evidence[:5]):
            txt = e["text"].replace("|", "\\|").replace("\n", " ")
            txt = txt if len(txt) <= 60 else txt[:60] + "…"
            L.append(
                f"| {e['idx']} | {_fmt_dt(e['ts'])} | {e['speaker']} | {txt} | "
                f"{', '.join(e['reasons'])} |"
            )
    L.append("")

    # --- Tier 3
    L.append("## 4. Tier 3 정황 후보 — 사람의 판단이 필요한 항목")
    L.append("")
    if not c.subtle_evidence:
        L.append("_해당 없음._")
    else:
        L.append(
            "아래 항목은 **확정 지표가 아닙니다.** 맥락 추론으로 추출한 후보이며, "
            "종합 위험도 점수에는 반영되지 않았습니다. 조사관의 확인이 필요합니다."
        )
        L.append("")
        L.append("| # | 일시 | 발화자 | 내용 | 정황 유형 |")
        L.append("|---|------|--------|------|-----------|")
        for e in c.subtle_evidence:
            txt = e["text"].replace("|", "\\|").replace("\n", " ")
            txt = txt if len(txt) <= 60 else txt[:60] + "…"
            L.append(
                f"| {e['idx']} | {_fmt_dt(e['ts'])} | {e['speaker']} | {txt} | "
                f"{', '.join(e['tags'])} |"
            )
    L.append("")

    # --- 별건 위반
    L.append("## 5. 별건 법위반 단서")
    L.append("")
    if not c.law_flags:
        L.append("_해당 없음._")
    else:
        L.append(
            "대화 중 직장 내 괴롭힘 외의 노동관계법 위반이 의심되는 표현이 관측되었습니다. "
            "괴롭힘 성립 여부와 별개로 확인이 필요합니다."
        )
        L.append("")
        L.append("| 의심 유형 | 관련 조항 |")
        L.append("|-----------|-----------|")
        for name, law in c.law_flags.items():
            L.append(f"| {name} | {law} |")
    L.append("")

    # --- 근거 조항
    L.append("## 6. 관련 법령 및 판단기준")
    L.append("")
    L.append(
        "아래 인용은 본 서비스에 적재된 **폐쇄형 코퍼스** 내에서만 검색되었습니다. "
        "코퍼스 외부의 법령·판례는 인용되지 않습니다."
    )
    L.append("")
    for req in ["R1", "R2", "R3", "부수위반"]:
        items = [x for x in c.citations if x["req"] == req]
        if not items:
            continue
        L.append(f"**[{req}]**")
        L.append("")
        for x in items:
            badge = "" if x["verified"] else " ⚠️미검증"
            L.append(f"- **{x['citation']}** — {x['title']}{badge}")
            L.append(f"  > {textwrap.shorten(x['text'], 300, placeholder=' …')}")
        L.append("")

    # --- 처리 정보
    L.append("## 7. 처리 정보")
    L.append("")
    L.append("| 항목 | 값 |")
    L.append("|------|-----|")
    L.append(f"| 독성 분류 백엔드 | `{c.tox_backend}` |")
    L.append(f"| 법령 검색 백엔드 | `{c.rag_backend}` |")
    masked = ", ".join(f"{k} {v}건" for k, v in c.masking_counts.items()) or "없음"
    L.append(f"| 개인정보 마스킹 | {masked} |")
    L.append("")

    L.append("---")
    L.append("")
    L.append(f"> ⚖️ {DISCLAIMER}")
    return "\n".join(L)


# Tier 3 후보는 확정 증거가 아니므로 진정서 본문 요약에서 제외한다
_EXCLUDE_FROM_COMPLAINT = {"subtle_count", "public_exposure", "toxic_mean", "regularity"}

# 단위가 다른 지표를 한 줄로 세우기 위한 정규화 기준
_UNIT_SCALE = {"%": 1.0, "회/주": 0.25, "분": 0.01, "": 0.5}


def _top_metrics(block, n: int = 3):
    """단위가 섞인 지표들 중 '강한 신호' 순으로 상위 n개를 고른다.

    값 크기를 그대로 비교하면 '9건'이 '90.6%'(0.906)보다 커져 순서가 뒤집힌다.
    단위별 스케일을 적용해 비교 가능한 축으로 맞춘다.
    """
    cand = [
        m
        for m in block.metrics
        if m.value > 0 and m.key not in _EXCLUDE_FROM_COMPLAINT
    ]
    return sorted(
        cand, key=lambda m: -(m.value * _UNIT_SCALE.get(m.unit, 0.3))
    )[:n]


def _summary_paragraph(c: CaseSummary) -> str:
    s = c.requirement_scores
    parts = []

    strong = [b for b in c.blocks if b.score >= 0.6]
    weak = [b for b in c.blocks if b.score < 0.35]

    parts.append(
        f"관찰 기간 {c.span_days}일 동안 총 {c.n_messages:,}건의 메시지를 분석한 결과, "
        f"종합 위험도는 **{c.risk_score:.2f}({c.risk_label})** 으로 산출되었습니다."
    )

    if c.all_requirements_met:
        parts.append(
            "근로기준법 제76조의2의 3대 성립요건 모두에서 최소 기준 이상의 지표가 관측되었습니다"
            f"(우위성 {s['R1']:.2f} · 적정범위 초과 {s['R2']:.2f} · 고통·환경악화 {s['R3']:.2f})."
        )
    elif weak:
        names = ", ".join(f"{b.code}({b.title})" for b in weak)
        parts.append(
            f"다만 {names} 요건에서는 유의미한 지표가 관측되지 않아, "
            "현재 자료만으로는 3요건 동시 충족을 뒷받침하기 어렵습니다."
        )

    if strong:
        top = max(strong, key=lambda b: b.score)
        tops = _top_metrics(top, 1)
        if tops:
            parts.append(
                f"가장 강한 신호는 {top.title} 영역의 '{tops[0].label} {tops[0].display}' 입니다."
            )

    if c.law_flags:
        parts.append(
            f"아울러 {', '.join(c.law_flags.keys())} 등 "
            f"{len(c.law_flags)}건의 별건 법위반 단서가 함께 관측되었습니다."
        )

    if c.needs_human_review:
        parts.append(f"⚠️ {c.review_reason}")

    return " ".join(parts)


# ================================================================ 진정서 초안


def complaint_draft(
    case: CaseSummary,
    complainant: str = "(성명)",
    workplace: str = "(사업장명)",
    office: str = "(관할 지방고용노동청)",
) -> str:
    """피해 근로자용 진정서 초안 (Markdown)."""
    c = case
    L: list[str] = []

    L.append("# 진 정 서")
    L.append("")
    L.append("## 1. 당사자")
    L.append("")
    L.append("| 구분 | 내용 |")
    L.append("|------|------|")
    L.append(f"| 진정인 | {complainant} |")
    L.append(f"| 피진정인 | {c.actor} |")
    L.append(f"| 사업장 | {workplace} |")
    L.append(f"| 접수 관서 | {office} |")
    L.append("")

    L.append("## 2. 진정 취지")
    L.append("")
    L.append(
        f"진정인은 {_fmt_d(c.period_start)}부터 {_fmt_d(c.period_end)}까지 "
        f"피진정인으로부터 근로기준법 제76조의2에서 정한 직장 내 괴롭힘에 해당하는 "
        f"행위를 반복적으로 받았기에, 이에 대한 조사와 시정 조치를 요청드립니다."
    )
    L.append("")

    L.append("## 3. 진정 이유")
    L.append("")
    L.append(
        f"진정인은 위 기간 중 피진정인과 메신저를 통해 총 {c.n_messages:,}건의 대화를 "
        f"주고받았으며, 해당 기록을 분석한 결과 다음과 같은 사실이 확인됩니다."
    )
    L.append("")

    for b in c.blocks:
        L.append(f"### {b.code}. {b.title}")
        L.append("")
        for m in _top_metrics(b, 3):
            L.append(f"- {m.label}: **{m.display}**" + (f" — {m.note}" if m.note else ""))
        L.append("")

    L.append("### 구체적 사실관계")
    L.append("")
    if not c.key_evidence:
        L.append("_(대화 기록에서 임계치를 초과하는 발화가 확인되지 않았습니다.)_")
    else:
        for i, e in enumerate(c.key_evidence[:8], 1):
            L.append(f"{i}. **{_fmt_dt(e['ts'])}** — {e['speaker']}")
            L.append(f"   > {e['text']}")
            L.append(f"   ({', '.join(e['reasons'])})")
            L.append("")

    if c.law_flags:
        L.append("### 그 밖에 확인이 필요한 사항")
        L.append("")
        for name, law in c.law_flags.items():
            L.append(f"- {name} — {law} 위반 여부 확인 요청")
        L.append("")

    L.append("## 4. 요청 사항")
    L.append("")
    L.append("1. 위 사실관계에 대한 조사")
    L.append("2. 근로기준법 제76조의3에 따른 사용자의 조사·조치 의무 이행 여부 확인")
    L.append("3. 조사 기간 중 진정인에 대한 보호조치(근무장소 변경 등) 검토")
    L.append("4. 진정 제기를 이유로 한 불이익 처우 방지(근로기준법 제76조의3 제6항)")
    L.append("")

    L.append("## 5. 첨부 자료")
    L.append("")
    L.append("1. 메신저 대화 기록 원본 (.txt)")
    L.append(f"2. 정량 분석 보고서 (사건번호 {c.case_id})")
    L.append("3. (해당 시) 진료 기록, 근무일지, 동료 진술서 등")
    L.append("")

    L.append("## 6. 보완하면 좋을 자료")
    L.append("")
    for tip in _evidence_tips(c):
        L.append(f"- {tip}")
    L.append("")

    L.append(f"{datetime.now().strftime('%Y년 %m월 %d일')}")
    L.append("")
    L.append(f"진정인 {complainant} (서명 또는 날인)")
    L.append("")
    L.append("---")
    L.append("")
    L.append(f"> ⚖️ {DISCLAIMER} 본 초안은 제출 전 노무사·변호사의 검토를 권고합니다.")
    return "\n".join(L)


def _evidence_tips(c: CaseSummary) -> list[str]:
    """관측된 지표를 근거로 '무엇을 더 모으면 좋은지' 안내한다."""
    tips: list[str] = []
    s = c.requirement_scores

    if s.get("R1", 0) < 0.4:
        tips.append(
            "지위·관계의 우위를 뒷받침할 조직도, 직급 확인 자료, 업무 지시 계통 자료"
        )
    if s.get("R2", 0) >= 0.4:
        tips.append(
            "근무시간 외 지시가 실제 업무 수행으로 이어졌음을 보여줄 근태 기록·출퇴근 기록"
        )
    if s.get("R3", 0) >= 0.4:
        tips.append(
            "정신적 고통을 입증할 진료 기록, 상담 기록, 휴직·병가 신청서"
        )
    if c.n_speakers >= 3:
        tips.append("같은 대화방에 있던 동료의 진술서 또는 확인서")
    if c.law_flags:
        tips.append("임금명세서, 근로계약서, 연장근로 동의서 등 근로조건 관련 서류")

    tips.append("대화 기록은 발췌본이 아닌 원본 전체를 함께 보관·제출")
    return tips


# ================================================================ LLM 보강 (선택)


LLM_SYSTEM_PROMPT = """당신은 노동 사건 문서를 정리하는 보조자입니다.

절대 규칙:
1. 주어진 [지표]와 [인용]에 없는 사실, 숫자, 법령, 판례를 새로 만들지 마십시오.
2. 숫자는 주어진 값을 그대로 사용하고 반올림하거나 바꾸지 마십시오.
3. 괴롭힘이 성립한다/성립하지 않는다고 단정하지 마십시오. 관측된 사실만 서술합니다.
4. 법적 조언을 하지 마십시오. 최종 판단은 근로감독관·노무사·변호사의 몫입니다.
5. 확신할 수 없는 부분은 '해당 자료만으로는 확인되지 않음'이라고 쓰십시오.

당신의 역할은 주어진 재료를 읽기 쉬운 문장으로 다듬는 것뿐입니다."""


def polish_with_llm(
    text: str,
    case: CaseSummary,
    client=None,
    model: str = "claude-sonnet-4-5",
) -> tuple[str, bool]:
    """LLM으로 문장을 다듬는다. 실패하면 원문을 그대로 반환한다.

    반환: (문서, LLM 사용 여부)
    """
    if client is None:
        return text, False
    try:
        msg = client.messages.create(
            model=model,
            max_tokens=4000,
            system=LLM_SYSTEM_PROMPT,
            messages=[
                {
                    "role": "user",
                    "content": (
                        "아래 보고서의 서술 문장만 자연스럽게 다듬어 주세요. "
                        "표·숫자·인용문은 그대로 두십시오.\n\n" + text
                    ),
                }
            ],
        )
        return msg.content[0].text, True
    except Exception:
        return text, False
