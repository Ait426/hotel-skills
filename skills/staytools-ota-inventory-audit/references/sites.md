# 사이트별 수집 절차

**YFlux PMS · 야놀자(NOL) 모텔 파트너센터 · 여기어때 모텔 파트너센터를 쓰는 숙소에서 디버깅한 절차다.**
숙소가 쓰는 시스템이 다르면 같은 항목(객실타입×날짜 잔여 / 상품×날짜 판매상태·잔여·요금)을
그 시스템의 화면이나 내보내기 파일에서 읽는다. 숙소 ID·상품 이름·객실 수는 `hotel-profile.md` 에서 온다.
화면 구조는 바뀔 수 있다 — 스니펫이 빈 값을 주면 "0건"으로 읽지 말고 다시 확인한다.

브라우저는 Claude in Chrome(`mcp__claude-in-chrome__*`). 세 사이트 모두 사용자가 로그인해 둔 세션을 쓴다.
계정이 여러 크롬에 연결돼 있으면 먼저 어느 브라우저인지 물어봐야 한다.

---

## 공통 — 좌표 환산 (이거 틀리면 엉뚱한 데를 누른다)

**클릭 좌표 = DOM의 getBoundingClientRect 값 × (1568 / window.innerWidth)**

(⚠ 2026-10 화면 변경 가능성 있음, 확인 필요 — 브라우저 줌이 걸리면 이 공식이 어긋난 관측이 있다.)

스크린샷 이미지의 픽셀 좌표와 클릭 좌표계가 **다를 수 있다.** 스크린샷을 눈으로 보고 좌표를 찍지 말고,
항상 DOM에서 요소 위치를 읽어 위 식으로 환산해라. 탭마다 innerWidth가 다르다(예: 1920이면 계수 0.8167, 1536이면 1.021). 탭마다 다시 계산한다.

MUI 셀렉트는 좌표 클릭으로 열고, **키보드로 고른다**: 열린 뒤 `ArrowUp`/`ArrowDown`으로 이동 후 `Return`.
값이 없는 셀렉트는 `ArrowDown` N번이 인덱스 N에 안착한다. 첫 항목은 `Home`, 마지막은 `End`.

---

## 1) YFlux PMS — 기준 재고

- 주소: `https://pms.yflux.biz/reservationManagement/availableRooms`
- 상단 라디오로 **숙박 / 대실** 전환. 좌측 메뉴 `예약 > 판매 가능 객실`
- 오늘부터 30일이 자동으로 표시된다

DOM 수집:
```js
const days   = [...document.querySelectorAll('.times-header .day-view')].map(e=>e.innerText.replace(/\s+/g,' ').trim());
const rows   = [...document.querySelectorAll('.times-body-container > .room-type')];
const labels = [...document.querySelectorAll('.left .room-type')].map(e=>e.innerText.replace(/\s+/g,' ').trim());
const out={}; rows.forEach((r,i)=>{ out[labels[i]] = [...r.children].map(c=>c.textContent.trim()) });
```

객실 타입과 타입별 객실 수는 프로필에 적힌 것과 화면 라벨을 대조한다. 다르면 프로필부터 고친다.

PMS 대실 잔여는 거의 항상 만실 수준이라 대실 판정의 기준으로는 약하다. **대실은 두 OTA끼리 비교하는 게 더 유용하다.**

---

## 2) 야놀자(NOL) 파트너센터

- 숙박: `https://partner.yanolja.com/sale/motel/calendar/new?startDate=YYYY-MM-01&endDate=YYYY-MM-31`
- 대실: 같은 주소에 `&useType=RENT`
- 로드되면 공지 모달이 뜬다. `[role=dialog]` 안의 빈 텍스트 버튼(X)을 눌러 닫고, "하루동안 공지 보지 않기" 체크박스가 있으면 같이 체크한다.

### 주차 펼치기
우측에 `1주 ~ 6주` 버튼이 있다. 해당 주를 눌러야 그 주의 카드가 렌더된다.

### 가상 스크롤 우회 — 이게 핵심
카드가 뷰포트 밖이면 DOM에 자리만 있고 **텍스트가 비어 있다.** `window.scrollTo`나 `scrollIntoView`로는
렌더가 트리거되지 않는다. **실제 휠 스크롤만 먹는다.**

가장 빠른 방법:
```js
document.body.style.zoom = '0.2';   // 한 화면에 한 달치를 다 넣는다
window.scrollTo(0,0);
```
그다음 `computer` 도구로 **실제 스크롤 2틱**을 준다 → 한 번에 전부 렌더된다. 수집이 끝나면 `zoom=''`로 되돌린다.

