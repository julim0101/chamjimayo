"""
참지마요 — UI 컴포넌트

구조: 웹사이트. 상단 고정 네비 + 중앙 정렬 콘텐츠 + 푸터.
      Streamlit 사이드바는 쓰지 않는다.

톤: 단일 다크 테마.
    배경 #101317, 본문 #E3E6EA (순백 아님 — 눈부심 방지).
    강조색은 파랑 하나, 나머지는 위험도 신호에만 쓴다.

규칙
  1. 장식하지 않는다. 영문 eyebrow, 대문자 자간 라벨, 마케팅 헤드라인 금지.
  2. 타입 스케일은 5단계만. 24 / 17 / 14.5 / 13 / 11.5
  3. 간격은 8의 배수. 섹션 48, 카드 패딩 24, 요소 12.
  4. 모든 카드는 같은 반경(10px), 같은 배경(--surf).
  5. 숫자는 tabular. 표는 왼쪽 정렬, 수치만 오른쪽 정렬.
"""

from __future__ import annotations

import html

import pandas as pd
import streamlit as st

_FONT = (
    '<link rel="stylesheet" as="style" crossorigin '
    'href="https://cdn.jsdelivr.net/gh/orioncactus/pretendard@v1.3.9/dist/web/'
    'variable/pretendardvariable-dynamic-subset.min.css" />'
)

