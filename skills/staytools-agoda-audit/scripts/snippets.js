/* 아고다 조사용 브라우저 스니펫 모음
 *
 * 전부 실제로 디버깅을 마친 코드다. 포털 DOM은 data-testid 가 있는 곳과 없는 곳이
 * 섞여 있어서 즉석에서 짜면 대부분 빈 배열이 나온다. 여기 있는 걸 써라.
 *
 * 사용법: 해당 페이지에서 함수 본문을 그대로 실행한다 (javascript_tool).
 */

// ─────────────────────────────────────────────────────────────
// 0. 사전 점검 — 로그인 + 렌더링
// ─────────────────────────────────────────────────────────────
function preflight() {
  const t = document.body.innerText || '';
  const route = location.pathname + location.hash;   // 해시 라우팅 때문에 hash 필수
  const hasId   = /ID\s*\d{6,}/.test(t);
  const hasNav  = t.includes('비즈니스 성장 프로그램');
  const isLogin = /(login|signin|auth)/i.test(route)
                  || !!document.querySelector('input[type="password"]');
  return {
    로그인됨: hasId && hasNav && !isLogin,
    // 임계값 주의: 이 포털의 정상 페이지도 1,200~1,500자다 (요금제 1,450 / 프로그램 허브 1,237).
    // 껍데기만 온 상태는 100~300자 수준이므로 800 이 실제 경계다.
    렌더링됨: t.length > 800,
    길이: t.length, route: route.slice(0, 60),
  };
}

// ─────────────────────────────────────────────────────────────
// 0-B. 이 계정이 가진 숙소 전부 — 숙소 ID를 모를 때 여기부터
//    /mldc/ko-kr/app/iam/propertysearch
//
//    이름·ID·도시·판매상태·당월 수익·평균단가·콘텐츠 점수를 한 표로 준다.
//    헤더의 숙소 칩을 눌러도 드롭다운에 뜨지만(검색창이 '숙소명 또는 숙소 ID' 를 받는다),
//    목록 페이지 쪽이 파싱하기 쉽고 지표까지 딸려온다.
// ─────────────────────────────────────────────────────────────
function properties() {
  const rows = [...document.querySelectorAll('tbody tr')].map(tr => {
    const c = [...tr.querySelectorAll('td')].map(x => x.innerText.replace(/\s+/g, ' ').trim());
    if (!c.length) return null;
    const m = c[0].match(/^(.*?)\s*(판매 중|판매 중지|Live|Inactive)?\s*(\d{6,})\s*·\s*(.*)$/);
    return {
      name:   m ? m[1].trim() : c[0],
      status: m ? (m[2] || '') : '',
      id:     m ? m[3] : (c[0].match(/\d{6,}/) || [''])[0],
      loc:    m ? m[4] : '',
      revenueMTD: c[1] || '', adrMTD: c[2] || '', contentScore: c[3] || '',
    };
  }).filter(Boolean);
  return { n: rows.length, rows };
}

// ─────────────────────────────────────────────────────────────
// 1-A. ★ 기본 경로 — ARI "목록 보기"
//    /mldc/ko-kr/app/ari/availabilitycenter/{id}?startDate=YYYY-MM-DD&endDate=YYYY-MM-DD
//
//    객실 × 요금제 × 날짜를 평범한 <table> 로 준다. 아코디언·Mixed·필터 리셋이 전부 없다.
//    ariRates() 의 월별 캘린더보다 이쪽을 먼저 써라.
// ─────────────────────────────────────────────────────────────
function ariList() {
  const out = [];
  document.querySelectorAll('table').forEach(tb => {
    const rows = [...tb.querySelectorAll('tr')].map(tr =>
      [...tr.querySelectorAll('th,td')].map(c => c.innerText.replace(/\s+/g, ' ').trim()));
    if (rows.length > 1) out.push(rows);
  });
  return { 표: out.length, 데이터: out };
}