### 셀 파싱
```js
const ST=['판매','마감','매진','준비','종료','미설정'];
const walk=e=>{const o=[];const w=document.createTreeWalker(e,NodeFilter.SHOW_TEXT);let n;while(n=w.nextNode()){const t=n.textContent.trim();if(t)o.push(t)}return o};
[...document.querySelectorAll('.DataCalendar-dateCell')].forEach(c=>{
  const cont=c.querySelector('.DataCalendar-dateCell-contents'); if(!cont) return;
  const day=(walk(c)[0]||'').trim();
  const stack=[...cont.children].find(x=>x.children.length>0); if(!stack) return;
  const items=[...stack.children].map(it=>{
    const t=walk(it); if(!ST.includes(t[0])) return null;
    const gold = /^Gold\s*\d+%$/.test(t[1]||'');   // 할인 변형 라벨(예: 'Gold 10%')이 끼면 이름은 그다음 노드에 있다
    const name = (gold ? t[2] : t[1]) || '';
    const ri = t.indexOf('재고');
    return { name, gold, status:t[0], stock: ri>=0 ? t[ri+1] : null };
  }).filter(Boolean);
});
```
`innerText`는 안 보이는 카드를 건너뛰므로 **TreeWalker로 읽어라.**

상태 뜻: `판매`=판매 가능 · `마감`=수동 마감 · `매진`=재고 0 · `준비`=판매 기간 밖 · `미설정`=상품 등록 안 됨

### 숙박 상품
상품 목록은 숙소마다 다르다. 프로필의 「OTA 상품 ↔ PMS 객실 매핑」 표가 기준이다.
매 조사마다 화면에서 상품 이름 배열을 먼저 찍어 프로필과 달라졌는지(상품이 늘거나 줄었는지) 확인한다.

### 대실 상품
프로필에 「대실 운영 상품」으로 적힌 것만 운영 대상이다 — 나머지는 미설정이 정상

### ★ 더 빠른 길 — 화면을 긁지 말고 내부 API 응답을 가로채라

가상 스크롤 + TreeWalker는 **텍스트**만 준다(재고/판매가가 문자열, 미설정 판정이 애매). 캘린더가 부르는
내부 API를 가로채면 **날짜 × 상품별 구조체가 그대로** 온다. 한 달치 한 번에, 오차 없이.

엔드포인트: `https://sos-mashup.yanolja.com/motel/properties/<propertyId>/salesCalendar/rateplan/daily/inventories?startDate=&endDate=`

- **직접 fetch 하면 `AUTHENTICATION_REQUIRED`가 온다.** 재현하지 말고 가로채라.
- **이 앱은 XHR(axios)을 쓴다.** `window.fetch`만 후킹하면 아무것도 안 잡힌다 — `XMLHttpRequest.prototype.send`를 후킹해야 한다.
- **`history.pushState` + 합성 `popstate`로는 라우터가 안 움직인다.** 재요청을 일으키려면 **실제 UI 클릭**이 필요하다
  (상단 `YYYY.MM` 좌우의 `<`/`>` 버튼, 또는 `대실`/`숙박` 탭).

```js
// 1) 후킹 (한 번만)
window.__full=null;
const os=XMLHttpRequest.prototype.send;
XMLHttpRequest.prototype.send=function(){
  this.addEventListener('load',()=>{
    if(String(this.responseURL||'').indexOf('daily/inventories')>-1) window.__full=this.responseText;
  });
  return os.apply(this,arguments);
};
```
```js
// 2) 월 이동 버튼 좌표 구하기 → computer 도구로 실제 클릭
const S=1568/window.innerWidth;
const sp=[...document.querySelectorAll('*')].find(e=>e.children.length===0&&/^\d{4}\.\d+$/.test(e.textContent.trim()));
[...sp.parentElement.children].map(c=>{const r=c.getBoundingClientRect();
  return [c.tagName, Math.round((r.left+r.width/2)*S), Math.round((r.top+r.height/2)*S)]});
// → [["BUTTON",277,142],["SPAN",345,142],["BUTTON",413,142]]  ← 좌: 이전달, 우: 다음달
```
```js
// 3) 클릭 후 파싱
const I = JSON.parse(window.__full).inventories;   // 31일 × 상품수
// 각 원소: {date, roomtypeName, useType:'STAY'|'RENT', bookingRate, rackRate,
//           quantity, soldQuantity, reservableQuantity, saleOpen, inventoryStatus,
//           checkInTime, checkOutTime, useTime, roomInventoryLinkStatus, ...}
```

