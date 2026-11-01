# 수정 절차

고치기 전에 **무엇을 어떻게 바꿀지 목록으로 먼저 보고**하고, 요금 신규 결정·상시 마감 상품은 승인을 받는다.
오늘 날짜는 대상이 아니다(SKILL.md). 사용자가 "조회·조치안까지만"이라고 했으면 이 문서의 조작은 하지 않는다.

**야놀자(NOL) 모텔 파트너센터 · 여기어때 모텔 파트너센터에서 디버깅한 절차다.** 상품 이름·상품 수·이용시간·요금대는
`hotel-profile.md` 에서 온다. 화면 구조는 바뀔 수 있으니 저장 전후로 반드시 다시 읽어 확인한다.

---

## 공통 — 저장 직전에 그 칸만 한 번 더 읽는다

전수 수집과 저장 사이에도 값은 바뀐다. 한 숙소 관측: 수집 때 `판매`였던 칸이 닫으려고 보니 몇 분 사이 이미 `마감`이었고, 누가 바꿨는지는 확인하지 못했다.
방향이 반대였다면 사람이 방금 한 조치를 그대로 되돌리는 셈이다.

- 저장 누르기 직전에 **그 칸의 OTA 상태**를 다시 읽는다. 이미 원하는 상태면 누르지 않는다.
- **열 때는 PMS 잔여도 다시 읽는다.** 잘못 닫으면 판매 손실이지만, 잘못 열면 재고가 적은 객실은 바로 이중 판매다.
- 다시 읽은 값이 바뀌어 있으면 **새 값으로 판정을 다시 한다.** 그 사이 취소로 방이 생겼으면 닫지 않고, 그 사이 팔려 0이 됐으면 열지 않는다.

---

## 야놀자 — 객실 필터가 핵심

> **⚠ 2026-10 화면 변경 가능성 있음, 확인 필요.** 이 절의 모달·좌표 클릭 절차는 이전 화면 기준이다. 포털에서 재검증하지 못해 그대로 두었다. 현재 화면이 다르면 아래 「야놀자 판매설정 모달」 절의 변경 취지를 보고 먼저 확인한다.

야놀자 `판매설정` 모달은 **그 날짜의 모든 상품**을 보여주고, 미설정 상품이 하나라도 섞이면
"모든 판매 정보를 설정해야 저장이 가능합니다"로 막힌다. 그런데 상단 **`객실: 전체선택` 드롭다운으로 상품을 좁히면
모달에도 그 상품만 뜬다.** 이게 이 작업을 가능하게 하는 열쇠다.

### 순서

**1) 객실 필터로 대상 상품만 남긴다**
`객실:` 라벨을 눌러 드롭다운을 열고 해당 상품 체크박스를 좌표 클릭(JS 클릭은 안 먹는다) → `적용(N)`.
라벨이 `객실: 일부선택 (n/전체)`로 바뀌면 성공. **작업이 끝나면 `전체선택`으로 되돌려 놔라.**

**2) 날짜를 고른다**
- 요일 헤더 체크박스(일·월·화·수·목·금·토)로 그 요일 전체를 한 번에 선택할 수 있다 — 20일치도 클릭 몇 번이면 된다
- 개별 날짜는 셀 아무 데나 클릭하면 토글된다
- 하단에 `N개 일자 선택됨`으로 확인. `선택취소`로 초기화

**3) `판매설정` 버튼 → 모달**
여러 날짜의 값이 서로 다르면 `0개/5개`, `19:00/24:00`처럼 **합쳐서 표시**된다. 그럴 땐 전부 명시적으로 다시 설정하면 된다.
모달이 뜨고 나서 **상품 행이 렌더될 때까지 3~5초 기다려라.** 너무 빨리 읽으면 행이 없다.

**4) 값 입력**
텍스트 입력(하위타입 재고 / 판매가)은 React 제어 컴포넌트라 `el.value=` 로는 안 먹는다. 네이티브 setter를 써라:
```js
const set=(el,val)=>{
  const s=Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype,'value').set;
  s.call(el,val);
  el.dispatchEvent(new Event('input',{bubbles:true}));
  el.dispatchEvent(new Event('change',{bubbles:true}));
};
```
제대로 먹었는지는 **입금예정가가 다시 계산되는지**로 확인한다 (판매가에서 그 숙소의 수수료를 뺀 값으로 따라 바뀐다).

