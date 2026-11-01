// 부킹닷컴 익스트라넷·소비자 페이지에서 값을 읽고 입력하는 브라우저 스니펫.
// 화면 구조가 바뀌면 틀릴 수 있다. 빈 결과는 "값 없음"이 아니라 "판별 불가"로 적는다.

// 프로모션 할인율 칸 입력. 「검토」는 스크립트로 눌리지 않으니 실제 마우스로 누른다.
window.__setInput = function(el, val){
  const setter=Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype,'value').set;
  el.focus(); setter.call(el,String(val));
  el.dispatchEvent(new Event('input',{bubbles:true}));
  el.dispatchEvent(new Event('change',{bubbles:true})); el.blur();
  return el.value;
};

// ses= 가 없는 링크는 눌렀을 때 로그아웃될 수 있다. 누르기 전에 본다.
window.__sesLinks = function(){
  return [...document.querySelectorAll('a')].map(x=>({t:x.innerText.trim(),ses:/[?&]ses=/.test(x.href)}));
};

// 재무 예약 명세서를 금액만 읽는다. 표나 페이지 글자를 통째로 읽으면 예약번호·투숙객 이름까지 나오니 쓰지 않는다.
// 머리글 이름으로 칸을 찾고 체크인·체크아웃·상태·금액 칸만 돌려준다. r 은 수수료율(%)이다.
window.__statement = function(){
  const hs=[...document.querySelectorAll('thead th')].map(x=>x.innerText.trim());
  const ix=re=>hs.findIndex(h=>re.test(h)), n=s=>Number((s||'').replace(/[^\d]/g,''));
  const col={ci:ix(/체크인/),co:ix(/체크아웃/),st:ix(/투숙 여부/),a:ix(/예약 금액/),f:ix(/수수료 금액\(/)};
  if(Object.values(col).some(i=>i<0)) return {error:'머리글을 찾지 못함',hs};
  return [...document.querySelectorAll('tbody tr')].map(r=>{
    const c=[...r.children].map(x=>x.innerText.trim()), a=n(c[col.a]), f=n(c[col.f]);
    return {ci:c[col.ci],co:c[col.co],st:c[col.st],a,f,r:a?+(f/a*100).toFixed(2):null};
  });
};

// 소비자 페이지 예약 가능 여부. nameOK 가 false 면 주소 오류이니 정지로 판정하지 않는다.
window.__availability = function(name){
  const t=document.body.innerText;
  return { nameOK:t.includes(name),
           blocked:/예약하실 수 없습니다|현재 저희 사이트에서/.test(t),
           rows:document.querySelectorAll('#hprt-table tr').length };
};

// 소비자 페이지 요금 행. partner 가 true 면 우리 요금이 아니다. won 은 할인이 있으면 [기존 요금, 표시 요금] 순이다.
// 조식 선택 금액과 「객실 선택」 뒤의 수량별 합계는 뺀다.
window.__rates = function(){
  return [...document.querySelectorAll('#hprt-table tbody tr')].map((r,i)=>{
    const t=(r.innerText||'').replace(/\s+/g,' ').replace(/조식 ₩[\d,]+/g,'').split('객실 선택')[0];
    return {i, partner:/파트너사/.test(t), won:[...new Set(t.match(/₩\s?[\d,]{4,}/g)||[])], off:(t.match(/\d+%\s?(OFF|할인)/)||[''])[0],
            refund:/환불 불가/.test(t), breakfast:/조식/.test(t)};
  }).filter(x=>x.won.length);
};
