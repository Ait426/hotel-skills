# 아고다 파트너 포털 지도

`{id}`는 숙소 ID로 치환한다. 두 개의 호스트 경로 계열이 섞여 있다 — `/mldc/ko-kr/app/...`와
`/ko-kr/kipp/app/...`, `/ko-kr/app/...`. 아래 표의 경로를 그대로 써라. 추측하면 404가 난다.

## 0장. 사전 점검 — 이걸 안 하면 진단서 전체가 거짓이 된다

빈 페이지를 "0건"으로 읽는 사고가 실제로 난다. 아래 순서를 먼저 돌려라.

### 0-1. 로그인 판별

```js
(() => {
  const t = document.body.innerText || '';
  const route = location.pathname + location.hash;   // 해시 라우팅 사이트 때문에 hash까지 본다
  const hasId   = /ID\s*\d{6,}/.test(t);
  const hasNav  = t.includes('비즈니스 성장 프로그램');
  const isLogin = /(login|signin|auth)/i.test(route)
                  || !!document.querySelector('input[type="password"]');
  return { 로그인됨: hasId && hasNav && !isLogin, hasId, hasNav, isLogin, route: route.slice(0,40) };
})()
```

`pathname`만 보면 안 된다. 해시 라우팅을 쓰는 채널 매니저(WINGSCMS 등)에서는
로그인 화면이어도 `pathname`이 `/`라서 통과해 버린다. **실제로 이 실수를 한 번 했다.**

로그인이 안 되어 있으면 사용자에게 요청하고 기다려라. 절대 대신 로그인하지 마라.

### 0-2. 렌더링 확인

값을 읽기 전에 그 페이지에 내용이 실제로 그려졌는지 본다.

```js
({ len: (document.body.innerText||'').length, ready: document.readyState })
```

`len`이 1,500 미만이면 아직 안 그려진 것이다. 6~10초 더 기다렸다 다시 읽어라.
**"0건"과 "아직 안 그려짐"을 구별하지 못하면 조사 결과 전체가 무의미하다.**

## 숙소 ID를 모를 때

`/mldc/ko-kr/app/iam/propertysearch` — **이 계정이 가진 숙소 전부**를 표로 준다.
이름 · ID · 도시 · 판매 상태 · 당월 수익 · 평균 1일당 요금 · **콘텐츠 점수**까지 한 번에 나온다.
`snippets.js` 의 `properties()` 로 긁어라.

헤더 상단의 숙소 칩(`숙소명 ID xxxxxxx ⌄`)을 눌러도 드롭다운이 열린다.
검색창이 **숙소명 또는 숙소 ID** 를 받으므로, 사용자가 이름만 알아도 여기서 ID를 찾을 수 있다.
드롭다운 맨 아래 `모든 숙소 보기` 가 위 목록 페이지로 간다.

## 경로표

| 영역 | 경로 |
|---|---|
| 사진 | `/ko-kr/app/setting/photos/{id}` |
| **모든 숙소 (ID 찾기)** | `/mldc/ko-kr/app/iam/propertysearch` — {id} 불필요 |
| 숙소 설정 | `/ko-kr/kipp/app/settings/propertysetting/{id}` |
| 객실 설정 | `/ko-kr/kipp/app/settings/roomsetup/{id}` |
| 객실 매핑 | `/mldc/ko-kr/app/setting/rooms/{id}/room-mapping` |
| 요금제 | `/ko-kr/app/pricing-metadata/rateplan/{id}` |
| **ARI 캘린더** | `/mldc/ko-kr/app/ari/calendar/{id}` — `?startDate=YYYY-MM-DD&endDate=…` 먹는다 |
| 프로모션 목록 | `/ko-kr/kipp/app/manage/promotioncard/{id}` |

**단, 쿼리가 먹었는지를 URL 로 판단하지 마라.** 도구가 `location.search` 를 `[BLOCKED]` 로 가리고
`location.pathname` 만 보면 쿼리가 안 보여서 "안 먹는다"고 오판한다.
**우측 패널에 찍힌 날짜 텍스트를 읽어서 확인해라.**
| 프로모션 만들기 | `/ko-kr/kipp/app/manage/promotionsetting/{id}` |
| **할인 시뮬레이터** | `/mldc/ko-kr/app/pricing-metadata/promotions/promotionsimulator/{id}` |
| 예약 현황 | `/mldc/ko-kr/app/reporting/booking/{id}?bookingType=confirmed%2Camended` |
| 성장 프로그램 허브 | `/ko-kr/app/mnc/{id}/partner-programs-hub` |
| Maximum Gain 상세 | `/ko-kr/app/mnc/maximumgain/moreinfo/{id}` |
| 투숙객 이용후기 | `/mldc/ko-kr/app/setting/review/{id}` |
| 정산 거래 내역 | `/ko-kr/app/finance/transactions/{id}` |