각 상품 행의 input 순서: `[0] 판매상태(hidden, true=판매) [1] 재고 [2] 판매가 [3] 개시시각 [4] 마감시각 [5] 이용시간(분)`

셀렉트는 좌표 클릭 후 키보드:
- 판매상태: 판매=첫 항목 → `Home` + `Return`
- 시각: 10:00부터 30분 간격 29개. 11:00=인덱스 2, 12:00=4, 19:00=18, 24:00=마지막(`End`)
- 이용시간: 2시간부터 30분 간격 25개. 7시간=인덱스 10

**5) `저장` → `확인`**
`저장` 왼쪽 끝에 빨간 **`일괄 마감`이 있다. 절대 누르지 마라.**
저장 확인창이 안 뜨면 `저장`을 한 번 더 누르고 `확인` 좌표를 다시 읽어라.

---

## 여기어때 — 칩 + 날짜 + 하단 버튼

훨씬 간단하다. 상단 **상품 칩으로 대상만 켜고**, 날짜 체크박스를 고른 뒤, 하단 `판매`/`마감` 버튼을 누른다.
확인창 문구는 "선택된 날짜의 상품을 모두 …"라고 나오지만 **실제로는 칩으로 켜둔 상품에만 적용된다** (검증 완료).
단 **칩은 몇 초 뒤 전체로 풀릴 수 있다.** 누르기 전에 아래 「판매상태는 캘린더 버튼으로」의 가드를 반드시 통과시켜라.

```js
// 칩: button.chip, 선택 상태는 className 에 is-selected
// 날짜: tbody td 안의 input[type=checkbox] — JS .click() 동작
// 하단 버튼: 판매 button.btn-color-type05 / 준비중 .type04 / 마감 .type03 / 판매설정 .btn-primary.btn-lg
```

**주의 — 유령 모달**: 이전에 열렸던 `.modal` 노드가 DOM에 남아 문구가 갱신되지 않는 경우가 있다.
`마감`을 눌렀는데 확인창이 "판매 상태로 적용하시겠습니까?"라고 나오면 **그 모달은 잔여물이다.**
페이지를 새로 로드한 뒤 다시 선택하고 누르면 문구가 정확해진다. 문구가 의도와 다르면 절대 확인을 누르지 마라.

칩과 날짜 선택은 **작업 후 전부 원상복구**해라 (칩 전부 켜기, 날짜 체크 해제).

---

## 끝나고 반드시

바꾼 날짜를 **다시 읽어서** 상태·재고·요금이 의도대로 들어갔는지 확인한다.
확인하지 못한 항목은 보고서에 "미확인"으로 남기고 완료라고 쓰지 않는다.

---

## 여기어때 — 요금(판매가) 수정: UI 클릭으로는 안 된다

날짜별 요금은 `판매설정` 버튼 → `/reservation/calendar/setup/stay/<날짜>` 화면에서 바꾸는데,
**이 화면의 `적용` 버튼은 `type="submit"` 이고 폼 안에 있어서 클릭하면 네이티브 폼 전송이 일어나
페이지가 통째로 새로고침되고 저장 XHR이 취소된다.** 결과는 `등록된 객실정보가 없습니다` 배너 뒤 그 달 캘린더로 튕김.
그리고 `setup/...` URL로 **직접 이동해도 안 된다** — 라우터 state 없이 들어가면 캘린더로 리다이렉트된다.

여기어때 파트너센터는 **Vue 2 + Vuex + BootstrapVue**다. 컴포넌트를 직접 잡아서 처리하면 100% 재현된다.

### 1) 캘린더 → 설정 화면 (라우터 push)

