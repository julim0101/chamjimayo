"""
파이프라인 스모크 테스트

    python scripts/smoke_test.py

데모 5종을 끝까지 돌려 다음을 확인합니다.
  1. 파싱 성공 여부
  2. 역할(가해/피해) 추정 정확도
  3. 고위험군과 대조군의 위험도 분리
  4. 리포트·진정서 생성 성공 여부

발표 전 / 배포 전 / 코드 수정 후 반드시 한 번 돌리세요.
"""

from __future__ import annotations

import logging
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from core.pipeline import analyze_file  # noqa: E402
from core.report import complaint_draft, inspector_report  # noqa: E402

logging.basicConfig(level=logging.ERROR)

DEMO_DIR = ROOT / "data" / "demo"

# (파일 키워드, 기대 가해자, 기대 피해자, 기대 구분)
EXPECTED = [
    ("demo0", "박수선 선생님", "이지은", "high"),
    ("demo1", "강준호 부장", "서민경", "high"),
    ("demo2", "대표님", None, "high"),
    ("demo3", "이하늘 팀장", "정우진", "low"),
    ("demo4", "조현석 과장", "한소미", "subtle"),
]

HIGH_MIN = 0.45   # 고위험군 최소 위험도
LOW_MAX = 0.20    # 대조군 최대 위험도


def main() -> int:
    files = sorted(DEMO_DIR.glob("*.txt"))
    if not files:
        print(f"❌ 데모 파일이 없습니다: {DEMO_DIR}")
        return 1

    fails: list[str] = []
    rows = []

    for key, exp_actor, exp_subject, kind in EXPECTED:
        match = [f for f in files if key in f.name]
        if not match:
            fails.append(f"{key}: 파일 없음")
            continue
        path = match[0]

        try:
            r = analyze_file(path, mask_names=False)
        except Exception as e:
            fails.append(f"{path.name}: 분석 실패 — {e}")
            continue

        c = r.case

        if c.actor != exp_actor:
            fails.append(f"{path.name}: 가해자 추정 오류 (기대 {exp_actor}, 실제 {c.actor})")
        if exp_subject and c.subject != exp_subject:
            fails.append(f"{path.name}: 피해자 추정 오류 (기대 {exp_subject}, 실제 {c.subject})")

        if kind == "high" and c.risk_score < HIGH_MIN:
            fails.append(f"{path.name}: 고위험인데 위험도 {c.risk_score:.2f} < {HIGH_MIN}")
        if kind == "low" and c.risk_score > LOW_MAX:
            fails.append(f"{path.name}: 대조군인데 위험도 {c.risk_score:.2f} > {LOW_MAX}")
        if kind == "subtle":
            if c.risk_score > 0.38:
                fails.append(f"{path.name}: 교묘한 정황 사건의 정량 점수가 예상보다 높음")
            if not c.needs_human_review:
                fails.append(f"{path.name}: Tier 3 검토 큐에 올라오지 않음")

        try:
            rep = inspector_report(c)
            draft = complaint_draft(c)
            assert len(rep) > 500 and len(draft) > 400
        except Exception as e:
            fails.append(f"{path.name}: 리포트 생성 실패 — {e}")

        rows.append(
            (path.name, c.risk_score, c.priority, c.risk_label, c.actor,
             c.subject, len(c.key_evidence), len(c.subtle_evidence),
             len(c.law_flags), c.needs_human_review)
        )

    # ---- 출력
    print("=" * 104)
    print(f"{'파일':32s}{'위험도':>7s}{'우선순위':>9s} {'등급':9s}{'가해자':12s}{'피해자':10s}"
          f"{'증거':>4s}{'정황':>5s}{'별건':>5s}{'검토':>5s}")
    print("-" * 104)
    for n, rs, pr, lb, ac, sb, ke, se, lf, nr in rows:
        print(f"{n[:32]:32s}{rs:7.3f}{pr:9.3f} {lb:9s}{ac[:11]:12s}{(sb or '—')[:9]:10s}"
              f"{ke:4d}{se:5d}{lf:5d}{'  O' if nr else '  -':>5s}")
    print("=" * 104)

    if rows:
        highs = [r[1] for r, e in zip(rows, EXPECTED) if e[3] == "high"]
        lows = [r[1] for r, e in zip(rows, EXPECTED) if e[3] == "low"]
        if highs and lows:
            print(f"\n분리도: 고위험 최저 {min(highs):.3f} vs 대조군 최고 {max(lows):.3f} "
                  f"(격차 {min(highs) - max(lows):.3f})")

    r0 = analyze_file([f for f in files if "demo0" in f.name][0])
    print(f"백엔드: 독성분류 `{r0.case.tox_backend}` · 법령검색 `{r0.case.rag_backend}`")

    if fails:
        print(f"\n❌ 실패 {len(fails)}건")
        for f in fails:
            print(f"   · {f}")
        return 1

    print("\n✅ 전체 통과")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
