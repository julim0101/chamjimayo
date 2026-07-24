"""
참지마요 — 카카오톡 대화 내보내기(.txt) 파서

PC판 / 모바일판 두 가지 내보내기 포맷을 모두 인식하여
(speaker, timestamp, text) 구조로 정규화한다.

PC판   : [이름] [오전 7:41] 메시지
         --------------- 2025년 5월 12일 월요일 ---------------
모바일 : 2025년 5월 12일 오전 7:41, 이름 : 메시지
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime, date, time
from typing import Optional

import pandas as pd

# ---------------------------------------------------------------- 정규식

# --------------- 2025년 5월 12일 월요일 ---------------
RE_DATE_DIVIDER = re.compile(
    r"^-{3,}\s*(\d{4})년\s*(\d{1,2})월\s*(\d{1,2})일\s*[월화수목금토일]요일\s*-{3,}\s*$"
)

# [박수선 선생님] [오전 7:41] 메시지
RE_PC_LINE = re.compile(
    r"^\[(?P<speaker>[^\]]{1,40})\]\s*\[(?P<ampm>오전|오후)\s*(?P<h>\d{1,2}):(?P<m>\d{2})\]\s*(?P<text>.*)$"
)

# 2025년 5월 12일 오전 7:41, 박수선 : 메시지
RE_MOBILE_LINE = re.compile(
    r"^(?P<y>\d{4})년\s*(?P<mo>\d{1,2})월\s*(?P<d>\d{1,2})일\s*"
    r"(?P<ampm>오전|오후)\s*(?P<h>\d{1,2}):(?P<m>\d{2}),\s*"
    r"(?P<speaker>.{1,40}?)\s*:\s*(?P<text>.*)$"
)

# 저장한 날짜 : 2025-06-30 22:14:03
RE_SAVED_AT = re.compile(r"^저장한\s*날짜\s*:\s*(\d{4})-(\d{2})-(\d{2})")

# "3병동 프리셉터방" 님과 카카오톡 대화
RE_ROOM = re.compile(r'^"?(?P<room>.+?)"?\s*(님과의?)?\s*카카오톡\s*대화\s*$')

# 시스템 메시지 (분석 대상에서 제외)
SYSTEM_PATTERNS = (
    "님이 들어왔습니다",
    "님이 나갔습니다",
    "님을 초대했습니다",
    "채팅방 관리자가",
    "저장한 메시지",
    "운영정책을 위반한",
)

# 첨부/비텍스트 메시지
ATTACHMENT_TOKENS = {
    "사진": "photo",
    "동영상": "video",
    "이모티콘": "emoticon",
    "삭제된 메시지입니다.": "deleted",
    "파일": "file",
    "음성메시지": "voice",
}


# ---------------------------------------------------------------- 데이터 구조


@dataclass
class ChatMeta:
    """대화방 메타 정보."""

    room: str = ""
    saved_at: Optional[date] = None
    source_format: str = ""  # "pc" | "mobile"
    total_lines: int = 0
    parsed_messages: int = 0
    speakers: list[str] = field(default_factory=list)


# ---------------------------------------------------------------- 내부 유틸


def _to_24h(ampm: str, hour: int, minute: int) -> time:
    """'오전 12:30' -> 00:30, '오후 12:30' -> 12:30 처리 포함."""
    h = hour % 12
    if ampm == "오후":
        h += 12
    return time(h, minute)


def _classify_attachment(text: str) -> Optional[str]:
    stripped = text.strip()
    for token, kind in ATTACHMENT_TOKENS.items():
        if stripped == token or stripped == f"({token})" or stripped.startswith(f"({token})"):
            return kind
    return None


def _is_system(text: str) -> bool:
    return any(p in text for p in SYSTEM_PATTERNS)


# ---------------------------------------------------------------- 파서


def parse_kakao(raw: str) -> tuple[pd.DataFrame, ChatMeta]:
    """카카오톡 내보내기 텍스트를 DataFrame + 메타로 변환한다.

    반환 DataFrame 컬럼:
        idx        int      원본 등장 순서
        speaker    str      발화자 (원문 표기)
        ts         datetime 발화 시각
        text       str      메시지 본문 (멀티라인은 \n 결합)
        kind       str      'text' | 'photo' | 'video' | 'emoticon' | 'deleted' | ...
        n_chars    int      본문 길이
    """
    lines = raw.replace("\r\n", "\n").replace("\r", "\n").split("\n")
    meta = ChatMeta(total_lines=len(lines))

    records: list[dict] = []
    cur_date: Optional[date] = None

    for line in lines[:6]:
        m = RE_SAVED_AT.match(line.strip())
        if m:
            meta.saved_at = date(int(m[1]), int(m[2]), int(m[3]))
        m = RE_ROOM.match(line.strip())
        if m:
            meta.room = m.group("room").replace("님과", "").strip()

    for line in lines:
        stripped = line.strip()

        # 1) 날짜 구분선
        m = RE_DATE_DIVIDER.match(stripped)
        if m:
            cur_date = date(int(m[1]), int(m[2]), int(m[3]))
            continue

        if not stripped:
            continue

        # 2) PC판 메시지
        m = RE_PC_LINE.match(line)
        if m and cur_date is not None:
            meta.source_format = meta.source_format or "pc"
            ts = datetime.combine(
                cur_date, _to_24h(m["ampm"], int(m["h"]), int(m["m"]))
            )
            records.append(
                {
                    "speaker": m["speaker"].strip(),
                    "ts": ts,
                    "text": m["text"].strip(),
                }
            )
            continue

        # 3) 모바일판 메시지
        m = RE_MOBILE_LINE.match(line)
        if m:
            meta.source_format = meta.source_format or "mobile"
            ts = datetime.combine(
                date(int(m["y"]), int(m["mo"]), int(m["d"])),
                _to_24h(m["ampm"], int(m["h"]), int(m["m"])),
            )
            records.append(
                {
                    "speaker": m["speaker"].strip(),
                    "ts": ts,
                    "text": m["text"].strip(),
                }
            )
            continue

        # 4) 헤더/시스템 라인은 무시, 그 외는 직전 메시지의 이어지는 줄로 결합
        if records and not _is_system(stripped) and cur_date is not None:
            if not stripped.startswith("---") and "카카오톡 대화" not in stripped:
                records[-1]["text"] += "\n" + stripped

    if not records:
        return _empty_frame(), meta

    df = pd.DataFrame(records)
    df = df[~df["text"].apply(_is_system)].reset_index(drop=True)

    df["kind"] = df["text"].apply(lambda t: _classify_attachment(t) or "text")
    df["n_chars"] = df["text"].str.len()
    df.insert(0, "idx", range(len(df)))

    df = df.sort_values("ts", kind="stable").reset_index(drop=True)
    df["idx"] = range(len(df))

    meta.parsed_messages = len(df)
    meta.speakers = df["speaker"].value_counts().index.tolist()
    return df, meta


def parse_kakao_file(path: str) -> tuple[pd.DataFrame, ChatMeta]:
    """파일 경로로 파싱. 인코딩은 utf-8 → cp949 순으로 시도."""
    for enc in ("utf-8", "utf-8-sig", "cp949"):
        try:
            with open(path, "r", encoding=enc) as f:
                return parse_kakao(f.read())
        except UnicodeDecodeError:
            continue
    raise UnicodeDecodeError(
        "kakao", b"", 0, 1, "utf-8/cp949 모두 디코딩에 실패했습니다."
    )


def _empty_frame() -> pd.DataFrame:
    return pd.DataFrame(
        columns=["idx", "speaker", "ts", "text", "kind", "n_chars"]
    ).astype({"idx": int, "n_chars": int})


# ---------------------------------------------------------------- 진단


def parse_quality(df: pd.DataFrame, meta: ChatMeta) -> dict:
    """파싱 품질 진단 — UI에서 '제대로 읽혔는지' 보여주기 위한 지표."""
    if df.empty:
        return {"ok": False, "reason": "메시지를 한 건도 인식하지 못했습니다."}

    span_days = (df["ts"].max() - df["ts"].min()).days + 1
    return {
        "ok": True,
        "room": meta.room,
        "format": meta.source_format,
        "messages": len(df),
        "speakers": len(meta.speakers),
        "period_start": df["ts"].min(),
        "period_end": df["ts"].max(),
        "span_days": span_days,
        "attachment_ratio": round(float((df["kind"] != "text").mean()), 4),
    }