```js
const fv=t=>{const b=[...document.querySelectorAll('button')].find(x=>x.textContent.trim()===t);
  if(!b)return null;let e=b;while(e){if(e.__vue__)return e.__vue__;e=e.parentElement}return null};
const cal=fv('판매설정');
const T=cal.targetGoods.total, D=cal.targetDates.total;   // 30일치 [{date,rooms:[...]}]
const i=D.indexOf('2026-09-20');
cal.checkedGoods=[T[i]]; cal.checkedDate=['2026-09-20'];
cal.confirmedSalesSetupModal(true);                        // → setup 화면으로 push (2~3초 소요)
```
`checkedGoods`에 여러 날짜 객체를 넣으면 다중 날짜도 되지만, **저장 시 모든 상품 행의 상태·재고가
모든 선택 날짜에 똑같이 덮인다.** 날짜마다 마감 상품이 다르면(예: 토요일 조식 마감) 망가지므로
**하루씩 처리하는 게 안전하다.**

### 1-b) 🚨 저장 전 필수 가드 — 설정 화면은 등록 안 된 상품까지 저장해 등록한다

설정 화면의 `selectedGoodsDatas`에는 **그 날짜에 등록되지 않은 상품도 상품 마스터 기본값으로** 들어 있다.
그대로 저장하면 그 상품이 **그 날짜에 신규 등록된다.** 한 숙소 관측: 캘린더에 없던 상품이 `판매`에 엉뚱한 기본 요금으로 끼어 있었고, 저장 후 실제로 새로 등록되는 것을 확인했다.

저장 전에 캘린더 상품과의 차집합을 구한다. 비어 있어야 안전하다.
```js
const calRooms=T[i].rooms;                                        // 그 날짜의 캘린더 rooms
const calSet=new Set(calRooms.map(r=>String(r.armgno)));
const extra=g.selectedGoodsDatas.filter(o=>!calSet.has(String(o.armgno)));
```
비어 있지 않으면 **행을 지우지 마라** (백엔드가 전체 셋으로 받을 수 있다). 숙박은 그 행을 `dpod_state='4'`(마감) + 같은 상품 다른 날짜의 요금으로 맞춘 뒤 저장한다.
대실은 이 경로의 상태 변경이 서버에 반영되지 않으므로(아래) 저장하지 말고 칩으로 좁혀 `extra`를 비운다. 그래도 남으면 멈추고 확인한다.

### 2) 설정 화면에서 값 변경 + 저장

```js
const st=fv('적용');
const g=st.$store.state.goodsStore;
// 가드 — 엉뚱한 날짜에 쓰지 않도록 반드시 확인
if(g.selectedDates.join()!=='2026-09-20') throw 0;
if(g.selectedGoodsDatas.length!==EXPECTED) throw 0;   // EXPECTED = 프로필의 그 채널 숙박 상품 수

g.selectedGoodsDatas.forEach((o,k)=>{ o.dpod_price = V[k] });   // 판매가만 바꾼다
const res = await st.updateSelectedGoods({type:2});             // {result:true} 면 성공
```
- `selectedGoodsDatas` = 작업본(행 컴포넌트의 `goodsData` prop과 **같은 객체**), `__selectedGoodsDatas__` = 원본
- `dpod_price` 판매가 / `dpod_qty` 재고 / `dpod_state` `"1"`=판매 `"4"`=마감 → **건드리지 않으면 그대로 보존된다**
- 🚨 **`type` 값을 틀리면 다른 탭에 써진다. 호출 전에 반드시 `st.routerParams`를 찍어 확인해라.**
  `type:2` = 숙박. **대실 페이지에서 `type:2`로 저장하면 그 값이 숙박에 덮어써진다** —
  실제로 대실 상품의 요금·재고·이용시간이 같은 이름의 숙박 상품 이틀치를 덮은 사고가 있었다.
  응답은 `{result:true}`였고 대실 캘린더는 안 바뀌어서 "저장 실패"로 오인했다.
  **"저장이 안 먹은 것 같다"면 못 먹은 게 아니라 다른 데 먹었는지를 먼저 의심해라.**
- **🚨 판매상태(`dpod_state`)는 이 경로로 바꾸지 마라.** 숙박은 먹히지만 **대실은 `{result:true}`를 돌려주고도
  서버에 반영되지 않는다**(실측). 상태 변경은 아래 "판매상태는 캘린더 버튼으로" 절차를 써라.
  `updateSelectedGoods`는 **요금·재고·시각 전용**으로 생각하는 게 안전하다.
