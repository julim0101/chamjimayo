"""
참지마요 — 한국어 조사 처리

리포트는 화자 이름을 문장에 그대로 끼워 넣기 때문에
받침 유무에 따라 조사를 바꾸지 않으면 "박수선 선생님가" 같은 문장이 나온다.
공문서 성격의 산출물에서 이런 오류는 신뢰도를 깎는다.
"""

from __future__ import annotations

import re

_HANGUL_START = 0xAC00
_HANGUL_END = 0xD7A3

# 받침으로 읽히는 숫자·영문 끝소리
_DIGIT_JONG = {"0": True, "1": True, "3": True, "6": True, "7": True, "8": True,
               "2": False, "4": False, "5": False, "9": False}
_ALPHA_JONG = set("lmnr")  # L, M, N, R 로 끝나면 받침으로 읽힘

_TRAILING = re.compile(r"[)\]\}」』】>\s]+$")

JOSA_PAIRS = {
    "이": ("이", "가"),
    "가": ("이", "가"),
    "은": ("은", "는"),
    "는": ("은", "는"),
    "을": ("을", "를"),
    "를": ("을", "를"),
    "과": ("과", "와"),
    "와": ("과", "와"),
    "으로": ("으로", "로"),
    "로": ("으로", "로"),
    "이나": ("이나", "나"),
    "나": ("이나", "나"),
    "이라": ("이라", "라"),
    "라": ("이라", "라"),
    "이란": ("이란", "란"),
    "란": ("이란", "란"),
    "이며": ("이며", "며"),
    "며": ("이며", "며"),
}


def has_jongseong(word: str) -> bool:
    """단어의 마지막 글자에 받침이 있는지 판정한다."""
    w = _TRAILING.sub("", (word or "").strip())
    if not w:
        return False
    ch = w[-1]
    code = ord(ch)

    if _HANGUL_START <= code <= _HANGUL_END:
        # 한글 음절 = 0xAC00 + (초성*21 + 중성)*28 + 종성
        return (code - _HANGUL_START) % 28 != 0
    if ch.isdigit():
        return _DIGIT_JONG.get(ch, False)
    if ch.isalpha():
        return ch.lower() in _ALPHA_JONG
    return False


def josa(word: str, particle: str) -> str:
    """단어에 맞는 조사를 붙여 반환한다.

        josa("박수선 선생님", "이")  -> "박수선 선생님이"
        josa("이지은", "이")        -> "이지은이"
        josa("대표", "이")          -> "대표가"
    """
    pair = JOSA_PAIRS.get(particle)
    if pair is None:
        return f"{word}{particle}"
    return f"{word}{pair[0] if has_jongseong(word) else pair[1]}"


def J(word: str, particle: str) -> str:
    """josa()의 짧은 별칭 — 템플릿 문자열에서 쓰기 편하도록."""
    return josa(word, particle)
