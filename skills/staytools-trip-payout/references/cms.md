## (선택) WINGSCMS를 쓰는 숙소

**WINGSCMS를 쓰지 않는 숙소는 이 절을 건너뛴다.** 주소는 `https://wingscms.com` 이다. 그룹 코드는 프로필에 적는다.

| 화면 | 경로 | 하는 일 |
|---|---|---|
| 요금세트 생성 | `#/app/cm/cm03_0600` | **가격 숫자**를 바꾸는 화면 |
| 요금 관리 | `#/app/cm/cm03_0200` | 날짜별 세트 지정·확인. 이 화면에도 저장 버튼이 있으니 읽기만 할 때는 누르지 않는다 |

**세트 값과 날짜 매핑은 두 단계다.** 값만 넣고 매핑을 안 하면 달력은 옛 세트를 보여 준다. 판매가를 바꾸면 관련 그룹(조식 등)도 프로필 규칙대로 같이 입력한다.
세트의 열은 여러 개다. 한 열만 고치면 나머지가 구멍으로 남는다.

### 입력 절차

그룹을 바꿀 때마다 헤더를 다시 읽는다. **칸 id를 외우지 마라** — 그룹·재로드에 따라 달라진다.

```js
const heads=[...document.querySelectorAll('.ag-header-cell')].map(h=>[h.getAttribute('col-id'),h.innerText.trim().split('\n')[0]]);
```

```js
// 탭이 백그라운드여도 멈추지 않는 대기. setTimeout은 스로틀돼 칸이 0으로 남을 수 있다
window.__sleep=ms=>new Promise(res=>{const t0=performance.now();const ch=new MessageChannel();
 ch.port1.onmessage=()=>{if(performance.now()-t0>=ms)res();else ch.port2.postMessage(0);};ch.port2.postMessage(0);});

// 빈 값을 먼저 넣어 React 값 추적기를 깨고, 이벤트 사이에 틈을 준다
window.__put=async function(el,val){
  const set=Object.getOwnPropertyDescriptor(HTMLInputElement.prototype,'value').set;
  el.focus(); set.call(el,''); el.dispatchEvent(new Event('input',{bubbles:true})); await __sleep(120);
  set.call(el,String(val)); el.dispatchEvent(new Event('input',{bubbles:true})); await __sleep(120);
  el.dispatchEvent(new Event('change',{bubbles:true})); await __sleep(120);
  el.dispatchEvent(new Event('blur',{bubbles:true}));
};
```

- 행은 객실 이름으로 확인한다. 왼쪽 고정열과 가운데 영역이 같은 `row-index`를 쓰니 컨테이너를 구분해 읽는다.
- 한 호출에 1~4칸만 넣고, **별도 호출로** DOM값과 React값을 대조한다. 어긋난 칸은 그대로 저장하면 옛 값이 남는다.
- `Runtime.evaluate`는 45초에서 끊긴다. 화면 전환과 재조회를 한 호출에 몰지 않는다.
- 그룹을 바꾼 뒤에는 스크린샷을 찍어 그리드 값까지 확인하고 나서 읽는다. 0개가 읽히면 값이 없는 게 아니라 안 그려진 것이다.
- 입력 전 값과 요금ID를 롤백값으로 적는다.

| 함정 | 대처 |
|---|---|
| 저장 전 새로고침·이동 | 확인창이 떠 탭이 멈출 수 있다. 이탈하지 않는다 |
| 포커스가 저장 버튼으로 흘러간 채 Enter | 저장이 눌린다. Enter를 쓰지 않는다 |
| 저장 뒤 같은 탭에서 옛 값이 보인다 | 저장 실패로 단정하지 말고 **새 탭으로** 읽는다. 재저장에서 오류(`ORA-20106`)가 난 적이 있다 |
| 숨은 모달 문구를 DOM에서 잡아 오판 | 「저장 되었습니다」는 화면으로 확인한다 |
| 이전 모달이 남아 그리드를 가린다 | 보이는 확인 버튼을 닫고 다시 읽는다 |
| 요금 관리 표의 「요금세트」 줄과 「요금」 줄이 한 칸 어긋난다 | 이미 아는 짝으로 맞춰 본다 |

저장 확인은 모달 + 재조회 + 새 요금ID 세 가지로 하고, 최종 확인은 고객 페이지 정가로 한다.