- 화면 입력창에 직접 타이핑할 땐 **Tab 등으로 blur해야** 스토어에 반영된다. 네이티브 setter + input 이벤트는 표시만 바뀌고 스토어에 안 들어간다

### 3) 한 날짜 끝나면 캘린더로 다시 이동
`navigate` 로 `/reservation/calendar/stay/YYYY-MM` 을 다시 열고 4초 대기 후 다음 날짜를 처리한다.

### 캘린더 날짜 선택이 안 먹을 때
`#day01`~`#day30` 체크박스에 JS `.click()` 을 하면 DOM은 체크되지만 **Vue의 `checkedDate`가 안 바뀌어**
`판매설정`이 아무 반응도 하지 않는다. 좌표 클릭은 먹지만 불안정하다. 위의 Vue 직접 조작이 가장 확실하다.

---

## 야놀자 판매설정 모달 — 실제로 먹히는 순서

> **⚠ 2026-10 화면 변경 가능성 있음, 확인 필요.** 포털에서 재검증하지 못해 아래 절차는 그대로 두었다. 한 숙소 관측으로 드러난 변경 취지는 이렇다.
> - `판매설정`이 `[role=dialog]` 모달이 아니라 전체 페이지(`/sale/motel/calendar/new/detail`)로 열리고, 입력칸은 `name`으로 바로 잡혀 가상 스크롤 우회가 필요 없다.
> - 객실 필터·요일 헤더·`판매설정`·`저장`·`확인`과 판매상태 셀렉트가 좌표 클릭 대신 MouseEvent dispatch로 동작했다. 개별 상품은 `input`이 아니라 `.MuiListItemButton-root` 행에 쏴야 한다.
> - 브라우저 줌이 걸리면 좌표 환산 공식이 어긋났다.
>
> 화면을 먼저 읽고, 맞는 쪽 절차를 쓴다. 저장 전 날짜·상품 확인은 어느 화면이든 그대로다.

모달은 **가상 스크롤**이다. 열자마자 상품 행이 하나도 렌더되지 않고 빈 흰 카드만 있다.
`document.querySelectorAll('[role=dialog] input').length === 0` 이면 아직이다.
**모달 안쪽 스크롤 컨테이너 위에서 실제 휠 스크롤을 아래로 1칸, 위로 2칸** 하면 렌더된다.
프로그램적 `scrollTop` 변경으로는 안 된다. 한 번에 5개 행만 렌더되니 스크롤하며 나눠 작업한다.
**한 번 값을 넣은 행은 언마운트됐다 다시 렌더돼도 값이 유지된다** (react-hook-form이 상태를 들고 있다).

행 잡기:
```js
const d=document.querySelector('[role=dialog]');
window.__row=id=>{const e=[...d.querySelectorAll('*')].find(x=>x.children.length===0&&x.textContent.trim()==='객실 (ID : '+id+')');
  if(!e)return null;let r=e;for(let i=0;i<8;i++){r=r.parentElement;if(r&&r.querySelectorAll('input').length>=4)break}return r};
```
각 행의 input 5개: `[0] 판매상태(MuiSelect-nativeInput, 읽기 전용) [1] 재고 [2] 판매가 [3] 입실시각 [4] 퇴실시각`
input 이름이 `roomtypeInventories.N.inventories.0.bookingRate` 형태다.

**판매가·재고**는 네이티브 setter로 넣으면 먹는다 (입금예정가가 따라서 다시 계산되는지로 확인).
**판매상태는 네이티브 setter로 절대 안 된다.** 반드시 좌표 클릭 → 키보드:
```
select 좌표 클릭 → 2초 대기 → Home → 1초 대기 → Return → 2초 대기
```
`Home`과 `Return` 사이에 대기가 없으면 조용히 실패한다. 옵션은 `[0] 판매 / [1] 마감` 두 개뿐이다.
**판매가를 바꾸면 행 높이가 26px쯤 밀린다.** 값 입력 후에는 좌표를 반드시 다시 계산하고 클릭해라.

