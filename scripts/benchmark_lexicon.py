"""
어휘엔진(core/lexicon) 벤치마크 — Korean UnSmile 데이터셋 대비

우리 어휘 기반 독성 점수(lexicon_toxicity)가 공개 혐오표현 데이터셋의
'악플/욕설' 라벨을 얼마나 잡아내는지 정밀도/재현율/F1로 검증한다.

주의(정직):
  - UnSmile은 '소수자 혐오' 중심 데이터셋이고, 우리 타깃은 '직장 갑질/비하'다.
    두 도메인이 겹치는 구간은 사실상 '악플/욕설' 카테고리다. 그래서 이 벤치마크는
    우리 엔진의 '욕설·모욕 탐지력'을 재는 것이지, 직장 특화 비하 성능이 아니다.
  - 데이터셋 라이선스: CC-BY-NC-ND 4.0 (비상업·연구 목적 사용).

실행:
  # (권장) 전체 valid셋 — 네트워크 필요
  pip install datasets
  python scripts/benchmark_lexicon.py

  # 로컬 TSV로 실행
  python scripts/benchmark_lexicon.py path/to/unsmile_valid_v1.0.tsv
"""
from __future__ import annotations
import sys, csv
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from core.lexicon import lexicon_toxicity  # noqa: E402

THRESH = 0.5
ABUSE = "악플/욕설"


def load_rows(argv):
    # 1) 로컬 TSV 경로 인자
    for a in argv[1:]:
        p = Path(a)
        if p.exists():
            rows = []
            with open(p, encoding="utf-8") as f:
                r = csv.DictReader(f, delimiter="\t")
                for d in r:
                    rows.append((d["문장"], int(d[ABUSE]), int(d["clean"])))
            return rows, f"TSV {p.name}"
    # 2) huggingface datasets
    try:
        from datasets import load_dataset
        ds = load_dataset("smilegate-ai/kor_unsmile")["valid"]
        return [(x["문장"], int(x[ABUSE]), int(x["clean"])) for x in ds], "HF valid (전체)"
    except Exception as e:
        print(f"[datasets 미사용: {e}] → 내장 예비 샘플로 실행합니다.\n")
        return SAMPLE, f"내장 샘플 N={len(SAMPLE)} (예비)"


def evaluate(rows, positive="abuse"):
    tp = fp = fn = tn = 0
    for text, abuse, clean in rows:
        y = 1 if (abuse == 1 if positive == "abuse" else clean == 0) else 0
        pred = 1 if lexicon_toxicity(text) >= THRESH else 0
        if pred and y: tp += 1
        elif pred and not y: fp += 1
        elif not pred and y: fn += 1
        else: tn += 1
    prec = tp / (tp + fp) if tp + fp else 0.0
    rec = tp / (tp + fn) if tp + fn else 0.0
    f1 = 2 * prec * rec / (prec + rec) if prec + rec else 0.0
    acc = (tp + tn) / len(rows) if rows else 0.0
    return dict(tp=tp, fp=fp, fn=fn, tn=tn, precision=prec, recall=rec, f1=f1, accuracy=acc)


def main():
    rows, src = load_rows(sys.argv)
    print(f"데이터: {src} · 총 {len(rows)}문장 · 임계값 {THRESH}\n")
    for pos, name in [("abuse", "악플/욕설 탐지"), ("clean", "비(非)clean = 욕설·혐오 전체 탐지")]:
        m = evaluate(rows, pos)
        print(f"[{name}]")
        print(f"  정밀도 {m['precision']:.3f} · 재현율 {m['recall']:.3f} · F1 {m['f1']:.3f} · 정확도 {m['accuracy']:.3f}")
        print(f"  (TP {m['tp']} · FP {m['fp']} · FN {m['fn']} · TN {m['tn']})\n")
    print("해석: 어휘 단독은 명시적 욕설(씨발·좆·새끼 등)에 정밀도가 높지만,")
    print("      코드화된 표현(극혐·찐따·무뇌충 등)은 놓쳐 재현율에 한계가 있다.")
    print("      → 정식판은 이 한계를 KcELECTRA(UnSmile) 모델과의 앙상블로 보완한다.")


# UnSmile valid셋에서 발췌한 예비 샘플 (text, 악플/욕설, clean)
SAMPLE = [
    ("여자들은 취미가 애낳는건가.. 취미를 좀 가져라", 0, 0),
    ("저새끼 슈스케나온새끼잖아 ㅋㅋㅋ", 1, 0),
    ("두번째는 펨섭이라그래", 0, 1),
    ("민주화보소 ㅋㅋㅋㅋ찐따저장소답네", 1, 0),
    ("재크 나이프 하니까 진중곤이 생각나네요", 0, 1),
    ("뭐 어쩌라고 시발", 1, 0),
    ("혐오가 당연한 건 없습니다", 0, 1),
    ("한남 답이 없노", 0, 0),
    ("빨건 빨아야지", 0, 1),
    ("좆만이 집 좋네", 1, 0),
    ("조현병과 정신분열은 다릅니다", 0, 1),
    ("야이 점쟁이새끼야 더러운글 그만올리고점사나 잘봐라", 1, 0),
    ("마 계섀끼야 마 니 등킨도나쓰 무봤나 으이", 1, 0),
    ("웃챙ㅋㅋㅋㅋ관심많노이기", 0, 1),
    ("액정 두드려 깰뻔했노 조오옷팔", 1, 0),
    ("영대병원네거리도 괜찮드만", 0, 1),
    ("막짤 파일명 보소 ㅋㅋㅋ", 0, 1),
    ("형수님 잘계시죠?", 0, 1),
    ("진짜 극혐이네요", 1, 0),
    ("남자 여자 모두 응원합니다", 0, 1),
    ("한쪽에만 도덕성을 요구하는거 보고도 이상함을 못느낀다면 무뇌충이노", 1, 0),
    ("기억하기 싫은데?", 0, 1),
    ("나도 호신술 배워야겠노 글 잘 봤다 이기야", 0, 1),
    ("diskcopy a: b:", 0, 1),
    ("사이비 종교", 1, 0),
    ("시바.. 저게 법이냐....", 1, 0),
    ("판결을 지지합니다", 0, 1),
    ("레알 개새끼네", 1, 0),
    ("결혼은 사기", 1, 0),
    ("합법 씨발ㅋㅋ컨셉이라도 개웃기네ㅋㅋㅋㅋ", 1, 0),
    ("구속여부는 무슨....징역90년 구형하면 되겠구만...C", 1, 0),
    ("보기좆네요 일베는 씨발아찌 찌찌를 응원합니다^^", 1, 0),
    ("저건 진짜 악마새끼네", 1, 0),
    ("정말 국격 떨어진다...다른 나라에서 대한민국을 뭐라 보겠盧...", 0, 1),
    ("이게 일상이지", 0, 1),
    ("미국처럼 이름 불러", 0, 1),
    ("똥꼬충 다 죽여야된다.", 0, 0),
    ("이 개슬람 개새끼가 병원에서 지가 테러했다고 자랑을 했단다.", 0, 0),
    ("전라도 시발 다 불태웠으면", 0, 0),
    ("애만 불상하지 뭐 애가 무슨 죄가 있어", 0, 1),
]

if __name__ == "__main__":
    main()