// ─────────────────────────────────────────────────────────────
// 1-B. ARI 월별 캘린더 (목록 보기가 안 될 때만)
//    /mldc/ko-kr/app/ari/calendar/{id}?startDate=YYYY-MM-DD&endDate=YYYY-MM-DD
//
//    ★ 함정 3개 — 전부 실제로 당했다:
//    (1) 객실 필터 기본값이 1개다. "전체 선택" → "적용하기" 를 먼저 눌러라.
//        날짜를 바꿔 재진입하면 필터가 다시 1개로 리셋된다. 매번 다시 켜라.
//    (2) 값이 "Mixed" 로 나온다. 단일 날짜인데도 우측 패널이 다 그려지기 전이면 Mixed 다.
//        아래 코드가 재시도하지만, 끝까지 Mixed 면 목록 보기(1-A)로 우회해라.
//    (3) location.search 는 도구가 [BLOCKED] 로 가린다. 쿼리가 먹었는지는
//        URL 로 판단하지 말고 우측 패널의 날짜 텍스트를 읽어서 확인해라.
// ─────────────────────────────────────────────────────────────
async function ariRates() {
  // 접힌 객실 카드를 전부 편다 — 안 펴면 rate-card-input 이 DOM 에 없다
  document.querySelectorAll('[data-testid^="ycs-calendar-page-room-card-accordion-toggle-"]')
    .forEach(b => { if (b.getAttribute('aria-expanded') !== 'true') b.click(); });
  await new Promise(r => setTimeout(r, 2000));

  const names = {};
  document.querySelectorAll('[data-testid^="ycs-calendar-page-room-card-accordion-toggle-"]').forEach(b => {
    const rid = b.getAttribute('data-testid').split('-').pop();
    let e = b;
    for (let i = 0; i < 6 && e; i++) { e = e.parentElement; if (e && e.textContent.includes('(' + rid + ')')) break; }
    names[rid] = (e?.textContent || '').replace(/\s+/g, ' ').split('예약 가능')[0].trim();
  });

  // Mixed 가 남아 있으면 한 번 더 기다렸다 읽는다
  const mixedNow = () => [...document.querySelectorAll('[data-testid^="rate-card-input-"]')]
      .filter(i => /Mixed/i.test(i.value || '')).length;
  if (mixedNow() > 0) await new Promise(r => setTimeout(r, 3000));

  const rows = [];
  document.querySelectorAll('[data-testid^="rate-card-input-"]').forEach(inp => {
    const id = inp.getAttribute('data-testid').replace('rate-card-input-', '');
    const [roomId, planId] = id.split('-');
    let e = inp, box = null;
    for (let i = 0; i < 8 && e; i++) { e = e.parentElement; if (e && /\(\d{6,}\)/.test(e.textContent || '')) { box = e; break; } }
    rows.push({
      room: names[roomId] || roomId, roomId, planId,
      plan: (box?.textContent || '').replace(/\s+/g, '').split('x')[0].slice(0, 45),
      rate: inp.value,
    });
  });
  return { date: document.querySelector('[data-testid="date-range-info"]')?.innerText, n: rows.length, rows };
}

// ─────────────────────────────────────────────────────────────
// 2. 소비자 페이지 오퍼 — 노출가 · 할인 내역
//    반드시 탭을 활성화한 "직후" 실행. 백그라운드면 빈 배열이 나온다.
//    ★ 재판매 오퍼를 가르지 않는다. 화면 텍스트 확인용이고, 값은 2-B 를 쓴다.
// ─────────────────────────────────────────────────────────────
function consumerOffers() {
  const btns = [...document.querySelectorAll('button,a')]
    .filter(b => (b.textContent || '').trim().startsWith('예약하기'));
  const seen = new Set(), out = [];
  for (const b of btns) {
    let e = b; while (e && (e.textContent || '').length < 400) e = e.parentElement;
    let box = e;
    for (let i = 0; i < 4 && box; i++) { if (/객실 사진 및 상세 구성 보기/.test(box.textContent || '')) break; box = box.parentElement; }
    const t = (box?.textContent || '').replace(/\s+/g, ' ').trim();
    const k = t.slice(0, 45); if (seen.has(k)) continue; seen.add(k);
    out.push(t.slice(0, 1700));
  }
  return { rendered: btns.length > 0, n: out.length, out };
}

