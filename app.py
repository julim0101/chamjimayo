"""
참지마요 (ChamJiMayo)
텍스트 마이닝 · 노동법 RAG 기반 직장 내 괴롭힘 입증 지원 서비스

제8회 K-디지털 트레이닝 해커톤 · 참교육스쿨

실행:  streamlit run app.py
"""

from __future__ import annotations

import logging
from datetime import time
from pathlib import Path

import streamlit as st

import ui
from core import metrics as M
from core import toxicity as T
from core.pipeline import AnalysisResult, analyze
from core.rag.retriever import LawRetriever
from core.report import complaint_draft, inspector_report

logging.basicConfig(level=logging.WARNING)

ROOT = Path(__file__).parent
DEMO_DIR = ROOT / "data" / "demo"

st.set_page_config(
    page_title="참지마요",
    page_icon="⚖️",
    layout="wide",
    initial_sidebar_state="collapsed",
)

CONSOLE = "근로감독관 수사지원"
SOFT = "피해 근로자 리포트"


# ---------------------------------------------------------------- 리소스


@st.cache_resource(show_spinner="노동법 코퍼스를 불러오는 중…")
def get_retriever() -> LawRetriever:
    return LawRetriever()


@st.cache_resource(show_spinner="독성 분류 모델을 준비하는 중…")
def get_classifier() -> T.ToxicityClassifier:
    return T.get_classifier()


@st.cache_data(show_spinner=False)
def list_demos() -> list[tuple[str, str]]:
    out = []
    for p in sorted(DEMO_DIR.glob("*.txt")):
        for enc in ("utf-8", "utf-8-sig", "cp949"):
            try:
                out.append((p.stem, p.read_text(encoding=enc)))
                break
            except UnicodeDecodeError:
                continue
    return out


def _decode(data: bytes) -> str | None:
    for enc in ("utf-8", "utf-8-sig", "cp949"):
        try:
            return data.decode(enc)
        except UnicodeDecodeError:
            continue
    return None


def _sig(cfg: dict) -> tuple:
    wh = cfg["wh"]
    return (wh.start, wh.end, wh.shift_work, cfg["tox_threshold"], cfg["mask_names"])


def run_analysis(raw: str, name: str, cfg: dict) -> AnalysisResult:
    return analyze(
        raw,
        source_name=name,
        work_hours=cfg["wh"],
        mask_names=cfg["mask_names"],
        classifier=get_classifier(),
        retriever=get_retriever(),
        tox_threshold=cfg["tox_threshold"],
    )


# ---------------------------------------------------------------- 사이드바


def chrome() -> dict:
    """상단 네비 + 설정. 사이드바를 쓰지 않는다."""
    r, clf = get_retriever(), get_classifier()
    stats = r.stats()
    ui.nav([
        ("법령", f"{stats['total']}건"),
        ("검색", stats['backend']),
        ("분류", clf.backend),
    ])

    role = st.radio("화면", [CONSOLE, SOFT], key="role",
                    horizontal=True, label_visibility="collapsed")

    with st.expander("분석 설정"):
        c1, c2, c3, c4 = st.columns([1, 1, 1.4, 1])
        start = c1.time_input("근무 시작", time(9, 0), step=1800)
        end = c2.time_input("근무 종료", time(18, 0), step=1800)
        tox = c3.slider("독성 판정 임계값", 0.3, 0.9, 0.5, 0.05)
        with c4:
            shift = st.checkbox(
                "교대제 사업장",
                help="병원·제조업 등 야간이 정상 근무인 경우.",
            )
            mask = st.checkbox("실명 가리기", value=True)

    return {
        "role": role,
        "wh": M.WorkHours(start=start, end=end, shift_work=shift),
        "tox_threshold": tox,
        "mask_names": mask,
    }


# ---------------------------------------------------------------- 감독관


