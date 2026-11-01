# 입금가 실측

계산값과 실측값을 나누는 기준이다.

## ★ 입금가는 고객페이지에 없다 — 확인 경로는 하나뿐

| 고객페이지에 뜨는 것 | 안 뜨는 것 |
|---|---|
| 세전 정가 · 할인 후 세전 · 세금 포함 총 요금 · 할인율 배지 | 수수료 · 엑셀러레이터 · **입금가** |

```
/lodging/reservations/legacyReservationDetails.html?htid={htid}&reservationIds=<예약번호>
```

**결제 내역은 iframe 안에 있다.** 본문 텍스트만 긁으면 금액이 하나도 안 나온다.

```js
const f=[...document.querySelectorAll('iframe')].find(x=>/payment-display-iframe/.test(x.id||''));
f.contentDocument.body.innerText.replace(/\s+/g,' ');
```

읽히는 것: `Nightly rates` / `Promotion: <이름>` / `Taxes` / `Total guest payment` /
`Expedia Group's compensation` / `Accelerator (n%)` / **`Your total payout`**

화면이 한국어면 라벨이 다르다: `1박 요금` / `프로모션: <이름>` / `세금` / `총 고객 결제 금액` / `Expedia Group 수수료` / `엑셀러레이터` / **`총 지불금`**.
합계 줄의 엑셀러레이터에는 %가 없고, 아래 `1박 결제 세부 정보`의 `엑셀러레이터 (n%)` 에서 읽는다.

금액은 박별로 반올림해 합산한다. 공식을 합계에 곱하면 박수만큼 몇 원 차이 날 수 있으니 1박 값으로 대조하거나 `payout.py booking --nights N` 을 쓴다.
예약 목록과 상세 앞부분에는 투숙객 이름이 있다. 목록은 `__bookingIds()`, 결제 내역은 `__payment()` 로 필요한 값만 읽는다.

★ `Promotion:` 줄에 **어떤 프로모션이 붙었는지 이름이 그대로 찍힌다.**
자국 POS/그 외 판정을 여기서 한다 (예: `KR Same-day-Members` = 한국 POS, `SD - Same-day-Members` = 그 외).

**"입금가"라고 쓰려면 여기까지 와야 한다.** 고객페이지 숫자에 계수를 곱한 것은 **계산값**이다.
둘을 섞어 쓰지 마라.

### 실측 원장 — 이런 표로 남긴다 (오차 1원 이내가 목표)

| 예약 | 예약일 | 붙은 프로모션 | 세전 | 할인후 | 결제 | 엑셀 | **실입금** | 계수 |
|---|---|---|---:|---:|---:|---:|---:|---:|
| 예약 A (가상) | 당일 | `KR Same-day-Members` 30% | 150,000 | 105,000 | 115,500 | 5% | **92,925** | 0.885 |

예약번호와 투숙객 이름은 원장에 남기지 않는다. "예약 A/B"와 예약일로만 가리킨다.
