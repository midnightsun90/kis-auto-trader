"""키/계좌 검증: 토큰 발급 -> 현재가(키 검증) -> 잔고(계좌번호 검증). 비밀값은 출력 안 함."""
from config import load_config
from kis_api import KISApi

cfg = load_config()
print(f"[1] env={cfg.env_name}, base={cfg.base_url}")
print(f"    appkey={cfg.appkey[:6]}...({len(cfg.appkey)}자), CANO={cfg.cano}-{cfg.acnt_prdt_cd}")

api = KISApi(cfg)

# 1) 토큰
tok = api.access_token()
print(f"[2] 토큰 발급 OK (길이 {len(tok)})")

# 2) 현재가 -> appkey/secret 검증
price = api.current_price("005930")
print(f"[3] 삼성전자(005930) 현재가: {price:,}원  -> 키 정상")

# 3) 잔고 -> CANO/ACNT_PRDT_CD 검증
try:
    bal = api.balance()
    s = bal["summary"]
    print(f"[4] 잔고조회 OK -> 계좌번호 정상")
    print(f"    예수금(dnca_tot_amt): {s.get('dnca_tot_amt')}")
    print(f"    총평가(tot_evlu_amt): {s.get('tot_evlu_amt')}")
    print(f"    보유종목 수: {len(bal['holdings'])}")
except Exception as e:
    print(f"[4] 잔고조회 실패 -> 계좌번호/상품코드 확인 필요: {e}")
