"""
참지마요 — 노동법 폐쇄형 RAG 검색기

두 개의 백엔드를 가진다.

  1. dense  : sentence-transformers 임베딩 + FAISS 내적 검색 (기본)
  2. bm25   : 한국어 문자 n-gram BM25 (폴백, 순수 numpy)

폐쇄형(closed-domain)이 핵심이다. 검색 범위는 data/law/ 안의
법령·매뉴얼·판례로 한정되며, 그 밖의 지식은 인용하지 않는다.
LLM은 '검색된 문서 안에서만' 근거를 인용하도록 강제된다(core/llm.py).

한국어에서 형태소 분석기 없이도 쓸 만한 검색을 얻기 위해
BM25 폴백은 어절 토큰 + 문자 2·3-gram을 함께 색인한다.
"""

from __future__ import annotations

import json
import logging
import math
import re
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable, Optional

import numpy as np

log = logging.getLogger(__name__)

DATA_DIR = Path(__file__).resolve().parents[2] / "data" / "law"
INDEX_DIR = Path(__file__).resolve().parents[2] / "data" / "index"

EMBED_MODEL_CANDIDATES = [
    "jhgan/ko-sroberta-multitask",
    "snunlp/KR-SBERT-V40K-klueNLI-augSTS",
    "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2",
]


# ---------------------------------------------------------------- 문서


@dataclass
class LawDoc:
    id: str
    type: str  # 법령 | 판단기준 | 행위유형 | 절차 | 판례
    title: str
    text: str
    tags: list[str] = field(default_factory=list)
    maps_to: list[str] = field(default_factory=list)
    verified: bool = False
    meta: dict = field(default_factory=dict)

    @property
    def citation(self) -> str:
        """리포트에 인용할 출처 표기."""
        m = self.meta
        if self.type == "법령":
            return f"{m.get('act','')} {m.get('article','')}"
        if self.type == "판례":
            return f"{m.get('court','')} {m.get('date','')} 선고 {m.get('case_no','')} 판결"
        return f"{m.get('source_doc', '고용노동부 매뉴얼')}"

    @property
    def searchable(self) -> str:
        return f"{self.title} {' '.join(self.tags)} {self.text}"


def load_corpus(data_dir: Path = DATA_DIR) -> list[LawDoc]:
    """data/law/*.jsonl 을 모두 읽어 LawDoc 리스트로 반환."""
    docs: list[LawDoc] = []
    for path in sorted(data_dir.glob("*.jsonl")):
        for line_no, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            line = line.strip()
            if not line:
                continue
            try:
                d = json.loads(line)
            except json.JSONDecodeError as e:
                log.warning("%s:%d JSON 파싱 실패 — %s", path.name, line_no, e)
                continue
            if d.get("id") == "PREC-TEMPLATE":  # 템플릿 행은 색인 제외
                continue
            known = {"id", "type", "title", "text", "tags", "maps_to", "verified"}
            docs.append(
                LawDoc(
                    id=d.get("id", f"{path.stem}-{line_no}"),
                    type=d.get("type", "기타"),
                    title=d.get("title", ""),
                    text=d.get("text", ""),
                    tags=d.get("tags", []),
                    maps_to=d.get("maps_to", []),
                    verified=bool(d.get("verified", False)),
                    meta={k: v for k, v in d.items() if k not in known},
                )
            )
    return docs


# ---------------------------------------------------------------- 토크나이저


_WS = re.compile(r"[^\w가-힣]+")


def ko_tokens(text: str, ngrams: tuple[int, ...] = (2, 3)) -> list[str]:
    """어절 토큰 + 문자 n-gram. 형태소 분석기 없이 한국어 검색 성능을 확보."""
    text = _WS.sub(" ", text).strip()
    toks: list[str] = [w for w in text.split() if w]
    compact = text.replace(" ", "")
    for n in ngrams:
        toks.extend(compact[i : i + n] for i in range(max(0, len(compact) - n + 1)))
    return toks


# ---------------------------------------------------------------- BM25


class BM25:
    """순수 numpy BM25 — 외부 의존성 없는 폴백 검색기."""

    def __init__(self, corpus_tokens: list[list[str]], k1: float = 1.5, b: float = 0.75):
        self.k1, self.b = k1, b
        self.N = len(corpus_tokens)
        self.doc_len = np.array([len(t) for t in corpus_tokens], dtype=float)
        self.avgdl = float(self.doc_len.mean()) if self.N else 0.0
        self.tf: list[Counter] = [Counter(t) for t in corpus_tokens]

        df = Counter()
        for t in corpus_tokens:
            df.update(set(t))
        self.idf = {
            term: math.log(1 + (self.N - n + 0.5) / (n + 0.5)) for term, n in df.items()
        }

    def search(self, query: str, top_k: int = 5) -> list[tuple[int, float]]:
        q = ko_tokens(query)
        if not q or self.N == 0:
            return []
        scores = np.zeros(self.N)
        for term in set(q):
            idf = self.idf.get(term)
            if idf is None:
                continue
            f = np.array([tfd.get(term, 0) for tfd in self.tf], dtype=float)
            denom = f + self.k1 * (1 - self.b + self.b * self.doc_len / (self.avgdl or 1))
            scores += idf * (f * (self.k1 + 1)) / np.where(denom == 0, 1, denom)
        order = np.argsort(-scores)[:top_k]
        return [(int(i), float(scores[i])) for i in order if scores[i] > 0]