def view_console(cfg: dict) -> None:
    ui.hero(
        "근로감독관 수사지원",
        "조사 착수 <em>전</em>, 어디부터 볼지 정해드립니다",
        "쏟아지는 직장 내 괴롭힘 신고를 근로기준법 제76조의2 성립요건으로 정량 분석해 "
        "사건별 조사 우선순위를 산출합니다. 성립 여부는 판정하지 않고, 검토 순서만 제안합니다.",
        ["사건 업로드", "정량 분석", "우선순위 · 별건위반"],
    )

    src = st.radio("대상", ["데모 사건", "파일 업로드"], horizontal=True,
                   label_visibility="collapsed")

    payloads: list[tuple[str, str]] = []
    if src == "데모 사건":
        demos = list_demos()
        if not demos:
            st.error(f"데모 파일이 없습니다: `{DEMO_DIR}`")
            return
        names = [d[0] for d in demos]
        picked = st.multiselect("사건", names, default=names, label_visibility="collapsed")
        payloads = [(n, t) for n, t in demos if n in picked]
    else:
        ups = st.file_uploader(
            "카카오톡 대화 내보내기 (.txt) — 여러 건 동시 업로드 가능",
            type=["txt"], accept_multiple_files=True,
        )
        for u in ups or []:
            if (txt := _decode(u.getvalue())) is not None:
                payloads.append((u.name, txt))

    if not payloads:
        ui.empty(
            "분석할 사건을 선택하세요",
            "위에서 데모 사건을 고르거나 카카오톡 대화 파일(.txt)을 올리면 조사 우선순위를 산출합니다.",
            icon="🗂️",
        )
        return

    if st.button(f"{len(payloads)}건 분석", type="primary"):
        results: list[AnalysisResult] = []
        bar = st.progress(0.0, text="분석 준비 중…")
        for i, (name, raw) in enumerate(payloads, 1):
            bar.progress(i / len(payloads), text=f"[{i}/{len(payloads)}] {name}")
            try:
                results.append(run_analysis(raw, name, cfg))
            except Exception as e:
                st.error(f"{name} — {e}")
        bar.empty()
        results.sort(key=lambda r: -r.case.priority)
        st.session_state["insp"] = results
        st.session_state["insp_sig"] = _sig(cfg)

    results = st.session_state.get("insp")
    if not results:
        return
    if st.session_state.get("insp_sig") != _sig(cfg):
        ui.note("warn", "<b>설정이 변경되었습니다.</b> 반영하려면 다시 분석하세요.")

    _console_results(results, cfg)


def _console_results(results: list[AnalysisResult], cfg: dict) -> None:
    cases = [r.case for r in results]
    review = [c for c in cases if c.needs_human_review]

    ui.section("분석 결과")
    ui.kpis([
        ("분석 사건", f"{len(cases)}", "건"),
        ("고위험", f"{sum(1 for c in cases if c.risk_label == '높음')}", "건"),
        ("3요건 충족", f"{sum(1 for c in cases if c.all_requirements_met)}", "건"),
        ("별건 위반 단서", f"{sum(len(c.law_flags) for c in cases)}", "건"),
    ])

    ui.section(
        "조사 우선순위",
        "우선순위 = 괴롭힘 성립 가능성 + 별건 법위반의 중대성. "
        "괴롭힘 점수가 낮아도 임금체불·신고자 보복처럼 그 자체로 형사처벌 대상인 "
        "단서가 있으면 순위가 올라갑니다.",
    )
    ui.case_table(cases)

    if review:
        ui.section(
            f"사람의 검토가 필요한 사건 · {len(review)}건",
            "정량 지표는 낮지만 맥락상 정황이 관측된 사건입니다. "
            "폭언 없는 배제·따돌림은 숫자로 잘 드러나지 않아 별도로 올립니다.",
        )
        for c in review:
            ui.note(
                "warn",
                f"<b>{c.room}</b> · {c.case_id} — 위험도 {c.risk_score:.2f}<br>{c.review_reason}",
            )

    ui.section("사건 상세")
    labels = [f"{i}. {c.room}  ·  {c.risk_label} {c.risk_score:.2f}"
              for i, c in enumerate(cases, 1)]
    pick = st.selectbox("사건", labels, label_visibility="collapsed")
    _detail(results[labels.index(pick)], cfg, console=True)


# ---------------------------------------------------------------- 상세 (공용)


