"""
KIS(한국투자증권) OpenAPI 환경 설정.

비밀키는 코드에 하드코딩하지 않고 .env에서 읽는다.
(강의 12_2 노트북은 토큰/키를 소스에 직접 적었으나, 유출 위험이 있어 권장하지 않는다.)

모의투자(paper)와 실전(real)은 도메인과 tr_id가 다르다. KIS_ENV로 전환한다.
"""

import os
from dataclasses import dataclass

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass  # python-dotenv 미설치 시 OS 환경변수만 사용


# 도메인
REAL_DOMAIN = "https://openapi.koreainvestment.com:9443"
PAPER_DOMAIN = "https://openapivts.koreainvestment.com:29443"


@dataclass
class Config:
    paper: bool          # True=모의투자, False=실전
    appkey: str
    appsecret: str
    cano: str            # 계좌번호 앞 8자리 (종합계좌번호)
    acnt_prdt_cd: str    # 계좌번호 뒤 2자리 (상품코드, 보통 "01")
    dry_run: bool        # True면 실제 주문 API를 호출하지 않고 로그만 남김

    @property
    def base_url(self) -> str:
        return PAPER_DOMAIN if self.paper else REAL_DOMAIN

    # --- 거래 tr_id (모의는 V, 실전은 T 접두) ---
    @property
    def tr_buy(self) -> str:
        return "VTTC0802U" if self.paper else "TTTC0802U"   # 현금 매수

    @property
    def tr_sell(self) -> str:
        return "VTTC0801U" if self.paper else "TTTC0801U"   # 현금 매도

    @property
    def tr_balance(self) -> str:
        return "VTTC8434R" if self.paper else "TTTC8434R"   # 주식 잔고조회

    # 시세(현재가)는 모의/실전 공통
    TR_PRICE = "FHKST01010100"

    @property
    def env_name(self) -> str:
        return "모의투자(paper)" if self.paper else "실전(real)"


def load_config() -> Config:
    """환경변수에서 설정을 읽는다. 기본은 안전하게 모의투자 + dry-run."""
    env = os.getenv("KIS_ENV", "paper").strip().lower()
    paper = env != "real"
    dry_run = os.getenv("KIS_DRY_RUN", "true").strip().lower() in ("1", "true", "yes", "y")

    missing = [k for k in ("KIS_APPKEY", "KIS_APPSECRET", "KIS_CANO") if not os.getenv(k)]
    if missing:
        raise RuntimeError(
            f".env에 다음 값이 필요합니다: {', '.join(missing)}  (.env.example 참고)"
        )

    return Config(
        paper=paper,
        appkey=os.environ["KIS_APPKEY"],
        appsecret=os.environ["KIS_APPSECRET"],
        cano=os.environ["KIS_CANO"],
        acnt_prdt_cd=os.getenv("KIS_ACNT_PRDT_CD", "01"),
        dry_run=dry_run,
    )