CSS = f"""{_FONT}
<style>
:root {{
  --bg:      #101317;
  --surf:    #171B21;
  --surf-2:  #1D222A;
  --line:    #252B34;
  --line-2:  #2E3541;

  --fg:      #E3E6EA;
  --fg-2:    #A2AAB5;
  --fg-3:    #6F7885;
  --fg-4:    #4B535E;

  --accent:  #4C8DFF;
  --high:    #E5484D;
  --mid:     #E5A03A;
  --low:     #7D8794;
  --none:    #545C68;

  --r: 10px;
  --nav-h: 56px;
}}

html, body, .stApp, button, input, textarea, select {{
  font-family: "Pretendard Variable", Pretendard, -apple-system, BlinkMacSystemFont,
               system-ui, "Segoe UI", sans-serif !important;
  -webkit-font-smoothing: antialiased;
}}
.stApp {{ background: var(--bg); color: var(--fg); }}
#MainMenu, footer, header[data-testid="stHeader"] {{ display: none !important; }}
section[data-testid="stSidebar"] {{ display: none !important; }}

.main .block-container {{
  padding: calc(var(--nav-h) + 36px) 32px 96px;
  max-width: 1180px; margin: 0 auto;
}}
p, div, span, li, label {{ font-size: 14.5px; }}
::selection {{ background: var(--accent); color: #fff; }}
::-webkit-scrollbar {{ width: 10px; height: 10px; }}
::-webkit-scrollbar-track {{ background: transparent; }}
::-webkit-scrollbar-thumb {{ background: var(--line-2); border-radius: 9px; }}

/* ───────── 상단 네비 ───────── */
.nav {{
  position: fixed; top: 0; left: 0; right: 0; height: var(--nav-h); z-index: 100;
  background: rgba(16,19,23,.88); backdrop-filter: blur(10px);
  border-bottom: 1px solid var(--line);
  display: flex; align-items: center; padding: 0 32px;
}}
.nav-in {{ max-width: 1180px; margin: 0 auto; width: 100%; display: flex;
           align-items: center; gap: 28px; }}
.nav-b {{ font-size: 16px; font-weight: 700; color: var(--fg); letter-spacing: -.03em; }}
.nav-b i {{ font-style: normal; color: var(--accent); }}
.nav-s {{ margin-left: auto; font-size: 12.5px; color: var(--fg-3); }}
.nav-s b {{ color: var(--fg-2); font-weight: 600; }}

/* 네비 링크 = Streamlit radio */
div[data-testid="stRadio"].navsel {{ position: fixed; top: 0; left: 0; right: 0;
  z-index: 101; height: var(--nav-h); pointer-events: none; }}
div[data-testid="stRadio"].navsel > div {{ pointer-events: auto; }}

/* ───────── 페이지 헤더 ───────── */
.ph {{ margin-bottom: 32px; }}
.ph h1 {{ margin: 0; font-size: 24px; font-weight: 700; letter-spacing: -.03em; color: var(--fg); }}
.ph p {{ margin: 8px 0 0; color: var(--fg-3); font-size: 14.5px; line-height: 1.65; max-width: 76ch; }}

/* ───────── 섹션 ───────── */
.sec {{ margin: 48px 0 16px; }}
.sec:first-child {{ margin-top: 0; }}
.sec h2 {{ margin: 0; font-size: 17px; font-weight: 650; letter-spacing: -.02em; color: var(--fg); }}
.sec p {{ margin: 6px 0 0; color: var(--fg-3); font-size: 13px; line-height: 1.65; max-width: 82ch; }}

/* ───────── 카드 / 그리드 ───────── */
.card {{ background: var(--surf); border: 1px solid var(--line); border-radius: var(--r); padding: 24px; }}
.g2 {{ display: grid; grid-template-columns: repeat(2,1fr); gap: 12px; }}
.g3 {{ display: grid; grid-template-columns: repeat(3,1fr); gap: 12px; }}
.g4 {{ display: grid; grid-template-columns: repeat(4,1fr); gap: 12px; }}

/* KPI */
.kpi {{ background: var(--surf); border: 1px solid var(--line); border-radius: var(--r); padding: 18px 20px; }}
.kpi span {{ display: block; font-size: 13px; color: var(--fg-3); }}
.kpi b {{ display: block; font-size: 26px; font-weight: 700; letter-spacing: -.035em;
          margin-top: 6px; font-variant-numeric: tabular-nums; color: var(--fg); }}
.kpi b em {{ font-style: normal; font-size: 13px; font-weight: 500; color: var(--fg-3); margin-left: 3px; }}

/* ───────── 표 ───────── */
.tb {{ width: 100%; border-collapse: collapse; background: var(--surf);
       border: 1px solid var(--line); border-radius: var(--r); overflow: hidden; }}
.tb th {{ font-size: 12px; font-weight: 600; color: var(--fg-3); text-align: left;
          padding: 12px 16px; background: var(--surf-2); border-bottom: 1px solid var(--line); white-space: nowrap; }}
.tb td {{ padding: 14px 16px; border-bottom: 1px solid var(--line); color: var(--fg-2); vertical-align: middle; }}
.tb tr:last-child td {{ border-bottom: none; }}
.tb tr:hover td {{ background: var(--surf-2); }}
.tb .n {{ font-variant-numeric: tabular-nums; text-align: right; font-weight: 650; color: var(--fg); }}
.tb .idx {{ color: var(--fg-4); font-variant-numeric: tabular-nums; width: 28px; }}
.tb .nm {{ color: var(--fg); font-weight: 600; }}
.tb .sub {{ display: block; font-size: 12px; color: var(--fg-4); margin-top: 2px; font-weight: 400; }}

/* 게이지 */
.gg {{ height: 4px; background: var(--line-2); border-radius: 4px; overflow: hidden; min-width: 80px; }}
.gg i {{ display: block; height: 100%; border-radius: 4px; }}

/* 태그 */
.tag {{ display: inline-block; font-size: 12px; font-weight: 600; padding: 3px 9px;
        border-radius: 6px; white-space: nowrap; }}
.tag.q {{ background: var(--surf-2); color: var(--fg-2); font-weight: 500; margin: 0 4px 4px 0; }}

/* ───────── 요건 ───────── */
.req {{ background: var(--surf); border: 1px solid var(--line); border-radius: var(--r); padding: 20px; }}
.req > span {{ font-size: 12px; color: var(--fg-4); }}
.req > h3 {{ margin: 6px 0 0; font-size: 14.5px; font-weight: 600; color: var(--fg-2);
             line-height: 1.5; min-height: 44px; }}
.req > b {{ display: block; font-size: 30px; font-weight: 700; letter-spacing: -.04em;
            margin: 14px 0 10px; font-variant-numeric: tabular-nums; }}
.req > p {{ margin: 12px 0 0; font-size: 12px; color: var(--fg-4); line-height: 1.55; }}

/* 지표 목록 */
.mr {{ display: flex; justify-content: space-between; align-items: baseline; gap: 14px;
       padding: 11px 0; border-bottom: 1px solid var(--line); }}
.mr:last-child {{ border-bottom: none; }}
.mr .l {{ font-size: 13px; color: var(--fg-2); }}
.mr .n {{ font-size: 12px; color: var(--fg-4); margin-top: 2px; line-height: 1.5; }}
.mr .v {{ font-size: 13.5px; font-weight: 650; color: var(--fg); white-space: nowrap;
          font-variant-numeric: tabular-nums; }}

/* ───────── 증거 ───────── */
.ev {{ padding: 16px 0; border-bottom: 1px solid var(--line); }}
.ev:last-child {{ border-bottom: none; }}
.ev .m {{ font-size: 12px; color: var(--fg-4); margin-bottom: 8px; font-variant-numeric: tabular-nums; }}
.ev .q {{ font-size: 14.5px; line-height: 1.7; color: var(--fg); }}
.ev .t {{ margin-top: 10px; }}

/* ───────── 인용 ───────── */
.ct {{ padding: 16px 0; border-bottom: 1px solid var(--line); }}
.ct:last-child {{ border-bottom: none; }}
.ct .s {{ font-size: 14px; font-weight: 650; color: var(--fg); }}
.ct .t {{ font-size: 13px; color: var(--fg-3); margin-top: 2px; }}
.ct .b {{ font-size: 13px; color: var(--fg-2); line-height: 1.75; margin-top: 8px; }}

/* ───────── 알림 ───────── */
.note {{ background: var(--surf); border: 1px solid var(--line); border-left: 3px solid var(--fg-4);
         border-radius: var(--r); padding: 14px 16px; font-size: 13.5px; line-height: 1.65;
         color: var(--fg-2); margin-bottom: 12px; }}
.note b {{ color: var(--fg); font-weight: 650; }}
.note.warn {{ border-left-color: var(--mid); }}
.note.info {{ border-left-color: var(--accent); }}

/* ───────── 사건 헤더 ───────── */
.ch {{ background: var(--surf); border: 1px solid var(--line); border-radius: var(--r);
       padding: 22px 24px; display: flex; justify-content: space-between; gap: 32px; align-items: flex-start; }}
.ch h2 {{ margin: 0; font-size: 18px; font-weight: 650; letter-spacing: -.025em; color: var(--fg); }}
.ch .m {{ margin-top: 6px; font-size: 12.5px; color: var(--fg-3); font-variant-numeric: tabular-nums; }}
.ch .p {{ display: flex; gap: 28px; margin-top: 18px; }}
.ch .p div span {{ display: block; font-size: 12px; color: var(--fg-4); }}
.ch .p div b {{ display: block; font-size: 14px; font-weight: 650; color: var(--fg); margin-top: 3px; }}
.ch .s {{ text-align: right; flex: none; }}
.ch .s b {{ display: block; font-size: 34px; font-weight: 700; letter-spacing: -.045em;
            line-height: 1; font-variant-numeric: tabular-nums; }}
.ch .s span {{ display: block; font-size: 12.5px; font-weight: 600; margin-top: 5px; }}

/* ───────── 히트맵 ───────── */
.hm table {{ border-collapse: separate; border-spacing: 3px; }}
.hm td.c {{ width: 18px; height: 18px; border-radius: 3px; }}
.hm td.d {{ font-size: 11.5px; color: var(--fg-4); padding-right: 8px; text-align: right; }}
.hm th.h {{ font-size: 10.5px; color: var(--fg-4); padding-bottom: 5px; }}
.hm .lg {{ display: flex; align-items: center; gap: 6px; margin-top: 14px; font-size: 12px; color: var(--fg-3); }}
.hm .lg i {{ width: 11px; height: 11px; border-radius: 3px; display: inline-block; }}

/* ───────── 푸터 ───────── */
.ft {{ margin-top: 72px; padding-top: 24px; border-top: 1px solid var(--line);
       font-size: 12.5px; color: var(--fg-4); line-height: 1.75; }}

/* ───────── Streamlit 위젯 ───────── */
.stTabs [data-baseweb="tab-list"] {{ gap: 2px; border-bottom: 1px solid var(--line); }}
.stTabs [data-baseweb="tab"] {{ height: 38px; padding: 0 14px; font-size: 13.5px;
  font-weight: 550; color: var(--fg-3); background: transparent; border: none; }}
.stTabs [aria-selected="true"] {{ color: var(--fg) !important; font-weight: 650; }}
.stTabs [data-baseweb="tab-highlight"] {{ background: var(--accent); height: 2px; }}
.stTabs [data-baseweb="tab-panel"] {{ padding-top: 20px; }}

.stButton > button, .stDownloadButton > button {{
  border-radius: 8px; font-weight: 600; font-size: 14px; padding: 10px 18px;
  border: 1px solid var(--line-2); background: var(--surf-2); color: var(--fg);
  letter-spacing: -.015em;
}}
.stButton > button:hover {{ border-color: var(--fg-4); background: var(--line); }}
.stButton > button[kind="primary"], .stDownloadButton > button[kind="primary"] {{
  background: var(--accent); border-color: var(--accent); color: #fff;
}}
div[data-testid="stExpander"] {{ border: 1px solid var(--line); background: var(--surf); border-radius: var(--r); }}
div[data-testid="stExpander"] summary {{ font-size: 13.5px; color: var(--fg-2); }}
div[data-testid="stFileUploader"] section {{ border: 1px dashed var(--line-2);
  border-radius: var(--r); background: var(--surf); padding: 22px; }}
div[data-testid="stTextInput"] input,
div[data-baseweb="select"] > div, div[data-baseweb="input"] {{
  background: var(--surf) !important; border-color: var(--line-2) !important;
  border-radius: 8px !important; color: var(--fg) !important;
}}
div[data-testid="stDataFrame"] {{ border-radius: var(--r); overflow: hidden; }}
hr {{ border-color: var(--line); margin: 32px 0; }}
.stProgress > div > div > div {{ background: var(--accent); }}
</style>"""