포털 상단 검색창(placeholder가 `페이지…`로 시작)에 페이지 이름을 치면 이동할 수 있다.
**네비게이션 드롭다운은 DOM 클릭으로 안 열린다.** 검색창을 쓰거나 URL로 직접 가라.

## 렌더링 함정 — 여기서 시간을 다 쓴다

**소비자 페이지 객실 그리드는 탭이 활성일 때만 그려진다.**
`agoda.com` 숙소 페이지의 요금 그리드는 백그라운드 탭에서 DOM이 비어 있다.
`computer` 도구로 클릭·스크롤해서 탭을 활성화한 **직후** JS로 읽어라. 순서가 바뀌면 빈 배열이 나온다.

**사진 이미지는 canvas로 못 읽는다.** CORS 헤더가 없어 `toDataURL`이 `SecurityError`로 죽는다
(tainted canvas). 사진 내용 확인은 스크린샷뿐이다.

**사진 페이지는 렌더러가 자주 멈춘다.** 스크린샷이 30초 타임아웃 나면 6~10초 기다렸다 재시도.
그래도 안 되면 탭을 닫고 새로 열어라. **뷰포트가 208px로 고착되는 현상**도 있다 —
`resize_window`로 안 고쳐지고 탭 재생성만이 답이다.

**이미지 URL은 가려진다.** 쿼리스트링이 붙은 URL은 도구가 `[BLOCKED]`로 마스킹한다.
URL을 컨텍스트로 가져오려 하지 말고 페이지 안에서 처리해라.

**ARI 캘린더는 지난 날짜를 안 연다.** 과거 요금은 채널 매니저의 요금 변경 이력에서 봐야 한다.

**목록에서 항목을 처리하면 인덱스가 즉시 밀린다.** 사진 태그, 프로모션 등 필터된 목록에서
하나를 처리하면 그게 목록에서 빠진다. **배치마다 목록을 다시 읽어라.**

**`window.open`으로 새 탭을 여는 버튼이 있다.** MCP 탭 그룹 밖으로 열려서 안 보인다.
후크를 걸어 URL만 가로채고 직접 navigate 해라.

```js
const orig = window.open; window.__u = null;
window.open = u => { window.__u = u; return null; };
document.querySelector('[data-testid="..."]').click();
setTimeout(() => window.open = orig, 3000);
// 잠시 뒤 window.__u 를 읽는다
```

## 쓰기 금지 원칙

조사는 **읽기만** 한다. 아래 버튼은 값을 세팅해 두고 **사용자가 누르게 남겨라.**

요금 저장 · 프로모션 적용/중지 · 캠페인 저장/삭제 · 매핑 문제 신고 · 프로그램 적용하기

사진 태그처럼 되돌리기 쉬운 콘텐츠 작업은 사용자가 "고쳐줘"라고 했으면 진행해도 된다.
**삭제는 어떤 경우에도 하지 마라.** 되돌릴 수 없다.

할인 시뮬레이터는 예외 — 화면에 "실제로 적용되지 않습니다"라고 쓰여 있다. 마음껏 돌려라.

### 눌러선 안 되는 팝업 — X로만 닫는다

포털(특히 ARI 캘린더)을 열면 광고성 팝업이 뜬다. 버튼을 누르면 Σ나 비용이 바로 바뀐다. **조사 중에는 어떤 버튼도 누르지 말고 X로만 닫는다.**
숙소가 원해서 켜는 경우에도 입금가를 먼저 계산하고 사용자가 누른다.

| 팝업 | 위험한 버튼 | 누르면 |
|---|---|---|
| 「추가 N% 할인율 제공해…」 | 지금 할인 업데이트하기 | Maximum Gain 상향, 입금가 하락 |
| 「모든 캠페인 적용하기」 류 | 전부 | 캠페인 일괄 참여 |
| 아고다 다이내믹 요금 플러스 | 지금 적용하기 | 요금 자동 조정 |
| 「예약을 늘리고 취소율을 …% 줄여보세요」 | 지금 적용하기 | 패키지 할인 추가 |
| 「아고다 회원의 예약을 유도하세요」 | 지금 적용하기 | 로그인 사용자 할인 추가 |
| VIP 프로모션 | VIP 프로모션 적용하기 | 타겟팅-VIP 할인 추가 |
| Sponsored Listing | 지금 캠페인 설정하기 | 광고 과금 |
| 「Occupancy-based promotion」 | Review promotion | 객실 점유율 프로모션 재개 |

