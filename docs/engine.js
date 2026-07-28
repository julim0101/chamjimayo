/* 참지마요 — 브라우저 분석 엔진 (core/ 파이썬 파이프라인의 JS 포팅, 어휘 모드)
   parser → masking → Tier1 지표 → 3요건 점수 → 위험도/조사우선순위 → 증거/별건
   * 딥러닝 독성모델(KcELECTRA)은 브라우저에서 못 돌리므로 어휘사전 폴백을 사용한다
     (파이썬도 모델 미설치 시 동일 폴백. Tier1 정량 지표는 완전히 동일).            */
(function (root) {
"use strict";

/* ============================ 어휘 사전 ============================ */
const DIRECTIVE = [
  /(해라|하라|해놔|해둬|해와|해놓|놔라|둬라|와라|가라)/,
  /(가져와|보내라|보내놔|보내$|제출해|정리해|만들어서|다시\s*해|다시$)/,
  /(하세요|하십시오|해주세요|하도록|하시고)/,
  /(적어서\s*보내|보고해|보고하고|올려놔|올려|확인해|처리해|끝내|마무리해|수정해|고쳐|세팅해)/,
  /(전화해|연락해|나와|나오|들어와|출근해|앉아서)/,
  /\d{1,2}\s*시까지/,
  /(까지\s*(해|보내|제출|끝|올려|정리|다시)|오늘\s*안에|내일까지|아침까지|퇴근\s*전|주말까지)/,
  /(지금\s*(당장|다시|해|보내|와|나와|전화)|즉시|바로\s*(해|보내|와|봐))/,
  /(나\s*좀\s*보|잠깐\s*보자|이따\s*보|사무실로\s*(나와|와)|올라와|내려와)/,
];
const REBUKE = [
  /(그것도\s*못|이것도\s*못|제대로\s*못|이게\s*(다|맞|말이|보고서|시안|인계))/,
  /(왜\s*(그랬|아직|이래|이렇게|안|못|그러|이\s*모양)|누가\s*그렇게|몇\s*번을|또\s*야)/,
  /(알고는\s*있|생각은\s*하|정신\s*(있|차려)|제정신|뭐\s*하는|뭐해|뭐하다가|뭐였어)/,
  /(아직도\s*안|이\s*시간까지|왜\s*연락이\s*없|씹은\s*거|자냐|안\s*자고)/,
  /(겨우\s*이거|이\s*정도|고작)/,
];
const APOLOGY = [
  /(죄송|송구|미안|사과드|잘못했)/,
  /(알겠습니다|알겠어요|확인하겠|시정하겠|주의하겠|반성|명심|유의하겠)/,
  /(다시\s*하겠|보완하겠|수정하겠|바로\s*하겠|처리하겠|준비하겠|올리겠|보내드리겠)/,
  /^(넵|넨|네넵|네|예|알겠)[\s.!~ㅠㅜ]*$/,
];
const PROFANITY = ["씨발","시발","ㅅㅂ","존나","좆","병신","ㅂㅅ","지랄","미친놈","미친년","새끼","개새","돌대가리","머저리","등신","빡대가리","또라이","놈","년","이딴","그딴","ㅈㄹ","닥쳐"];
const DEMEANING = ["답이 없","구제불능","쓸모없","쓸데없","무능","일머리가 없","머리는 뒀다","머리가 나쁘","눈치가 그렇게 없","눈치가 없","생각이 없","기본이 안","기본도 안","실력에","그 실력","자질이","그릇이 안","수준이","수준을","성의가 없","제대로 못","그것도 못","이것도 못","못 견디","못 버텨","안 통과","초등학생이","알바를 하지","때려치워","때려치우","입만 살","못 미덥","답답해 하","답답하","버벅","늘어지","핑계는","정신력이 약","정신 상태가","정신력 문제","글러먹","창피한 줄","부끄러운 줄","얼굴에 먹칠","얼굴 뜨거","회사 얼굴에","깎아먹","민폐","이기적","꾀병","요즘 애들","요즘 것들","요즘 젊은","젊은 애들","나 때는","내가 신규때","다른 신규들은","다른 사람은 다","다들 너","너만 이래","너만 문제","나 같으면","배운 사람이","대학 어디","너 같은","이런 애","너란 사람","너는 진짜","넌 진짜","넌 그냥","넌 원래","너 때문에","네 탓","니 탓","네가 문제","니가 문제","네 뒷수습","뒷수습을 왜","밥값도 못","월급 아깝","돈 아깝","뽑아준 내가","뽑은 게 잘못","받아준 게"];
const THREAT = ["그만둬","그만두는 게","관둬","나가","나갈 거면","싫으면 나가","잘릴","자를","자르는 거","짤릴","책임져","책임인 거","각오해","각오하고","인사고과","평가에 반영","성과급? 꿈도","재계약","다음 계약","매장","이 바닥 좁","업계에서","어디 가서 일하나","어디 가서도 못","가만 안 둬","가만 안 두","두고 보자","얼굴 보지 말자","손해배상","월급은 없","월급도 없","월급에서 깔","대가는 각오","알아서 해","대신할 사람 널렸","너 대신","안 잡아"];
const DENIAL = ["사람이 되","인간이 되","왜 사냐","왜 살아","존재야","배은망덕","은혜도 모르","은혜를 몰라","고마운 줄 알아","알아주질 않","놀이터야","장난하는 것도"];
const TOXIC_LEXICON = {"욕설·비속어":PROFANITY,"능력·인격 비하":DEMEANING,"협박·불이익 암시":THREAT,"인격 부정":DENIAL};
const TOXIC_WEIGHTS = {"욕설·비속어":1.0,"능력·인격 비하":0.75,"협박·불이익 암시":0.9,"인격 부정":0.9};
const SUBTLE = {
  "업무 배제":[/(빼고|제외하고|둘이서|우리끼리|따로\s*(얘기|보)|메인으로\s*가|호흡이\s*좋)/,/(안\s*해도\s*(돼|되|됩니다)|신경\s*쓰지\s*마|나서지\s*마|손대지\s*마)/,/(지켜보|아직\s*이르|부담스럽지\s*않|무리하지\s*마|편할\s*대로)/],
  "의견 묵살":[/(앞서가지\s*마|너무\s*나서|의욕은\s*좋은데|그건\s*나중에|일단\s*됐)/,/(됐고|그만하고|나중에\s*얘기|다음에\s*하|이번엔\s*아니)/],
  "가스라이팅":[/(다\s*(너|당신|그쪽|소미씨|지은|민경)?\s*(잘되라고|생각해서|크라고|위해서))/,/(교육이야|배려한\s*거|나중에\s*고마|고생을\s*하는데|챙기는\s*거)/,/(예민(하게|한)|오해(한|하는)|기분\s*탓|피해의식|괴롭혔어)/,/(다들\s*그렇게|나만\s*그런\s*게\s*아니|모두가\s*알|다\s*내\s*편)/,/(사회생활\s*(배우|가르|처음|그렇게)|이런\s*것도\s*다)/],
  "공개 망신":[/(다들\s*보는데|다른\s*(쌤|사람|팀원|사람들)\s*(다|들|한테)|공개적으로)/,/(다들\s*잘\s*들어|다들\s*(너|알)|뒤에서\s*뭐라)/],
  "신고 억제·보복 암시":[/(신고(라도|할|하)|노동청|인사팀에|고발|진정)/,/(누가\s*네?\s*말을\s*믿|뒤에서\s*(찌르|딴소리)|일러바|고자질)/,/(짜고\s*이러|둘이\s*짜|얘기\s*한마디라도)/],
};
const LABOR = {
  "임금 미지급·감액":{law:"근로기준법 제43조(임금 지급) · 제36조(금품 청산)",pats:[/(월급(은|도)?\s*없|월급에서\s*(깔|까|공제)|급여에서\s*(깔|차감))/,/(손해\s*난\s*거.*(월급|급여)|일한\s*거.*월급도\s*없)/]},
  "연장·휴일근로수당 미지급":{law:"근로기준법 제56조(연장·야간 및 휴일 근로)",pats:[/(야근수당.*(없|안\s*줘|그런\s*거)|수당.*무슨\s*수당)/,/(주말인데.*나와|주말.*사무실로|휴일.*출근)/]},
  "근로시간 위반":{law:"근로기준법 제50조(근로시간) · 제53조(연장 근로의 제한)",pats:[/(주\s*5일.*(대기업|여긴\s*아니)|퇴근할\s*생각\s*하지\s*마)/,/(새벽\s*\d{1,2}시에\s*나와|끝낼\s*때까지\s*퇴근)/]},
  "신고자 불이익 처우":{law:"근로기준법 제76조의3 제6항(신고를 이유로 한 불이익 처우 금지)",pats:[/(노동청.*(가봐|가서)|신고.*(해봐|할\s*생각)|뒤에서\s*찌르.*각오)/,/(인사팀에\s*뭐라|어디\s*가서\s*일하나|매장시키)/]},
  "직장 내 괴롭힘 조치의무 위반":{law:"근로기준법 제76조의3(직장 내 괴롭힘 발생 시 조치)",pats:[/(내가\s*널\s*괴롭|괴롭힘\s*아니|다\s*교육이야)/]},
};
const anyMatch = (pats, t) => pats.some(p => p.test(t));
const isDirective = t => anyMatch(DIRECTIVE, t);
const isRebuke = t => anyMatch(REBUKE, t);
const isApology = t => anyMatch(APOLOGY, t);
function toxicHits(t){ const h=[]; for(const cat in TOXIC_LEXICON) for(const w of TOXIC_LEXICON[cat]) if(t.indexOf(w)>=0) h.push([cat,w]); return h; }
function lexToxicity(t){ const h=toxicHits(t); if(!h.length) return 0; let s=0; const seen=new Set(); for(const [cat,w] of h){ if(seen.has(w))continue; seen.add(w); s+=(TOXIC_WEIGHTS[cat]||0.5);} return Math.min(1, 1-Math.pow(0.25,s)); }
function subtleHits(t){ const o=[]; for(const cat in SUBTLE) if(anyMatch(SUBTLE[cat],t)) o.push(cat); return o; }
function laborHits(t){ const o=[]; for(const name in LABOR) if(anyMatch(LABOR[name].pats,t)) o.push([name,LABOR[name].law]); return o; }

/* ============================ 개인정보 마스킹 ============================ */
const PII = [
  ["[주민번호]",/\b\d{6}\s*[-–]\s*[1-4]\d{6}\b/g],
  ["[연락처]",/\b01[0-9][-.\s]?\d{3,4}[-.\s]?\d{4}\b/g],
  ["[연락처]",/\b0\d{1,2}[-.\s]\d{3,4}[-.\s]\d{4}\b/g],
  ["[이메일]",/\b[\w.+-]+@[\w-]+\.[\w.]{2,}\b/g],
  ["[카드번호]",/\b\d{4}[-\s]\d{4}[-\s]\d{4}[-\s]\d{4}\b/g],
  ["[링크]",/https?:\/\/\S+/g],
];
function maskPII(t){ let s=t; for(const [tag,re] of PII) s=s.replace(re,tag); return s; }

/* ============================ 파서 ============================ */
const RE_DATE = /^-{3,}\s*(\d{4})년\s*(\d{1,2})월\s*(\d{1,2})일\s*[월화수목금토일]요일\s*-{3,}\s*$/;
const RE_PC = /^\[([^\]]{1,40})\]\s*\[(오전|오후)\s*(\d{1,2}):(\d{2})\]\s*(.*)$/;
const RE_MOBILE = /^(\d{4})년\s*(\d{1,2})월\s*(\d{1,2})일\s*(오전|오후)\s*(\d{1,2}):(\d{2}),\s*(.{1,40}?)\s*:\s*(.*)$/;
const RE_ROOM = /^"?(.+?)"?\s*(?:님과의?)?\s*카카오톡\s*대화\s*$/;
const SYSTEM = ["님이 들어왔습니다","님이 나갔습니다","님을 초대했습니다","채팅방 관리자가","저장한 메시지","운영정책을 위반한"];
const isSystem = t => SYSTEM.some(p => t.indexOf(p) >= 0);
function to24(ampm,h,m){ let hh=h%12; if(ampm==="오후")hh+=12; return [hh,m]; }

function parseKakao(raw){
  const lines = raw.replace(/\r\n/g,"\n").replace(/\r/g,"\n").split("\n");
  const meta = { room:"", format:"" };
  for(const line of lines.slice(0,6)){ const m=RE_ROOM.exec(line.trim()); if(m) meta.room=m[1].replace(/님과/g,"").trim(); }
  const recs=[]; let cur=null;
  for(const line of lines){
    const s=line.trim();
    let m=RE_DATE.exec(s);
    if(m){ cur=[+m[1],+m[2],+m[3]]; continue; }
    if(!s) continue;
    m=RE_PC.exec(line);
    if(m && cur){ meta.format=meta.format||"pc"; const [hh,mm]=to24(m[2],+m[3],+m[4]);
      recs.push({speaker:m[1].trim(), ts:new Date(cur[0],cur[1]-1,cur[2],hh,mm), text:m[5].trim()}); continue; }
    m=RE_MOBILE.exec(line);
    if(m){ meta.format=meta.format||"mobile"; const [hh,mm]=to24(m[4],+m[5],+m[6]);
      recs.push({speaker:m[7].trim(), ts:new Date(+m[1],+m[2]-1,+m[3],hh,mm), text:m[8].trim()}); continue; }
    if(recs.length && !isSystem(s) && cur && !s.startsWith("---") && s.indexOf("카카오톡 대화")<0)
      recs[recs.length-1].text += "\n"+s;
  }
  let msgs = recs.filter(r => !isSystem(r.text));
  msgs.sort((a,b)=> a.ts-b.ts);
  msgs.forEach((r,i)=>{ r.idx=i; });
  meta.messages=msgs.length;
  return {msgs, meta};
}

/* ============================ 통계 유틸 ============================ */
const mean = a => a.length ? a.reduce((x,y)=>x+y,0)/a.length : 0;
const clip=(x,lo,hi)=>Math.max(lo,Math.min(hi,x));
const norm=(x,lo,hi)=> hi<=lo?0:clip((x-lo)/(hi-lo),0,1);
function wavg(vals,ws){ let s=0,w=0; for(let i=0;i<vals.length;i++){s+=vals[i]*ws[i];w+=ws[i];} return w?s/w:0; }
function median(a){ if(!a.length) return NaN; const b=a.slice().sort((x,y)=>x-y); const n=b.length,m=n>>1; return n%2?b[m]:(b[m-1]+b[m])/2; }
function stdSample(a){ if(a.length<2) return 0; const mu=mean(a); return Math.sqrt(a.reduce((s,x)=>s+(x-mu)*(x-mu),0)/(a.length-1)); }
const uniq = a => Array.from(new Set(a));
function disp(v,u){ if(u==="%") return (v*100).toFixed(1)+"%"; if(u==="회"||u==="일"||u==="건") return v.toFixed(0)+u; return v.toFixed(2)+u; }
function mk(key,label,value,unit,note){ return {key,label,value,unit,note:note||"",display:disp(value,unit)}; }
function hash6(s){ let h=0; for(let i=0;i<s.length;i++){ h=(h*31+s.charCodeAt(i))>>>0; } return ("000000"+h.toString(16).toUpperCase()).slice(-6); }

/* ============================ 주석 ============================ */
function annotate(msgs, maskNames){
  // 마스킹: PII는 항상, 이름은 옵션(데모는 실명 유지)
  const speakersByCount = uniq(msgs.map(m=>m.speaker));
  const aliasMap={}; speakersByCount.forEach((sp,i)=>aliasMap[sp]="화자 "+String.fromCharCode(65+i));
  const A=msgs.map(m=>{
    let text=maskPII(m.text);
    const sp = maskNames ? (aliasMap[m.speaker]||m.speaker) : m.speaker;
    return {...m, text, speaker:sp};
  });
  // 플래그
  for(let i=0;i<A.length;i++){
    const m=A[i], t=m.text, ts=m.ts;
    const hh=ts.getHours(), mm=ts.getMinutes(), tod=hh*60+mm;
    const dow=(ts.getDay()+6)%7;
    m.hour=hh; m.dow=dow;
    m.date=ts.getFullYear()+"-"+(ts.getMonth()+1)+"-"+ts.getDate();
    m.is_workday = dow<=4;
    const in_hours = tod>=540 && tod<=1080;
    m.is_offhours = !(m.is_workday && in_hours);
    m.is_holiday = !m.is_workday;
    m.is_night = (tod>=1320)||(tod<=360);
    m.is_directive = isDirective(t);
    m.is_rebuke = isRebuke(t);
    m.is_apology = isApology(t);
    m.tox = lexToxicity(t);
    m.subtle = subtleHits(t);
    m.laws = laborHits(t);
    m.nChars = t.length;
    m.gap_min = i===0 ? 0 : (A[i].ts - A[i-1].ts)/60000;
  }
  // burst (연속 동일화자)
  let bstart=0;
  for(let i=1;i<=A.length;i++){
    if(i===A.length || A[i].speaker!==A[bstart].speaker){
      const size=i-bstart; for(let j=bstart;j<i;j++) A[j].burst_size=size; bstart=i;
    }
  }
  return A;
}

/* ============================ 역할 추정 ============================ */
function inferRoles(A){
  const by={}; for(const m of A){ (by[m.speaker]=by[m.speaker]||[]).push(m); }
  const total=A.length;
  const prof={};
  for(const sp in by){ const g=by[sp];
    prof[sp]={ msgs:g.length,
      dir: mean(g.map(x=>x.is_directive?1:0)),
      reb: mean(g.map(x=>x.is_rebuke?1:0)),
      apo: mean(g.map(x=>x.is_apology?1:0)),
      off: mean(g.map(x=>x.is_offhours?1:0)),
      tox: mean(g.map(x=>x.tox)),
      share: g.length/total };
  }
  for(const sp in prof){ const p=prof[sp];
    p.actor = p.share*1 + p.dir*1.2 + p.reb*0.8 + p.tox*1.5 + p.off*0.5 - p.apo*1.0;
    p.subject = p.apo*1.5 - p.dir*1.0 - p.tox*1.0 + (1-p.share)*0.3;
  }
  const sps=Object.keys(prof);
  let actor=sps[0]; for(const s of sps) if(prof[s].actor>prof[actor].actor) actor=s;
  let subject=""; const others=sps.filter(s=>s!==actor);
  if(others.length){ subject=others[0]; for(const s of others) if(prof[s].subject>prof[subject].subject) subject=s; }
  return {actor, subject, prof};
}

/* ============================ 선택적 무응답 ============================ */
function selectiveResponse(A, actor, subject, win=120){
  const nsp=uniq(A.map(m=>m.speaker)).length;
  if(nsp<3 || !subject) return {applicable:false};
  const rates={};
  for(let i=0;i<A.length;i++){
    const s=A[i].speaker, t=A[i].ts; if(s===actor) continue;
    let answered=false;
    for(let j=i+1;j<A.length;j++){
      if((A[j].ts-t)/60000 > win) break;
      if(A[j].speaker===actor){ answered=true; break; }
    }
    const r=rates[s]=rates[s]||{total:0,answered:0,ignored:[]};
    r.total++; if(answered) r.answered++; else r.ignored.push(A[i].idx);
  }
  for(const s in rates) rates[s].rate = rates[s].total?rates[s].answered/rates[s].total:0;
  const subj=rates[subject];
  if(!subj || subj.total<3) return {applicable:false};
  const others=Object.keys(rates).filter(s=>s!==subject && rates[s].total>=3).map(s=>rates[s].rate);
  const peer=others.length?mean(others):0;
  return {applicable:true, subject_rate:subj.rate, peer_rate:peer, gap:Math.max(0,peer-subj.rate), ignored:subj.ignored};
}

/* ============================ 3요건 ============================ */
function req1(A, actor, subject){
  const Ax=A.filter(m=>m.speaker===actor), S=subject?A.filter(m=>m.speaker===subject):[];
  const total=A.length;
  const ms= total?Ax.length/total:0;
  const a_dir=mean(Ax.map(x=>x.is_directive?1:0)), s_dir=mean(S.map(x=>x.is_directive?1:0));
  const dir_gap=Math.max(0,a_dir-s_dir);
  const a_apo=mean(Ax.map(x=>x.is_apology?1:0)), s_apo=mean(S.map(x=>x.is_apology?1:0));
  const apo_gap=Math.max(0,s_apo-a_apo);
  const burst=Ax.filter(x=>x.burst_size>=3);
  const burst_ratio=Ax.length?burst.length/Ax.length:0;
  const sMed=median(S.filter(x=>x.gap_min>=0&&x.gap_min<=240).map(x=>x.gap_min));
  const aMed=median(Ax.filter(x=>x.gap_min>=0&&x.gap_min<=240).map(x=>x.gap_min));
  const latency=(isNaN(sMed)||isNaN(aMed))?0:(aMed-sMed);
  const totC=A.reduce((s,x)=>s+x.nChars,0); const cs=totC?Ax.reduce((s,x)=>s+x.nChars,0)/totC:0;
  const score=wavg([norm(ms,.5,.85),norm(dir_gap,.05,.4),norm(apo_gap,.05,.35),norm(burst_ratio,.1,.5),norm(latency,0,60)],[.3,.25,.2,.15,.1]);
  return {code:"R1",title:"지위 또는 관계의 우위",basis:"근로기준법 제76조의2 — 「직장에서의 지위 또는 관계 등의 우위를 이용하여」",score,
    metrics:[mk("speech_share","발화 독점률 (건수)",ms,"%",`전체 ${total}건 중 ${Ax.length}건을 ${actor} 발화`),
      mk("char_share","발화 독점률 (분량)",cs,"%","글자 수 기준 점유율"),
      mk("directive_gap","지시 발화 비대칭",dir_gap,"%",`${actor} ${(a_dir*100).toFixed(0)}% vs 상대 ${(s_dir*100).toFixed(0)}%`),
      mk("apology_gap","사과·수용 표현 비대칭",apo_gap,"%",`대상자 ${(s_apo*100).toFixed(0)}% vs ${actor} ${(a_apo*100).toFixed(0)}%`),
      mk("burst_ratio","일방적 연속 발화 비율",burst_ratio,"%","상대 응답 없이 3회 이상 연속 발화"),
      mk("latency_gap","응답 지연 격차",latency,"분","대상자가 더 빨리 응답할수록 응답 압박이 크다")]};
}
function req2(A, actor){
  const Ax=A.filter(m=>m.speaker===actor);
  const tsAll=A.map(m=>m.ts); const span=Math.max(1, Math.floor((Math.max(...tsAll)-Math.min(...tsAll))/86400000)+1);
  const weeks=Math.max(1, span/7);
  const off=Ax.filter(x=>x.is_offhours);
  const offDemand=off.filter(x=>x.is_directive||x.is_rebuke);
  const night=Ax.filter(x=>x.is_night), holi=Ax.filter(x=>x.is_holiday);
  const off_ratio=Ax.length?off.length/Ax.length:0;
  const offDays=uniq(off.map(x=>x.date)); const periodicity=offDays.length/span;
  let regularity=0;
  if(offDays.length>=3){
    const ds=offDays.map(d=>{const[y,mo,dd]=d.split("-").map(Number);return new Date(y,mo-1,dd);}).sort((a,b)=>a-b);
    const gaps=[]; for(let i=1;i<ds.length;i++) gaps.push((ds[i]-ds[i-1])/86400000);
    const mu=mean(gaps); const cv=mu?stdSample(gaps)/mu:0; regularity=clip(1-cv,0,1);
  }
  const rd=offDemand.length/weeks, rn=night.length/weeks, rh=holi.length/weeks;
  const score=wavg([norm(off_ratio,.10,.55),norm(rd,.3,4),norm(rn,.2,3),norm(rh,.2,2.5),norm(periodicity,.05,.40),norm(regularity,.20,.80)],[.25,.25,.15,.12,.13,.10]);
  return {code:"R2",title:"업무상 적정범위를 넘는 행위",basis:"근로기준법 제76조의2 — 「업무상 적정범위를 넘어」",score,
    metrics:[mk("offhours_ratio","근무시간 외 발화 비율",off_ratio,"%",`${actor}의 발화 ${Ax.length}건 중 ${off.length}건이 근무시간 외`),
      mk("offhours_demand_rate","주당 시간외 지시·응답요구",rd,"회/주",`관찰 ${span}일간 총 ${offDemand.length}건`),
      mk("night_rate","주당 심야(22–06시) 연락",rn,"회/주",`총 ${night.length}건`),
      mk("holiday_rate","주당 휴일 연락",rh,"회/주",`총 ${holi.length}건`),
      mk("periodicity","시간외 연락 발생일 비율",periodicity,"%",`관찰 ${span}일 중 ${offDays.length}일에 발생`),
      mk("regularity","반복 주기의 규칙성",regularity,"","간격의 변동이 작을수록 일회성이 아닌 지속적 패턴")]};
}
function req3(A, actor, subject, sel){
  const Ax=A.filter(m=>m.speaker===actor);
  const toxic=Ax.filter(x=>x.tox>=0.5); const density=Ax.length?toxic.length/Ax.length:0;
  const mean_tox=mean(Ax.map(x=>x.tox));
  const tsAll=A.map(m=>m.ts); const span=Math.max(1, Math.floor((Math.max(...tsAll)-Math.min(...tsAll))/86400000)+1);
  const weeks=Math.max(1,span/7);
  const rebuke=Ax.filter(x=>x.is_rebuke); const r_reb=rebuke.length/weeks;
  const nsp=uniq(A.map(m=>m.speaker)).length; const pub=nsp>=3;
  const S=subject?A.filter(m=>m.speaker===subject):[];
  const burden=S.length?S.filter(x=>x.is_offhours).length/S.length:0;
  const parts=[norm(density,.05,.45),norm(mean_tox,.05,.5),norm(r_reb,.3,4),pub?1:0,norm(burden,.1,.5)];
  const ws=[.35,.2,.2,.1,.15];
  if(sel && sel.applicable){ parts.push(norm(sel.gap,.1,.5)); ws.push(.25); }
  const score=wavg(parts,ws);
  const subtleN=Ax.filter(x=>x.subtle.length>0).length;
  const metrics=[mk("toxic_density","모욕·독성 발화 밀도",density,"%",`${actor}의 발화 ${Ax.length}건 중 ${toxic.length}건이 독성 임계치 초과`),
    mk("toxic_mean","평균 독성 확률",mean_tox,"","0에 가까울수록 중립, 1에 가까울수록 공격적"),
    mk("rebuke_rate","주당 질책성 추궁",r_reb,"회/주",`총 ${rebuke.length}건`),
    mk("public_exposure","제3자 노출 여부",pub?1:0,"",`참여자 ${nsp}명 — 공개적 질책은 정신적 고통을 가중`),
    mk("subject_offhours_burden","대상자의 시간외 응답 부담",burden,"%",""),
    mk("subtle_count","정황 후보 발화 (Tier 3)",subtleN,"건","배제·묵살·가스라이팅 의심 — 최종 판단은 사람")];
  if(sel&&sel.applicable) metrics.push(mk("selective_ignore","선택적 무응답 격차",sel.gap,"%",`대상자 응답률 ${(sel.subject_rate*100).toFixed(0)}% vs 동료 평균 ${(sel.peer_rate*100).toFixed(0)}%`));
  return {code:"R3",title:"신체적·정신적 고통 또는 근무환경 악화",basis:"근로기준법 제76조의2 — 「신체적·정신적 고통을 주거나 근무환경을 악화시키는 행위」",score,metrics};
}

/* ============================ 종합/우선순위 ============================ */
function combine(blocks){ const s=blocks.map(b=>b.score); if(!s.length)return 0;
  const arith=mean(s); const geo=Math.pow(s.reduce((p,x)=>p*clip(x,1e-6,1),1), 1/s.length);
  return clip(0.5*arith+0.5*geo,0,1); }
const RISK=[[.60,"높음","#C1121F"],[.38,"중간","#E36414"],[.20,"낮음","#5C6B73"],[0,"관측 없음","#8D99AE"]];
function riskLevel(s){ for(const [th,lab,col] of RISK) if(s>=th) return {label:lab,color:col}; return {label:"관측 없음",color:"#8D99AE"}; }
const SEVERITY={"신고자 불이익 처우":0.20,"임금 미지급·감액":0.12,"연장·휴일근로수당 미지급":0.10,"근로시간 위반":0.08,"직장 내 괴롭힘 조치의무 위반":0.06};
function priorityScore(risk, flags){ let bonus=0; const reasons=[]; for(const name in flags){ bonus+=(SEVERITY[name]!==undefined?SEVERITY[name]:0.05); reasons.push(name);} return {priority:clip(risk+bonus,0,1),reasons}; }

/* ============================ 증거 ============================ */
function collectLawFlags(A){ const f={}; for(const m of A) for(const [n,l] of m.laws) f[n]=l; return f; }
function keyEvidence(A, actor, limit=12){
  const Ax=A.filter(m=>m.speaker===actor); if(!Ax.length) return [];
  Ax.forEach(r=>{ r._w = r.tox*2 + ((r.is_offhours&&r.is_directive)?1.2:0) + (r.is_night?0.8:0) + (r.is_holiday?0.5:0) + (r.is_rebuke?0.6:0) + r.laws.length*1.5; });
  let top=Ax.slice().sort((a,b)=>b._w-a._w).slice(0,limit).filter(r=>r._w>0.3).sort((a,b)=>a.ts-b.ts);
  return top.map(r=>{ const reasons=[];
    if(r.tox>=0.5) reasons.push("독성 "+r.tox.toFixed(2));
    if(r.is_offhours&&r.is_directive) reasons.push("근무시간 외 지시");
    if(r.is_night) reasons.push("심야 연락");
    if(r.is_holiday) reasons.push("휴일 연락");
    if(r.is_rebuke) reasons.push("질책성 추궁");
    for(const [n] of r.laws) reasons.push("⚖ "+n);
    return {idx:r.idx, ts:r.ts, speaker:r.speaker, text:r.text, reasons};
  });
}
function subtleEvidence(A, actor, limit=10){
  return A.filter(m=>m.speaker===actor && m.subtle.length>0).slice(0,limit)
    .map(r=>({idx:r.idx,ts:r.ts,speaker:r.speaker,text:r.text,tags:r.subtle}));
}

/* ============================ 최상위 ============================ */
function analyze(raw, opts){
  opts=opts||{};
  const maskNames = opts.maskNames!==undefined?opts.maskNames:false;
  const {msgs, meta}=parseKakao(raw);
  if(!msgs.length) throw new Error("카카오톡 대화를 인식하지 못했습니다. 텍스트로 내보낸 .txt인지 확인해 주세요.");
  const A=annotate(msgs, maskNames);
  const {actor, subject}=inferRoles(A);
  const sel=selectiveResponse(A, actor, subject);
  const blocks=[req1(A,actor,subject), req2(A,actor), req3(A,actor,subject,sel)];
  const risk=combine(blocks);
  const {label,color}=riskLevel(risk);
  const flags=collectLawFlags(A);
  const {priority,reasons}=priorityScore(risk, flags);
  const subtle=subtleEvidence(A,actor);
  const key=keyEvidence(A,actor);
  const needsReview = risk<0.38 && subtle.length>=3;
  const rs={}; blocks.forEach(b=>rs[b.code]=b.score);
  let reviewReason="";
  if(needsReview){
    const tags=Array.from(new Set(subtle.flatMap(e=>e.tags))).sort();
    reviewReason=`정량 지표는 낮으나(${risk.toFixed(2)}) 정황 후보 ${subtle.length}건 관측 — ${tags.join(', ')}`;
    if(sel.applicable && sel.gap>=0.15)
      reviewReason+=` / 선택적 무응답 격차 ${(sel.gap*100).toFixed(0)}%p(대상자 ${(sel.subject_rate*100).toFixed(0)}% vs 동료 ${(sel.peer_rate*100).toFixed(0)}%)`;
  }
  const tsAll=A.map(m=>m.ts); const start=new Date(Math.min(...tsAll)), end=new Date(Math.max(...tsAll));
  return {
    case_id:"CJ-"+hash6(raw),
    room:meta.room||opts.name||"대화", source:opts.name||"",
    actor, subject, n_messages:A.length, n_speakers:uniq(A.map(m=>m.speaker)).length,
    period_start:start, period_end:end, span_days:Math.floor((end-start)/86400000)+1,
    blocks, risk_score:risk, risk_label:label, risk_color:color,
    priority, priority_reasons:reasons, law_flags:flags,
    key_evidence:key, subtle_evidence:subtle,
    needs_human_review:needsReview, review_reason:reviewReason,
    requirement_scores:rs, tox_backend:"lexicon", rag_backend:"—",
    all_requirements_met: blocks.every(b=>b.score>=0.35),
  };
}

const API={analyze, parseKakao};
if(typeof module!=="undefined" && module.exports) module.exports=API;
root.ChamEngine=API;
})(typeof window!=="undefined"?window:globalThis);
