"""
시연용 QR 코드 생성

    pip install qrcode[pil]
    python scripts/make_qr.py https://huggingface.co/spaces/<계정>/chamjimayo

발표 슬라이드와 현장 배포물에 넣을 QR 이미지를 만듭니다.
출력: assets/qr_demo.png (1200x1200), assets/qr_demo_slide.png (여백 최소)
"""

from __future__ import annotations

import sys
from pathlib import Path

OUT_DIR = Path(__file__).resolve().parents[1] / "assets"


def main() -> int:
    if len(sys.argv) < 2:
        print(__doc__)
        return 1
    url = sys.argv[1].strip()

    try:
        import qrcode
        from qrcode.constants import ERROR_CORRECT_H
    except ImportError:
        print("qrcode 패키지가 필요합니다:  pip install 'qrcode[pil]'")
        return 1

    OUT_DIR.mkdir(exist_ok=True)

    # 현장 배포물용 — 여백 넉넉히, 오류정정 최고 등급(로고 삽입 대비)
    qr = qrcode.QRCode(version=None, error_correction=ERROR_CORRECT_H, box_size=40, border=4)
    qr.add_data(url)
    qr.make(fit=True)
    img = qr.make_image(fill_color="#1D3557", back_color="white")
    p1 = OUT_DIR / "qr_demo.png"
    img.save(p1)

    # 슬라이드용 — 여백 최소
    qr2 = qrcode.QRCode(version=None, error_correction=ERROR_CORRECT_H, box_size=40, border=1)
    qr2.add_data(url)
    qr2.make(fit=True)
    p2 = OUT_DIR / "qr_demo_slide.png"
    qr2.make_image(fill_color="#1D3557", back_color="white").save(p2)

    print(f"URL : {url}")
    print(f"생성: {p1}  ({img.size[0]}x{img.size[1]})")
    print(f"생성: {p2}")
    print("\n※ 인쇄 전 반드시 실제 휴대폰으로 스캔해 접속되는지 확인하세요.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