여러 날짜의 값이 서로 다르면 입력칸이 **비고 placeholder에 `50,000원/65,000원`처럼 둘 다 표시**된다.
이때 **비워 두면 그 항목은 날짜별 기존 값이 유지된다** — 재고가 날짜마다 다를 때 유용하다.
반대로 값이 이미 채워져 있으면(모든 날짜가 같으면) 덮어쓸 값만 넣으면 된다.
스크립트로 일괄 입력할 때 `if(!ins[2].value)` 같은 조건을 걸면 **이미 값이 있는 행이 옛 요금 그대로 남는다.** 무조건 덮어써라.

날짜 묶기는 요일 헤더 체크박스가 가장 빠르다. 지난달 날짜(회색 칸)는 헤더로 선택해도 포함되지 않는다.
연휴가 낀 달은 요일 그룹에서 몇 개 빼고 몇 개 더하는 식으로 만든다 —
예: 2026년 10월 금요일 요금 = 금 헤더 전체 − 10/9 + 10/8.

`저장` → `저장 하시겠습니까?` → `확인` 을 누르면 캘린더로 돌아온다. 그게 성공 신호다.

---

## 이용시간(입실·퇴실) 바꾸기

**기준값**은 프로필의 「상품별 이용시간」 표에서 읽는다 (예: 일반 객실 15시 입실 ~ 익일 11시 퇴실, 장시간 상품 13시 ~ 익일 19시).
"익일"은 두 채널 모두 **상품 속성으로 암묵 처리**된다. 저장할 값은 시(hour) 숫자뿐이다 (예: `13`과 `19`).

### 야놀자 — 한 달치를 한 번에

시간은 모든 날짜에 같은 값을 넣으므로 **날짜 전체선택이 가능하다.**
1. `객실:` 드롭다운 → `전체선택` 체크박스를 눌러 전부 해제 → 대상 상품만 체크 → `적용(N)`
   (**미설정 상품이 있는 달이면 그 상품은 필터에서 빼라.** 섞이면 저장이 막힌다)
2. 캘린더 헤더 맨 왼쪽 **마스터 체크박스**(요일 헤더들보다 더 왼쪽, 라벨 없음)를 누르면 그 달 전체가 선택된다.
   지난달 회색 칸은 포함되지 않는다 — `30개 일자 선택`처럼 개수로 확인해라.
3. `판매설정` → 모달에서 **시간 셀렉트만** 바꾼다. 재고·판매가 칸은 날짜마다 값이 다르면 비어 있고,
   **비워 두면 날짜별 값이 그대로 유지된다.** 절대 채우지 마라.
4. 시각 옵션은 **10:00부터 1시간 간격 14개** (10:00=0 … 23:00=13). 11:00=1, 12:00=2, 13:00=3, 19:00=9.
   `Home` → `Down`×N → `Return`, 각 키 사이 1초 대기.

### 여기어때 — Vuex 필드 직접 수정

`selectedGoodsDatas[i].chkin_time` / `.chkout_time` (문자열 시(hour))를 바꾸고 `updateSelectedGoods({type:2})`.
```js
const A=g.selectedGoodsDatas;
A.find(o=>o.armgname.trim()==='<상품명>').chkin_time='<입실 시>';     // 프로필의 상품별 이용시간
A.find(o=>o.armgname.trim()==='<상품명>').chkout_time='<퇴실 시>';
```

**여기어때도 다중 날짜가 된다** — `cal.checkedGoods`에 날짜 객체 여러 개를 넣으면 된다.
단 저장은 모든 상품 행 값을 **선택한 모든 날짜에 동일하게** 쓰므로, **재고·요금·상태가 완전히 같은 날짜끼리만 묶어라.**
캘린더에서 날짜별 (상태|잔여|요금) 서명을 만들어 그룹으로 나눈 뒤 그룹 단위로 저장하는 게 안전하다.

### ⚠ 여기어때 함정 — 미설정 상품이 기본값으로 끼어든다

