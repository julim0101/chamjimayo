/* 참지마요 — 리포트 생성 (core/report.py 포팅)
   inspector(c): 감독관용 증거 분석 보고서(.md)
   complaint(c, {complainant,workplace,office}): 피해자용 진정서 초안(.md)          */
(function (root) {
"use strict";

const DISCLAIMER = "본 문서는 대화 로그의 통계적 분석 결과이며, 직장 내 괴롭힘의 성립 여부를 판정하는 문서가 아닙니다. 사실관계의 진위 판별과 법적 판단은 근로감독관·노무사·변호사 등 권한 있는 전문가가 수행합니다. 분석은 제출된 대화 기록에 한정되며, 기록 외의 정황(대면 발언, 업무 배경, 당사자 관계 등)은 반영되지 않았습니다.";

const two=n=>String(n).padStart(2,"0");
const fmtDt=d=>d.getFullYear()+"-"+two(d.getMonth()+1)+"-"+two(d.getDate())+" "+two(d.getHours())+":"+two(d.getMinutes());
const fmtD=d=>d.getFullYear()+"-"+two(d.getMonth()+1)+"-"+two(d.getDate());
const shorten=(t,n)=>{ t=String(t).replace(/\s+/g," ").trim(); return t.length<=n?t:t.slice(0,n-1).replace(/\S+$/,"").trim()+" …"; };
const cell=t=>String(t).replace(/\|/g,"\\|").replace(/\n/g," ");

const EXCLUDE=new Set(["subtle_count","public_exposure","toxic_mean","regularity"]);
const USCALE={"%":1.0,"회/주":0.25,"분":0.01,"":0.5};
function topMetrics(block,n){
  const cand=block.metrics.filter(m=>m.value>0 && !EXCLUDE.has(m.key));
  return cand.sort((a,b)=>-(a.value*(USCALE[a.unit]!==undefined?USCALE[a.unit]:0.3))+(b.value*(USCALE[b.unit]!==undefined?USCALE[b.unit]:0.3))).slice(0,n);
}

function summaryParagraph(c){
  const s=c.requirement_scores, P=[];
  const strong=c.blocks.filter(b=>b.score>=0.6), weak=c.blocks.filter(b=>b.score<0.35);
  P.push(`관찰 기간 ${c.span_days}일 동안 총 ${c.n_messages.toLocaleString()}건의 메시지를 분석한 결과, 종합 위험도는 **${c.risk_score.toFixed(2)}(${c.risk_label})** 으로 산출되었습니다.`);
  if(c.all_requirements_met){
    P.push(`근로기준법 제76조의2의 3대 성립요건 모두에서 최소 기준 이상의 지표가 관측되었습니다(우위성 ${s.R1.toFixed(2)} · 적정범위 초과 ${s.R2.toFixed(2)} · 고통·환경악화 ${s.R3.toFixed(2)}).`);
  } else if(weak.length){
    P.push(`다만 ${weak.map(b=>b.code+"("+b.title+")").join(", ")} 요건에서는 유의미한 지표가 관측되지 않아, 현재 자료만으로는 3요건 동시 충족을 뒷받침하기 어렵습니다.`);
  }
  if(strong.length){
    const top=strong.reduce((a,b)=>b.score>a.score?b:a);
    const t=topMetrics(top,1);
    if(t.length) P.push(`가장 강한 신호는 ${top.title} 영역의 '${t[0].label} ${t[0].display}' 입니다.`);
  }
  const flags=Object.keys(c.law_flags);
  if(flags.length) P.push(`아울러 ${flags.join(", ")} 등 ${flags.length}건의 별건 법위반 단서가 함께 관측되었습니다.`);
  if(c.needs_human_review) P.push(`⚠️ ${c.review_reason}`);
  return P.join(" ");
}

function inspector(c){
  const L=[];
  L.push("# 직장 내 괴롭힘 정량 분석 보고서","");
  L.push(`**사건번호** \`${c.case_id}\`  ·  **생성일시** ${fmtDt(new Date())}`,"");
  L.push("| 항목 | 내용 |","|------|------|");
  L.push(`| 분석 대상 | ${c.room} |`);
  L.push(`| 관찰 기간 | ${fmtD(c.period_start)} ~ ${fmtD(c.period_end)} (${c.span_days}일) |`);
  L.push(`| 총 메시지 | ${c.n_messages.toLocaleString()}건 · 참여자 ${c.n_speakers}명 |`);
  L.push(`| 행위 의심자 | ${c.actor} |`);
  L.push(`| 피해 의심 대상자 | ${c.subject||"—"} |`);
  L.push(`| **종합 위험도** | **${c.risk_score.toFixed(2)} / 1.00 — ${c.risk_label}** |`);
  L.push(`| 조사 우선순위 | ${c.priority.toFixed(2)} |`);
  L.push(`| 3요건 동시 충족 | ${c.all_requirements_met?"예":"아니오"} |`,"");
  L.push("## 1. 분석 요약","",summaryParagraph(c),"");
  L.push("## 2. 근로기준법 제76조의2 성립요건별 지표","");
  for(const b of c.blocks){
    L.push(`### ${b.code}. ${b.title} — ${b.score.toFixed(2)}`,"",`> ${b.basis}`,"");
    L.push("| 지표 | 값 | 산출 근거 |","|------|-----|-----------|");
    for(const m of b.metrics) L.push(`| ${m.label} | **${m.display}** | ${m.note||"—"} |`);
    L.push("");
  }
  L.push("## 3. 핵심 증거 발화","");
  if(!c.key_evidence.length){ L.push("_임계치를 초과하는 발화가 관측되지 않았습니다._"); }
  else{
    L.push("Tier 1(확정 지표)·Tier 2(분류 지표) 기준 상위 발화입니다.","");
    L.push("| # | 일시 | 발화자 | 내용 | 판정 근거 |","|---|------|--------|------|-----------|");
    for(const e of c.key_evidence){ let t=cell(e.text); if(t.length>60)t=t.slice(0,60)+"…";
      L.push(`| ${e.idx} | ${fmtDt(e.ts)} | ${e.speaker} | ${t} | ${e.reasons.join(", ")} |`); }
  }
  L.push("");
  L.push("## 4. Tier 3 정황 후보 — 사람의 판단이 필요한 항목","");
  if(!c.subtle_evidence.length){ L.push("_해당 없음._"); }
  else{
    L.push("아래 항목은 **확정 지표가 아닙니다.** 맥락 추론으로 추출한 후보이며, 종합 위험도 점수에는 반영되지 않았습니다. 조사관의 확인이 필요합니다.","");
    L.push("| # | 일시 | 발화자 | 내용 | 정황 유형 |","|---|------|--------|------|-----------|");
    for(const e of c.subtle_evidence){ let t=cell(e.text); if(t.length>60)t=t.slice(0,60)+"…";
      L.push(`| ${e.idx} | ${fmtDt(e.ts)} | ${e.speaker} | ${t} | ${e.tags.join(", ")} |`); }
  }
  L.push("");
  L.push("## 5. 별건 법위반 단서","");
  const flags=Object.entries(c.law_flags);
  if(!flags.length){ L.push("_해당 없음._"); }
  else{
    L.push("대화 중 직장 내 괴롭힘 외의 노동관계법 위반이 의심되는 표현이 관측되었습니다. 괴롭힘 성립 여부와 별개로 확인이 필요합니다.","");
    L.push("| 의심 유형 | 관련 조항 |","|-----------|-----------|");
    for(const [n,l] of flags) L.push(`| ${n} | ${l} |`);
  }
  L.push("");
  L.push("## 6. 관련 법령","","각 요건의 판단 근거 조문과 별건 위반 관련 조항입니다.","");
  for(const b of c.blocks) L.push(`- **${b.code}** ${b.basis}`);
  for(const [n,l] of flags) L.push(`- **[별건]** ${n} — ${l}`);
  L.push("");
  L.push("## 7. 처리 정보","","| 항목 | 값 |","|------|-----|");
  L.push(`| 독성 분류 백엔드 | \`${c.tox_backend}\` (브라우저 어휘 폴백) |`);
  L.push("| 개인정보 마스킹 | 연락처·이메일·계좌·카드·주민번호 등 자동 마스킹 |","");
  L.push("---","",`> ⚖️ ${DISCLAIMER}`);
  return L.join("\n");
}

function evidenceTips(c){
  const s=c.requirement_scores, t=[];
  if((s.R1||0)<0.4) t.push("지위·관계의 우위를 뒷받침할 조직도, 직급 확인 자료, 업무 지시 계통 자료");
  if((s.R2||0)>=0.4) t.push("근무시간 외 지시가 실제 업무 수행으로 이어졌음을 보여줄 근태 기록·출퇴근 기록");
  if((s.R3||0)>=0.4) t.push("정신적 고통을 입증할 진료 기록, 상담 기록, 휴직·병가 신청서");
  if(c.n_speakers>=3) t.push("같은 대화방에 있던 동료의 진술서 또는 확인서");
  if(Object.keys(c.law_flags).length) t.push("임금명세서, 근로계약서, 연장근로 동의서 등 근로조건 관련 서류");
  t.push("대화 기록은 발췌본이 아닌 원본 전체를 함께 보관·제출");
  return t;
}

function complaint(c, opts){
  opts=opts||{};
  const complainant=opts.complainant||"(성명)", workplace=opts.workplace||"(사업장명)", office=opts.office||"(관할 지방고용노동청)";
  const L=[];
  L.push("# 진 정 서","");
  L.push("## 1. 당사자","","| 구분 | 내용 |","|------|------|");
  L.push(`| 진정인 | ${complainant} |`);
  L.push(`| 피진정인 | ${c.actor} |`);
  L.push(`| 사업장 | ${workplace} |`);
  L.push(`| 접수 관서 | ${office} |`,"");
  L.push("## 2. 진정 취지","");
  L.push(`진정인은 ${fmtD(c.period_start)}부터 ${fmtD(c.period_end)}까지 피진정인으로부터 근로기준법 제76조의2에서 정한 직장 내 괴롭힘에 해당하는 행위를 반복적으로 받았기에, 이에 대한 조사와 시정 조치를 요청드립니다.`,"");
  L.push("## 3. 진정 이유","");
  L.push(`진정인은 위 기간 중 피진정인과 메신저를 통해 총 ${c.n_messages.toLocaleString()}건의 대화를 주고받았으며, 해당 기록을 분석한 결과 다음과 같은 사실이 확인됩니다.`,"");
  for(const b of c.blocks){
    L.push(`### ${b.code}. ${b.title}`,"");
    for(const m of topMetrics(b,3)) L.push(`- ${m.label}: **${m.display}**`+(m.note?` — ${m.note}`:""));
    L.push("");
  }
  L.push("### 구체적 사실관계","");
  if(!c.key_evidence.length){ L.push("_(대화 기록에서 임계치를 초과하는 발화가 확인되지 않았습니다.)_"); }
  else{
    c.key_evidence.slice(0,8).forEach((e,i)=>{
      L.push(`${i+1}. **${fmtDt(e.ts)}** — ${e.speaker}`);
      L.push(`   > ${e.text.replace(/\n/g," ")}`);
      L.push(`   (${e.reasons.join(", ")})`,"");
    });
  }
  const flags=Object.entries(c.law_flags);
  if(flags.length){
    L.push("### 그 밖에 확인이 필요한 사항","");
    for(const [n,l] of flags) L.push(`- ${n} — ${l} 위반 여부 확인 요청`);
    L.push("");
  }
  L.push("## 4. 요청 사항","");
  L.push("1. 위 사실관계에 대한 조사");
  L.push("2. 근로기준법 제76조의3에 따른 사용자의 조사·조치 의무 이행 여부 확인");
  L.push("3. 조사 기간 중 진정인에 대한 보호조치(근무장소 변경 등) 검토");
  L.push("4. 진정 제기를 이유로 한 불이익 처우 방지(근로기준법 제76조의3 제6항)","");
  L.push("## 5. 첨부 자료","");
  L.push("1. 메신저 대화 기록 원본 (.txt)");
  L.push(`2. 정량 분석 보고서 (사건번호 ${c.case_id})`);
  L.push("3. (해당 시) 진료 기록, 근무일지, 동료 진술서 등","");
  L.push("## 6. 보완하면 좋을 자료","");
  for(const tip of evidenceTips(c)) L.push(`- ${tip}`);
  L.push("");
  const now=new Date();
  L.push(`${now.getFullYear()}년 ${two(now.getMonth()+1)}월 ${two(now.getDate())}일`,"");
  L.push(`진정인 ${complainant} (서명 또는 날인)`,"");
  L.push("---","",`> ⚖️ ${DISCLAIMER} 본 초안은 제출 전 노무사·변호사의 검토를 권고합니다.`);
  return L.join("\n");
}

const API={inspector, complaint};
if(typeof module!=="undefined" && module.exports) module.exports=API;
root.ChamReport=API;
})(typeof window!=="undefined"?window:globalThis);