문구와 버튼은 바뀔 수 있다. 목록에 없어도 할인·적용을 권하는 팝업은 같게 취급한다.

---

## 2. 아고다 파트너 포털 — 예약 리포팅

```
https://portal.agoda.com/mldc/ko-kr/app/reporting/booking/{id}?bookingType=confirmed%2Camended
```

**크롬 창이 백그라운드여도 정상 렌더링된다.** 이 점이 결정적이다.

### 예약 하나 조회하는 순서

1. 상세 서랍(drawer)이 열려 있으면 먼저 닫는다 — 서랍이 뒤쪽 목록 클릭을 막는다.
   서랍 좌상단의 `›` 접기 버튼을 누른다 (Escape는 잘 안 먹는다).
2. 검색창(placeholder `예약 번호 / 투숙객 이름`)에 예약번호를 넣고 `조회하기` 클릭.
   React 제어 입력이라 값 주입은 네이티브 setter로 해야 한다:
   ```js
   const inp=[...document.querySelectorAll('input')]
     .find(e=>e.placeholder&&e.placeholder.indexOf('예약 번호')===0);
   const set=Object.getOwnPropertyDescriptor(
     window.HTMLInputElement.prototype,'value').set;
   set.call(inp, bookingNumber);
   inp.dispatchEvent(new Event('input',{bubbles:true}));
   [...document.querySelectorAll('button')]
     .find(b=>b.innerText.trim()==='조회하기').click();
   ```
3. 결과 행을 클릭해 서랍을 연다. 결과가 1건이면 화면 좌표 약 `(250, 415)`.
4. 서랍의 `결제 및 요금` 탭 → `기준 판매 요금`을 읽는다.
5. `프로모션 내역` 링크를 눌러 모달을 연다 → 날짜별 프로모션 %가 전부 나온다.
   여러 박이면 박 수만큼 행이 나오므로 데이터가 풍부하다.

탭이나 링크를 텍스트로 클릭할 때는 정확히 일치하는 요소 중 가장 깊은 것을 눌러야 한다:
```js
function deepClick(txt){
  const all=[...document.querySelectorAll('*')]
    .filter(e=>(e.textContent||'').trim()===txt);
  if(!all.length) return 0;
  const e=all[all.length-1]; e.click();
  if(e.parentElement) e.parentElement.click();
  return all.length;
}
```

### 페이지에서 읽어야 할 것

- `기준 판매 요금(세금 및 수수료 포함)` — 고객 결제
- `요금제` — 어느 상품인지 (예: `Room Only (요금제 ID)`)
- `객실 종류` — 매핑된 우리 객실인지 (예: `스탠다드 (객실 ID)`)
- `예약 생성일(방콕, UTC+7)` — 리드타임 계산용. **한국 시간이 아니다, +2시간**
- `프로모션 내역` 모달 — 날짜별 %

### 다른 유용한 포털 경로

```
/ko-kr/kipp/app/manage/promotioncard/{id}    프로모션 목록 (적용 중 / 중지)
/ko-kr/app/mnc/{id}/campaign/list            캠페인 목록
/ko-kr/app/mnc/{id}/campaign/detail/1/{cid}  캠페인 상세 (AGX 등)
/ko-kr/app/mnc/{id}/partner-programs-hub     프로그램 허브
/ko-kr/app/finance/transactions/{id}         거래 내역
/mldc/ko-kr/app/ari/calendar/{id}            ARI 캘린더
/mldc/ko-kr/app/setting/rooms/{id}/room-mapping   객실 매핑
```

404 나는 경로: `/mldc/ko-kr/app/promotions/{id}`, `/mldc/ko-kr/app/reporting/bookings/{id}`

---

## 5. 아고다 소비자 페이지 — 읽는 법 (2026-08 기준)

```
https://www.agoda.com/ko-kr/{숙소-슬러그}/hotel/{도시-슬러그}.html     ← 숙소의 아고다 페이지 주소를 그대로 쓴다
  ?checkIn=YYYY-MM-DD&los=1&adults=2&rooms=1&currencyCode=KRW&finalPriceView=1
```

**객실 그리드가 가상 스크롤이라 크롬 창이 화면 앞에 떠 있어야만 렌더링된다.**
백그라운드면 `document.visibilityState === "hidden"`, `requestAnimationFrame`이 안 돌고,
`[data-element-name="mob-room-group"]`이 0개다. 자리(약 7,000px)만 잡혀 있고 내용이 없다.