그 달에 **설정되지 않은 상품도 setup 화면의 `selectedGoodsDatas`에는 행으로 들어온다.**
`dpod_state:"1"`(판매)에 엉뚱한 기본 요금(예: 평소 닫아 두는 상품에 10,000원)이 박혀 있어서,
그대로 저장하면 **팔 생각도 없던 상품이 그 가격으로 열린다.**

막는 법: **캘린더 상단 상품 칩으로 대상 상품만 켜라.** 칩을 끄면 그 상품은 `selectedGoodsDatas`에서 아예 빠진다.
```js
const chips=[...document.querySelectorAll('button.chip')];
chips.forEach((c,i)=>{ if(i!==KEEP && c.className.includes('is-selected')) c.click() });
```
칩 클릭은 반영에 한 박자 걸린다 — 클릭 직후 같은 호출에서 상태를 읽으면 옛 값이 나온다. 1.5초 대기 후 확인해라.
저장 전에 `selectedGoodsDatas.length`와 상품명을 **반드시 검증**하고, 끝나면 칩을 전부 다시 켜라.

### 칩 되돌리기 — 한 번에 다 켜려 하지 마라

작업이 끝나면 칩을 전부 다시 켜야 하는데, 루프 안에서 `click()` + `await sleep()`을 여러 번 돌리면
페이지가 매 클릭마다 목록을 다시 그리느라 **`Runtime.evaluate`가 45초 타임아웃**으로 죽는다.
죽어도 클릭 일부는 반영돼 있으니, 다음 호출에서 **상태를 읽고 → 안 켜진 것만 한 개씩** 켜라.

```js
// 상태 확인
[...document.querySelectorAll('button.chip')].map(c=>c.className.includes('is-selected'))
// 안 켜진 것 하나만
const c=[...document.querySelectorAll('button.chip')].find(x=>!x.className.includes('is-selected'));
if(c) c.click();
```
마지막엔 전부 `true`인지 확인하고 끝낸다.

### 여기어때 화면 이동은 `navigate` 말고 `$router.push`

`navigate` 도구로 여기어때 캘린더 URL을 치면 전체 리로드가 걸려 **응답이 타임아웃**나는 일이 잦다.
이미 여기어때 탭이 떠 있으면 SPA 라우터를 직접 밀어라. 훨씬 빠르고 Vuex 상태도 유지된다.
```js
fv('판매설정').$router.push('/reservation/calendar/stay/YYYY-MM');   // 숙박
fv('판매설정').$router.push('/reservation/calendar/rent/YYYY-MM');   // 대실
```
(`fv`는 버튼 텍스트로 Vue 인스턴스를 찾는 헬퍼. 이 문서 위쪽 참고)

## 판매상태(판매/준비중/마감)는 캘린더 버튼으로 바꾼다 — 이게 확실한 경로

`updateSelectedGoods`로 `dpod_state`를 바꾸는 건 대실에서 조용히 실패한다. 상태는 캘린더에서 바꿔라.

1. **칩으로 상품을 좁힌다.** 확인 모달 문구가 *"선택된 날짜의 상품을 **모두** …"* 이므로
   **칩을 안 좁힌 상태에서는 절대 누르지 마라.**
   ```js
   const sel=()=>[...document.querySelectorAll('button.chip')].map(c=>c.className.includes('is-selected'));
   ```
   칩 클릭 한 번마다 캘린더가 refetch되어 10~20초 걸린다. **2.5초 간격 setTimeout 루프**로 돌리고
   진행 상황은 별도 호출로 폴링해라(한 호출 안에서 다 하려 들면 45초 타임아웃).
2. **날짜 셀을 클릭해 선택한다.** 셀은 `td label`이고 내부에 체크박스 input이 없으므로 label을 클릭한다.
   ```js
   const K=1568/window.innerWidth;
   [...document.querySelectorAll('td label')].map(l=>{const r=l.getBoundingClientRect();
     return {t:l.textContent.replace(/\s+/g,' ').trim().slice(0,20),
             x:Math.round((r.left+r.width/2)*K), y:Math.round((r.top+r.height/2)*K)}});
   ```
   **화면 밖 셀은 클릭이 씹힌다.** 먼저 스크롤하고 좌표를 다시 뽑아라.
   클릭 후 `cal.checkedDate`로 실제 선택됐는지 확인한다.
