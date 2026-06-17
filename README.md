# KIS 자동매매 시스템 (한국투자증권 OpenAPI)

한국투자증권 OpenAPI를 사용한 국내주식 **자동매매 시스템**입니다.
강의 12_2에서 다룬 **접근토큰 발급 · 현재가 조회**를 토대로, 자동매매에 필요한
**hashkey · 현금주문 · 잔고조회**와 **전략 · 매매 루프**까지 확장했습니다.

기본값은 **모의투자(paper) + dry-run**으로, 실수로 실거래가 나가지 않도록 설계했습니다.

---

## 1. 구조

```
kis-auto-trader/
├── config.py        # 환경 설정(.env 로드), 모의/실전 도메인·tr_id 전환
├── kis_api.py       # KIS API 클라이언트: 토큰·hashkey·시세·주문·잔고
├── strategy.py      # 매매 전략(SMA 교차 예시) — 교체 가능한 인터페이스
├── trader.py        # 자동매매 루프(폴링→신호→주문→거래로그)
├── demo_session.py  # 거래 기록 생성용: 시스템 주문 모듈로 모의주문 체결
├── export_records.py# 거래 기록 산출: 주문확인 + 체결집계 + 잔고 → records/
├── verify_keys.py   # 토큰·시세·잔고 종합 검증
├── examples/
│   └── quote.py     # 최소 검증: 현재가 조회
├── records/         # 거래 기록 저장 폴더(export_records.py가 생성)
├── .env.example     # 비밀키 템플릿 (.env로 복사해 사용)
├── requirements.txt
└── README.md
```

설계 원칙: **트레이더는 전략 내부를 모른다.** `strategy.update(price) -> 'buy'|'sell'|'hold'`
인터페이스만 지키면 전략을 자유롭게 갈아끼울 수 있습니다(전략 패턴).

---

## 2. 사용하는 KIS OpenAPI

| 기능 | 메서드 · 경로 | tr_id (모의 / 실전) |
|---|---|---|
| 접근토큰 발급 | `POST /oauth2/tokenP` | — |
| hashkey | `POST /uapi/hashkey` | — |
| 현재가 시세 | `GET /uapi/domestic-stock/v1/quotations/inquire-price` | `FHKST01010100` (공통) |
| 현금 매수 | `POST /uapi/domestic-stock/v1/trading/order-cash` | `VTTC0802U` / `TTTC0802U` |
| 현금 매도 | `POST /uapi/domestic-stock/v1/trading/order-cash` | `VTTC0801U` / `TTTC0801U` |
| 주식 잔고조회 | `GET /uapi/domestic-stock/v1/trading/inquire-balance` | `VTTC8434R` / `TTTC8434R` |
| 일별 주문체결조회 | `GET /uapi/domestic-stock/v1/trading/inquire-daily-ccld` | `VTTC8001R` / `TTTC8001R` |

도메인:
- 모의투자: `https://openapivts.koreainvestment.com:29443`
- 실전: `https://openapi.koreainvestment.com:9443`

공통 헤더: `authorization: Bearer <token>`, `appkey`, `appsecret`, `tr_id`, `custtype: P`.
주문 POST에는 `hashkey` 헤더가 추가로 필요합니다.

---

## 3. 핵심 설계 포인트 (오럴 대비)

- **토큰 캐싱** — 접근토큰은 발급이 분당 1회로 제한되고 24시간 유효합니다. 매번 재발급하면
  곧 막히므로 `.token.json`에 (환경·appkey별로) 캐시하고 만료 1분 전까지 재사용합니다.
- **hashkey** — 주문 본문 위변조 방지용 해시. 주문 직전 본문을 `/uapi/hashkey`로 보내
  받은 값을 헤더에 싣습니다.
- **모의/실전 전환** — 도메인과 tr_id만 바뀝니다. `KIS_ENV`로 한 곳에서 전환(`config.py`).
- **다중 안전장치** —
  1) 기본 `KIS_DRY_RUN=true`: 주문 API를 호출하지 않고 의도만 로그.
  2) 실전(`real`) 주문은 `KIS_ALLOW_REAL_ORDER=yes`가 없으면 코드가 차단.
  3) 기본 종목·수량을 소량(1주)으로.
- **비밀 분리** — appkey/secret/계좌번호는 `.env`에서만 읽습니다. (강의 노트북은 토큰을
  소스에 하드코딩했는데, 유출 위험이 있어 따르지 않았습니다.)
