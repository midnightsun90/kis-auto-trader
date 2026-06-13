"""
자동매매 루프.

흐름:
  1) 일정 주기로 현재가를 폴링(강의 12_2의 polling + KeyboardInterrupt 패턴 확장).
  2) 가격을 전략에 입력해 신호(buy/sell/hold)를 받는다.
  3) 신호에 따라 주문을 낸다(기본은 dry-run이라 실제 주문 대신 로그만).
  4) Ctrl+C로 안전하게 종료.

실행: python trader.py
설정: .env (KIS_ENV=paper, KIS_DRY_RUN=true 권장으로 시작)
"""

import argparse
import logging
import time

from config import load_config
from kis_api import KISApi
from strategy import SmaCrossStrategy

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)s  %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("trader")


def run(code: str, qty: int, interval: float, short: int, long: int):
    cfg = load_config()
    api = KISApi(cfg)
    strat = SmaCrossStrategy(short=short, long=long)

    log.info("환경=%s  종목=%s  주문수량=%d  주기=%.1fs  dry_run=%s",
             cfg.env_name, code, qty, interval, cfg.dry_run)
    log.info("전략=SMA(%d/%d). Ctrl+C로 종료.", short, long)

    position = 0  # 보유 수량(이 세션 기준 단순 추적)
    try:
        while True:
            price = api.current_price(code)
            signal = strat.update(price)
            log.info("price=%d  signal=%s  position=%d", price, signal, position)

            if signal == "buy":
                res = api.buy(code, qty, ord_dvsn="01")  # 시장가
                position += qty
                log.info("매수 주문: %s", res)
            elif signal == "sell" and position > 0:
                res = api.sell(code, position, ord_dvsn="01")
                log.info("매도 주문(%d주): %s", position, res)
                position = 0

            time.sleep(interval)
    except KeyboardInterrupt:
        log.info("사용자 종료. 현재 추적 포지션=%d주", position)


def main():
    p = argparse.ArgumentParser(description="KIS 자동매매 (기본 모의투자 + dry-run)")
    p.add_argument("--code", default="005930", help="종목코드 (기본 005930 삼성전자)")
    p.add_argument("--qty", type=int, default=1, help="신호당 주문 수량")
    p.add_argument("--interval", type=float, default=2.0, help="폴링 주기(초)")
    p.add_argument("--short", type=int, default=5, help="단기 이동평균 길이")
    p.add_argument("--long", type=int, default=20, help="장기 이동평균 길이")
    args = p.parse_args()
    run(args.code, args.qty, args.interval, args.short, args.long)


if __name__ == "__main__":
    main()