3. **하단 버튼**: `판매`=`.btn-color-type05` / `준비중`=`.btn-color-type04` / `마감`=`.btn-color-type03`

   🚨 **버튼을 누르는 바로 그 호출 안에서 칩·선택 상품·날짜를 검사하고, 통과할 때만 누른다.** 앞선 호출의 확인은 믿지 마라.
   한 숙소 관측: 페이지 이동 직후 칩 하나만 켜져 있다가 몇 초 뒤 전 상품이 켜지고 날짜 선택도 비워졌다. 그대로 눌렀으면 전 상품이 마감될 상황이었고, 이 가드가 막았다.
   ```js
   const fire=el=>['mousedown','mouseup','click'].forEach(t=>
     el.dispatchEvent(new MouseEvent(t,{bubbles:true,cancelable:true,view:window})));   // .click()은 안 눌리는 경우가 있다
   // c = 캘린더 컴포넌트, 대상 = 상품명, 날짜들 = 의도한 날짜 배열
   const chips=[...document.querySelectorAll('button.chip')].filter(b=>b.className.includes('is-selected'));
   const ok = chips.length===1 && chips[0].textContent.trim().startsWith(대상)
     && c.checkedGoods.every(g=>{const en=g.rooms.filter(r=>!r.disabled);return en.length===1&&en[0].armgname.trim()===대상})
     && [...c.checkedDate].sort().join()===[...날짜들].sort().join();
   if(ok) fire(버튼); else '가드 실패 — 누르지 않음';
   ```
   칩으로 선택된 상품만 `disabled:false`다. 페이지 이동 후에는 5초 이상 기다렸다가 칩을 다시 읽고 시작한다.
4. **모달 문구를 읽고** 의도와 맞을 때만 `확인`. **`확인`도 3번과 같은 가드를 그 호출 안에서 통과할 때만 누르고, 실패하면 `취소`를 누른다.** 모달은 뷰포트 밖에 렌더될 수 있으니 좌표를 DOM에서 계산한다.
   ```js
   [...document.querySelectorAll('.modal-content button')].map(b=>{const r=b.getBoundingClientRect();
     return b.textContent.trim()+'@'+Math.round((r.left+r.width/2)*K)+','+Math.round((r.top+r.height/2)*K)});
   ```
5. **끝나면 칩을 전부 되돌린다.** 칩 필터는 새로 로드해도 유지될 때가 있지만 **몇 초 뒤 전체 선택으로 풀릴 수도 있다.** 유지된다고도, 저절로 돌아온다고도 믿지 마라.

> 읽기는 칩과 무관하다. `cal.targetGoods.total[i].rooms`는 칩 필터와 상관없이 전 상품을 담는다.

### 저장 결과는 캘린더 데이터로 검증한다

**`selectedGoodsDatas`의 행과 캘린더 `rooms`의 행은 같은 객체다.** 로컬에서 값만 바꿔도
캘린더가 바뀐 것처럼 보인다. 검증은 반드시 **재fetch 후**에 한다 —
다른 달/다른 탭으로 `$router.push` 했다가 돌아오거나 `location.href`로 실제 로드를 시켜라.

`updateSelectedGoods`가 `{result:true}`를 줘도 그걸로 끝내지 마라.
(`saleStatus` 필드도 성패 지표가 아니다 — 실패한 저장에서도 `result:true`가 나온다.)

### 작업 끝에 이상값 전수 스캔을 돌려라