// ─────────────────────────────────────────────────────────────
// 2-B. ★ 직판 오퍼만 골라내기 — 객실명 대조 대신 오퍼 ID 디코딩
//    로그인하지 않은 소비자 페이지에서, 마우스 휠로 끝까지 내린 뒤 실행.
//
//    직판 = 공급사 코드(또는 zigzag 값)가 있고 디코딩 텍스트에 'Some(' 가 없는 오퍼.
//    ★ supplier 기본값 332 는 한 숙소에서 확인한 값이다. 다른 숙소는 확인 필요.
//       ARI CMS와 맞는 오퍼의 코드와 대조한 뒤 다르면 인자로 넘겨라.
//    roomNames 예: { '객실 ID': '표시 이름' } — 그 숙소 값을 넘긴다. 없으면 빈 값이다.
//
//    rows 형식: [객실, 원래 요금, 손님 결제, 룸온리|조식, 환불불가|무료취소, 인원]
//    원래 요금이 비어 있으면 쿠폰이 없는 오퍼다 → 손님 결제 = 원래 요금.
// ─────────────────────────────────────────────────────────────
function directOffers({ supplier = 332, roomNames = {} } = {}) {
  const b64 = s => Uint8Array.from(
    atob((s + '==='.slice((s.length + 3) % 4)).replace(/-/g, '+').replace(/_/g, '/')),
    c => c.charCodeAt(0));
  // 바이트열에서 varint 후보를 전부 뽑는다 (원래 값 + zigzag 복원 값)
  function vints(bytes) {
    const out = [];
    for (let i = 0; i < bytes.length - 1; i++) {
      const k = bytes[i];
      if ((k & 7) !== 0) continue;
      const f = k >> 3;
      if (f < 1 || f > 30) continue;
      let v = 0n, sh = 0n, j = i + 1;
      while (j < bytes.length) {
        const x = BigInt(bytes[j]);
        v |= (x & 0x7fn) << sh; sh += 7n; j++;
        if (!(x & 0x80n)) break;
        if (sh > 63n) break;
      }
      out.push(String(v), String((v >> 1n) ^ (-(v & 1n))));
    }
    return out;
  }

  const code = String(supplier), zig = String(supplier * 2);
  const rows = [];
  let resale = 0, resaleMin = null, undecoded = 0;
  for (const el of document.querySelectorAll('[data-room-offer-id]')) {
    let v, txt;
    try {
      const by = b64(el.getAttribute('data-room-offer-id'));
      v = vints(by);
      txt = new TextDecoder().decode(by);
    } catch (err) {
      // 못 푼 오퍼는 직판·재판매 어느 쪽으로도 세지 않고 건수를 남긴다
      console.warn('오퍼 ID 디코딩 실패', err);
      undecoded++;
      continue;
    }
    const direct = (v.includes(code) || v.includes(zig)) && !txt.includes('Some(');
    const t = el.innerText.replace(/\s+/g, ' ');
    const orig = (t.match(/₩\s?([\d,]+)\s*-\d+%/) || [])[1] || '';
    const pay = (t.match(/₩\s?([\d,]+)\s*1박당/) || [])[1] || '';
    if (!direct) {
      resale++;
      const n = pay ? +pay.replace(/,/g, '') : null;
      if (n !== null && (resaleMin === null || n < resaleMin)) resaleMin = n;
      continue;
    }
    rows.push([
      Object.keys(roomNames).filter(id => v.includes(id)).map(id => roomNames[id]).join(),
      orig, pay,
      /조식 포함/.test(t) ? '조식' : '룸온리',
      /환불 불가/.test(t) ? '환불불가' : '무료취소',
      ((t.match(/성인 (\d)명/) || [])[1] || '') + '인',
    ]);
  }
  return { 직판: rows, 재판매수: resale, 재판매최저: resaleMin, 디코딩실패: undecoded, 공급사코드: code };
}

// ─────────────────────────────────────────────────────────────
// 3. 프로모션 목록 — 적용 중 / 종류 / 할인율
//    /ko-kr/kipp/app/manage/promotioncard/{id}
// ─────────────────────────────────────────────────────────────
function promotions() {
  const t = document.body.innerText || '';
  const active   = (t.match(/적용 중 \((\d+)\)/) || [])[1];
  const inactive = (t.match(/적용 중지 \((\d+)\)/) || [])[1];
  const i = t.indexOf('적용 중 (');
  // 블록을 통째로 넘기고 사람이 읽어서 표로 옮긴다 — 행 구조가 자주 바뀌어 파싱은 깨지기 쉽다
  return { active, inactive, block: t.slice(i, i + 3500) };
}

