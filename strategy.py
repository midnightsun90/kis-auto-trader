"""
매매 전략.

예시로 단순 이동평균 교차(SMA crossover)를 구현한다.
  - 단기 이동평균이 장기 이동평균을 상향 돌파(golden cross) -> 매수 신호
  - 하향 돌파(dead cross) -> 매도 신호
  - 그 외 -> 보류(hold)

전략은 update(price)에 가격을 하나씩 흘려넣으면 'buy'/'sell'/'hold'를 반환하는
간단한 인터페이스만 지키면 교체 가능하다(트레이더는 전략 내부를 모른다).
"""

from collections import deque


class SmaCrossStrategy:
    def __init__(self, short: int = 5, long: int = 20):
        assert short < long
        self.short = short
        self.long = long
        self.prices = deque(maxlen=long)
        self._prev_diff = None  # 직전 (단기-장기) 부호로 교차 시점 판정

    def update(self, price: float) -> str:
        self.prices.append(price)
        if len(self.prices) < self.long:
            return "hold"

        prices = list(self.prices)
        short_ma = sum(prices[-self.short:]) / self.short
        long_ma = sum(prices) / self.long
        diff = short_ma - long_ma

        signal = "hold"
        if self._prev_diff is not None:
            if self._prev_diff <= 0 < diff:
                signal = "buy"    # 골든크로스
            elif self._prev_diff >= 0 > diff:
                signal = "sell"   # 데드크로스
        self._prev_diff = diff
        return signal