바꾼 날짜만 보지 말고 **그 달 전체**를 훑어 엉뚱한 값이 섞였는지 본다. 한 번에 다 잡힌다.
```js
T.forEach(d=>d.rooms.forEach(r=>{
  const n=r.armgname.trim(), ci=(r.dpod_chkin_date||'').slice(11,16), co=(r.dpod_chkout_date||'').slice(11,16);
  const exp=TIMES[n];                       // 프로필의 상품별 이용시간. 예: {ci:'15:00', co:'11:00'}
  if(r.price>0 && r.price<STAY_MIN)         bad.push(d.date+' '+n+' 대실요금대');   // 숙박에 대실값 유입
  if(exp && !(ci===exp.ci && co===exp.co))  bad.push(d.date+' '+n+' 시각이상');
}));
// STAY_MIN = 프로필의 숙박 최저 요금. TIMES = {상품명: {ci, co}}.
// 대실 쪽은 반대로: r.price 가 프로필의 대실 최고 요금보다 크면 숙박값이 유입된 것
// 날짜별 상품 수도 같이 센다: [...new Set(T.map(d=>d.rooms.length))]
``` 캘린더로 돌아가
`cal.targetGoods.total`을 읽으면 날짜별 최종 상태가 그대로 나온다 — 이게 진짜 확인이다.
```js
cal.targetGoods.total.map(d=>d.date.slice(5)+'|'+
  d.rooms.map(r=>r.status+'/'+(r.price/1000)+'/'+r.total_stock).join(' ')).join('\n')
// status 1=판매 3=준비중 4=마감 · price 판매가 · total_stock 남은 재고 · sales_volume 판매된 수
```
한 번에 다 뽑으면 출력이 잘리니 **10일씩 끊어서** 읽어라.

---

## 한 달 오픈 — 마감 해제는 맨 마지막이다

**"오픈하자"를 마감 해제 지시로 좁게 읽지 마라.** 한 달 오픈은 요금·상품·재고가 다 준비된 뒤의 마지막 한 걸음이다.

### 순서 (고정)

1. **요금** — 프로필의 tier대로 값이 다 들어갔나? tier마다 같은 단일값이면 미입력을 의심한다. 딱 떨어지는 값은 특히 기본값일 수 있다
2. **서열** — 상위 객실이 하위 객실보다 싸지 않나? 프로필로 등급 순서를 알 수 없으면 사용자에게 묻는다
3. **상품 목록** — 전달과 비교해 빠진 상품이 없나?
4. **재고** — 0이면 마감 해제로는 안 열린다
5. **상태 코드** — **준비중은 마감이 아니다.** 여기어때 `status:3`은 판매 기간 밖이라 마감 해제로 안 열리고 판매 기간 설정이 따로 필요하다
6. **마감 해제** — 위가 전부 끝나고 검증된 뒤에만 한다

### 이미 팔린 칸은 먼저 목록으로 뽑는다

마감 해제는 그 달 전체를 `판매`로 깐다. 그런데 닫혀 있는 동안에도 다른 채널에서 예약이 들어와 PMS 잔여는 줄어 있다.
**오픈 전에 PMS를 읽어 "오픈할 때 닫아 둘 칸" 목록을 만들고**(오버부킹 허용치 적용), 해제에서 빼거나 해제 직후 닫는다. 재고가 1실 같은 객실부터 본다.
오픈 다음 날에는 재고 조사를 한 번 더 돌린다.

### 다음 달 말일까지 점검하되, 자동으로 열지 않는다

매 조사에서 범위를 **다음 달 말일까지** 넓혀 그 달이 통째로 못 파는 상태인지 본다. 전 날짜 `마감` · 재고 0 · `준비중` · 상품 미등록이 모두 해당한다.
모든 채널이 똑같이 닫혀 있으면 채널 비교로는 안 잡힌다. **PMS 잔여 대 판매 가능 여부로만 보인다.**
발견하면 **보고만 하고 자동으로 열지 마라.** 한 달을 여는 건 운영자의 판단이다. 프로필의 「열지 않는 기간」도 확인한다.

### 어디서 끊겨도 안 팔리는 상태로 멈춘다

요금 입력 → 요금 검증 → 마감 해제 순서를 지키면 세션이 중간에 끊겨도 전부 마감이라 아무것도 안 팔린다.
반대 순서면 틀린 요금이 열린 채로 멈출 수 있다. 한 숙소 관측: 요금 작업이 절반 진행된 지점에서 브라우저가 끊겼지만 마감 해제 전이라 손해가 없었다.
재개할 때는 **이미 저장한 구간을 재조회로 먼저 검증**하고 다음 구간으로 간다.
