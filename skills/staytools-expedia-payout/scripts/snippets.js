// 익스피디아 파트너센트럴·고객페이지에서 값을 읽고 입력하는 브라우저 스니펫.
// 포털 구조가 바뀌면 틀릴 수 있다. 결과의 날짜와 오류 표시를 먼저 확인한다.

// ★ 탭이 백그라운드여도 동작한다. 마지막 blur가 핵심 —
// blur는 버블링은 안 하지만 캡처 리스너는 탄다. React 16이 이걸로 값을 받는다.
window.__setInput = function(el, val){
  const s = Object.getOwnPropertyDescriptor(HTMLInputElement.prototype,'value').set;
  el.focus();
  s.call(el, String(val));
  el.dispatchEvent(new Event('input',  {bubbles:true}));
  el.dispatchEvent(new Event('change', {bubbles:true}));
  el.dispatchEvent(new FocusEvent('focusout',{bubbles:true}));
  el.dispatchEvent(new FocusEvent('blur',{bubbles:false}));
  return el.value;
};

// 카드 제목으로 Edit 링크 찾기. length<300 가드가 필수 —
// 없으면 조상 탐색이 페이지 전체 텍스트를 물어 엉뚱한 섹션을 연다.
window.__edCard = function(re){
  const eds=[...document.querySelectorAll('a,button')].filter(b=>/^\s*Edit\s*$/.test(b.textContent||''));
  for(const b of eds){ let c=b,best='';
    for(let k=0;k<8&&c;k++){ c=c.parentElement; const tx=(c&&c.innerText||'').replace(/\s+/g,' ');
      if(tx.length>8 && tx.length<300){ best=tx; break; } }
    if(re.test(best)){ b.click(); return 'ok'; } }
  return 'nf';
};

// 고객페이지 읽기 — won은 객실마다 3개씩: 세전 정가 / 할인 후 세전 / 세금 포함
window.__customer = function(){
const t=document.body.innerText.replace(/\s+/g,' ');
const h=document.documentElement.innerHTML;
return ({ err:/문제가 있는 것 같습니다/.test(t),
   dt:(t.match(/날짜 ([^인]{5,40})인원/)||['',''])[1],
   pct:[...new Set(h.match(/\d+%\s?할인/g)||[])],
   won:[...new Set(h.match(/₩[\d,]{5,9}/g)||[])].slice(0,24) });
};

// 예약 상세의 결제 내역 읽기. 결제 내역은 iframe 안에 있다.
window.__payment = function(){
  const f=[...document.querySelectorAll('iframe')].find(x=>/payment-display-iframe/.test(x.id||''));
  if(!f) return null;
  // 금액 영역만 돌려준다. 앞부분은 투숙객 정보가 섞일 수 있다.
  const t=f.contentDocument.body.innerText.replace(/\s+/g,' ');
  const i=t.search(/결제 정보|Nightly rates/);
  return i<0 ? null : t.slice(i);
};

// 예약 목록에서 예약 ID만 뽑는다. 목록 원문에는 투숙객 이름이 있으니 화면 글자를 그대로 내보내지 않는다.
// 확인 번호(17자리)는 \b 경계로 걸러진다.
window.__bookingIds = function(){
  return [...new Set(document.body.innerText.match(/\b\d{10}\b/g)||[])];
};

// 점검 화면 본문만 읽는다. 왼쪽 메뉴 글자를 빼고 이메일과 8자리 이상 번호를 가린다. 예약·메시지·후기 목록에는 쓰지 않는다.
window.__epcText = function(max){
  let t=document.body.innerText.replace(/\s+/g,' ');
  t=t.replace(/홈 홈 판매 증진을 위한 기회.*?데이터 및 분석 정보 데이터 및 분석 정보 /g,' ')
     .replace(/관리 관리 도움말 및 지원.*$/,'')
     .replace(/[\w.+-]+@[\w.-]+/g,'@').replace(/\b\d{8,}\b/g,'#');
  return t.slice(0,max||3000);
};

// 투숙 후 이용 후기 화면의 앞부분(안내·필터·답변 대기 문구)만 읽는다. 후기 목록 전에서 자른다.
window.__epcReviewHead = function(){
  const t=document.body.innerText.replace(/\s+/g,' ');
  const f=t.indexOf('필터');
  if(f<0) return {error:'필터 위치를 못 찾음. 화면이 덜 떴으면 기다렸다 다시 부른다'};
  // 필터 뒤 글자는 판정에만 쓰고 내보내지 않는다. 답변 대기 후기가 있으면 그 자리에 투숙객 이름이 온다.
  return {noneWaiting:/답변을 기다리는 이용 후기가 없습니다/.test(t.slice(f,f+120)), head:t.slice(0,f).replace(/[\w.+-]+@[\w.-]+/g,'@')};
};
