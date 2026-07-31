"""
참지마요 — UI 컴포넌트 (네이티브 전용)

설계 원칙
  1. HTML/CSS 문자열을 쓰지 않는다. 외형은 전적으로 .streamlit/config.toml 이 정한다.
     → Streamlit 버전이 올라가도 selector 가 깨질 일이 없다.
  2. 공개 API(함수 이름·시그니처)는 이전 HTML 버전과 100% 동일하다.
     app.py 는 한 줄도 고치지 않는다.
  3. app.py 가 넘기는 레거시 HTML 문자열(<b>, <br>, <em>)은 _md() 가 마크다운으로 바꾼다.
     호출부를 건드리지 않고 HTML 렌더링만 제거하기 위한 다리.

색은 config.toml 의 팔레트를 따르며, 위험도 신호에만 예외적으로 직접 지정한다.
"""

from __future__ import annotations

import re

import pandas as pd
import streamlit as st

# 위험도 색 — config.toml chartCategoricalColors 와 같은 계열
C_HIGH = "#FF5A5A"
C_MID = "#FFB020"
C_LOW = "#828DA0"
C_NONE = "#AAB2C2"
C_ACCENT = "#5563F0"
C_WATCH = "#C6F24E"

_BADGE = {
    "높음": "red",
    "중간": "orange",
    "낮음": "gray",
    "관측 없음": "gray",
    "검토 필요": "green",
}

_TAGRE = re.compile(r"<[^>]+>")


def _md(s) -> str:
    """레거시 HTML 조각을 마크다운으로 변환한다. 태그는 남기지 않는다."""
    s = str(s)
    s = re.sub(r"<br\s*/?>", "  \n", s, flags=re.I)
    s = re.sub(r"</?(?:b|strong)>", "**", s, flags=re.I)
    s = re.sub(r"</?(?:em|i)>", "*", s, flags=re.I)
    return _TAGRE.sub("", s)


def inject() -> None:
    """이전 버전과의 호환을 위해 남겨둔다. 테마는 config.toml 이 담당한다."""
    return None


def sig(label: str) -> str:
    return {
        "높음": C_HIGH,
        "중간": C_MID,
        "낮음": C_LOW,
    }.get(label, C_NONE)


def tag(label: str, color: str = "") -> str:
    """마크다운 배지 문자열을 돌려준다 (st.markdown 에 그대로 넣을 수 있다)."""
    return f":{_BADGE.get(label, 'gray')}-badge[{label}]"


def gauge(v: float, color: str = "") -> float:
    """이전 시그니처 유지. 이제는 진행률 값을 그대로 돌려주고 표가 막대를 그린다."""
    return max(0.0, min(1.0, float(v)))


# ================================================================ 레이아웃


def nav(stats: list[tuple[str, str]] | str = "") -> None:
    with st.sidebar:
        st.markdown("### ⚖️ 참지마요")
        st.caption("근로감독관 수사지원")
        if isinstance(stats, str):
            if stats:
                st.caption(_md(stats))
        elif stats:
            st.divider()
            for k, v in stats:
                st.metric(k, v)


def page_head(title: str, desc: str = "", eyebrow: str = "") -> None:
    if eyebrow:
        st.caption(_md(eyebrow))
    st.title(_md(title))
    if desc:
        st.caption(_md(desc))


def section(title: str, desc: str = "") -> None:
    st.subheader(_md(title), divider="gray")
    if desc:
        st.caption(_md(desc))


def note(kind: str, body: str) -> None:
    fn = {
        "warn": st.warning,
        "error": st.error,
        "ok": st.success,
    }.get(kind, st.info)
    fn(_md(body))


def hero(eyebrow: str, title_html: str, desc: str, steps: list[str] | None = None) -> None:
    if eyebrow:
        st.caption(_md(eyebrow))
    st.title(_md(title_html))
    if desc:
        st.markdown(_md(desc))
    if steps:
        st.markdown(" ".join(f":blue-badge[{i}. {s}]" for i, s in enumerate(steps, 1)))
    st.write("")


def empty(title: str, desc: str = "", icon: str = "📂") -> None:
    with st.container(border=True):
        st.markdown(f"### {icon} {_md(title)}")
        if desc:
            st.caption(_md(desc))


def footer(text: str) -> None:
    st.divider()
    st.caption(_md(text))


# ================================================================ 데이터


def kpis(items: list[tuple[str, str, str]]) -> None:
    cols = st.columns(len(items))
    for col, (label, value, unit) in zip(cols, items):
        with col:
            st.metric(label, f"{value}{unit}", border=True)


