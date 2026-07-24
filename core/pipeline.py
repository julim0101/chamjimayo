"""
참지마요 — End-to-End 분석 파이프라인

    카톡 .txt
      ↓ parser        구조화
      ↓ masking       개인정보 자동 마스킹  (분석 전에 반드시 수행)
      ↓ metrics       Tier 1 정량 지표
      ↓ toxicity      Tier 2 독성 분류
      ↓ scoring       3요건 결합 · 위험도 · 증거 추출
      ↓ rag           법령·판단기준 인용
    CaseSummary

이 모듈만 import 하면 전체 파이프라인을 쓸 수 있다.
UI(app.py)와 배치 처리(batch)에서 공통으로 사용한다.
"""

from __future__ import annotations

import hashlib
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import pandas as pd

from . import metrics as M
from . import toxicity as T
from .masking import MaskResult, mask_dataframe
from .parser import ChatMeta, parse_kakao, parse_quality
from .rag.retriever import LawRetriever
from .scoring import CaseSummary, attach_citations, build_case

log = logging.getLogger(__name__)


@dataclass
class AnalysisResult:
    case: CaseSummary
    adf: pd.DataFrame  # 주석 달린 전체 대화 (증거 역추적용)
    meta: ChatMeta
    quality: dict
    mask: MaskResult
    profile: pd.DataFrame  # 화자별 프로필


def _case_id(name: str, raw: str) -> str:
    h = hashlib.sha1(raw.encode("utf-8", "ignore")).hexdigest()[:6].upper()
    return f"CJ-{h}"


def analyze(
    raw: str,
    source_name: str = "업로드 파일",
    *,
    work_hours: Optional[M.WorkHours] = None,
    mask_names: bool = True,
    actor_override: Optional[str] = None,
    subject_override: Optional[str] = None,
    classifier: Optional[T.ToxicityClassifier] = None,
    retriever: Optional[LawRetriever] = None,
    tox_threshold: float = 0.5,
) -> AnalysisResult:
    """카카오톡 원문 텍스트 한 건을 끝까지 분석한다."""

    # 1. 구조화
    df, meta = parse_kakao(raw)
    quality = parse_quality(df, meta)
    if not quality.get("ok"):
        raise ValueError(
            "카카오톡 대화를 인식하지 못했습니다. "
            "카카오톡 → 채팅방 → 메뉴 → 대화 내용 내보내기(텍스트)로 저장한 .txt 파일인지 확인해 주세요."
        )

    # 2. 개인정보 마스킹 (분석 전 필수 단계)
    mask = mask_dataframe(df, mask_names=mask_names)
    work_df = mask.df

    # 3. Tier 1 주석 + 역할 추정
    adf = M.annotate(work_df, work_hours)
    auto_actor, auto_subject, profile = M.infer_roles(adf)
    actor = actor_override or auto_actor
    subject = subject_override or auto_subject
    if subject == actor:  # 수동 지정 충돌 방지
        others = [s for s in adf["speaker"].unique() if s != actor]
        subject = others[0] if others else ""

    # 4. Tier 2 독성 분류
    adf, tox_backend = T.apply_toxicity(adf, classifier, threshold=tox_threshold)

    # 5. 3요건 연산 (Tier 2 점수를 요건③에 반영)
    sel = M.selective_response(adf, actor, subject)
    blocks = [
        M.requirement_1(adf, actor, subject),
        M.requirement_2(adf, actor),
        M.requirement_3(adf, actor, subject, tox_col="tox_score", sel=sel),
    ]

    # 6. 스코어링 + 증거 추출
    case = build_case(
        case_id=_case_id(source_name, raw),
        source_name=source_name,
        room=meta.room or source_name,
        adf=adf,
        actor=actor,
        subject=subject,
        blocks=blocks,
        tox_backend=tox_backend,
        masking_counts=mask.counts,
    )

    # 7. 폐쇄형 RAG 인용
    r = retriever or LawRetriever()
    case.rag_backend = r.backend
    case = attach_citations(case, r)

    return AnalysisResult(
        case=case, adf=adf, meta=meta, quality=quality, mask=mask, profile=profile
    )


def analyze_file(path: str | Path, **kwargs) -> AnalysisResult:
    p = Path(path)
    for enc in ("utf-8", "utf-8-sig", "cp949"):
        try:
            raw = p.read_text(encoding=enc)
            break
        except UnicodeDecodeError:
            continue
    else:
        raise UnicodeDecodeError("kakao", b"", 0, 1, "인코딩을 인식하지 못했습니다.")
    kwargs.setdefault("source_name", p.name)
    return analyze(raw, **kwargs)


def analyze_many(paths: list[str | Path], **kwargs) -> list[AnalysisResult]:
    """감독관 대시보드용 다건 분석. 모델·검색기는 1회만 적재해 재사용한다."""
    clf = kwargs.pop("classifier", None) or T.get_classifier()
    ret = kwargs.pop("retriever", None) or LawRetriever()
    out: list[AnalysisResult] = []
    for p in paths:
        try:
            out.append(analyze_file(p, classifier=clf, retriever=ret, **kwargs))
        except Exception as e:
            log.error("분석 실패 %s: %s", p, e)
    return sorted(out, key=lambda r: -r.case.priority)