시도해봤지만 전부 실패한 우회:
- 스크롤하며 누적 수집 → 그리드가 없으니 0건
- HTML 직접 fetch → 요금이 HTML에 없다 (클라이언트 렌더링)
- `visibilityState` / `rAF` 강제 패치 → visible로 바뀌지만 IntersectionObserver가 안 돌아 여전히 0건
- 클라우드 컨테이너에서 Playwright → agoda.com 네트워크 차단

### ★ 되는 방법 — computer 툴로 탭을 깨운 직후 JS를 쏜다

`computer` 툴(스크린샷·클릭·스크롤)은 그 탭을 **활성화**시킨다. 활성화된 그 순간
그리드가 마운트되므로, **바로 다음 호출**로 `javascript_tool`을 쏘면 읽힌다.
`browser_batch`로 [scroll → javascript_exec] 를 붙여 보내면 한 번에 된다.
중간에 다른 탭을 건드리면 다시 언마운트되니, 읽기 직전에 그 탭을 만져야 한다.

```
1. navigate  → 소비자 페이지 URL
2. wait 8초  (room-grid API 완료 대기)
3. computer scroll (down 8) — 이게 탭을 깨운다
4. javascript_exec — 아래 스니펫
```

**앵커가 바뀌었다.** `data-element-name="mob-room-group"` 계열은 더 이상 없고
클래스가 `a8dff-` 접두어로 난독화돼 있다. 텍스트 기준으로 잡는 게 안정적이다.

```js
(() => {
  const btns=[...document.querySelectorAll('button,a')]
    .filter(b=>(b.textContent||'').trim().startsWith('예약하기'));
  if(!btns.length) return 'not rendered';       // ← 이러면 탭이 다시 잠든 것
  let e=btns[0]; while(e && (e.textContent||'').length<500) e=e.parentElement;
  return (e.textContent||'').replace(/\s+/g,' ').trim().slice(0,900);
})()
```

읽히는 값: `메가 세일: ₩ N 할인!` · `쿠폰(AGODA_SPONSORED) 할인: ₩ N` ·
`원래 요금: ₩ N`(세전) · 표시가 · `1박당 총 금액 ₩ N`(세금포함 = 표시가 × 1.1).

⚠ 위 스니펫은 첫 카드만 읽고 재판매 오퍼를 가르지 않는다. 화면 구조 확인용이다. 값을 쓸 때는 아래 「직판 오퍼만 골라내기」를 따른다.
`원래 요금`의 세전·세금 포함 표기는 화면 라벨로 확인한다.

**메가세일 할인액이 기준요금 판정에 쓰인다.** 직판 오퍼에서 `(CMS ÷ 세금배수) × 메가세일 할인율`과 원 단위로 맞으면
그 오퍼의 기준값이 그 CMS라는 뜻이다. 객실·요금제 매칭을 추측할 필요가 없다.

### ★ 기준요금은 소비자 페이지 말고 ARI 캘린더에서 읽어라

아고다가 **실제로 들고 있는** 우리 요금이다. 백그라운드에서도 읽힌다.

```
portal.agoda.com/mldc/ko-kr/app/ari/calendar/{id}?startDate=YYYY-MM-DD&endDate=YYYY-MM-DD
```

객실 필터가 기본 1개다. 전체 선택 → 적용하기 후 아코디언을 모두 펴야 객실이 다 보인다.

```js
document.querySelectorAll('[data-testid^="ycs-calendar-page-room-card-accordion-toggle-"]')
  .forEach(b=>{ if(b.getAttribute('aria-expanded')!=='true') b.click(); });
// 그 다음
[...document.querySelectorAll('[data-testid^="rate-card-input-"]')]
  .map(i=>({ id:i.getAttribute('data-testid').replace('rate-card-input-',''), val:i.value }));
// id 형식: {roomId}-{ratePlanId}   값 라벨: "판매 요금(세금 및 봉사료 포함)"
```

창이 보이는 상태라면 이 앵커로 읽는다:

| 앵커 | 뜻 |
|---|---|
| `[data-element-name="roomgrid"]` | 그리드 전체 |
| `[data-element-name="mob-room-group"]` | 객실 타입 하나 |
| `[data-element-name="mob-room-offer"]` | 요금제 하나 |
| `[data-element-name="fpc-room-price"]` | 표시가 |
| `[data-element-name="mob-room-header-occupancy-info"]` | 객실명 근처 |