def inject() -> None:
    st.markdown(CSS, unsafe_allow_html=True)


# ================================================================ 유틸

def _e(s) -> str:
    return html.escape(str(s))


def _w(h: str) -> None:
    st.markdown(h, unsafe_allow_html=True)


def sig(label: str) -> str:
    return {"높음": "var(--high)", "중간": "var(--mid)", "낮음": "var(--low)"}.get(
        label, "var(--none)"
    )


# ================================================================ 레이아웃


def nav(status: str = "") -> None:
    s = f'<div class="nav-s">{status}</div>' if status else ""
    _w(
        f'<div class="nav"><div class="nav-in">'
        f'<div class="nav-b">참지마요</div>{s}</div></div>'
    )


def page_head(title: str, desc: str = "") -> None:
    p = f"<p>{_e(desc)}</p>" if desc else ""
    _w(f'<div class="ph"><h1>{_e(title)}</h1>{p}</div>')


def section(title: str, desc: str = "") -> None:
    p = f"<p>{_e(desc)}</p>" if desc else ""
    _w(f'<div class="sec"><h2>{_e(title)}</h2>{p}</div>')


def note(kind: str, body: str) -> None:
    _w(f'<div class="note {kind}">{body}</div>')


def footer(text: str) -> None:
    _w(f'<div class="ft">{text}</div>')


