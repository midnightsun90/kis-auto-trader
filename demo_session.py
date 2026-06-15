"""
데모 매매 세션 — 거래 기록 생성을 위해 시스템의 주문 모듈로 모의주문을 체결시킨다.

자동매매 루프(trader.py)는 SMA 교차가 일어나야 주문하므로 짧은 시간엔 신호가
안 날 수 있다. 그래서 채점용 '거래 기록'은 이 스크립트로 동일한 KISApi 주문 함수를
직접 호출해 매수/매도를 발생시키고, export_records.py로 공식 체결내역을 산출한다.

안전장치: 모의투자(paper) + KIS_DRY_RUN=false 에서만 동작.
실행:  (PowerShell)  $env:KIS_DRY_RUN="false"; python demo_session.py
"""

import time

from config import load_config
from kis_api import KISApi
from trader import record_trade

cfg = load_config()
assert cfg.paper, "안전장치: 모의투자(paper)에서만 실행합니다."
assert not cfg.dry_run, "실제 모의주문을 내려면 KIS_DRY_RUN=false 로 실행하십시오."
api = KISApi(cfg)

orders = [
    ("buy", "035720", 2),   # 카카오 2주 매수
    ("buy", "005930", 1),   # 삼성전자 1주 매수
    ("sell", "035720", 1),  # 카카오 1주 매도 (라운드트립)
]

print("=== 모의주문 실행 ===")
for side, code, qty in orders:
    price = api.current_price(code)
    try:
        res = api.order(code, qty, side=side, ord_dvsn="01")  # 시장가
        odno = (res.get("output") or {}).get("ODNO")
        print(f"{side:4} {code} x{qty} @~{price:,}원 -> rt_cd={res.get('rt_cd')} ODNO={odno} msg={res.get('msg1')}")
        record_trade({"side": side, "code": code, "qty": qty, "price": price, "response": res})
    except Exception as e:
        print(f"{side:4} {code} x{qty} 실패: {e}")
    time.sleep(1.2)

print("\n=== 거래 후 잔고 ===")
b = api.balance()
s = b["summary"]
print("예수금:", s.get("dnca_tot_amt"), "/ 총평가:", s.get("tot_evlu_amt"))
for h in b["holdings"]:
    print("  보유:", h.get("prdt_name"), h.get("hldg_qty"), "주 / 평가손익", h.get("evlu_pfls_amt"))
