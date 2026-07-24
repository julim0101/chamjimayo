"""
참지마요 — Tier 2 독성 분류

한국어 혐오·악플 분류 모델(KcELECTRA 계열)로 발화의 독성 확률을 산출한다.

설계 요점
  1. **모델 + 어휘 앙상블.** 직장 내 괴롭힘은 욕설보다 '능력 비하'가 많다.
     공개 혐오표현 모델은 욕설에는 강하지만 "일머리가 없어" 같은
     직장 맥락 비하에는 약하다. 두 탐지기는 커버리지가 서로 다르므로
     noisy-OR(합집합)로 결합한다.
  2. **폴백 필수.** transformers/torch 미설치 또는 모델 다운로드 실패 시
     어휘 점수만으로 동작한다. 데모가 죽지 않는 것이 최우선.
  3. **캐시.** 동일 문장 재계산 방지 + Streamlit 재실행 대비.

기본 모델: smilegate-ai/kor_unsmile (KcELECTRA 기반 다중 레이블 혐오표현 분류)
"""

from __future__ import annotations

import functools
import logging
from dataclasses import dataclass, field
from typing import Optional

import numpy as np
import pandas as pd

from . import lexicon

log = logging.getLogger(__name__)

# 후보 모델 (앞에서부터 로드 시도)
MODEL_CANDIDATES = [
    "smilegate-ai/kor_unsmile",
    "sgunderscore/hatescore-korean-hate-speech",
]

# kor_unsmile 레이블 중 직장 내 괴롭힘과 직결되는 것에 가중
LABEL_WEIGHTS = {
    "악플/욕설": 1.0,
    "기타 혐오": 0.8,
    "연령": 0.8,
    "성별": 0.7,
    "여성/가족": 0.7,
    "남성": 0.7,
    "인종/국적": 0.6,
    "지역": 0.6,
    "종교": 0.6,
    "성소수자": 0.6,
}


@dataclass
class ToxicityResult:
    scores: np.ndarray
    model_scores: Optional[np.ndarray] = None
    lex_scores: Optional[np.ndarray] = None
    backend: str = "lexicon"  # "model+lexicon" | "lexicon"
    model_name: str = ""
    labels: list[dict] = field(default_factory=list)


class ToxicityClassifier:
    """지연 로딩 + 자동 폴백 독성 분류기."""

    def __init__(self, model_name: Optional[str] = None, device: str = "cpu"):
        self.model_name = model_name
        self.device = device
        self._pipe = None
        self._tried = False
        self._cache: dict[str, tuple[float, list]] = {}

    # ---------------------------------------------------------- 모델 로딩

    def _load(self) -> bool:
        if self._tried:
            return self._pipe is not None
        self._tried = True
        try:
            from transformers import (  # type: ignore
                AutoModelForSequenceClassification,
                AutoTokenizer,
                TextClassificationPipeline,
            )
        except Exception as e:  # pragma: no cover
            log.warning("transformers 미설치 — 어휘 폴백으로 동작합니다. (%s)", e)
            return False

        candidates = [self.model_name] if self.model_name else MODEL_CANDIDATES
        for name in candidates:
            try:
                tok = AutoTokenizer.from_pretrained(name)
                mdl = AutoModelForSequenceClassification.from_pretrained(name)
                self._pipe = TextClassificationPipeline(
                    model=mdl,
                    tokenizer=tok,
                    device=-1 if self.device == "cpu" else 0,
                    return_all_scores=True,
                    function_to_apply="sigmoid",
                    truncation=True,
                    max_length=256,
                )
                self.model_name = name
                log.info("독성 분류 모델 로드 완료: %s", name)
                return True
            except Exception as e:  # pragma: no cover
                log.warning("모델 로드 실패 %s: %s", name, e)
        return False

    @property
    def backend(self) -> str:
        return "model+lexicon" if self._pipe is not None else "lexicon"

    # ---------------------------------------------------------- 추론

    def _model_score(self, texts: list[str]) -> tuple[np.ndarray, list[list[dict]]]:
        """모델 독성 확률과 레이블별 점수를 반환."""
        raw = self._pipe(texts, batch_size=16)  # type: ignore
        scores, labels = [], []
        for item in raw:
            best = 0.0
            for d in item:
                lab = d["label"]
                if lab in ("clean", "clean/none", "None"):
                    continue
                w = LABEL_WEIGHTS.get(lab, 0.5)
                best = max(best, float(d["score"]) * w)
            scores.append(best)
            labels.append(sorted(item, key=lambda d: -d["score"])[:3])
        return np.array(scores), labels

    def score_texts(self, texts: list[str]) -> ToxicityResult:
        """문장 리스트의 독성 점수(0~1)를 산출한다."""
        lex = np.array([lexicon.lexicon_toxicity(t) for t in texts])

        if not self._load():
            return ToxicityResult(scores=lex, lex_scores=lex, backend="lexicon")

        try:
            mdl, labels = self._model_score(texts)
        except Exception as e:  # pragma: no cover
            log.warning("모델 추론 실패 — 어휘 폴백. (%s)", e)
            return ToxicityResult(scores=lex, lex_scores=lex, backend="lexicon")

        # noisy-OR: 두 탐지기의 커버리지가 다르므로 합집합으로 결합
        combined = 1 - (1 - mdl) * (1 - lex)
        return ToxicityResult(
            scores=combined,
            model_scores=mdl,
            lex_scores=lex,
            backend="model+lexicon",
            model_name=self.model_name or "",
            labels=labels,
        )


# ---------------------------------------------------------------- 편의 함수


@functools.lru_cache(maxsize=1)
def get_classifier(model_name: Optional[str] = None) -> ToxicityClassifier:
    """프로세스당 1회만 모델을 적재한다."""
    return ToxicityClassifier(model_name)


def apply_toxicity(
    adf: pd.DataFrame,
    classifier: Optional[ToxicityClassifier] = None,
    threshold: float = 0.5,
) -> tuple[pd.DataFrame, str]:
    """annotate() 결과에 Tier 2 독성 점수를 부착한다.

    추가 컬럼:
        tox_score   float  최종 독성 확률 (모델 ⊕ 어휘)
        tox_model   float  모델 단독 점수 (폴백 시 NaN)
        is_toxic    bool   threshold 초과 여부

    반환: (DataFrame, 사용된 backend 이름)
    """
    if adf.empty:
        adf = adf.copy()
        adf["tox_score"] = []
        adf["tox_model"] = []
        adf["is_toxic"] = []
        return adf, "lexicon"

    clf = classifier or get_classifier()
    texts = adf["text"].fillna("").astype(str).tolist()
    res = clf.score_texts(texts)

    out = adf.copy()
    out["tox_score"] = res.scores
    out["tox_model"] = res.model_scores if res.model_scores is not None else np.nan
    out["is_toxic"] = out["tox_score"] >= threshold
    return out, res.backend
