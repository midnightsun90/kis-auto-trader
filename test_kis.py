"""키 없이 가능한 검증: 설정 로딩, 전략 신호, dry-run 주문(네트워크 미사용)."""
import os

# 더미 환경변수로 설정 주입 (실제 키 불필요, dry-run)
os.environ.update({
    "KIS_ENV": "paper",
    "KIS_DRY_RUN": "true",
    "KIS_APPKEY": "DUMMY_KEY",
    "KIS_APPSECRET": "DUMMY_SECRET",
    "KIS_CANO": "12345678",
    "KIS_ACNT_PRDT_CD": "01",
})

from config import load_config
from kis_api import KISApi
from strategy import SmaCrossStrategy

cfg = load_config()
assert cfg.paper is True
assert cfg.base_url == "https://openapivts.koreainvestment.com:29443"
assert cfg.tr_buy == "VTTC0802U" and cfg.tr_sell == "VTTC0801U" and cfg.tr_balance == "VTTC8434R"
print(f"config OK: {cfg.env_name}, dry_run={cfg.dry_run}, base={cfg.base_url}")

# 실전 전환 시 tr_id가 T 접두로 바뀌는지
os.environ["KIS_ENV"] = "real"
cfg_real = load_config()
assert cfg_real.base_url == "https://openapi.koreainvestment.com:9443"
assert cfg_real.tr_buy == "TTTC0802U"
print(f"real switch OK: {cfg_real.base_url}, tr_buy={cfg_real.tr_buy}")
os.environ["KIS_ENV"] = "paper"

# dry-run 주문은 네트워크 호출 없이 의도만 반환해야 함
api = KISApi(load_config())
res = api.buy("005930", 1, ord_dvsn="01")
assert res.get("dry_run") is True, res
assert res["intent"]["side"] == "buy" and res["intent"]["code"] == "005930"
print(f"dry-run order OK: {res['intent']}")

# 전략: 하락 후 상승 -> 골든크로스(buy) 발생, 다시 하락 -> 데드크로스(sell)
strat = SmaCrossStrategy(short=3, long=6)
series = [10, 9, 8, 7, 6, 5,  6, 8, 11, 14, 18, 22,  18, 14, 10, 6, 3, 1]
signals = [strat.update(p) for p in series]
print("signals:", signals)
assert "buy" in signals, "골든크로스 매수 신호가 나와야 함"
assert "sell" in signals, "데드크로스 매도 신호가 나와야 함"
assert signals.index("buy") < signals.index("sell"), "buy가 sell보다 먼저여야 함"
print("strategy OK")

print("ALL TESTS PASSED")
