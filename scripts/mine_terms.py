"""UnSmile train셋에서 '현재 어휘사전이 놓치는 독성 표현'을 채굴한다.
   - FN: non-clean인데 lexicon<0.5로 놓친 문장
   - FN에서 자주 나오고 clean에는 드문 char n-gram(2~4) = 추가 후보
"""
import sys, csv, re
from pathlib import Path
from collections import Counter
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from core.lexicon import lexicon_toxicity

TSV = sys.argv[1]
rows = []
with open(TSV, encoding="utf-8") as f:
    for d in csv.DictReader(f, delimiter="\t"):
        rows.append((d["문장"], int(d["clean"])))

han = re.compile(r"[가-힣]+")
def grams(t):
    out = set()
    for w in han.findall(t):
        for n in (2,3,4):
            for i in range(len(w)-n+1):
                out.add(w[i:i+n])
    return out

fn, clean = Counter(), Counter()
n_fn = 0
for text, cl in rows:
    toxic = cl == 0
    missed = toxic and lexicon_toxicity(text) < 0.5
    if missed:
        n_fn += 1
        for g in grams(text): fn[g] += 1
    if cl == 1:
        for g in grams(text): clean[g] += 1

print(f"놓친 독성 문장(FN): {n_fn}\n후보 (FN빈도 높고 clean엔 드문 표현):\n")
cand = []
for g, c in fn.items():
    cl = clean.get(g, 0)
    if c >= 8 and cl <= max(1, c*0.15):   # 독성 특이도 높은 것만
        cand.append((g, c, cl, c/(c+cl)))
cand.sort(key=lambda x: -x[1])
for g, c, cl, r in cand[:120]:
    print(f"{g}\t FN {c}\t clean {cl}\t 특이도 {r:.2f}")
