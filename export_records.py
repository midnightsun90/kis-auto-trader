"""
거래 기록 산출 — KIS 일별 체결내역 + 잔고를 조회해 records/ 에 저장.

자동매매로 실제 체결이 발생한 날(장중 trader.py 실행 후) 돌리면,
공식 체결내역(거래 기록)과 그날 잔고 스냅샷을 JSON + 사람이 읽는 Markdown으로 남긴다.

사용:
  python export_records.py            # 오늘 날짜
  python export_records.py 20260615   # 특정일(YYYYMMDD)
"""

import json
import os
import sys
from datetime import datetime

from config import load_config
from kis_api import KISApi

D = os.path.dirname(os.path.abspath(__file__))
REC_DIR = os.path.join(D, "records")


def g(row, *keys):
    """여러 후보 키 중 먼저 값이 있는 것을 반환(KIS 필드명 변형 대비)."""
    for k in keys:
        v = row.get(k)
        if v not in (None, ""):
            return v
    return ""


def to_markdown(date, env, ccld, bal):
    lines = [
        f"# 자동매매 거래 기록 — {date}",
        "",
        f"- 환경: {env}",
        f"- 체결/주문 건수: {len(ccld)}",
        "",
        "## 체결 내역",
        "",
        "| 시각 | 종목 | 구분 | 주문수량 | 체결수량 | 체결평균가 | 체결금액 |",
        "|---|---|---|---|---|---|---|",
    ]
    for r in ccld:
        lines.append(
            "| {tm} | {nm}({cd}) | {sb} | {oq} | {cq} | {pr} | {amt} |".format(
                tm=g(r, "ord_tmd"),
                nm=g(r, "prdt_name"),
                cd=g(r, "pdno"),
                sb=g(r, "sll_buy_dvsn_cd_name", "sll_buy_dvsn_cd"),
                oq=g(r, "ord_qty"),
                cq=g(r, "tot_ccld_qty"),
                pr=g(r, "avg_prvs", "ccld_prvs", "ord_unpr"),
                amt=g(r, "tot_ccld_amt"),
            )
        )
    s = bal.get("summary", {})
    lines += [
        "",
        "## 잔고 스냅샷",
        "",
        f"- 예수금(dnca_tot_amt): {s.get('dnca_tot_amt', '')}",
        f"- 총평가금액(tot_evlu_amt): {s.get('tot_evlu_amt', '')}",
        f"- 평가손익합(evlu_pfls_smtl_amt): {s.get('evlu_pfls_smtl_amt', '')}",
        f"- 보유종목 수: {len(bal.get('holdings', []))}",
    ]
    return "\n".join(lines)


def main():
    date = sys.argv[1] if len(sys.argv) > 1 else datetime.now().strftime("%Y%m%d")
    cfg = load_config()
    api = KISApi(cfg)

    ccld = api.daily_ccld(date)
    bal = api.balance()

    os.makedirs(REC_DIR, exist_ok=True)
    json_path = os.path.join(REC_DIR, f"records_{date}.json")
    md_path = os.path.join(REC_DIR, f"records_{date}.md")

    with open(json_path, "w", encoding="utf-8") as f:
        json.dump({"date": date, "env": cfg.env_name, "executions": ccld, "balance": bal},
                  f, ensure_ascii=False, indent=2)
    with open(md_path, "w", encoding="utf-8") as f:
        f.write(to_markdown(date, cfg.env_name, ccld, bal))

    print(f"저장 완료: {json_path}")
    print(f"저장 완료: {md_path}")
    print(f"체결/주문 건수: {len(ccld)}")


if __name__ == "__main__":
    main()