def case_table(cases) -> None:
    df = pd.DataFrame(
        [
            {
                "#": i,
                "사건": c.room,
                "메시지": c.n_messages,
                "우선순위": gauge(c.priority),
                "판정": c.risk_label,
                "3요건": "충족" if c.all_requirements_met else "미충족",
                "별건 위반": len(c.law_flags),
                "관찰 기간": f"{c.period_start:%Y.%m.%d}–{c.period_end:%m.%d}",
            }
            for i, c in enumerate(cases, 1)
        ]
    )
    st.dataframe(
        df,
        hide_index=True,
        width="stretch",
        column_config={
            "#": st.column_config.NumberColumn(width=45),
            "사건": st.column_config.TextColumn(width="medium"),
            "메시지": st.column_config.NumberColumn(format="%,d건", width=85),
            "우선순위": st.column_config.ProgressColumn(
                min_value=0.0, max_value=1.0, format="%.2f",
                color=C_HIGH, width="medium",
                help="괴롭힘 성립 가능성 + 별건 법위반의 중대성",
            ),
            "판정": st.column_config.TextColumn(width=80),
            "3요건": st.column_config.TextColumn(width=75),
            "별건 위반": st.column_config.NumberColumn(format="%d건", width=85),
            "관찰 기간": st.column_config.TextColumn(width="small"),
        },
    )


def case_head(case) -> None:
    st.subheader(case.room)
    st.markdown(
        f"{tag(case.risk_label)} &nbsp; `{case.case_id}` &nbsp; "
        f"{case.period_start:%Y.%m.%d}–{case.period_end:%Y.%m.%d} · {case.span_days}일 · "
        f"메시지 {case.n_messages:,}건 · 참여자 {case.n_speakers}명"
    )
    a, b, c, d = st.columns(4)
    a.metric("행위 의심자", case.actor, border=True)
    b.metric("피해 의심 대상자", case.subject or "—", border=True)
    c.metric("3요건", "충족" if case.all_requirements_met else "미충족", border=True)
    d.metric("조사 우선순위", f"{case.priority:.2f}", border=True)


def requirements(blocks) -> None:
    cols = st.columns(len(blocks))
    for col, b in zip(cols, blocks):
        with col, st.container(border=True):
            st.caption(f"요건 {b.code[1]}")
            st.markdown(f"**{b.title}**")
            st.progress(gauge(b.score), text=f"{b.score:.2f}")
            st.caption(b.legal_basis.split("—")[-1].strip())


def metrics(block) -> None:
    df = pd.DataFrame(
        [{"지표": m.label, "값": m.display, "비고": m.note or ""} for m in block.metrics]
    )
    st.dataframe(
        df, hide_index=True, width="stretch",
        column_config={
            "지표": st.column_config.TextColumn(width="medium"),
            "값": st.column_config.TextColumn(width=110),
            "비고": st.column_config.TextColumn(width="large"),
        },
    )


def evidence(e: dict, subtle: bool = False) -> None:
    with st.container(border=True):
        st.caption(f"{e['ts']:%Y.%m.%d %H:%M} · {e['speaker']} · #{e['idx']}")
        st.markdown(f"> {e['text']}")
        tags = e.get("tags") or e.get("reasons") or []
        if tags:
            color = "orange" if subtle else "red"
            st.markdown(" ".join(f":{color}-badge[{t}]" for t in tags))


def citation(x: dict) -> None:
    with st.container(border=True):
        badge = ":green-badge[검증]" if x["verified"] else ":orange-badge[미검증]"
        st.markdown(f"**{x['citation']}** {badge}")
        st.caption(x["title"])
        body = x["text"][:300] + ("…" if len(x["text"]) > 300 else "")
        st.markdown(f"> {body}")


def heatmap(adf: pd.DataFrame, actor: str, ws: int = 9, we: int = 18) -> None:
    A = adf[adf["speaker"] == actor]
    if A.empty:
        st.info("표시할 발화가 없습니다.")
        return

    dow = ["월", "화", "수", "목", "금", "토", "일"]
    g = (
        A.groupby(["dow", "hour"]).size()
        .reindex(pd.MultiIndex.from_product([range(7), range(24)], names=["dow", "hour"]))
        .fillna(0).astype(int).reset_index(name="건수")
    )
    g["요일"] = g["dow"].map(lambda d: dow[d])
    g["구분"] = g.apply(
        lambda r: "근무시간 외" if (r["dow"] >= 5 or r["hour"] < ws or r["hour"] >= we)
        else "근무시간 내",
        axis=1,
    )

    import altair as alt

    chart = (
        alt.Chart(g[g["건수"] > 0])
        .mark_rect(cornerRadius=2)
        .encode(
            x=alt.X("hour:O", title="시각", axis=alt.Axis(values=list(range(0, 24, 3)))),
            y=alt.Y("요일:O", title=None, sort=dow),
            color=alt.Color(
                "구분:N",
                scale=alt.Scale(
                    domain=["근무시간 내", "근무시간 외"], range=[C_ACCENT, C_HIGH]
                ),
                legend=alt.Legend(title=None, orient="top"),
            ),
            opacity=alt.Opacity("건수:Q", scale=alt.Scale(range=[0.35, 1.0]), legend=None),
            tooltip=["요일", "hour", "건수", "구분"],
        )
        .properties(height=200)
    )
    st.altair_chart(chart, use_container_width=True)
    st.caption(f"최대 {int(g['건수'].max())}건 · 근무시간 {ws}–{we}시 기준")
