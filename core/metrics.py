"""
참지마요 — Tier 1 정량 지표 엔진

근로기준법 제76조의2 직장 내 괴롭힘 성립 3요건을
반박 불가능한 수학적 연산으로 환산한다.

  요건① 지위·관계의 우위        → 발화 독점률, 지시 비대칭, 연속 발화, 사과 비대칭
  요건② 업무상 적정범위 초과    → 시간외 지시, 심야·휴일 연락, 주기성, 반복 지시
  요건③ 신체적·정신적 고통      → (구조 신호) 공개 질책, 대상자 응답 부담
                                   ※ 어휘 독성 밀도는 Tier 2(toxicity.py)에서 결합

모든 지표는 원문 메시지 인덱스를 함께 남겨, 대시보드에서
"이 숫자는 이 발화들에서 나왔다"를 즉시 역추적할 수 있게 한다.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import time
from typing import Optional

import numpy as np
import pandas as pd

from . import lexicon
from .korean import josa

# ---------------------------------------------------------------- 설정


@dataclass
class WorkHours:
    """근무시간 정의. 사업장 특성에 맞게 UI에서 조정 가능."""

    start: time = time(9, 0)
    end: time = time(18, 0)
    workdays: tuple[int, ...] = (0, 1, 2, 3, 4)  # Mon=0 … Sun=6
    night_start: time = time(22, 0)
    night_end: time = time(6, 0)
    # 교대제 사업장(간호사 등)은 야간이 정상 근무일 수 있음
    shift_work: bool = False


# ---------------------------------------------------------------- 주석 달기


def annotate(df: pd.DataFrame, wh: Optional[WorkHours] = None) -> pd.DataFrame:
    """메시지 단위 플래그를 부착한다. 모든 지표 연산의 기반."""
    wh = wh or WorkHours()
    out = df.copy()
    if out.empty:
        return out

    ts = out["ts"]
    t = ts.dt.time
    dow = ts.dt.dayofweek

    out["date"] = ts.dt.date
    out["hour"] = ts.dt.hour
    out["dow"] = dow

    out["is_workday"] = dow.isin(wh.workdays)
    in_hours = (t >= wh.start) & (t <= wh.end)
    out["is_offhours"] = ~(out["is_workday"] & in_hours)
    out["is_holiday"] = ~out["is_workday"]
    out["is_night"] = (t >= wh.night_start) | (t <= wh.night_end)
    if wh.shift_work:
        # 교대제에서는 심야 자체가 아니라 '휴무일 심야'만 이례로 본다
        out["is_night"] = out["is_night"] & out["is_holiday"]

    txt = out["text"].fillna("")
    out["is_directive"] = txt.apply(lexicon.is_directive)
    out["is_rebuke_q"] = txt.apply(lexicon.is_rebuke_question)
    out["is_apology"] = txt.apply(lexicon.is_apology)
    out["lex_toxicity"] = txt.apply(lexicon.lexicon_toxicity)
    out["toxic_terms"] = txt.apply(lambda s: [w for _, w in lexicon.toxic_hits(s)])
    out["subtle_tags"] = txt.apply(lexicon.subtle_hits)
    out["law_flags"] = txt.apply(lexicon.labor_violation_hits)

    # 연속 발화 블록 (동일 화자가 끊기지 않고 이어서 말한 묶음)
    block = (out["speaker"] != out["speaker"].shift()).cumsum()
    out["burst_id"] = block
    out["burst_size"] = block.map(block.value_counts())

    # 직전 메시지로부터의 경과 시간(분) — 응답 지연 산출용
    out["gap_min"] = ts.diff().dt.total_seconds().div(60).fillna(0)

    return out


# ---------------------------------------------------------------- 역할 추정


def infer_roles(adf: pd.DataFrame) -> tuple[str, str, pd.DataFrame]:
    """가해 의심자(actor)와 피해 의심 대상자(subject)를 추정한다.

    구조 신호만 사용한다 (내용 판단은 Tier 2/3 몫):
      actor  ← 발화 비중 · 지시 비율 · 시간외 발화 · 독성 밀도가 높은 화자
      subject← 사과 비율이 높고 지시를 받는 화자

    반환: (actor, subject, 화자별 프로필 DataFrame)
    """
    if adf.empty:
        return "", "", pd.DataFrame()

    g = adf.groupby("speaker")
    prof = pd.DataFrame(
        {
            "msgs": g.size(),
            "chars": g["n_chars"].sum(),
            "directive_ratio": g["is_directive"].mean(),
            "rebuke_ratio": g["is_rebuke_q"].mean(),
            "apology_ratio": g["is_apology"].mean(),
            "offhours_ratio": g["is_offhours"].mean(),
            "toxicity": g["lex_toxicity"].mean(),
        }
    )
    prof["msg_share"] = prof["msgs"] / prof["msgs"].sum()

    prof["actor_score"] = (
        prof["msg_share"] * 1.0
        + prof["directive_ratio"] * 1.2
        + prof["rebuke_ratio"] * 0.8
        + prof["toxicity"] * 1.5
        + prof["offhours_ratio"] * 0.5
        - prof["apology_ratio"] * 1.0
    )
    prof["subject_score"] = (
        prof["apology_ratio"] * 1.5
        - prof["directive_ratio"] * 1.0
        - prof["toxicity"] * 1.0
        + (1 - prof["msg_share"]) * 0.3
    )

    actor = prof["actor_score"].idxmax()
    subject = prof.drop(index=actor)["subject_score"].idxmax() if len(prof) > 1 else ""
    return actor, subject, prof.sort_values("actor_score", ascending=False)


# ---------------------------------------------------------------- 지표 결과


@dataclass
class Metric:
    key: str
    label: str
    value: float
    unit: str = ""
    evidence_idx: list[int] = field(default_factory=list)
    note: str = ""

    @property
    def display(self) -> str:
        if self.unit == "%":
            return f"{self.value * 100:.1f}%"
        if self.unit == "회" or self.unit == "일" or self.unit == "건":
            return f"{self.value:.0f}{self.unit}"
        return f"{self.value:.2f}{self.unit}"


@dataclass
class RequirementBlock:
    code: str  # "R1" | "R2" | "R3"
    title: str
    legal_basis: str
    metrics: list[Metric] = field(default_factory=list)
    score: float = 0.0  # 0.0 ~ 1.0


# ---------------------------------------------------------------- 지표 연산


def _norm(x: float, lo: float, hi: float) -> float:
    """구간 정규화 후 0~1 클리핑."""
    if hi <= lo:
        return 0.0
    return float(np.clip((x - lo) / (hi - lo), 0.0, 1.0))


def selective_response(
    adf: pd.DataFrame, actor: str, subject: str, window_min: int = 120
) -> dict:
    """단체 대화방에서의 '선택적 무응답' 정량화.

    교묘한 따돌림은 폭언이 없어 어휘 지표로는 잡히지 않는다.
    그러나 "누구의 말에는 답하고 누구의 말은 흘리는가"는 순수한 구조 통계이며,
    반박이 어려운 Tier 1 지표가 된다.

    각 참여자 발화에 대해 window_min 이내에 actor의 응답이 이어졌는지를 세고,
    대상자의 응답률과 나머지 참여자 평균 응답률의 격차를 반환한다.
    """
    n_speakers = adf["speaker"].nunique()
    if n_speakers < 3 or not subject:
        return {"applicable": False}

    rates: dict[str, dict] = {}
    ts = adf["ts"].tolist()
    sp = adf["speaker"].tolist()
    idxs = adf["idx"].tolist()

    for i, (s, t) in enumerate(zip(sp, ts)):
        if s == actor:
            continue
        answered = False
        for j in range(i + 1, len(sp)):
            if (ts[j] - t).total_seconds() > window_min * 60:
                break
            if sp[j] == actor:
                answered = True
                break
            if sp[j] != s:  # 다른 참여자가 먼저 끼어들면 그 시점까지만 본다
                continue
        r = rates.setdefault(s, {"total": 0, "answered": 0, "ignored_idx": []})
        r["total"] += 1
        if answered:
            r["answered"] += 1
        else:
            r["ignored_idx"].append(idxs[i])

    for s, r in rates.items():
        r["rate"] = r["answered"] / r["total"] if r["total"] else 0.0

    subj = rates.get(subject)
    if not subj or subj["total"] < 3:
        return {"applicable": False}

    others = [r["rate"] for s, r in rates.items() if s != subject and r["total"] >= 3]
    peer_rate = float(np.mean(others)) if others else 0.0

    return {
        "applicable": True,
        "subject_rate": subj["rate"],
        "peer_rate": peer_rate,
        "gap": max(0.0, peer_rate - subj["rate"]),
        "ignored_idx": subj["ignored_idx"],
        "per_speaker": rates,
    }


def requirement_1(adf: pd.DataFrame, actor: str, subject: str) -> RequirementBlock:
    """요건① 지위·관계의 우위 — 대화 구조의 비대칭성으로 측정."""
    A = adf[adf["speaker"] == actor]
    S = adf[adf["speaker"] == subject] if subject else adf.iloc[0:0]
    total = len(adf)

    ms = len(A) / total if total else 0.0
    cs = A["n_chars"].sum() / adf["n_chars"].sum() if adf["n_chars"].sum() else 0.0

    a_dir = A["is_directive"].mean() if len(A) else 0.0
    s_dir = S["is_directive"].mean() if len(S) else 0.0
    dir_gap = max(0.0, a_dir - s_dir)

    a_apo = A["is_apology"].mean() if len(A) else 0.0
    s_apo = S["is_apology"].mean() if len(S) else 0.0
    apo_gap = max(0.0, s_apo - a_apo)

    burst = A[A["burst_size"] >= 3]
    burst_ratio = len(burst) / len(A) if len(A) else 0.0

    # 응답 지연 비대칭: 대상자가 훨씬 빨리 답한다 = 응답 압박
    s_reply = S[S["gap_min"].between(0, 240)]["gap_min"].median() if len(S) else np.nan
    a_reply = A[A["gap_min"].between(0, 240)]["gap_min"].median() if len(A) else np.nan
    latency_gap = float(a_reply - s_reply) if not (np.isnan(s_reply) or np.isnan(a_reply)) else 0.0

    metrics = [
        Metric("speech_share", "발화 독점률 (건수)", ms, "%",
               A["idx"].tolist(),
               f"전체 {total}건 중 {len(A)}건을 {josa(actor, '이')} 발화"),
        Metric("char_share", "발화 독점률 (분량)", cs, "%", [],
               "글자 수 기준 점유율"),
        Metric("directive_gap", "지시 발화 비대칭", dir_gap, "%",
               A[A["is_directive"]]["idx"].tolist(),
               f"{actor} {a_dir*100:.0f}% vs 상대 {s_dir*100:.0f}%"),
        Metric("apology_gap", "사과·수용 표현 비대칭", apo_gap, "%",
               S[S["is_apology"]]["idx"].tolist() if len(S) else [],
               f"대상자 {s_apo*100:.0f}% vs {actor} {a_apo*100:.0f}%"),
        Metric("burst_ratio", "일방적 연속 발화 비율", burst_ratio, "%",
               burst["idx"].tolist(),
               "상대 응답 없이 3회 이상 연속 발화"),
        Metric("latency_gap", "응답 지연 격차", latency_gap, "분", [],
               "대상자가 더 빨리 응답할수록 응답 압박이 크다"),
    ]

    score = float(
        np.average(
            [
                _norm(ms, 0.5, 0.85),
                _norm(dir_gap, 0.05, 0.4),
                _norm(apo_gap, 0.05, 0.35),
                _norm(burst_ratio, 0.1, 0.5),
                _norm(latency_gap, 0, 60),
            ],
            weights=[0.3, 0.25, 0.2, 0.15, 0.1],
        )
    )
    return RequirementBlock(
        "R1", "지위 또는 관계의 우위",
        "근로기준법 제76조의2 — 「직장에서의 지위 또는 관계 등의 우위를 이용하여」",
        metrics, score,
    )


def requirement_2(adf: pd.DataFrame, actor: str) -> RequirementBlock:
    """요건② 업무상 적정범위 초과 — 시간·주기 구조로 측정.

    건수 지표는 모두 **주당 발생률**로 정규화한다.
    대화량이나 관찰 기간에 따라 값이 흔들리면 사건 간 비교가 불가능하기 때문이다.
    """
    A = adf[adf["speaker"] == actor]
    span_days = max(1, (adf["ts"].max() - adf["ts"].min()).days + 1)
    weeks = max(1.0, span_days / 7)

    off = A[A["is_offhours"]]
    # 고용노동부 매뉴얼: "반복적 업무 지시 또는 즉각적인 응답 요구"
    # → 명령형뿐 아니라 응답을 압박하는 추궁도 시간외 요구에 포함한다.
    off_demand = off[off["is_directive"] | off["is_rebuke_q"]]
    night = A[A["is_night"]]
    holi = A[A["is_holiday"]]

    off_ratio = len(off) / len(A) if len(A) else 0.0
    off_days = off["date"].nunique()
    periodicity = off_days / span_days  # 시간외 연락 발생일 / 관찰 기간

    # 반복성: 시간외 연락 발생일 간 간격의 규칙성 (변동계수의 역수)
    if off_days >= 3:
        ds = pd.to_datetime(pd.Series(sorted(off["date"].unique())))
        gaps = ds.diff().dt.days.dropna()
        cv = gaps.std() / gaps.mean() if gaps.mean() else 0.0
        regularity = float(np.clip(1 - cv, 0, 1))
    else:
        regularity = 0.0

    r_demand, r_night, r_holi = len(off_demand) / weeks, len(night) / weeks, len(holi) / weeks

    metrics = [
        Metric("offhours_ratio", "근무시간 외 발화 비율", off_ratio, "%",
               off["idx"].tolist(),
               f"{actor}의 발화 {len(A)}건 중 {len(off)}건이 근무시간 외"),
        Metric("offhours_demand_rate", "주당 시간외 지시·응답요구", r_demand, "회/주",
               off_demand["idx"].tolist(),
               f"관찰 {span_days}일간 총 {len(off_demand)}건"),
        Metric("night_rate", "주당 심야(22–06시) 연락", r_night, "회/주",
               night["idx"].tolist(), f"총 {len(night)}건"),
        Metric("holiday_rate", "주당 휴일 연락", r_holi, "회/주",
               holi["idx"].tolist(), f"총 {len(holi)}건"),
        Metric("periodicity", "시간외 연락 발생일 비율", periodicity, "%", [],
               f"관찰 {span_days}일 중 {off_days}일에 발생"),
        Metric("regularity", "반복 주기의 규칙성", regularity, "", [],
               "간격의 변동이 작을수록 일회성이 아닌 지속적 패턴"),
    ]

    score = float(
        np.average(
            [
                _norm(off_ratio, 0.10, 0.55),
                _norm(r_demand, 0.3, 4.0),
                _norm(r_night, 0.2, 3.0),
                _norm(r_holi, 0.2, 2.5),
                _norm(periodicity, 0.05, 0.40),
                _norm(regularity, 0.20, 0.80),
            ],
            weights=[0.25, 0.25, 0.15, 0.12, 0.13, 0.10],
        )
    )
    return RequirementBlock(
        "R2", "업무상 적정범위를 넘는 행위",
        "근로기준법 제76조의2 — 「업무상 적정범위를 넘어」",
        metrics, score,
    )


def requirement_3(
    adf: pd.DataFrame,
    actor: str,
    subject: str,
    tox_col: str = "lex_toxicity",
    sel: dict | None = None,
) -> RequirementBlock:
    """요건③ 신체적·정신적 고통 / 근무환경 악화.

    Tier 2 모델 점수가 있으면 tox_col 로 넘겨받아 사용하고,
    없으면 어휘 기반 폴백 점수를 쓴다.
    """
    A = adf[adf["speaker"] == actor]
    toxic = A[A[tox_col] >= 0.5]
    density = len(toxic) / len(A) if len(A) else 0.0
    mean_tox = float(A[tox_col].mean()) if len(A) else 0.0

    span_days = max(1, (adf["ts"].max() - adf["ts"].min()).days + 1)
    weeks = max(1.0, span_days / 7)
    rebuke = A[A["is_rebuke_q"]]
    r_rebuke = len(rebuke) / weeks
    n_speakers = adf["speaker"].nunique()
    public = n_speakers >= 3  # 제3자가 있는 단체 대화방에서의 질책

    # 대상자의 사과 발화 중 심야/시간외 비율 = 시간외 응답 부담
    S = adf[adf["speaker"] == subject] if subject else adf.iloc[0:0]
    s_off = S[S["is_offhours"]]
    burden = len(s_off) / len(S) if len(S) else 0.0

    subtle = A[A["subtle_tags"].apply(len) > 0]

    metrics = [
        Metric("toxic_density", "모욕·독성 발화 밀도", density, "%",
               toxic["idx"].tolist(),
               f"{actor}의 발화 {len(A)}건 중 {len(toxic)}건이 독성 임계치 초과"),
        Metric("toxic_mean", "평균 독성 확률", mean_tox, "", [],
               "0에 가까울수록 중립, 1에 가까울수록 공격적"),
        Metric("rebuke_rate", "주당 질책성 추궁", r_rebuke, "회/주",
               rebuke["idx"].tolist(), f"총 {len(rebuke)}건"),
        Metric("public_exposure", "제3자 노출 여부", 1.0 if public else 0.0, "", [],
               f"참여자 {n_speakers}명 — 공개적 질책은 정신적 고통을 가중"),
        Metric("subject_offhours_burden", "대상자의 시간외 응답 부담", burden, "%",
               s_off["idx"].tolist() if len(s_off) else []),
        Metric("subtle_count", "정황 후보 발화 (Tier 3)", float(len(subtle)), "건",
               subtle["idx"].tolist(),
               "배제·묵살·가스라이팅 의심 — 최종 판단은 사람"),
    ]

    parts = [
        _norm(density, 0.05, 0.45),
        _norm(mean_tox, 0.05, 0.5),
        _norm(r_rebuke, 0.3, 4.0),
        1.0 if public else 0.0,
        _norm(burden, 0.1, 0.5),
    ]
    weights = [0.35, 0.2, 0.2, 0.1, 0.15]

    # 단체 대화방 한정: 선택적 무응답(배제) 지표
    if sel and sel.get("applicable"):
        metrics.append(
            Metric(
                "selective_ignore", "선택적 무응답 격차", sel["gap"], "%",
                sel["ignored_idx"],
                f"대상자 응답률 {sel['subject_rate']*100:.0f}% vs "
                f"동료 평균 {sel['peer_rate']*100:.0f}% — 폭언 없이도 성립하는 배제 신호",
            )
        )
        parts.append(_norm(sel["gap"], 0.1, 0.5))
        weights.append(0.25)

    score = float(np.average(parts, weights=weights))
    return RequirementBlock(
        "R3", "신체적·정신적 고통 또는 근무환경 악화",
        "근로기준법 제76조의2 — 「신체적·정신적 고통을 주거나 근무환경을 악화시키는 행위」",
        metrics, score,
    )


# ---------------------------------------------------------------- 통합


def compute_all(
    adf: pd.DataFrame,
    actor: str,
    subject: str,
    tox_col: str = "lex_toxicity",
) -> list[RequirementBlock]:
    sel = selective_response(adf, actor, subject)
    return [
        requirement_1(adf, actor, subject),
        requirement_2(adf, actor),
        requirement_3(adf, actor, subject, tox_col, sel),
    ]