// ─────────────────────────────────────────────────────────────
// 4. 할인 시뮬레이터 — Σ가 덧셈인지 확인 + 최대 할인 계산
//    /mldc/ko-kr/app/pricing-metadata/promotions/promotionsimulator/{id}
//    ★ 이 화면에는 Maximum Gain 같은 "프로그램"이 빠져 있다. 결과에 따로 더해라.
// ─────────────────────────────────────────────────────────────
function simSet(idx, v) {
  const el = [...document.querySelectorAll('input')][idx];
  const setter = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, 'value').set;
  el.focus(); setter.call(el, v);
  el.dispatchEvent(new Event('input',  { bubbles: true }));
  el.dispatchEvent(new Event('change', { bubbles: true }));
  el.blur(); return el.value;
}
async function simRun() {
  const b = [...document.querySelectorAll('button')].find(x => (x.innerText || '').trim() === '할인 시뮬레이션하기');
  if (!b || b.disabled) return { err: '버튼 없음/비활성' };
  b.click();
  await new Promise(r => setTimeout(r, 3500));
  const t = document.body.innerText || '';
  const i = t.indexOf('시뮬레이션 결과 보기');
  return { result: t.slice(i, i + 400).replace(/\n{2,}/g, '\n') };
}
// 입력칸 순서: [0] 전역검색 [1] 판매요금 [2] 메가세일 [3] 시즌 [4] 알뜰 [5..] 타겟팅
// 예: simSet(1,'160000'); simSet(2,'10'); simSet(3,'10'); await simRun();

// ─────────────────────────────────────────────────────────────
// 5. 예약 상세 — 프로모션 내역 (지역 타겟팅 확인용)
//    예약 목록에서 건을 연 뒤 "결제 및 요금" 탭을 누르고 실행
// ─────────────────────────────────────────────────────────────
function bookingDetail() {
  const t = document.body.innerText || '';
  const g = re => (t.match(re) || [])[1]?.trim();
  return {
    예약번호: g(/예약 번호\s*\n\s*(\d+)/),
    거주국가: g(/투숙객 거주 국가\s*\n\s*([^\n]+)/),
    기준판매요금: g(/기준 판매 요금[^\n]*\n\s*KRW\s*([\d.,]+)/),
    요금제: g(/요금제\s*\n\s*([^\n]+)/),
    프로모션: g(/프로모션\s*\n\s*([^\n]+)/),
  };
}

// ─────────────────────────────────────────────────────────────
// 6. 사진 — 카테고리별 문제 집계
//    /ko-kr/app/setting/photos/{id}
// ─────────────────────────────────────────────────────────────
function photoAudit() {
  // ★ innerText 로 세라. DOM 노드로 세면 배지가 중첩돼 있어 값이 몇 배로 튄다
  //   (`해상도가 낮습니다` 가 querySelectorAll 로는 8개, innerText 로는 1개).
  const t = document.body.innerText || '';
  const lo = t.match(/저해상도 사진\s*\n?\s*(\d+)/);
  const mt = t.match(/태그 누락\s*\n?\s*(\d+)/);   // 배지가 없으면 0건이다

  // 총 장수는 상단 배지가 아니라 카테고리 합으로 검산해라. 둘이 다르면 카테고리 쪽이 맞다.
  const cats = [...t.matchAll(/([^\n]+)\n\((\d+)\)/g)]
      .map(m => ({ 카테고리: m[1].trim(), 장수: +m[2] }));
  const 합계 = cats.reduce((a, c) => a + c.장수, 0);

  const i = t.indexOf('각 카테고리의 메인 사진');
  const secs = t.slice(i).split(/사진 추가하기/).slice(0, -1).map(b => {
    const nm = (b.match(/([^\n]+)\n\((\d+)\)/) || []).slice(1);
    return {
      카테고리: nm[0], 장수: +nm[1],
      태그누락: (b.match(/태그 누락/g) || []).length,
      저해상도: (b.match(/해상도가 낮습니다/g) || []).length,
    };
  });
  return { 총장수: 합계, 저해상도: lo ? lo[1] : '0', 태그누락: mt ? mt[1] : '0',
           카테고리합: cats, 카테고리: secs };
}

// 사진 카드 목록 — 인덱스는 처리할 때마다 밀린다. 배치마다 다시 부를 것.
function photoCards() {
  return [...document.querySelectorAll('input[type=checkbox]')].map(cb => {
    let e = cb;
    for (let k = 0; k < 8 && e; k++) { e = e.parentElement; if (e && e.querySelector('img')) break; }
    return { cb, card: e };
  }).filter(x => x.card);
}

