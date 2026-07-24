# 배포 가이드 — 심사위원 QR 접속까지

목표: **QR 하나로 심사위원·참석자가 휴대폰에서 바로 체험**하는 상태.

---

## 0. 배포처 선택 — 결론부터

| 후보 | 무료 RAM | ML 모델 구동 | 결론 |
|------|----------|--------------|------|
| **Hugging Face Spaces** | **16GB** | ✅ 여유 | **← 권장** |
| Streamlit Community Cloud | 1GB | ❌ OOM 위험 | 경량 구성만 |

`torch` + KcELECTRA(약 440MB) + 임베딩 모델(약 400MB)을 함께 올리면
Streamlit Cloud 1GB 한도에서 **거의 확실히 메모리 초과로 죽습니다.**
시연 도중 앱이 재시작되는 건 최악이므로 HF Spaces를 기본으로 잡으세요.

> 백업으로 Streamlit Cloud에 `requirements-lite.txt` 버전을 하나 더 올려두는 걸 권합니다.
> ML 없이도 **Tier 1 정량 지표는 완전히 동일하게** 동작하므로 시연이 성립합니다.

---

## 1. Hugging Face Spaces 배포 (권장)

### 1-1. Space 만들기

1. <https://huggingface.co/spaces> → **Create new Space**
2. 설정
   - Owner: 팀 계정 또는 개인
   - Space name: `chamjimayo`
   - License: `mit`
   - SDK: **Streamlit**
   - Hardware: **CPU basic (무료)**
   - Visibility: **Public** ← QR 접속하려면 필수

### 1-2. `README.md` 상단에 Space 메타데이터 추가

HF Spaces는 README 맨 위 YAML 블록을 설정으로 읽습니다.
이 저장소의 `README.md` 최상단에 아래를 붙여넣으세요.

```yaml
---
title: 참지마요
emoji: ⚖️
colorFrom: blue
colorTo: indigo
sdk: streamlit
sdk_version: 1.40.0
app_file: app.py
pinned: false
---
```

### 1-3. 업로드

```bash
git clone https://huggingface.co/spaces/<계정>/chamjimayo
cd chamjimayo

# 이 디렉터리(chamjimayo/) 내용을 통째로 복사
cp -r /path/to/chamjimayo/* .

git add .
git commit -m "참지마요 MVP"
git push
```

### 1-4. 첫 빌드 주의사항

- 첫 배포는 **10~20분** 걸립니다 (torch 설치 + 모델 다운로드). 시연 당일에 하지 마세요.
- 모델은 첫 요청 시 다운로드됩니다. 배포 후 **반드시 한 번 직접 접속해 분석을 돌려** 캐시를 데워두세요.
- Space는 **48시간 무접속 시 sleep** 상태가 됩니다. 깨어나는 데 30초~1분 걸리므로
  **발표 30분 전에 한 번 접속**해 두세요. ← 이거 놓치면 심사위원 앞에서 로딩 화면만 봅니다.

---

## 2. Streamlit Community Cloud (백업)

```bash
# GitHub 저장소에 push 후
# https://share.streamlit.io → New app
#   Repository : <계정>/chamjimayo
#   Branch     : main
#   Main file  : app.py
```

배포 전 `requirements.txt` 를 경량 버전으로 교체:

```bash
cp requirements-lite.txt requirements.txt
```

---

## 3. QR 코드 만들기

```bash
pip install "qrcode[pil]"
python scripts/make_qr.py https://huggingface.co/spaces/<계정>/chamjimayo
```

`assets/qr_demo.png` (배포물용), `assets/qr_demo_slide.png` (슬라이드용) 생성.

> 인쇄·슬라이드 삽입 전에 **실제 휴대폰으로 직접 스캔**해 보세요.
> URL 오타는 현장에서 복구가 안 됩니다.

---

## 4. 배포 전 체크리스트

```
[ ] python scripts/smoke_test.py  → ✅ 전체 통과
[ ] 데모 5종이 data/demo/ 에 들어있는가
[ ] 감독관 화면: 5건 분석 → 우선순위 정렬 정상
[ ] 감독관 화면: Tier 3 검토 큐에 demo4가 올라오는가
[ ] 피해자 화면: 진정서 초안 다운로드 정상
[ ] 사이드바 '법령 코퍼스 검증률' 확인 (미검증이면 인용에 ⚠️ 표시됨)
[ ] 모바일 화면에서 표가 깨지지 않는가 (휴대폰으로 실제 접속)
[ ] 업로드 파일 30MB 제한이 충분한가
[ ] 발표 30분 전 접속해 Space 깨우기
```

---

## 5. 시연 시나리오 (권장 3분)

| 순서 | 화면 | 말할 것 |
|------|------|---------|
| 1 | 감독관 대시보드 · 5건 분석 | "수만 줄을 전수조사하는 대신, 먼저 볼 사건을 가려냅니다" |
| 2 | 우선순위 표 | "1위는 위험도가 가장 높은 사건이 아닙니다. 임금체불·신고자 보복이 겹친 사건입니다. **성립 가능성과 조사 우선순위는 다른 판단**입니다" |
| 3 | demo0 상세 · 성립요건 탭 | "발화 독점률 81%, 시간외 발화 89%. 이건 모델 추론이 아니라 **연산**입니다. 반박하려면 대화 기록 자체를 부정해야 합니다" |
| 4 | Tier 3 검토 큐 · demo4 | "이 사건은 정량 점수 0.10입니다. 폭언이 한 건도 없거든요. 그런데 **동료 응답률은 80%인데 이 사람만 58%**입니다. 저희는 이걸 점수에 섞지 않고 감독관에게 따로 올립니다. 확률적 추론을 확정 지표와 합산하면 숫자의 신뢰가 무너지니까요" |
| 5 | 대조군 demo3 | "정상 업무 대화는 0.06입니다. 오탐이 나지 않습니다" |
| 6 | 피해자 화면 · 진정서 초안 | "같은 엔진으로 피해자에게는 진정서 초안까지 만들어 줍니다" |

**반드시 말해야 할 한 줄**
> "저희는 괴롭힘 여부를 판정하지 않습니다. 판정은 감독관이 합니다.
> 저희가 하는 건 **판단에 필요한 자료를 법적 요건에 맞춰 정리**하는 것입니다."

---

## 6. 자주 나올 질문 대비

**Q. 조작된 대화를 올리면?**
현재 MVP는 위·변조를 검증하지 않습니다. 그래서 저희 산출물은 '증거'가 아니라
'정리된 자료'입니다. 확장 계획에 이미지 OCR·메타데이터 포렌식이 들어 있습니다. (기획서 4-3)

**Q. 정상 업무 지시를 괴롭힘으로 오판하지 않나?**
대조군 데모에서 0.06이 나옵니다. 3요건 결합에 기하평균을 섞어 한 요건이라도
낮으면 종합 점수가 오르지 않도록 설계했습니다.

**Q. 개인정보는?**
분석 **전에** 마스킹합니다. 실명·연락처·주소·계좌는 엔진에 전달되지 않습니다.
화자는 삭제 대신 가명 치환하는데, 삭제하면 발화 독점률을 못 구하기 때문입니다.

**Q. LLM 환각은?**
법령 인용은 폐쇄형 코퍼스 안에서만 검색됩니다. LLM은 문장을 다듬을 뿐
숫자와 인용은 건드리지 않습니다. API 키가 없어도 리포트는 템플릿으로 나옵니다.