# ---------------------------------------------------------------- 검색기


@dataclass
class Hit:
    doc: LawDoc
    score: float
    backend: str


class LawRetriever:
    """폐쇄형 노동법 검색기. dense 우선, 실패 시 BM25 폴백."""

    def __init__(self, data_dir: Path = DATA_DIR, prefer_dense: bool = True):
        self.docs = load_corpus(data_dir)
        self.backend = "bm25"
        self._embeds: Optional[np.ndarray] = None
        self._index = None
        self._model = None

        self._bm25 = BM25([ko_tokens(d.searchable) for d in self.docs])
        if prefer_dense:
            self._try_dense()

    # ---------------------------------------------------------- dense

    def _try_dense(self) -> bool:
        try:
            from sentence_transformers import SentenceTransformer  # type: ignore
        except Exception as e:
            log.info("sentence-transformers 미설치 — BM25로 동작합니다. (%s)", e)
            return False

        for name in EMBED_MODEL_CANDIDATES:
            try:
                self._model = SentenceTransformer(name)
                break
            except Exception as e:
                log.warning("임베딩 모델 로드 실패 %s: %s", name, e)
        if self._model is None:
            return False

        try:
            emb = self._model.encode(
                [d.searchable for d in self.docs],
                normalize_embeddings=True,
                show_progress_bar=False,
            ).astype("float32")
            self._embeds = emb
            try:
                import faiss  # type: ignore

                idx = faiss.IndexFlatIP(emb.shape[1])
                idx.add(emb)
                self._index = idx
            except Exception:
                self._index = None  # numpy 내적으로 대체
            self.backend = "dense"
            return True
        except Exception as e:
            log.warning("임베딩 생성 실패 — BM25 폴백. (%s)", e)
            return False

    def _dense_search(self, query: str, top_k: int) -> list[tuple[int, float]]:
        qv = self._model.encode(  # type: ignore
            [query], normalize_embeddings=True, show_progress_bar=False
        ).astype("float32")
        if self._index is not None:
            sims, ids = self._index.search(qv, top_k)
            return [(int(i), float(s)) for i, s in zip(ids[0], sims[0]) if i >= 0]
        sims = (self._embeds @ qv[0])  # type: ignore
        order = np.argsort(-sims)[:top_k]
        return [(int(i), float(sims[i])) for i in order]

    # ---------------------------------------------------------- public

    def search(
        self,
        query: str,
        top_k: int = 5,
        doc_types: Optional[Iterable[str]] = None,
        maps_to: Optional[str] = None,
        verified_only: bool = False,
    ) -> list[Hit]:
        """폐쇄형 검색. 코퍼스 밖의 어떤 것도 반환하지 않는다."""
        if not self.docs:
            return []

        pool = max(top_k * 4, 20)
        raw = (
            self._dense_search(query, pool)
            if self.backend == "dense"
            else self._bm25.search(query, pool)
        )

        hits: list[Hit] = []
        for i, s in raw:
            d = self.docs[i]
            if doc_types and d.type not in doc_types:
                continue
            if maps_to and maps_to not in d.maps_to:
                continue
            if verified_only and not d.verified:
                continue
            hits.append(Hit(doc=d, score=s, backend=self.backend))
            if len(hits) >= top_k:
                break
        return hits

    def for_requirement(self, code: str, query: str = "", top_k: int = 3) -> list[Hit]:
        """3요건(R1/R2/R3)별 근거 조항·판단기준을 가져온다."""
        seed = {
            "R1": "지위 또는 관계의 우위를 이용하여 저항하기 어려운 상태",
            "R2": "업무상 적정범위를 넘는 행위 근무시간 외 반복적 업무 지시",
            "R3": "신체적 정신적 고통 근무환경 악화 모욕 업무 배제",
        }.get(code, "")
        return self.search(f"{seed} {query}".strip(), top_k=top_k, maps_to=code)

    def stats(self) -> dict:
        total = len(self.docs)
        by_type = Counter(d.type for d in self.docs)
        verified = sum(1 for d in self.docs if d.verified)
        return {
            "total": total,
            "verified": verified,
            "verified_ratio": verified / total if total else 0.0,
            "by_type": dict(by_type),
            "backend": self.backend,
        }


# ---------------------------------------------------------------- 자가진단

_SELFTEST_QUERIES = [
    ("근무시간 외에 계속 업무 지시를 받았습니다", "R2"),
    ("다른 사람들 앞에서 모욕적인 말을 들었습니다", "R3"),
    ("상사가 해고를 언급하며 위협했습니다", None),
    ("단톡방에서 저만 빼고 일을 진행합니다", "R3"),
    ("야근수당을 주지 않겠다고 합니다", None),
    ("노동청에 신고하면 불이익을 주겠다고 합니다", None),
]


def _selftest() -> None:
    r = LawRetriever()
    print("=" * 72)
    print("코퍼스:", r.stats())
    print("=" * 72)
    for q, code in _SELFTEST_QUERIES:
        print(f"\n[{code or '-'}] {q}")
        for h in r.search(q, top_k=3, maps_to=code):
            badge = "✓" if h.doc.verified else "미검증"
            print(f"   {h.score:6.3f} [{badge}] {h.doc.citation} — {h.doc.title}")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    _selftest()
