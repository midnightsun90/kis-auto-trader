"""
거래 기록 산출 — 자동매매 체결 증빙.

세 가지 출처를 합쳐 records/ 에 저장한다(JSON 원본 + 사람이 읽는 Markdown):
  1) 주문 확인 — trader/run이 남긴 trades.jsonl (주문번호 ODNO, KIS 응답메시지)
  2) 공식 체결 — KIS 일별주문체결조회(집계 output2 + 상세 output1; 모의는 상세가 T+1 반영)
  3) 잔고 스냅샷 — 체결 후 보유종목·평가손익

사용:
  python export_records.py            # 오늘
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
TRADES_LOG = os.path.join(D, "trades.jsonl")


def load_order_log(date: str) -> list:
    """trades.jsonl에서 해당 날짜(YYYYMMDD)의 주문 기록을 읽는다."""
    iso_day = f"{date[:4]}-{date[4:6]}-{date[6:8]}"
    rows = []
    if os.path.exists(TRADES_LOG):
        with open(TRADES_LOG, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                r = json.loads(line)
                if r.get("ts", "").startswith(iso_day):
                    rows.append(r)
    return rows


def to_markdown(date, env, orders, ccld, bal):
    L = [f"# 자동매매 거래 기록 — {date}", "", f"- 환경: {env}",
         f"- 시스템 주문 건수: {len(orders)}", ""]

    # 1) 주문 확인 (시스템 → KIS)
    L += ["## 1. 주문 확인 (시스템이 KIS에 낸 주문)", "",
          "| 시각 | 구분 | 종목 | 수량 | 주문시세 | 주문번호(ODNO) | KIS 응답 |",
          "|---|---|---|---|---|---|---|"]
    for r in orders:
        resp = r.get("response", {}) or {}
        odno = (resp.get("output") or {}).get("ODNO", "")
        msg = (resp.get("msg1") or "").strip()
        side = {"buy": "매수", "sell": "매도"}.get(r.get("side"), r.get("side"))
        L.append(f"| {r.get('ts','')[11:]} | {side} | {r.get('code')} | {r.get('qty')} | "
                 f"{r.get('price'):,} | {odno} | {msg} |")

    # 2) 공식 체결 집계 (KIS)
    s = ccld.get("summary", {}) or {}
    L += ["", "## 2. 공식 체결 집계 (KIS 일별주문체결조회)", "",
          f"- 총주문수량: {s.get('tot_ord_qty','')}",
          f"- 총체결수량: {s.get('tot_ccld_qty','')}",
          f"- 총체결금액: {s.get('tot_ccld_amt','')} 원",
          f"- 추정제비용(수수료 등): {s.get('prsm_tlex_smtl','')} 원",
          f"- 매입평균가: {s.get('pchs_avg_pric','')}"]
    detail = ccld.get("detail", [])
    if detail:
        L += ["", "### 체결 상세", "",
              "| 시각 | 종목 | 구분 | 주문수량 | 체결수량 | 체결평균가 | 체결금액 |",
              "|---|---|---|---|---|---|---|"]
        for r in detail:
            L.append("| {tm} | {nm}({cd}) | {sb} | {oq} | {cq} | {pr} | {amt} |".format(
                tm=r.get("ord_tmd", ""), nm=r.get("prdt_name", ""), cd=r.get("pdno", ""),
                sb=r.get("sll_buy_dvsn_cd_name", r.get("sll_buy_dvsn_cd", "")),
                oq=r.get("ord_qty", ""), cq=r.get("tot_ccld_qty", ""),
                pr=r.get("avg_prvs", r.get("ord_unpr", "")), amt=r.get("tot_ccld_amt", "")))
    else:
        L += ["", f"> 라인별 상세(output1)는 비어 있습니다 — \"{ccld.get('msg','')}\". "
              "모의투자는 당일 상세가 T+1에 반영되므로, 다음 영업일 `python export_records.py "
              f"{date}` 재실행 시 상세가 채워집니다. (집계와 주문확인으로 체결은 이미 증빙됨)"]

    # 3) 잔고 스냅샷
    bs = bal.get("summary", {}) or {}
    L += ["", "## 3. 잔고 스냅샷 (체결 후)", "",
          f"- 예수금(dnca_tot_amt): {bs.get('dnca_tot_amt','')}",
          f"- 총평가금액(tot_evlu_amt): {bs.get('tot_evlu_amt','')}",
          f"- 평가손익합(evlu_pfls_smtl_amt): {bs.get('evlu_pfls_smtl_amt','')}", ""]
    holds = bal.get("holdings", [])
    if holds:
        L += ["| 종목 | 보유수량 | 평가금액 | 평가손익 |", "|---|---|---|---|"]
        for h in holds:
            L.append(f"| {h.get('prdt_name','')}({h.get('pdno','')}) | {h.get('hldg_qty','')} | "
                     f"{h.get('evlu_amt','')} | {h.get('evlu_pfls_amt','')} |")
    return "\n".join(L)


def main():
    date = sys.argv[1] if len(sys.argv) > 1 else datetime.now().strftime("%Y%m%d")
    cfg = load_config()
    api = KISApi(cfg)

    orders = load_order_log(date)
    ccld = api.daily_ccld(date)
    bal = api.balance()

    os.makedirs(REC_DIR, exist_ok=True)
    json_path = os.path.join(REC_DIR, f"records_{date}.json")
    md_path = os.path.join(REC_DIR, f"records_{date}.md")
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump({"date": date, "env": cfg.env_name, "orders": orders,
                   "ccld": ccld, "balance": bal}, f, ensure_ascii=False, indent=2)
    with open(md_path, "w", encoding="utf-8") as f:
        f.write(to_markdown(date, cfg.env_name, orders, ccld, bal))

    print(f"저장 완료: {json_path}")
    print(f"저장 완료: {md_path}")
    print(f"시스템 주문 {len(orders)}건 / 공식 체결 집계 총체결수량 "
          f"{(ccld.get('summary') or {}).get('tot_ccld_qty','?')}")


if __name__ == "__main__":
    main()