def _detail(r: AnalysisResult, cfg: dict, console: bool) -> None:
    c, adf = r.case, r.adf

    if console:
        ui.case_head(c)
        if c.law_flags:
            chips = "<br>".join(
                f'<b>{n}</b> <span style="color:var(--fg-3)">{law}</span>'
                for n, law in c.law_flags.items()
            )
            ui.note("warn", f"별건 법위반 단서 · {len(c.law_flags)}건<br>{chips}")

    tabs = st.tabs([
        "성립요건",
        f"증거 {len(c.key_evidence)}",
        f"정황 {len(c.subtle_evidence)}",
        "법령 근거",
        "시간 패턴",
        "리포트",
    ])

    with tabs[0]:
        ui.requirements(c.blocks)
        st.write("")
        cols = st.columns(3)
        for col, b in zip(cols, c.blocks):
            with col:
                ui.metrics(b)
        if console:
            with st.expander("화자별 프로필 — 역할 추정 근거"):
                st.dataframe(r.profile.round(3), use_container_width=True)

    with tabs[1]:
        if not c.key_evidence:
            ui.note("ok", "임계치를 초과하는 발화가 관측되지 않았습니다.")
        for e in (c.key_evidence if console else c.key_evidence[:8]):
            ui.evidence(e)

    with tabs[2]:
        if not c.subtle_evidence:
            ui.note("ok", "정황 후보가 관측되지 않았습니다.")
        else:
            ui.note(
                "warn",
                "이 항목들은 <b>확정 지표가 아닙니다.</b> 맥락 추론으로 뽑은 <b>후보</b>이며 "
                "위험도 점수에 반영되지 않았습니다. 판단은 사람이 합니다.",
            )
            for e in c.subtle_evidence:
                ui.evidence(e, subtle=True)

    with tabs[3]:
        _citations(c)

    with tabs[4]:
        ui.heatmap(adf, c.actor, cfg["wh"].start.hour, cfg["wh"].end.hour)
        if console:
            st.write("")
            with st.expander("전체 대화 원문"):
                cols = ["idx", "ts", "speaker", "text", "is_offhours",
                        "is_night", "is_directive", "tox_score"]
                st.dataframe(
                    adf[[x for x in cols if x in adf.columns]],
                    use_container_width=True, hide_index=True, height=440,
                )

    with tabs[5]:
        if console:
            md = inspector_report(c)
            st.download_button(
                "증거 분석 보고서 (.md)",
                md.encode("utf-8"),
                file_name=f"{c.case_id}_증거분석보고서.md",
                mime="text/markdown",
                type="primary",
            )
            with st.expander("미리보기", expanded=True):
                st.markdown(md)
        else:
            _complaint(c)


def _citations(c) -> None:
    if not c.citations:
        ui.note("info", "인용된 조항이 없습니다.")
        return
    ui.note(
        "info",
        "법령·고용노동부 매뉴얼만 담은 <b>폐쇄형 코퍼스</b> 안에서만 검색합니다. "
        "외부 지식은 인용하지 않습니다.",
    )
    labels = {
        "R1": "요건① 지위·관계의 우위",
        "R2": "요건② 업무상 적정범위 초과",
        "R3": "요건③ 고통·근무환경 악화",
        "부수위반": "별건 법위반",
    }
    for req, label in labels.items():
        items = [x for x in c.citations if x["req"] == req]
        if not items:
            continue
        st.markdown(
            f'<div style="font-size:11px;font-weight:700;letter-spacing:.13em;'
            f'text-transform:uppercase;color:var(--fg-4);margin:28px 0 4px">{label}</div>',
            unsafe_allow_html=True,
        )
        for x in items:
            ui.citation(x)


