# 화면 지도와 함정

브라우저 코드는 `scripts/snippets.js` 에 있다.

## 화면 지도

### 파트너센트럴 (EPC) — `{htid}` 는 프로필의 숙소 ID

주소 앞부분은 `https://apps.expediapartnercentral.com` 이다. 프로모션 허브는 `/supply-promotions/hub` 로 넘어간다.
허브 목록의 `Open details for <이름>` 링크에서 프로모션 ID를 얻는다. 허브의 대상 표시만으로 조건을 단정하지 말고 수정 화면에서 확인한다.

| 화면 | 경로 |
|---|---|
| 예약 목록 | `/lodging/bookings?htid={htid}` |
| **예약 상세(입금가)** | `/lodging/reservations/legacyReservationDetails.html?htid={htid}&reservationIds=<번호>` |
| 프로모션 허브 | `/lodging/promotions/hub?htid={htid}` |
| 프로모션 상세 | `/supply-promotions/details/<ID>?propertyId={htid}` |
| **프로모션 수정** ★ | `/lodging/promotions/standard/edit/<ID>?htid={htid}` |
| 결제/정산 | `/lodging/accounting/paymentsHub.html` |

**★ 조건은 반드시 「수정」 화면에서 확인한다.** 상세 화면의 「대상」란은 요약이라 **당일 조건이 안 보인다.**
읽기만 하면 안전하다 — **Submit을 안 누르면 아무것도 안 바뀐다.**
(원본 조사에서 이 규칙을 어겨 두 번 오판했다.)

### 고객페이지
```
https://www.expedia.co.kr/{숙소-슬러그}.h{htid}.Hotel-Information?chkin=YYYY-MM-DD&chkout=YYYY-MM-DD&adults=2
```
POS별 가격을 보려면 그 POS의 도메인으로 연다.

### 채널 매니저 (WINGSCMS 계열을 쓰는 숙소의 예) — 익스 상품그룹 코드는 프로필에

| 화면 | 경로 | 하는 일 |
|---|---|---|
| 요금세트 생성 | `#/app/cm/cm03_0600` | **가격 숫자**를 바꾸는 유일한 화면 |
| **요금세트 적용** | `#/app/cm/cm03_2500` | ★ **날짜별 세트 매핑 — 진짜 화면** |
| 요금세트적용_요금조정 | `#/app/cm/cm03_2500_m` | ⚠ **별개 화면. 여기 넣으면 반영 안 된다** |
| 요금 관리 | `#/app/cm/cm03_0200` | 확인용. **검증은 여기서** |

**구분법**: 상품그룹을 고른 뒤 달력에 WEEK/FRI/SAT 칩이 잔뜩 있으면 `cm03_2500`(맞는 화면), 텅 비어 있으면 `cm03_2500_m`(틀린 화면).
다른 채널 매니저를 쓰면 "가격을 바꾸는 화면 / 날짜에 매핑하는 화면 / 확인하는 화면"을 프로필에 적어 둔다.
채널 매니저가 없는 숙소는 파트너센트럴의 요금·재고 캘린더에서 달력요금을 직접 바꾼다. 그 화면 경로는 이 문서에 없으니
계정에서 확인해 프로필에 적고, 적혀 있지 않으면 변경 화면을 "미확인"으로 남긴다.

### 함정

| 함정 | 대처 |
|---|---|
| 리드타임 숫자칸이 안 먹힌다 (React onBlur만 있음) | `__setInput` |
| `ctrl+a`가 리터럴 "a"로 들어가 칸이 영구 고장 | 리로드 후 재시작. Backspace나 `__setInput` |
| 스크린샷 좌표 ≠ 페이지 좌표 (배율이 계속 흔들림) | 좌표 클릭 포기, JS `.click()` |
| 리드타임 일수만 바꾸면 Stay Dates가 안 따라와 Submit 비활성 | "Your audience choice has caused a conflict…" → Stay Dates 시작일도 같이 민다 |
| 리드타임을 **줄일 때는 경고가 없다** | 짧아진 만큼 앞날짜에 구멍이 생긴다. Stay Dates를 직접 확인 |
| EPC 화면 언어가 영어/한국어로 바뀐다 | `Edit`/`수정`, `Save and Preview`/`저장하고 미리보기` 양쪽 매칭 |
| 45초 CDP 한계 · `computer wait` 최대 10초 | 스크립트를 쪼개 `browser_batch`로 |
| Submit 후 앱이 자체 리다이렉트 | 10초 이상 기다린 뒤 다시 navigate |
| 고객페이지 요금 로드 실패 시 긁힌 ₩는 **경쟁사 값** | `err` 플래그와 화면 날짜를 먼저 확인 |
