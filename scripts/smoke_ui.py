"""
ui.py 스모크 테스트 — streamlit 없이 UI 함수 전체를 실제 데이터로 호출한다.

streamlit 을 설치하지 않고도 다음을 잡는다:
  · 존재하지 않는 속성 접근 (case.foo, block.bar)
  · 함수 시그니처 불일치
  · column_config / metric 등에 넘기는 인자 오타

실제 렌더링은 검증하지 못한다. 그건 `streamlit run app.py` 로 눈으로 봐야 한다.

실행:  python scripts/smoke_ui.py
"""

from __future__ import annotations

import glob
import sys
import types
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

CALLS: list[str] = []


# ---------------------------------------------------------------- streamlit 스텁


class _Ctx:
    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


class _Col(_Ctx):
    def __getattr__(self, name):
        return _rec(name)


def _rec(name):
    def f(*a, **k):
        CALLS.append(name)
        if name in {"container", "expander", "form", "spinner", "status"}:
            return _Ctx()
        if name == "columns":
            n = a[0] if a else 1
            return [_Col() for _ in range(n if isinstance(n, int) else len(n))]
        if name in {"tabs"}:
            return [_Ctx() for _ in a[0]]
        return None

    return f


class _ColumnConfig:
    """인자를 검증만 하고 버린다. 알 수 없는 kwarg 는 즉시 실패."""

    _ALLOWED = {
        "label", "width", "help", "pinned", "format", "min_value", "max_value",
        "step", "color", "disabled", "required", "default",
    }

    def __getattr__(self, kind):
        def f(*a, **k):
            bad = set(k) - self._ALLOWED
            if bad:
                raise TypeError(f"column_config.{kind}: 지원하지 않는 인자 {sorted(bad)}")
            CALLS.append(f"column_config.{kind}")
            return None

        return f


class _St(types.ModuleType):
    column_config = _ColumnConfig()

    def __getattr__(self, name):
        if name == "sidebar":
            return _Col()
        return _rec(name)


st = _St("streamlit")
sys.modules["streamlit"] = st


# ---------------------------------------------------------------- 실제 데이터

import ui  # noqa: E402
from core.pipeline import analyze  # noqa: E402
from core.rag.retriever import LawRetriever  # noqa: E402

ret = LawRetriever()
paths = sorted(glob.glob(str(ROOT / "data" / "demo" / "*.txt")))
results = [analyze(Path(p).read_text(encoding="utf-8"), Path(p).name, retriever=ret) for p in paths]
results.sort(key=lambda r: -r.case.priority)
cases = [r.case for r in results]
top = results[0]
c = top.case

print(f"데모 {len(cases)}건 분석 완료 — 대표 사건: {c.room}\n")

checks: list[tuple[str, str]] = []


def run(label, fn, *a, **k):
    try:
        fn(*a, **k)
        checks.append((label, "OK"))
    except Exception as e:
        checks.append((label, f"★ {type(e).__name__}: {e}"))


run("inject", ui.inject)
run("nav(str)", ui.nav, "5건 분석 완료")
run("nav(stats)", ui.nav, [("분석 사건", "5건"), ("고위험", "2건")])
run("page_head", ui.page_head, "근로감독관 콘솔", "설명", "eyebrow")
run("section", ui.section, "분석 결과", "부제")
run("note/info", ui.note, "info", "일반 안내")
run("note/warn+HTML", ui.note, "warn", f"<b>{c.room}</b> · {c.case_id}<br>{c.review_reason or '—'}")
run("hero", ui.hero, "근로감독관 수사지원", "조사 착수 <em>전</em>, 어디부터 볼지",
    "설명문", ["사건 업로드", "정량 분석", "우선순위"])
run("empty", ui.empty, "비어 있음", "설명", "🗂️")
run("footer", ui.footer, "참지마요")
run("sig", ui.sig, c.risk_label)
run("tag", ui.tag, c.risk_label)
run("gauge", ui.gauge, c.priority)
run("kpis", ui.kpis, [("분석 사건", "5", "건"), ("고위험", "2", "건"),
                      ("3요건 충족", "3", "건"), ("별건 위반", "8", "건")])
run("case_table", ui.case_table, cases)
run("case_head", ui.case_head, c)
run("requirements", ui.requirements, c.blocks)
run("metrics", ui.metrics, c.blocks[0])
if c.key_evidence:
    run("evidence", ui.evidence, c.key_evidence[0])
if c.subtle_evidence:
    run("evidence(subtle)", ui.evidence, c.subtle_evidence[0], True)
cits = getattr(c, "citations", None) or []
if cits:
    run("citation", ui.citation, cits[0])
run("heatmap", ui.heatmap, top.adf, c.actor)

print(f"{'항목':<22} 결과")
print("-" * 78)
for label, res in checks:
    print(f"{label:<22} {res}")

fails = [c_ for c_ in checks if c_[1] != "OK"]
print("-" * 78)
print(f"{len(checks) - len(fails)}/{len(checks)} 통과")
if fails:
    sys.exit(1)
