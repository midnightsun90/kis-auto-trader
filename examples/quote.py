"""
가장 단순한 검증 스크립트: 현재가 조회.
주문 권한 없이 appkey/appsecret/모의계좌만 있으면 동작한다.

실행: python examples/quote.py 005930
"""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config import load_config
from kis_api import KISApi


def main():
    code = sys.argv[1] if len(sys.argv) > 1 else "005930"
    api = KISApi(load_config())
    price = api.current_price(code)
    print(f"{code} 현재가: {price:,}원")


if __name__ == "__main__":
    main()