// 카드에 번호를 그려 넣는다 — 스크린샷으로 어느 사진이 몇 번인지 확인할 때 쓴다
function photoNumber() {
  document.querySelectorAll('.__n').forEach(e => e.remove());
  photoCards().forEach((c, i) => {
    c.card.style.position = 'relative';
    const d = document.createElement('div');
    d.className = '__n'; d.textContent = i;
    d.style.cssText = 'position:absolute;top:2px;right:2px;z-index:99;background:#c00;color:#fff;'
                    + 'font:bold 17px monospace;padding:3px 9px;border-radius:4px';
    c.card.appendChild(d);
  });
  return photoCards().length;
}

// 여러 장에 같은 태그 붙이기 — 태그는 라디오라 한 번에 1개다
async function photoTag(idxs, label) {
  let cs = photoCards();
  cs.forEach(c => { if (c.cb.checked) c.cb.click(); });
  idxs.forEach(i => { if (cs[i] && !cs[i].cb.checked) cs[i].cb.click(); });
  if (photoCards().filter(c => c.cb.checked).length !== idxs.length) return { err: '선택 불일치' };

  [...document.querySelectorAll('button')].find(x => (x.innerText || '').trim() === '태그하기')?.click();
  await new Promise(r => setTimeout(r, 1800));

  const dlg = [...document.querySelectorAll('div')]
    .find(d => /사진 태그하기/.test(d.innerText || '') && d.querySelectorAll('input[type=radio]').length > 50);
  if (!dlg) return { err: '다이얼로그 없음' };

  let target = null;
  for (const inp of dlg.querySelectorAll('input[type=radio]')) {
    let e = inp, txt = '';
    for (let i = 0; i < 5 && e; i++) { e = e.parentElement; const s = (e?.innerText || '').trim(); if (s && s.length < 30) { txt = s; break; } }
    if (txt === label) { target = inp; break; }
  }
  if (!target) return { err: '태그 없음: ' + label };
  target.click();
  await new Promise(r => setTimeout(r, 500));

  const sb = [...dlg.querySelectorAll('button')].find(b => (b.innerText || '').trim() === '사진 태그하기');
  if (!sb || sb.disabled) return { err: '제출 불가' };
  sb.click();
  await new Promise(r => setTimeout(r, 4000));
  const m = (document.body.innerText || '').match(/태그 누락\s*\n?\s*(\d+)/);
  return { ok: true, 적용: idxs.length + '장 → ' + label, 남은: m ? m[1] : '0' };
}

// ─────────────────────────────────────────────────────────────
// 7. 채널 매니저 요금 그리드 (WINGSCMS 계열)
//    그리드는 평범한 <table> 이다. 행 인덱스는 상품그룹 구성에 따라 다르니
//    먼저 rowIndex() 로 어느 행이 뭔지 확인하고 rates() 를 부른다.
// ─────────────────────────────────────────────────────────────
function cmsRowIndex() {
  return [...document.querySelectorAll('tr')].map((tr, i) => ({
    i,
    label: [...tr.children].slice(0, 2).map(td => (td.innerText || '').replace(/\s+/g, ' ').trim().slice(0, 24)).join(' / '),
    inputs: tr.querySelectorAll('input').length,
    selects: tr.querySelectorAll('select').length,
  })).filter(r => r.inputs || r.selects || r.label.replace(' / ', ''));
}
function cmsRates(rowMap) {          // rowMap 예: { '아고다': 46, '국내OTA': 55 }
  const trs = [...document.querySelectorAll('tr')];
  const dates = [...trs[1].children].map(td => (td.innerText || '').replace(/\s+/g, ' ').trim()).slice(1);
  const out = {};
  for (const [name, i] of Object.entries(rowMap)) {
    out[name] = trs[i] ? [...trs[i].querySelectorAll('input')].map(x => x.value) : null;
  }
  return { dates, rates: out };
}

// ─────────────────────────────────────────────────────────────
// 8. 새 탭으로 여는 버튼의 URL 가로채기
// ─────────────────────────────────────────────────────────────
function catchOpen(selector) {
  const orig = window.open; window.__u = null;
  window.open = u => { window.__u = u; return null; };
  document.querySelector(selector)?.click();
  setTimeout(() => { window.open = orig; }, 3000);
  return '잠시 뒤 window.__u 를 읽어라';
}