def _complaint(c) -> None:
    st.caption("아래를 채우면 초안에 반영됩니다. 입력값은 저장되지 않습니다.")
    f1, f2, f3 = st.columns(3)
    nm = f1.text_input("진정인 성명", "")
    wp = f2.text_input("사업장명", "")
    of = f3.text_input("관할 지방고용노동청", "")
    draft = complaint_draft(
        c,
        complainant=nm or "(성명)",
        workplace=wp or "(사업장명)",
        office=of or "(관할 지방고용노동청)",
    )
    st.write("")
    st.download_button(
        "진정서 초안 내려받기 (.md)",
        draft.encode("utf-8"),
        file_name=f"{c.case_id}_진정서초안.md",
        mime="text/markdown",
        type="primary",
    )
    with st.expander("미리보기", expanded=True):
        st.markdown(draft)


# ---------------------------------------------------------------- 피해자


def view_soft(cfg: dict) -> None:
    ui.hero(
        "피해 근로자 리포트",
        "내 대화가 <em>어떤 근거</em>가 되는지 정리해 드려요",
        "카카오톡 대화를 올리면 개인정보를 먼저 지우고, 법이 정한 요건에 맞춰 근거가 될 발화를 "
        "정리해 진정서 초안까지 만들어 드립니다.",
        ["대화 올리기", "자동 정리", "진정서 초안"],
    )

    ui.note(
        "info",
        "🔒 올리신 대화는 <b>분석하기 전에 개인정보가 먼저 지워집니다.</b> "
        "이름·연락처·주소·계좌번호는 분석 엔진에 전달되지 않아요.",
    )

    src = st.radio("입력", ["내 대화 올리기", "예시로 먼저 보기"], horizontal=True,
                   label_visibility="collapsed")

    raw, name = None, ""
    if src == "내 대화 올리기":
        with st.expander("카카오톡 대화 내보내는 방법"):
            st.markdown(
                "1. 카카오톡에서 해당 채팅방을 엽니다\n"
                "2. 우측 상단 **≡ 메뉴 → 대화 내용 → 대화 내용 내보내기**\n"
                "3. **텍스트만 보내기** 선택 → `.txt` 파일 저장\n"
                "4. 저장한 파일을 아래에 올려주세요"
            )
        up = st.file_uploader("카카오톡 대화 파일 (.txt)", type=["txt"])
        if up and (txt := _decode(up.getvalue())) is not None:
            raw, name = txt, up.name
    else:
        demos = list_demos()
        if demos:
            pick = st.selectbox("예시 대화", [d[0] for d in demos])
            raw, name = dict(demos)[pick], pick

    if not raw:
        return

    st.write("")
    if st.button("정리 시작", type="primary", use_container_width=True):
        try:
            st.session_state["vic"] = run_analysis(raw, name, cfg)
            st.session_state["vic_sig"] = _sig(cfg)
        except Exception as e:
            st.session_state.pop("vic", None)
            st.error(str(e))

    r = st.session_state.get("vic")
    if r is None:
        return
    if st.session_state.get("vic_sig") != _sig(cfg):
        ui.note("warn", "<b>설정이 변경되었습니다.</b> 반영하려면 다시 실행하세요.")

    c = r.case
    ui.section("정리 결과")
    ui.kpis([
        ("위험도", f"{c.risk_score:.2f}", c.risk_label),
        ("분석 기간", f"{c.span_days}", "일"),
        ("대화 수", f"{c.n_messages:,}", "건"),
        ("근거가 될 발화", f"{len(c.key_evidence)}", "건"),
    ])

    ui.section(
        "법은 세 가지를 함께 봅니다",
        "근로기준법 제76조의2는 ① 지위·관계의 우위 ② 업무상 적정범위 초과 "
        "③ 신체적·정신적 고통, 이 셋이 모두 있어야 직장 내 괴롭힘으로 봅니다.",
    )
    ui.requirements(c.blocks)

    st.write("")
    _detail(r, cfg, console=False)

    st.divider()
    st.caption(
        "본 결과는 대화 기록의 통계 분석이며 괴롭힘 성립 여부를 판정하지 않습니다. "
        "진정서는 초안이므로 제출 전 노무사·변호사 검토를 권합니다."
    )


# ---------------------------------------------------------------- main


def main() -> None:
    ui.inject()
    cfg = chrome()
    if cfg["role"] == CONSOLE:
        view_console(cfg)
    else:
        view_soft(cfg)


if __name__ == "__main__":
    main()