# ================================================================ 컴포넌트


def kpis(items: list[tuple[str, str, str]]) -> None:
    cells = "".join(
        f'<div class="kpi"><span>{_e(l)}</span><b>{_e(v)}<em>{_e(u)}</em></b></div>'
        for l, v, u in items
    )
    _w(f'<div class="g4">{cells}</div>')


def gauge(v: float, color: str) -> str:
    return f'<div class="gg"><i style="width:{max(0,min(1,v))*100:.1f}%;background:{color}"></i></div>'


def tag(label: str, color: str) -> str:
    return f'<span class="tag" style="background:{color}22;color:{color}">{_e(label)}</span>'


def case_table(cases) -> None:
    head = (
        "<tr><th></th><th>사건</th><th>우선순위</th><th></th><th>판정</th>"
        "<th>3요건</th><th>별건 위반</th><th>관찰 기간</th></tr>"
    )
    rows = []
    for i, c in enumerate(cases, 1):
        col = sig(c.risk_label)
        flags = (
            "".join(f'<span class="tag q">{_e(n)}</span>' for n in list(c.law_flags)[:2])
            + (f'<span class="tag q">+{len(c.law_flags)-2}</span>' if len(c.law_flags) > 2 else "")
        ) or '<span style="color:var(--fg-4)">—</span>'
        rows.append(
            f'<tr><td class="idx">{i}</td>'
            f'<td><span class="nm">{_e(c.room)}</span>'
            f'<span class="sub">{_e(c.case_id)} · 메시지 {c.n_messages:,}건</span></td>'
            f"<td>{gauge(c.priority, col)}</td>"
            f'<td class="n" style="color:{col}">{c.priority:.2f}</td>'
            f"<td>{tag(c.risk_label, col)}</td>"
            f'<td style="color:{"var(--fg-2)" if c.all_requirements_met else "var(--fg-4)"}">'
            f'{"충족" if c.all_requirements_met else "미충족"}</td>'
            f"<td>{flags}</td>"
            f'<td style="color:var(--fg-3);font-variant-numeric:tabular-nums">'
            f"{c.period_start:%Y.%m.%d}–{c.period_end:%m.%d}</td></tr>"
        )
    _w(f'<table class="tb"><thead>{head}</thead><tbody>{"".join(rows)}</tbody></table>')