- **레이트리밋 재시도** — KIS는 초당 거래건수 제한(`EGW00201`)이 있고 모의투자는 특히
  빡빡합니다. 호출이 몰리면 HTTP 500 + `rt_cd:1`로 거절되므로, `_send`에서 이를 감지해
  점증 백오프로 자동 재시도합니다(시세/주문/잔고 공통).

---

## 4. 설정 & 실행

```bash
pip install -r requirements.txt          # requests, python-dotenv

cp .env.example .env                     # Windows: copy .env.example .env
# .env 편집: KIS_APPKEY/SECRET/CANO 입력 (모의계좌 발급 후)

python verify_keys.py                    # 토큰·시세·잔고로 키/계좌 종합 검증
python examples/quote.py 005930          # 현재가만 간단 조회
python trader.py --code 005930 --qty 1   # 자동매매(기본 dry-run)
```

`trader.py` 옵션: `--code`(종목), `--qty`(수량), `--interval`(폴링 주기 초),
`--short`/`--long`(이동평균 길이).

검증 순서 권장:
1. `quote.py`로 토큰·시세 확인 → 키가 올바른지 점검.
2. `trader.py`를 **dry-run**으로 돌려 신호·로그 흐름 확인.
3. 모의투자 계좌에서 `KIS_DRY_RUN=false`로 실제 모의주문 체결 확인.
4. (선택) 실전 전환은 충분히 검증한 뒤에만.

> **모의계좌 발급 전 임시 진행:** 모의투자 신청이 지연되면, 실전 appkey로
> `examples/quote.py`(비주문) 검증만 먼저 하고, 모의계좌가 나오면 `.env`의 키와
> `KIS_ENV`만 바꾸면 됩니다. 주문 테스트는 반드시 모의에서 하십시오.

---

## 5. 거래 기록 (자동매매 체결 증빙)

자동매매가 **실제 체결**된 기록을 남기는 두 경로:

1. **trader.py 거래 로그** — 주문이 나갈 때마다 `trades.jsonl`에 시각·종목·매수매도·수량·응답을 한 줄씩 기록(런타임 로그, gitignore).
2. **공식 체결내역** — `export_records.py`가 KIS 일별주문체결조회 + 잔고를 받아 `records/records_<날짜>.json`(원본)과 `records_<날짜>.md`(표)로 저장. 이게 거래 기록의 공식 증빙입니다.

```bash
# 장중(평일 09:00~15:30)에 실제 모의주문을 내고:  (PowerShell)
$env:KIS_DRY_RUN="false"; python demo_session.py   # 매수 2건·매도 1건 체결
# (또는 자동매매 루프: python trader.py --code 005930 --qty 1)

# 체결내역을 기록으로 산출:
python export_records.py            # 오늘
python export_records.py 20260615   # 특정일(YYYYMMDD)
```

> 모의주문은 KRX 정규장 시간에만 체결됩니다. 폐장 중 주문은 거부/예약될 수 있습니다.

**실제 산출된 기록:** `records/`에 장중 실거래 기록이 날짜별로 있습니다.
- [`records_20260615.md`](records/records_20260615.md) — 11건 주문 / 공식 체결 17주 / 3,091,700원
- [`records_20260617.md`](records/records_20260617.md) — 8건 주문 / 공식 체결 13주 / 2,579,100원

각 기록은 ⑴ 주문확인(주문번호 ODNO·KIS 응답), ⑵ 공식 체결집계(KIS 일별주문체결조회 output2),
⑶ 체결 후 잔고 스냅샷을 담습니다. 모의투자 일별주문체결조회는 라인별 상세(output1)를 제공하지
않고 집계만 반환하므로, 종목별 체결 증빙은 주문확인 표와 잔고로 갈음합니다.

---

## 6. 면책

교육·과제 목적의 코드입니다. 실전 계좌 사용 시 발생하는 손실은 사용자 책임입니다.
실거래 전 반드시 모의투자에서 충분히 검증하십시오.

---

## 7. 참고

- 강의 12_2 (KIS OpenAPI: 토큰·현재가).
- [KIS Developers 포털](https://apiportal.koreainvestment.com/) · [공식 예제 저장소](https://github.com/koreainvestment/open-trading-api).
