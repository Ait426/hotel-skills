// 트립닷컴 eBooking·고객 페이지에서 값을 읽고 입력하는 브라우저 스니펫.
// 화면 구조가 바뀌면 틀릴 수 있다. 빈 결과는 "값 없음"이 아니라 "판별 불가"로 적는다.

// 프로모션 할인율 칸은 React 칸이다. 넣은 뒤 DOM값과 하단 요약이 새 %로 바뀌었는지 둘 다 본다.
window.__setInput = function(el, val){
  const s = Object.getOwnPropertyDescriptor(HTMLInputElement.prototype,'value').set;
  el.focus();
  s.call(el, String(val));
  el.dispatchEvent(new Event('input',  {bubbles:true}));
  el.dispatchEvent(new Event('change', {bubbles:true}));
  return el.value;
};

// 고객 페이지의 요금 행을 우리 요금(DIRECT)과 다른 공급처(AGENT)로 가른다. 클래스 이름은 바뀔 수 있다.
window.__resale = function(){
  return [...document.querySelectorAll('[class*="saleRoomItemBox__"]')].map((r,i)=>{
    const de=r.getAttribute('data-exposure')||'';
    const t=(r.innerText||'').replace(/\n+/g,' ~ ');
    return '['+i+'] '+(/AgentRoom/.test(de)?'AGENT ':'DIRECT')+' | '+(t.match(/[\d,]{6,}원/g)||[]).join(' / ');
  }).join('\n');
};

// 예약 드로어의 지불 정보만 읽는다. 앞뒤에는 투숙객 정보와 연락처가 있으니 금액 구간 밖은 내보내지 않는다.
window.__payment = function(){
  const t=document.body.innerText.replace(/\s+/g,' ');
  const i=t.lastIndexOf('지불 정보');
  const j=i<0 ? -1 : t.indexOf('자세히 보기', i);
  return j<0 ? null : t.slice(i, j);
};

// 예약 목록 한 페이지를 돈다. 번호는 내보내지 않고 목록 순번으로만 가리킨다.
// ★ 드로어를 닫지 않으면 주소의 orderId 만 바뀌고 내용은 옛 예약 그대로다. 그래서 매번 닫고,
// 목록 행 금액과 드로어 지급액이 같은지(same)로 그 예약이 맞는지 본다. same 이 false 면 그 값을 쓰지 마라.
window.__payments = async function(){
  const sleep=ms=>new Promise(r=>setTimeout(r,ms));
  const num=s=>Math.round(+String(s||'').replace(/,/g,''));
  const ids=[...new Set(document.body.innerText.match(/\b\d{13,19}\b/g)||[])], out=[];
  for(let n=0;n<ids.length;n++){
    const cell=[...document.querySelectorAll('td div,td span')].filter(e=>(e.innerText||'').trim()===ids[n]);
    if(!cell.length){ out.push({n, err:'셀 없음'}); continue; }
    const row=(cell[0].closest('tr').innerText||'').replace(/\s/g,'').match(/KRW([\d,]+)/);
    cell[cell.length-1].click(); await sleep(2500);
    const text=window.__payment();
    const pay=text && (text.match(/지급액 KRW ([\d,]+)/)||[])[1];
    document.querySelector('.he-trip-kit-ui-drawer-mask')?.click(); await sleep(900);
    const closed=!document.body.innerText.includes('지불 정보');
    out.push({n, same: !!pay && !!row && num(pay)===num(row[1]), closed, text});
    if(!closed) break;
  }
  return out;
};

// 점검 화면 본문만 읽는다. 왼쪽 메뉴·머리글 글자를 빼고 이메일과 8자리 이상 번호·전화번호를 가린다.
// 메인·예약·메시지·리뷰 목록 화면에는 쓰지 않는다. 투숙객 이름이 본문에 있다.
window.__ebText = function(max){
  const nav=[...document.querySelectorAll('aside,nav,[class*="menu"],[class*="Menu"],[class*="sider"],[class*="header"],[class*="Header"]')];
  let t=document.body.innerText;
  for(const n of nav){ const x=(n.innerText||'').trim(); if(x.length>20) t=t.split(x).join(' '); }
  t=t.replace(/\s+/g,' ').replace(/[\w.+-]+@[\w.-]+/g,'@').replace(/\b\d{8,}\b/g,'#').replace(/\+?\d[\d -]{8,}\d/g,'#');
  return t.slice(0,max||3000);
};