def case_head(case) -> None:
    col = sig(case.risk_label)
    _w(
        f'<div class="ch"><div>'
        f"<h2>{_e(case.room)}</h2>"
        f'<div class="m">{_e(case.case_id)} · {case.period_start:%Y.%m.%d}–'
        f"{case.period_end:%Y.%m.%d} · {case.span_days}일 · 메시지 {case.n_messages:,}건 · "
        f"참여자 {case.n_speakers}명</div>"
        f'<div class="p">'
        f"<div><span>행위 의심자</span><b>{_e(case.actor)}</b></div>"
        f"<div><span>피해 의심 대상자</span><b>{_e(case.subject or '—')}</b></div>"
        f"<div><span>3요건 충족</span><b>{'충족' if case.all_requirements_met else '미충족'}</b></div>"
        f"<div><span>조사 우선순위</span><b>{case.priority:.2f}</b></div>"
        f"</div></div>"
        f'<div class="s"><b style="color:{col}">{case.risk_score:.2f}</b>'
        f'<span style="color:{col}">{_e(case.risk_label)}</span></div></div>'
    )


def requirements(blocks) -> None:
    cards = []
    for b in blocks:
        col = (
            "var(--high)" if b.score >= 0.6
            else "var(--mid)" if b.score >= 0.38
            else "var(--low)" if b.score >= 0.2
            else "var(--none)"
        )
        basis = b.legal_basis.split("—")[-1].strip()
        cards.append(
            f'<div class="req"><span>요건 {b.code[1]}</span><h3>{_e(b.title)}</h3>'
            f'<b style="color:{col}">{b.score:.2f}</b>{gauge(b.score, col)}'
            f"<p>{_e(basis)}</p></div>"
        )
    _w(f'<div class="g3">{"".join(cards)}</div>')


def metrics(block) -> None:
    rows = []
    for m in block.metrics:
        n = f'<div class="n">{_e(m.note)}</div>' if m.note else ""
        rows.append(
            f'<div class="mr"><div><div class="l">{_e(m.label)}</div>{n}</div>'
            f'<div class="v">{_e(m.display)}</div></div>'
        )
    _w(f'<div class="card" style="padding:4px 20px">{"".join(rows)}</div>')


def evidence(e: dict, subtle: bool = False) -> None:
    col = "var(--mid)" if subtle else "var(--high)"
    tags = "".join(
        f'<span class="tag" style="background:{col}1A;color:{col};margin-right:4px">{_e(t)}</span>'
        for t in (e.get("tags") or e.get("reasons") or [])
    )
    _w(
        f'<div class="ev"><div class="m">{e["ts"]:%Y.%m.%d %H:%M} · {_e(e["speaker"])} · #{e["idx"]}</div>'
        f'<div class="q">{_e(e["text"])}</div><div class="t">{tags}</div></div>'
    )


def citation(x: dict) -> None:
    b = (
        tag("검증", "var(--low)") if x["verified"] else tag("미검증", "var(--mid)")
    )
    body = x["text"][:300] + ("…" if len(x["text"]) > 300 else "")
    _w(
        f'<div class="ct"><div class="s">{_e(x["citation"])} {b}</div>'
        f'<div class="t">{_e(x["title"])}</div><div class="b">{_e(body)}</div></div>'
    )


def heatmap(adf: pd.DataFrame, actor: str, ws: int = 9, we: int = 18) -> None:
    A = adf[adf["speaker"] == actor]
    if A.empty:
        st.info("표시할 발화가 없습니다.")
        return
    g = (
        A.groupby(["dow", "hour"]).size()
        .reindex(pd.MultiIndex.from_product([range(7), range(24)], names=["dow", "hour"]))
        .fillna(0).astype(int)
    )
    mx = max(1, int(g.max()))
    dow = ["월", "화", "수", "목", "금", "토", "일"]
    hdr = "<tr><th></th>" + "".join(
        f'<th class="h">{h if h % 6 == 0 else ""}</th>' for h in range(24)
    ) + "</tr>"
    rows = []
    for d in range(7):
        cells = []
        for h in range(24):
            n = int(g.loc[(d, h)])
            off = d >= 5 or h < ws or h >= we
            if n == 0:
                cells.append('<td class="c" style="background:var(--surf-2)"></td>')
            else:
                a = 0.32 + 0.68 * (n / mx)
                rgb = "229,72,77" if off else "76,141,255"
                cells.append(f'<td class="c" style="background:rgba({rgb},{a:.2f})"></td>')
        rows.append(f'<tr><td class="d">{dow[d]}</td>{"".join(cells)}</tr>')
    _w(
        f'<div class="hm"><table>{hdr}{"".join(rows)}</table>'
        f'<div class="lg"><i style="background:rgba(76,141,255,.85)"></i>근무시간 내'
        f'<i style="background:rgba(229,72,77,.85);margin-left:12px"></i>근무시간 외'
        f'<span style="margin-left:12px;color:var(--fg-4)">최대 {mx}건</span></div></div>'
    )
