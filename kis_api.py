"""
KIS(한국투자증권) OpenAPI 클라이언트.

강의 12_2에서 다룬 토큰 발급·현재가 조회를 토대로, 자동매매에 필요한
hashkey·현금주문·잔고조회까지 확장했다. 모든 호출은 requests로 직접 수행한다.

핵심 주의:
  - 접근토큰은 발급 횟수 제한(분당 1회)이 있고 24시간 유효하므로 파일에 캐시한다.
  - 주문 POST 본문은 hashkey 헤더가 필요하다.
  - 비밀키/토큰은 .env와 캐시파일에만 두고, 절대 커밋하지 않는다(.gitignore).
"""

import json
import os
import time

import requests

from config import Config

TOKEN_CACHE = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".token.json")


class KISApi:
    def __init__(self, cfg: Config):
        self.cfg = cfg
        self._token = None
        self._token_expire = 0.0
        self._load_cached_token()

    # ----------------------------- 토큰 -----------------------------
    def _load_cached_token(self):
        if not os.path.exists(TOKEN_CACHE):
            return
        try:
            with open(TOKEN_CACHE, "r", encoding="utf-8") as f:
                data = json.load(f)
            # 같은 환경(paper/real)·같은 appkey의 토큰만 재사용
            if data.get("env") == self.cfg.env_name and data.get("appkey") == self.cfg.appkey:
                if data.get("expire", 0) > time.time() + 60:
                    self._token = data["token"]
                    self._token_expire = data["expire"]
        except (json.JSONDecodeError, KeyError, OSError):
            pass

    def _save_cached_token(self):
        with open(TOKEN_CACHE, "w", encoding="utf-8") as f:
            json.dump(
                {
                    "token": self._token,
                    "expire": self._token_expire,
                    "env": self.cfg.env_name,
                    "appkey": self.cfg.appkey,
                },
                f,
            )

    def access_token(self) -> str:
        """유효한 접근토큰 반환. 캐시가 살아있으면 재사용, 아니면 새로 발급."""
        if self._token and self._token_expire > time.time() + 60:
            return self._token

        url = f"{self.cfg.base_url}/oauth2/tokenP"
        payload = {
            "grant_type": "client_credentials",
            "appkey": self.cfg.appkey,
            "appsecret": self.cfg.appsecret,
        }
        resp = requests.post(url, headers={"content-type": "application/json"},
                             data=json.dumps(payload))
        resp.raise_for_status()
        data = resp.json()
        if "access_token" not in data:
            raise RuntimeError(f"토큰 발급 실패: {data}")
        self._token = data["access_token"]
        # expires_in(초) 기준 만료시각 저장 (기본 86400 = 24h)
        self._token_expire = time.time() + int(data.get("expires_in", 86400))
        self._save_cached_token()
        return self._token

    # --------------------------- 요청 공통 ---------------------------
    # KIS는 초당 거래건수 제한(EGW00201)이 있다. 모의투자는 특히 빡빡해서
    # 호출이 몰리면 HTTP 500 + rt_cd:1 로 거절된다. 짧게 쉬었다가 재시도한다.
    RATE_LIMIT_CODE = "EGW00201"

    def _send(self, method, url, headers, params=None, body=None, retries=5):
        last = None
        for i in range(retries):
            resp = requests.request(
                method, url, headers=headers, params=params,
                data=json.dumps(body) if body is not None else None,
            )
            try:
                j = resp.json()
            except ValueError:
                j = None
            if j and j.get("msg_cd") == self.RATE_LIMIT_CODE:
                last = j
                time.sleep(0.3 * (i + 1))  # 점증 백오프
                continue
            resp.raise_for_status()
            return resp
        raise RuntimeError(f"레이트리밋 재시도 초과(EGW00201): {last}")

    # --------------------------- 공통 헤더 ---------------------------
    def _headers(self, tr_id: str, hashkey: str = None) -> dict:
        h = {
            "content-type": "application/json; charset=utf-8",
            "authorization": f"Bearer {self.access_token()}",
            "appkey": self.cfg.appkey,
            "appsecret": self.cfg.appsecret,
            "tr_id": tr_id,
            "custtype": "P",  # 개인
        }
        if hashkey:
            h["hashkey"] = hashkey
        return h

    # ---------------------------- hashkey ----------------------------
    def hashkey(self, body: dict) -> str:
        """주문 본문을 해시하여 hashkey를 얻는다 (주문 POST에 필요)."""
        url = f"{self.cfg.base_url}/uapi/hashkey"
        headers = {
            "content-type": "application/json; charset=utf-8",
            "appkey": self.cfg.appkey,
            "appsecret": self.cfg.appsecret,
        }
        resp = self._send("POST", url, headers, body=body)
        return resp.json()["HASH"]

    # ----------------------------- 시세 ------------------------------
    def current_price(self, code: str) -> int:
        """국내주식 현재가(원). code 예: '005930'(삼성전자)."""
        url = f"{self.cfg.base_url}/uapi/domestic-stock/v1/quotations/inquire-price"
        params = {"fid_cond_mrkt_div_code": "J", "fid_input_iscd": code}
        resp = self._send("GET", url, self._headers(Config.TR_PRICE), params=params)
        return int(resp.json()["output"]["stck_prpr"])

    # ----------------------------- 주문 ------------------------------
    def order(self, code: str, qty: int, price: int = 0,
              side: str = "buy", ord_dvsn: str = "00") -> dict:
        """현금 주문. side: 'buy'|'sell'. ord_dvsn: '00' 지정가, '01' 시장가.
        시장가는 price=0으로 둔다.

        dry_run이면 실제 호출 없이 의도만 반환한다(안전장치)."""
        side = side.lower()
        if side not in ("buy", "sell"):
            raise ValueError("side는 'buy' 또는 'sell'")
        if ord_dvsn == "01":
            price = 0  # 시장가

        body = {
            "CANO": self.cfg.cano,
            "ACNT_PRDT_CD": self.cfg.acnt_prdt_cd,
            "PDNO": code,
            "ORD_DVSN": ord_dvsn,
            "ORD_QTY": str(int(qty)),
            "ORD_UNPR": str(int(price)),
        }
        intent = {"side": side, "code": code, "qty": qty, "price": price,
                  "ord_dvsn": ord_dvsn, "env": self.cfg.env_name}

        if self.cfg.dry_run:
            return {"dry_run": True, "intent": intent}

        # 실전 주문은 명시적 옵트인 없이는 차단(사고 방지)
        if not self.cfg.paper and os.getenv("KIS_ALLOW_REAL_ORDER", "").lower() not in ("yes", "true", "1"):
            raise RuntimeError(
                "실전 계좌 주문은 KIS_ALLOW_REAL_ORDER=yes 를 설정해야 실행됩니다(안전장치)."
            )

        tr_id = self.cfg.tr_buy if side == "buy" else self.cfg.tr_sell
        url = f"{self.cfg.base_url}/uapi/domestic-stock/v1/trading/order-cash"
        hkey = self.hashkey(body)
        resp = self._send("POST", url, self._headers(tr_id, hashkey=hkey), body=body)
        out = resp.json()
        if out.get("rt_cd") != "0":
            raise RuntimeError(f"주문 실패: {out.get('msg1')} ({out})")
        return out

    def buy(self, code, qty, price=0, ord_dvsn="00"):
        return self.order(code, qty, price, side="buy", ord_dvsn=ord_dvsn)

    def sell(self, code, qty, price=0, ord_dvsn="00"):
        return self.order(code, qty, price, side="sell", ord_dvsn=ord_dvsn)

    # ----------------------------- 잔고 ------------------------------
    def balance(self) -> dict:
        """주식 잔고조회. 반환: {'holdings': [...], 'summary': {...}}."""
        url = f"{self.cfg.base_url}/uapi/domestic-stock/v1/trading/inquire-balance"
        params = {
            "CANO": self.cfg.cano,
            "ACNT_PRDT_CD": self.cfg.acnt_prdt_cd,
            "AFHR_FLPR_YN": "N",     # 시간외단일가 여부
            "OFL_YN": "",
            "INQR_DVSN": "02",       # 조회구분: 종목별
            "UNPR_DVSN": "01",
            "FUND_STTL_ICLD_YN": "N",
            "FNCG_AMT_AUTO_RDPT_YN": "N",
            "PRCS_DVSN": "01",       # 전일매매 포함
            "CTX_AREA_FK100": "",
            "CTX_AREA_NK100": "",
        }
        resp = self._send("GET", url, self._headers(self.cfg.tr_balance), params=params)
        out = resp.json()
        return {
            "holdings": out.get("output1", []),
            "summary": (out.get("output2") or [{}])[0],
        }

    # ------------------------- 체결내역(거래기록) -------------------------
    def daily_ccld(self, start_date: str, end_date: str = None) -> list:
        """주식 일별 주문체결 조회. 날짜는 'YYYYMMDD'. 자동매매 '거래 기록'의 공식 근거.
        반환: 체결/주문 내역 리스트(output1). 각 항목에 종목·매수매도·체결수량·체결단가·시각 등."""
        end_date = end_date or start_date
        url = f"{self.cfg.base_url}/uapi/domestic-stock/v1/trading/inquire-daily-ccld"
        params = {
            "CANO": self.cfg.cano,
            "ACNT_PRDT_CD": self.cfg.acnt_prdt_cd,
            "INQR_STRT_DT": start_date,
            "INQR_END_DT": end_date,
            "SLL_BUY_DVSN_CD": "00",   # 00 전체 / 01 매도 / 02 매수
            "INQR_DVSN": "00",         # 00 역순 / 01 정순
            "PDNO": "",                # 종목코드(공란=전체)
            "CCLD_DVSN": "00",         # 00 전체 / 01 체결 / 02 미체결
            "ORD_GNO_BRNO": "",
            "ODNO": "",
            "INQR_DVSN_3": "00",
            "INQR_DVSN_1": "",
            "CTX_AREA_FK100": "",
            "CTX_AREA_NK100": "",
        }
        resp = self._send("GET", url, self._headers(self.cfg.tr_ccld), params=params)
        return resp.json().get("output1", [])