읽어도 **재판매 오퍼가 섞여 있다** (객실 매핑의 미매핑 객실 등, 다른 업체가 되파는 요금).
숙소 요금보다 싸게 팔리는 경우도 있고, 직판과 객실명이 같은 경우도 있다. 공급처는 포털 어디에도 노출되지 않는다.
재판매 값으로 잰 계수는 모든 역산을 틀리게 한다 (한 숙소 관측: 재판매로 잰 계수 때문에 요금이 한 달간 의도와 달랐다).

### ★ 직판 오퍼만 골라내기 — 객실명 대조는 폐기

**객실명 글자 대조로 우리 것을 고르지 마라.** 오퍼 ID를 디코딩해 직판만 쓴다.
로그인하지 않은 상태로 연다 (회원가가 끼면 틀린다).

```
1. navigate → 소비자 페이지 URL
2. 8초 대기
3. 실제 마우스 휠로 끝까지 내린다 (window.scrollBy 로는 오퍼가 안 뜬다)
4. snippets.js 의 directOffers() 실행
```

판정: 오퍼의 `data-room-offer-id` 를 base64 → varint로 풀어 공급사 코드를 찾는다.
**직판 = 공급사 코드 `332`(zigzag `664`)가 있고, 디코딩 텍스트에 `Some(` 가 없는 오퍼.** 재판매는 `Some(공급처코드)|…` 가 붙는다.

⚠ **공급사 코드 `332` 는 한 숙소에서 확인한 값이다. 다른 숙소에서도 같은지 확인 필요.**
새 숙소에서는 ARI CMS와 원 단위로 맞는 오퍼의 코드가 같은지 먼저 대조하고, 다르면 `directOffers({supplier: 코드})` 로 부른다.
확인 전 값은 `verified:false` 로 적는다.

- 직판이 재판매보다 비싸면 직판 오퍼가 숨겨질 수 있다 (한 숙소 관측, 장기 박수에서 자주). 재판매 값을 쓰지 말고 계수로 계산해 「추정」으로 표시한다.
- **경쟁사 비교도 직판끼리 한다.** 그 호텔 페이지에서 같은 날짜·같은 박수의 직판 오퍼끼리 비교한다. 검색 목록 가격은 재판매일 수 있다.

---

## 6. 알려진 함정

| 증상 | 원인 | 대처 |
|---|---|---|
| 객실 그리드 DOM 0개 | 크롬 창이 백그라운드 | 포털 예약 리포팅으로 우회. 사용자에게 창을 앞으로 올려달라고 요청 |
| `javascript_tool` 결과가 `[BLOCKED: Cookie/query string data]` | 출력에 URL 쿼리스트링 포함 | `href.split('?')[0]`으로 잘라내고 src 제거 |
| CDP `Runtime.evaluate` 45초 타임아웃 | 무거운 페이지에서 긴 루프 | 루프를 async로 띄우고(`(async()=>{...})()`) 나중에 폴링 |
| `browser_batch` wait 거부 | 10초 초과 | 여러 개로 쪼갬 |
| 포털 목록 클릭이 안 먹음 | 상세 서랍이 열려 있음 | `›` 접기 버튼 먼저 |
| 예약 생성일이 2시간 어긋남 | 포털은 방콕(UTC+7) 표기 | 한국시간 = 표기 + 2시간 |
| 계산이 2~3% 어긋남 | 소비자 페이지 표시가를 썼음 | 포털 기준 판매 요금으로 대체 |
| 계산이 크게 어긋남 | Maximum Gain 을 Σ에서 빠뜨림 | Σ는 항상 MG부터 |
| 노출가가 예상보다 높음 | 한국 IP라 지역 타겟팅(International Rate 등)이 안 붙음 | 접속 국가로 갈린다. 국내에서 확인 불가 — 실제 예약 프로모션 내역으로 판정 |
| 노출가가 예상보다 낮음 | 쿠폰(AGODA_SPONSORED)이 추가로 깎임 | Σ와 별개 항목. 아고다 부담으로 정리됐으나 예약 내역으로 숙소마다 확인한다 |
| 아고다 요금칸에 타이핑 안 됨 | 요금관리 그리드에서 disabled | 값은 요금세트가 정한다. 세트를 바꿔야 한다 |
| 쓰려던 요금세트가 안 보임 | 다른 채널 상품그룹 전용 세트 | 상품그룹마다 쓸 수 있는 세트가 다르다 (`cms.md`) |

### 미해결 항목은 숙소 파일에 남긴다

조사 중 풀지 못한 것(중지된 프로모션의 사유, 캠페인 종료일 불일치, 미사용 크레딧,
미매핑 객실 목록, 메가세일 판매 기간 공백 등)은 여기가 아니라
`property.json` 의 `open[]` 과 `properties/{숙소}.md` 의 「아직 확인 못 한 것」에 적는다.
