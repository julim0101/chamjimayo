"""
참지마요 — 개인정보 자동 마스킹

분석 파이프라인에 투입되기 **전에** 식별정보를 제거한다.
기획서 3-2 '개인정보 보호 설계' 및 4-2 '식별정보 자동 마스킹' 대응.

설계 원칙
  1. 화자명은 삭제하지 않고 **일관된 가명(A/B/C…)** 으로 치환한다.
     - 삭제하면 발화 독점률·관계 우위 지표를 산출할 수 없기 때문.
  2. 본문 안에 등장하는 화자 실명도 같은 가명으로 치환해 재식별을 막는다.
  3. 주민번호·연락처·계좌·이메일·주소·카드번호는 유형 태그로 치환한다.
  4. 원본 ↔ 가명 매핑(alias_map)은 메모리에만 두고, 리포트 출력 시
     사용자가 '실명 표시'를 선택한 경우에만 역치환한다.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

import pandas as pd

# ---------------------------------------------------------------- 패턴

PATTERNS: list[tuple[str, re.Pattern]] = [
    # 주민등록번호 (뒷자리 첫 숫자까지)
    ("[주민번호]", re.compile(r"\b\d{6}\s*[-–]\s*[1-4]\d{6}\b")),
    # 휴대전화 / 일반전화
    ("[연락처]", re.compile(r"\b01[0-9][-.\s]?\d{3,4}[-.\s]?\d{4}\b")),
    ("[연락처]", re.compile(r"\b0\d{1,2}[-.\s]\d{3,4}[-.\s]\d{4}\b")),
    # 이메일
    ("[이메일]", re.compile(r"\b[\w.+-]+@[\w-]+\.[\w.]{2,}\b")),
    # 계좌번호 (은행명 동반 또는 3-2-6 이상 숫자열)
    (
        "[계좌번호]",
        re.compile(
            r"(?:국민|신한|우리|하나|농협|기업|카카오뱅크|토스뱅크|새마을|우체국|SC|씨티)\s*"
            r"\d{2,6}[-\s]?\d{2,6}[-\s]?\d{2,7}"
        ),
    ),
    # 카드번호
    ("[카드번호]", re.compile(r"\b\d{4}[-\s]\d{4}[-\s]\d{4}[-\s]\d{4}\b")),
    # 주소 (시/도 + 시군구 + 동/로/길 + 번지)
    (
        "[주소]",
        re.compile(
            r"(?:서울|부산|대구|인천|광주|대전|울산|세종|경기|강원|충북|충남|전북|전남|경북|경남|제주)"
            r"[가-힣\s]{0,10}(?:시|군|구)[가-힣\d\s]{0,15}(?:동|로|길)\s*[\d-]+"
        ),
    ),
    # 사번/직원번호
    ("[사번]", re.compile(r"(?:사번|직원번호|사원번호)\s*[:：]?\s*[A-Za-z0-9-]{4,}")),
    # URL
    ("[링크]", re.compile(r"https?://\S+")),
]

# 화자명에서 직함을 떼어내기 위한 접미사
TITLE_SUFFIXES = (
    "선생님", "팀장님", "과장님", "부장님", "차장님", "대리님", "주임님",
    "사장님", "이사님", "실장님", "본부장님", "센터장님", "원장님",
    "팀장", "과장", "부장", "차장", "대리", "주임", "사장", "이사",
    "실장", "본부장", "센터장", "원장", "쌤", "님", "씨",
)

ALIAS_LETTERS = [chr(ord("A") + i) for i in range(26)]


# ---------------------------------------------------------------- 결과 구조


@dataclass
class MaskResult:
    df: pd.DataFrame
    alias_map: dict[str, str] = field(default_factory=dict)  # 실명 -> 가명
    reverse_map: dict[str, str] = field(default_factory=dict)  # 가명 -> 실명
    counts: dict[str, int] = field(default_factory=dict)  # 유형별 마스킹 건수

    @property
    def total_masked(self) -> int:
        return sum(self.counts.values())


# ---------------------------------------------------------------- 이름 처리


def _strip_title(name: str) -> str:
    """'박수선 선생님' -> '박수선', '조현석 과장' -> '조현석'"""
    n = name.strip()
    for suf in sorted(TITLE_SUFFIXES, key=len, reverse=True):
        if n.endswith(suf) and len(n) > len(suf):
            n = n[: -len(suf)].strip()
            break
    return n


def _name_variants(name: str) -> list[str]:
    """본문에서 잡아낼 실명 변형들을 생성한다.

    '박수선 선생님' → ['박수선 선생님', '박수선', '수선']
    (성을 뗀 이름 2글자는 오탐 위험이 있어 3글자 이상 성명에서만 추출)
    """
    variants = {name.strip()}
    base = _strip_title(name)
    if base:
        variants.add(base)
        if len(base) >= 3:
            variants.add(base[1:])  # 성 제외
        for suf in ("쌤", "씨", "님"):
            variants.add(base + suf)
    return sorted((v for v in variants if len(v) >= 2), key=len, reverse=True)


def build_alias_map(speakers: list[str]) -> tuple[dict[str, str], dict[str, str]]:
    """등장 순서대로 화자 A, 화자 B … 가명을 부여한다."""
    alias_map, reverse_map = {}, {}
    for i, sp in enumerate(speakers):
        letter = ALIAS_LETTERS[i] if i < len(ALIAS_LETTERS) else f"Z{i}"
        alias = f"화자 {letter}"
        alias_map[sp] = alias
        reverse_map[alias] = sp
    return alias_map, reverse_map


# ---------------------------------------------------------------- 메인


def mask_dataframe(
    df: pd.DataFrame,
    mask_names: bool = True,
    speaker_order: list[str] | None = None,
) -> MaskResult:
    """파싱된 대화 DataFrame에 마스킹을 적용한다.

    Args:
        df: parser.parse_kakao 결과
        mask_names: 화자 실명을 가명으로 치환할지 여부
        speaker_order: 가명 부여 순서 지정 (기본: 발화량 내림차순)
    """
    if df.empty:
        return MaskResult(df=df.copy())

    out = df.copy()
    counts: dict[str, int] = {}

    speakers = speaker_order or out["speaker"].value_counts().index.tolist()
    alias_map, reverse_map = build_alias_map(speakers)

    # 1) 본문 내 실명 → 가명
    if mask_names:
        variant_pairs: list[tuple[re.Pattern, str]] = []
        for real, alias in alias_map.items():
            for v in _name_variants(real):
                variant_pairs.append((re.compile(re.escape(v)), alias))
        # 긴 변형부터 치환해야 부분 치환 오류가 없다
        variant_pairs.sort(key=lambda p: len(p[0].pattern), reverse=True)

        def _sub_names(t: str) -> str:
            nonlocal counts
            for pat, alias in variant_pairs:
                t, n = pat.subn(alias, t)
                if n:
                    counts["실명"] = counts.get("실명", 0) + n
            return t

        out["text"] = out["text"].apply(_sub_names)

    # 발화자 컬럼 자체를 가명으로 교체한다.
    # 본문만 마스킹하고 speaker 컬럼을 실명으로 두면, 지표 연산·리포트·대시보드에
    # 실명이 그대로 흘러가 마스킹의 의미가 없어진다.
    # 원본은 speaker_real 에만 남기고, 이 컬럼은 분석 파이프라인에서 사용하지 않는다.
    out["speaker_real"] = out["speaker"]
    if mask_names:
        out["speaker"] = out["speaker"].map(alias_map).fillna(out["speaker"])
        counts["발화자명"] = counts.get("발화자명", 0) + len(out)
    out["speaker_masked"] = out["speaker"]

    # 2) 정형 식별정보 → 유형 태그
    def _sub_patterns(t: str) -> str:
        nonlocal counts
        for tag, pat in PATTERNS:
            t, n = pat.subn(tag, t)
            if n:
                key = tag.strip("[]")
                counts[key] = counts.get(key, 0) + n
        return t

    out["text"] = out["text"].apply(_sub_patterns)
    out["n_chars"] = out["text"].str.len()

    return MaskResult(
        df=out,
        alias_map=alias_map,
        reverse_map=reverse_map,
        counts=counts,
    )


def unmask_text(text: str, reverse_map: dict[str, str]) -> str:
    """리포트에서 '실명 표시'를 선택했을 때 가명을 되돌린다."""
    for alias, real in sorted(reverse_map.items(), key=lambda x: -len(x[0])):
        text = text.replace(alias, real)
    return text