판정 대응표:
| 필드 | 뜻 |
|---|---|
| `saleOpen:false` | 마감 |
| `quantity` | 배정 총량 · `soldQuantity` 판매됨 · `reservableQuantity` 남은 것 |
| `quantity:null` + `checkInTime:null` | **미설정**(상품 미등록) |
| `inventoryStatus` | `SALE` / `CLOSE` / `SOLD_OUT` |
| `roomInventoryLinkStatus` | `UNLINKED`면 PMS와 재고 연동 없음 → 배정은 수동 관리 |

**PMS 잔여와 비교할 때는 `quantity`가 아니라 `reservableQuantity`를 써라.** 이미 팔린 방이 `quantity`에 남아 있어서
`quantity > PMS잔여`가 가짜 오버부킹으로 잡힌다.

---

## 3) 여기어때 파트너센터

- 로그인 관문: `https://partner.goodchoice.kr` — 로그인 안 돼 있으면 **대신 로그인하지 말고 사용자에게 요청한다**
- 숙박: `https://ad.goodchoice.kr/reservation/calendar/stay/YYYY-MM`
- 대실: `https://ad.goodchoice.kr/reservation/calendar/rent/YYYY-MM`

여기어때는 가상 스크롤이 없다. `innerText` 파싱으로 한 번에 다 읽힌다.

```js
const P=[/* 프로필의 여기어때 상품명을 화면 표기 그대로 넣는다. 예: '스탠다드','스탠다드 + 조식 1인','디럭스' */];
const L=document.body.innerText.split('\n').map(s=>s.trim());
// 날짜 숫자 다음 줄이 상품명이면 그 날짜 블록의 시작. 상품명 뒤 몇 줄 안에 상태와 '잔여 N'이 온다.
```
또는 DOM으로: `tbody td` 안의 `.calendar-item-wrapper__information-contents` 가 상품 카드,
`.calendar-item-wrapper__information-contents--room-type` 이 상품명.

채널마다 상품 수가 다를 수 있다(한 채널에만 있는 전용 상품). 프로필에 채널별 상품 목록을 따로 적는다.

날짜 셀 체크박스: `tbody td input[type=checkbox]` — 여기는 **JS `.click()`이 그대로 먹는다.**
상품 필터 칩: `button.chip` (선택 상태는 클래스에 `is-selected`) — 이것도 JS 클릭 가능.

---

## PMS — 30일 밖의 날짜를 읽는 법 (화면 조작 말고 API로)

`판매 가능 객실` 화면은 **오늘부터 30일**만 보여준다. 상단 날짜 피커로 시작일을 옮기려 해도
좁은 창에서는 날짜 셀 클릭이 잘 안 먹고, `selectedDate`를 직접 바꿔도 데이터는 다시 안 받아온다.

이 페이지는 **Vue**다. 컴포넌트를 잡아서 API를 직접 부르는 게 가장 빠르고 정확하다.

```js
// 1) 컴포넌트 잡기 — $apiService를 가진 첫 Vue 인스턴스를 찾는다
let v=null;
const walk=e=>{if(!e||v)return; if(e.__vue__&&e.__vue__.$apiService){v=e.__vue__;return} [...e.children].forEach(walk)};
walk(document.body);

// 2) ★ 한 달씩 끊어서 부른다. 61일(두 달)을 한 번에 주면 빈 배열 []이 온다
const sep = await v.$apiService.timelineApi.selectReportsAvailableRooms({from:'2026-09-01', to:'2026-09-30'});
const oct = await v.$apiService.timelineApi.selectReportsAvailableRooms({from:'2026-10-01', to:'2026-10-31'});
const data = sep;   // 아래 예시는 한 달 기준

// 3) 객실타입 × 날짜 잔여
data.availableRoomsForRoomTypes
  .filter(rt=>rt.roomCount)                      // roomCount 0 = '객실 타입 없음' 더미
  .forEach(rt=>console.log(rt.roomTypeName, rt.dailyAvailableRooms.map(x=>x.stayInventory)));
```
`dailyAvailableRooms[i]`는 `{date, stayInventory, rentInventory, stayReservationCount, outOfOrderCount, ...}`.
숙박 판정에 쓸 값은 **`stayInventory`(잔여)** 다.

판정을 빨리 하려면 **잔여 0인 (객실타입, 날짜) 조합만 먼저 뽑아라.** 대부분의 날은 방이 남아 있어서,
0인 칸만 찾으면 "닫혀 있어야 할 곳"이 바로 나오고 나머지는 전부 "열려 있어야 할 곳"이다.
