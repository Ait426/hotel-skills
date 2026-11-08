#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""property.json → 자체 완결 HTML 콘솔 한 장.

외부 참조가 없어 어디에 올려도 깨지지 않는다. 없는 섹션은 자동으로 빠지므로 부분 조사여도 돌아간다.

  python build_console.py property.json -o 콘솔.html [--check]
"""
import argparse
import json
import pathlib
import sys

from payout import floor_cells, lead_points

CATS = ("target", "portfolio", "campaign", "genius", "focus")

CSS = """:root{--ground:#ECEFEA;--surface:#F6F8F4;--sunk:#E1E6DE;--line:#CBD3C9;--text:#0F1A1C;--dim:#4C5A57;
--accent:#8F6516;--accent-soft:#EFE2C6;--ok:#256B4B;--ok-soft:#D3E7DB;--bad:#973129;--bad-soft:#F3D8D4;--warn-soft:#F5E4C8}
@media (prefers-color-scheme:dark){:root:not([data-theme="light"]){--ground:#0C1214;--surface:#141D1E;--sunk:#0A0F11;--line:#2A3739;
--text:#E2E8E2;--dim:#9DAAA6;--accent:#D5A244;--accent-soft:#3A2E16;--ok:#5CBF92;--ok-soft:#12291F;--bad:#E08078;--bad-soft:#2E1715;--warn-soft:#2E2312}}
:root[data-theme="dark"]{--ground:#0C1214;--surface:#141D1E;--sunk:#0A0F11;--line:#2A3739;--text:#E2E8E2;--dim:#9DAAA6;--accent:#D5A244;
--accent-soft:#3A2E16;--ok:#5CBF92;--ok-soft:#12291F;--bad:#E08078;--bad-soft:#2E1715;--warn-soft:#2E2312}
*{box-sizing:border-box}body{margin:0;background:var(--ground);color:var(--text);font:15px/1.55 system-ui,-apple-system,"Malgun Gothic",sans-serif}
.wrap{max-width:1180px;margin:0 auto;padding:28px 20px 72px}
header{display:flex;flex-wrap:wrap;gap:12px;align-items:flex-end;border-bottom:2px solid var(--text);padding-bottom:16px;margin-bottom:22px}
h1{margin:0;font-size:26px;letter-spacing:-.02em}.sub{color:var(--dim);font-size:13px}
.formula{margin-left:auto;font-size:12px;color:var(--dim);background:var(--sunk);border:1px solid var(--line);border-radius:5px;padding:7px 12px}
.card{background:var(--surface);border:1px solid var(--line);border-radius:9px;margin-bottom:18px;overflow:hidden}
.card h2{margin:0;font-size:13px;color:var(--dim);padding:12px 18px;background:var(--sunk);border-bottom:1px solid var(--line)}
.body{padding:16px 18px}.scroll{overflow-x:auto}
.cols{display:grid;grid-template-columns:minmax(0,1fr);gap:18px}@media(min-width:900px){.cols{grid-template-columns:minmax(0,1fr) 380px}}
.cols>*{min-width:0}
.field{display:flex;flex-direction:column;gap:4px;margin-bottom:12px;font-size:13px;color:var(--dim)}
.field input,.field select{font:inherit;font-size:15px;color:var(--text);background:var(--ground);border:1px solid var(--line);border-radius:5px;padding:7px 9px;width:100%}
.row2{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:0 14px}
.fig{font-size:38px;font-weight:700;letter-spacing:-.02em;font-variant-numeric:tabular-nums}
.line{display:flex;justify-content:space-between;gap:12px;padding:4px 0;border-bottom:1px solid var(--line);font-size:14px}
.line b{font-variant-numeric:tabular-nums}
table{border-collapse:collapse;width:100%;font-size:13.5px}th,td{padding:7px 10px;border-bottom:1px solid var(--line);text-align:right;white-space:nowrap}
th{color:var(--dim);font-weight:600;background:var(--sunk)}th:first-child,td:first-child{text-align:left}td.l,th.l{text-align:left;white-space:normal}
.tag{display:inline-block;font-size:12px;border-radius:4px;padding:1px 7px;background:var(--sunk);color:var(--dim)}
.tag.ok{background:var(--ok-soft);color:var(--ok)}.tag.bad{background:var(--bad-soft);color:var(--bad)}.tag.warn{background:var(--warn-soft);color:var(--accent)}
.note{font-size:12.5px;color:var(--dim);margin:10px 0 0}
small{color:var(--dim)}ul{margin:0;padding-left:18px}
@media(max-width:640px){.wrap{padding:18px 16px 56px}.formula{margin-left:0}.fig{font-size:32px}}
"""

JS = r"""
const D=JSON.parse(document.getElementById('data').textContent);
const C=D.coef,$=s=>document.querySelector(s),won=x=>Math.round(x).toLocaleString('ko-KR');
const esc=s=>{const e=document.createElement('i');e.textContent=s==null?'':String(s);return e.innerHTML};
const P=D.promotions||[],act=c=>P.filter(p=>p.cat===c&&(p.status||'적용')==='적용');
const deep=a=>a.reduce((b,p)=>!b||p.pct>b.pct?p:b,null);
function hit(p,lead,mem){if(p.member&&!mem)return false;const c=p.cond||'base';return c==='advance'?lead>=(p.minDays||0):c==='lastMinute'?lead<=(p.maxDays||0):true}
function best(rate,plan,occ,pos,mob,lead,mem){const base=rate*plan*occ,t=deep(act('target').filter(p=>p.pos===pos||(mob&&p.pos==='mobile'))),f=deep(act('portfolio').filter(p=>hit(p,lead,mem)));
 const tp=t?t.pct:0,fp=f?f.pct:0,o=[{n:[t,f].filter(Boolean).map(x=>x.name),orig:base*(1-tp/100),shown:base*(1-tp/100)*(1-fp/100)}];
 for(const c of act('campaign'))if(hit(c,lead,mem))o.push({n:[c.name],orig:base,shown:base*(1-c.pct/100)});
 const g=mem?deep(act('genius')):null;if(g)for(const x of o){x.shown*=1-g.pct/100;x.n=x.n.concat(g.name)}
 for(const c of act('focus'))if(hit(c,lead,mem))o.push({n:[c.name],orig:base,shown:base*(1-c.pct/100)});
 const b=o.reduce((a,x)=>x.shown<a.shown?x:a);return{...b,pay:b.shown*C.k}}
function need(goal,rate,c){const u=(D.property&&D.property.roundUnit)||100;return Math.ceil(+(goal*rate/c.pay).toFixed(6)/u)*u}
const room=()=>D.rooms[+$('#room').value],plan=()=>D.plans[+$('#plan').value],rate=()=>+$('#rate').value||0;
function occ(){const r=room(),pax=+$('#pax').value;return 1-(C.occStep||0)*Math.max(0,r.base-pax)}
function fillRoom(){const r=room(),s=$('#set');s.innerHTML=Object.keys(r.rates).filter(k=>r.rates[k]!=null).map(k=>`<option>${esc(k)}</option>`).join('');
 $('#pax').innerHTML=Array.from({length:r.base},(_,i)=>r.base-i).map(n=>`<option>${n}</option>`).join('');fillRate()}
function fillRate(){$('#rate').value=room().rates[$('#set').value]||0;render()}
function render(){const lead=+$('#lead').value,c=best(rate(),plan().mult,occ(),$('#pos').value,$('#mob').value==='1',lead,$('#mem').value==='1');
 $('#fig').textContent=won(c.pay);$('#promo').textContent=c.n.join(' · ')||'할인 없음';
 $('#lines').innerHTML=[['기존 요금',c.orig],['노출가',c.shown],['입금 계수',null]].map(([a,b])=>`<div class="line"><span>${a}</span><b>${b==null?C.k:won(b)}</b></div>`).join('');
 const f=C.floor;$('#verdict').innerHTML=f==null?'<span class="tag">하한 미지정</span>':c.pay>=f?`<span class="tag ok">하한 ${won(f)} 대비 +${won(c.pay-f)}</span>`
  :`<span class="tag bad">하한 ${won(f)} 대비 -${won(f-c.pay)}</span> <small>필요 판매가 ${won(need(f,rate(),c))}</small>`;
 const cell=(l,p,m)=>{const x=best(rate(),plan().mult,occ(),p,false,l,m);return `<td><small>${won(x.shown)}</small><br><b>${won(x.pay)}</b></td>`};
 $('#gridBody').innerHTML=D.leads.map(l=>{const n=best(rate(),plan().mult,occ(),'domestic',false,l,true).n.join(' · ')||'할인 없음';
  return `<tr><td>D-${l}+</td><td class="l">${esc(n)}</td>${cell(l,'domestic',true)}${cell(l,'domestic',false)}${cell(l,'international',true)}${cell(l,'international',false)}</tr>`}).join('')}
const ready=typeof C.k==='number'&&(D.rooms||[]).length>0&&(D.plans||[]).length>0;
if(ready){$('#room').innerHTML=D.rooms.map((r,i)=>`<option value="${i}">${esc(r.name)}</option>`).join('');
 $('#plan').innerHTML=D.plans.map((r,i)=>`<option value="${i}">${esc(r.name)} (${r.mult})</option>`).join('');
 $('#lead').innerHTML=D.leads.map(l=>`<option value="${l}">D-${l} 이상</option>`).join('');
 $('#room').onchange=fillRoom;$('#set').onchange=fillRate;['#rate','#plan','#pax','#pos','#mob','#lead','#mem'].forEach(s=>$(s).oninput=render);fillRoom()}
else{$('#calc').innerHTML='<div class="body"><span class="tag bad">계산 불가</span> 입금 계수, 객실 판매가, 요금제 중 빈 값이 있습니다. 아래 미확인 항목을 먼저 채우세요.</div>'}
"""


def esc(v):
    import html
    return html.escape("" if v is None else str(v))


def badge(ok):
    return '<span class="tag ok">실측</span>' if ok else '<span class="tag warn">미확인</span>'


def card(title, body):
    return f'<section class="card"><h2>{esc(title)}</h2>{body}</section>'


def table(headers, rows):
    head = "".join(f"<th>{h}</th>" for h in headers)
    return f'<div class="scroll"><table><thead><tr>{head}</tr></thead><tbody>{"".join(rows)}</tbody></table></div>'


def num(v):
    return "—" if v is None else f"{v:,.0f}"


def coef_card(d):
    c, v = d.get("coef") or {}, (d.get("coef") or {}).get("verified") or {}
    rows = [("k 입금 계수", c.get("k"), v.get("k")), ("인원 감액폭", c.get("occStep"), v.get("occStep")), ("입금가 하한", c.get("floor"), v.get("floor"))]
    rows += [(f'요금제 {p.get("name")}', p.get("mult"), p.get("verified")) for p in d.get("plans") or []]
    body = "".join(f'<tr><td>{esc(n)}</td><td>{"—" if x is None else x}</td><td>{badge(o)}</td></tr>' for n, x, o in rows)
    note = f'<p class="note">근거: {esc(c.get("source"))}</p>' if c.get("source") else ""
    return card("계수", f'<div class="body">{table(["항목", "값", "상태"], [body])}{note}</div>')


def calc_card():
    body = """<div class="cols"><div>
<div class="row2"><label class="field">객실<select id="room"></select></label><label class="field">요금세트<select id="set"></select></label>
<label class="field">요금제<select id="plan"></select></label><label class="field">인원<select id="pax"></select></label></div>
<label class="field">판매가<input id="rate" type="number" min="0" step="100"></label>
<div class="row2"><label class="field">접속<select id="pos"><option value="domestic">국내 접속</option><option value="international">해외 접속</option></select></label>
<label class="field">기기<select id="mob"><option value="0">PC</option><option value="1">모바일</option></select></label>
<label class="field">리드타임<select id="lead"></select></label>
<label class="field">손님<select id="mem"><option value="1">회원</option><option value="0">비회원</option></select></label></div>
</div><div><small>입금가 (계산값)</small><div class="fig" id="fig">—</div><div id="verdict"></div><p class="note" id="promo"></p><div id="lines"></div></div></div>"""
    return f'<section class="card" id="calc"><h2>계산기</h2><div class="body">{body}</div></section>'


def grid_card():
    heads = ["구간", '<span class="l">국내 회원에게 걸리는 할인</span>', "국내 회원", "국내 비회원", "해외 회원", "해외 비회원"]
    head = "".join(f"<th>{h}</th>" for h in heads)
    return card("리드타임별 입금가 (위 객실·세트·요금제·인원, PC 기준)",
                f'<div class="body"><div class="scroll"><table><thead><tr>{head}</tr></thead><tbody id="gridBody"></tbody></table></div>'
                '<p class="note">셀 순서: 노출가 · 입금가. 해외는 「해외 접속」이지 외국인이 아니다. 모두 계산값이고 "입금가 확정"은 예약 정산 내역으로만 한다.</p></div>')


def floor_card(d):
    if not isinstance((d.get("coef") or {}).get("k"), (int, float)):
        return ""
    limit = d["coef"].get("floor")
    rows = []
    for c in floor_cells(d):
        ok = None if limit is None else c["payout"] >= limit
        tag = '<span class="tag">미지정</span>' if ok is None else (f'<span class="tag ok">+{c["payout"] - limit:,.0f}</span>' if ok else f'<span class="tag bad">{c["payout"] - limit:,.0f}</span>')
        who = ("국내" if c["pos"] == "domestic" else "해외") + (" 모바일" if c["mobile"] else "") + (" 회원" if c["member"] else " 비회원")
        rows.append(f'<tr><td>{esc(c["room"])}</td><td class="l">{esc(c["set"])}</td><td class="l">{esc(c["plan"])} · D-{c["lead"]} · {who}</td><td>{num(c["shown"])}</td><td><b>{num(c["payout"])}</b></td><td>{tag}</td></tr>')
    return card("객실별 최심 칸", f'<div class="body">{table(["객실", "세트", "조건", "노출가", "입금가", "하한 대비"], rows)}'
                '<p class="note">기준 인원 기준이다. 인원을 줄이면 더 내려간다.</p></div>') if rows else ""


def promo_card(d):
    label = {"target": "타겟 요금", "portfolio": "포트폴리오형", "campaign": "캠페인", "genius": "Genius", "focus": "집중형"}
    pos = {"domestic": "국내 접속", "international": "해외 접속", "mobile": "모바일"}
    rows = []
    for m in d.get("promotions") or []:
        cond = {"advance": f'D-{m.get("minDays", 0)} 이상', "lastMinute": f'D-{m.get("maxDays", 0)} 이내'}.get(m.get("cond"), pos.get(m.get("pos"), "조건 없음"))
        if m.get("member"):
            cond += " · 회원"
        if m.get("period"):
            cond += f' · {m["period"]}'
        rows.append(f'<tr><td>{esc(m.get("name"))}</td><td class="l">{esc(label.get(m.get("cat"), m.get("cat")))}</td><td class="l">{esc(cond)}</td><td>{esc(m.get("pct"))}%</td><td class="l">{esc(m.get("status", "적용"))}</td></tr>')
    return card("프로모션", f'<div class="body">{table(["이름", "카테고리", "조건", "할인", "상태"], rows)}'
                '<p class="note">스냅샷이다. 변경 전에 익스트라넷에서 다시 읽는다.</p></div>') if rows else ""


def ledger_rows(d):
    k = (d.get("coef") or {}).get("k")
    return [(r, None if not isinstance(k, (int, float)) or not r.get("shown") else r["shown"] * k) for r in d.get("ledger") or []]


def ledger_card(d):
    rows = []
    for r, calc in ledger_rows(d):
        gap = None if calc is None or r.get("payout") is None else calc - r["payout"]
        tag = "—" if gap is None else f'<span class="tag {"ok" if abs(gap) <= r.get("nights", 1) else "bad"}">{gap:+,.0f}원</span>'
        ratio = "—" if not r.get("shown") or r.get("payout") is None else f'{r["payout"] / r["shown"]:.4f}'
        rows.append(f'<tr><td>{esc(r.get("label"))}</td><td class="l">{esc(r.get("path"))}</td><td>{num(r.get("shown"))}</td><td><b>{num(r.get("payout"))}</b></td><td>{ratio}</td><td>{tag}</td></tr>')
    return card("실측 원장 (예약 정산 내역)", f'<div class="body">{table(["예약", "경로", "손님 결제", "실입금", "입금 계수", "공식과 차이"], rows)}</div>') if rows else ""


AUDIT = {"bad": ("bad", "위험"), "warn": ("warn", "주의"), "ok": ("ok", "합격"), "unknown": ("", "못 읽음")}


def audit_card(d):
    """점검 결과. 위험 → 주의 → 못 읽음 → 합격 순으로 보여 준다."""
    order = {"bad": 0, "warn": 1, "unknown": 2, "ok": 3}
    items = sorted(d.get("audit") or [], key=lambda x: order.get(x.get("status"), 2))
    rows = []
    for a in items:
        cls, label = AUDIT.get(a.get("status"), AUDIT["unknown"])
        act = f'<br><small>조치: {esc(a.get("action"))}</small>' if a.get("action") else ""
        rule = f'<br><small>기준: {esc(a.get("rule"))}</small>' if a.get("rule") else ""
        src = f'<br><small>근거: {esc(a.get("source"))}</small>' if a.get("source") else ""
        rows.append(f'<tr><td><span class="tag {cls}">{label}</span></td><td class="l">{esc(a.get("area"))}</td>'
                    f'<td class="l"><b>{esc(a.get("item"))}</b>{rule}{act}{src}</td><td class="l">{esc(a.get("value"))}</td></tr>')
    if not rows:
        return ""
    count = {k: sum(1 for a in items if a.get("status") == k) for k in order}
    summary = f'<p class="note" style="margin:0 0 10px">위험 {count["bad"]} · 주의 {count["warn"]} · 못 읽음 {count["unknown"]} · 합격 {count["ok"]}</p>'
    return card("점검 결과", f'<div class="body">{summary}{table(["판정", "영역", "항목", "현재 값"], rows)}'
                '<p class="note">조회 시점의 스냅샷이다. 프로그램 요건과 심사 일정은 화면 문구를 옮긴 것이다.</p></div>')


# ── 현재 설정 · 발견 사항 · 프로그램 · 콘텐츠 · 요금제 · 노출가 실측 ──
# 아고다 스킬과 같은 산출물을 같은 칸 이름으로 낸다. 칸이 비면 그 카드는 빠진다.
UNVERIFIED = ' <span class="tag warn">미확인</span>'
LOWEST = ' <span class="tag warn">최저</span>'
SEV = {"high": ("bad", "높음"), "med": ("warn", "보통"), "info": ("", "참고")}
CSS += """.tiles{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:12px;margin-bottom:18px}
.tile{background:var(--surface);border:1px solid var(--line);border-radius:9px;padding:12px 14px;min-width:0}
.tile .k{font-size:12px;color:var(--dim)}.tile .v{font-size:22px;font-weight:700;font-variant-numeric:tabular-nums;overflow-wrap:anywhere}
.tile .n{font-size:12px;color:var(--dim);overflow-wrap:anywhere}
.call{border-left:3px solid var(--line);background:var(--sunk);border-radius:0 7px 7px 0;padding:10px 14px;margin:0 0 10px;font-size:14px}
.call.bad{border-color:var(--bad);background:var(--bad-soft)}.call.warn{border-color:var(--accent);background:var(--warn-soft)}
.call .lbl{display:block;font-weight:700;margin-bottom:4px}
"""


def dash(v, unit=""):
    return "—" if v is None or v == "" else f"{v:,}{unit}" if isinstance(v, (int, float)) else f"{esc(v)}{unit}"


def summary_tiles(d):
    """맨 위 요약. 손으로 넣은 summary[] 다음에 자동으로 세는 값을 붙인다."""
    tiles = [(t.get("label"), t.get("value"), t.get("note")) for t in d.get("summary") or []]
    promos = d.get("promotions")
    if isinstance(promos, list) and promos:
        on = sum(1 for m in promos if (m.get("status") or "적용") == "적용")
        tiles.append(("적용 중 프로모션", f"{on}건", f"전체 {len(promos)}건"))
    fs = d.get("findings") or []
    if fs:
        tiles.append(("발견 사항", f'{sum(1 for f in fs if f.get("severity") == "high")}건 높음',
                      f'보통 {sum(1 for f in fs if f.get("severity") == "med")} · 참고 {sum(1 for f in fs if f.get("severity") not in ("high", "med"))}'))
    au = d.get("audit") or []
    if au:
        tiles.append(("점검", f'위험 {sum(1 for a in au if a.get("status") == "bad")}',
                      f'주의 {sum(1 for a in au if a.get("status") == "warn")} · 전체 {len(au)}'))
    floor = (d.get("property") or {}).get("floor")
    if floor is None:
        floor = (d.get("coef") or {}).get("floor")
    tiles.append(("입금가 하한", dash(floor, "원") if floor is not None else "미지정", "사용자가 정한 값"))
    body = "".join(f'<div class="tile"><div class="k">{esc(k)}</div><div class="v">{esc(v)}</div>'
                   f'<div class="n">{esc(n)}</div></div>' for k, v, n in tiles)
    return f'<div class="tiles">{body}</div>'


def findings_card(d):
    """결론. 심각도 순, 실측(근거)과 판단(detail)을 나눠 보여 준다."""
    rank = {"high": 0, "med": 1, "info": 2}
    out = []
    for f in sorted(d.get("findings") or [], key=lambda x: rank.get(x.get("severity"), 3)):
        cls, label = SEV.get(f.get("severity"), SEV["info"])
        rev = f'<br><b>정정:</b> {esc(f["revised"])}' if f.get("revised") else ""
        ev = f'<br><small>근거 · {esc(f["evidence"])}</small>' if f.get("evidence") else ""
        out.append(f'<div class="call {cls}"><span class="lbl">{esc(f.get("title"))} <span class="tag {cls}">{label}</span></span>'
                   f'{esc(f.get("detail"))}{rev}{ev}</div>')
    return card("발견 사항", f'<div class="body">{"".join(out)}</div>') if out else ""


def programs_card(d):
    """설정 가능 범위와 현재 설정은 다른 사실이다. 칸을 나눠 적는다."""
    rows = [f'<tr><td class="l">{esc(x.get("name"))}{"" if x.get("verified", True) else UNVERIFIED}</td>'
            f'<td class="l">{dash(x.get("status"))}</td><td class="l">{dash(x.get("range"))}</td><td class="l"><b>{dash(x.get("setting"))}</b></td>'
            f'<td class="l">{esc(x.get("note"))}</td></tr>' for x in d.get("programs") or []]
    return card("프로그램", f'<div class="body">{table(["프로그램", "상태", "설정 가능 범위", "현재 설정", "비고"], rows)}</div>') if rows else ""


def content_card(d):
    ct = d.get("content") or {}
    ph, rv, mp = ct.get("photos"), ct.get("reviews"), ct.get("mapping")
    tiles = []
    if ph:
        tiles.append(("사진", dash(ph.get("total"), "장"), f'저해상도 {dash(ph.get("lowRes"))} · 태그 누락 {dash(ph.get("untagged"))}'))
    if rv:
        det = rv.get("detail") or {}
        low = min(det, key=det.get) if det else None
        tiles.append(("리뷰", dash(rv.get("score")), f'{dash(rv.get("count"))}건 · 미답변 {dash(rv.get("unanswered"))}'
                      + (f' · 최저 {low} {det[low]}' if low else "")))
    if mp:
        tot = mp.get("total")
        tiles.append(("객실 매핑", f'{dash(mp.get("mapped"))}/{dash(tot)}' if tot is not None else dash(mp.get("mapped")),
                      f'미매핑 {dash(mp.get("unmapped"))}'))
    if not tiles:
        return ""
    body = "".join(f'<div class="tile"><div class="k">{esc(k)}</div><div class="v">{v}</div><div class="n">{esc(n)}</div></div>'
                   for k, v, n in tiles)
    notes = "".join(f'<p class="note">{esc(k)}: {esc(x.get("note"))}</p>' for k, x in (("사진", ph), ("리뷰", rv), ("매핑", mp)) if x and x.get("note"))
    det = (rv or {}).get("detail") or {}
    if det:
        low = min(det, key=det.get)
        rows = [f'<tr><td>{esc(k)}{LOWEST if k == low else ""}</td><td>{esc(v)}</td>'
                f'<td>{dash(((rv.get("compare") or {}).get(k)))}</td></tr>' for k, v in sorted(det.items(), key=lambda x: -x[1])]
        notes += table(["리뷰 항목", "점수", "비교(경쟁권 등)"], rows)
    return card("콘텐츠", f'<div class="body"><div class="tiles">{body}</div>{notes}</div>')


def plans_card(d):
    """요금제 인벤토리. 가격(plans·rates)과 다른 것이다."""
    rows = [f'<tr><td class="l">{esc(x.get("name"))}</td><td>{dash(x.get("id"))}</td><td>{dash(x.get("rooms"))}</td>'
            f'<td class="l">{dash(x.get("base"))}</td><td class="l">{dash(x.get("policy"))}</td><td>{dash(x.get("sold"))}</td>'
            f'<td><span class="tag {"ok" if x.get("status") in ("적용 중", "활성", "판매 중") else ""}">{dash(x.get("status"))}</span></td></tr>'
            for x in d.get("ratePlans") or []]
    return card("요금제", f'<div class="body">{table(["요금제", "ID", "객실 수", "기준 요금제", "취소 정책", "예약 수", "상태"], rows)}'
                '<p class="note">예약 0건인 요금제는 노출가가 잘못됐거나 둘 이유가 없는 것이다. 끄기 전에 남은 요금제가 모든 객실을 덮는지 본다.</p></div>') if rows else ""


def measure_points(d):
    """노출가 실측. ratio = 화면값 ÷ 입력값. 3점 이상이면 비율이 서로 맞는지(선형) 본다."""
    out = []
    for m in d.get("measurements") or []:
        i, s = m.get("input"), m.get("shown")
        ratio = s / i if isinstance(i, (int, float)) and isinstance(s, (int, float)) and i else None
        out.append((m, ratio))
    return out


def measure_card(d):
    pts = measure_points(d)
    if not pts:
        return ""
    rows = []
    for m, r in pts:
        e = m.get("expected")
        gap = (m["shown"] - e) if isinstance(e, (int, float)) and isinstance(m.get("shown"), (int, float)) else None
        tag = "—" if gap is None else f'<span class="tag {"ok" if abs(gap) <= (m.get("tolerance") or 1) else "bad"}">{gap:+,.0f}</span>'
        rows.append(f'<tr><td class="l">{esc(m.get("label"))}</td><td class="l">{esc(m.get("condition"))}</td><td>{dash(m.get("input"))}</td>'
                    f'<td>{dash(m.get("shown"))}</td><td>{"—" if r is None else f"{r:.4f}"}</td><td>{dash(e)}</td><td>{tag}</td></tr>')
    rs = [r for _, r in pts if r is not None]
    note = ""
    if len(rs) >= 3:
        ok = max(rs) - min(rs) <= 0.001
        note = f'<p class="note"><span class="tag {"ok" if ok else "warn"}">{"선형 일치" if ok else "비율 어긋남"}</span> 비율 범위 {min(rs):.4f}~{max(rs):.4f} (허용 0.001). 조건이 다른 점은 다른 할인이 붙었을 수 있다.</p>'
    return card("노출가 실측 (고객 페이지)", f'<div class="body">{table(["측정", "조회 조건", "입력값", "화면값", "비율", "공식값", "차이"], rows)}{note}'
                '<p class="note">우리 요금(직판)만 넣는다. 재판매 오퍼 값은 넣지 않는다.</p></div>')


def inspect_check(d, errors, warns):
    """아고다 스킬과 같은 자체 점검: 형식 오류, 미확인 값이 보고에 빠졌는지, 실측 비율."""
    said = json.dumps([d.get("findings") or [], d.get("open") or []], ensure_ascii=False)
    for f in d.get("findings") or []:
        if f.get("severity") not in SEV:
            errors.append(f'발견 사항 {f.get("title")}: severity 는 {"·".join(SEV)} 중 하나다.')
        if not f.get("evidence"):
            warns.append(f'발견 사항 {f.get("title")}: 근거(evidence)가 비었다. 실측과 판단을 나눠 적는다.')
    for x in d.get("programs") or []:
        if x.get("verified") is False and (x.get("name") or "") not in said:
            warns.append(f'프로그램 {x.get("name")}: 미확인인데 findings·open 어디에도 없다.')
    for k, x in ((d.get("content") or {}).items()):
        for f, v in (x or {}).items():
            if f in ("total", "lowRes", "untagged", "count", "unanswered", "mapped", "unmapped") and v is not None and not isinstance(v, (int, float)):
                errors.append(f'content.{k}.{f} 는 숫자다.')
    for x in d.get("ratePlans") or []:
        if x.get("sold") == 0:
            warns.append(f'요금제 {x.get("name")}: 예약 0건. 노출가나 존재 이유를 확인한다.')
    rs = [r for _, r in measure_points(d) if r is not None]
    if len(rs) >= 3 and max(rs) - min(rs) > 0.001:
        warns.append(f'노출가 실측 비율이 어긋난다 ({min(rs):.4f}~{max(rs):.4f}). 조건이 같은지, 재판매 값이 섞였는지 본다.')
    if d.get("measurements") is not None and 0 < len(rs) < 3:
        warns.append("노출가 실측이 3점 미만이다. 선형 확인에는 날짜 3개 이상이 필요하다.")



PAGE_CSS = """.pgnav{display:flex;flex-wrap:wrap;gap:6px;margin:0 0 18px}
.pgtab{font:inherit;font-size:14px;color:var(--dim);background:var(--surface);border:1px solid var(--line);border-radius:6px;padding:7px 14px;cursor:pointer}
.pgtab[aria-pressed=true]{color:var(--text);background:var(--sunk);border-color:var(--text);font-weight:700}
"""
CSS += PAGE_CSS
PAGE_JS = """(function(){var t=[].slice.call(document.querySelectorAll('.pgtab'));if(!t.length)return;
function show(k,push){if(!document.getElementById('pg-'+k))k=t[0].dataset.pg;
t.forEach(function(b){b.setAttribute('aria-pressed',String(b.dataset.pg===k))});
document.querySelectorAll('.page').forEach(function(p){p.hidden=p.id!=='pg-'+k});
if(push){window.scrollTo(0,0);history.replaceState(null,'','#'+k)}}
t.forEach(function(b){b.onclick=function(){show(b.dataset.pg,true)}});show((location.hash||'#').slice(1),false)})();"""


def paged(pages):
    """아고다 콘솔과 같은 네 화면(현재 설정 · 계산기 · 요금표 · 실측 기록). 빈 화면은 빠진다."""
    made = [(f"p{i}", label, "".join(x for x in cards if x)) for i, (label, cards) in enumerate(pages)]
    made = [m for m in made if m[2]]
    if not made:
        return ""
    nav = "".join(f'<button class="pgtab" data-pg="{k}" aria-pressed="{str(i == 0).lower()}">{esc(label)}</button>'
                  for i, (k, label, _) in enumerate(made))
    body = "".join(f'<div class="page" id="pg-{k}"{"" if i == 0 else " hidden"}>{h}</div>' for i, (k, _, h) in enumerate(made))
    return f'<nav class="pgnav">{nav}</nav>{body}<script>{PAGE_JS}</script>'



# ── 조합 비교 — 아고다 계산기의 중복 규칙 강제 · 수수료 조합 비교와 같은 기능 ──
# promoGroups[].mode: locked(항상 적용) · single(그룹에서 하나만, 라디오) · multi(누적, 체크박스)
# commissionParts[].kind: base(결제액에서 % 차감) · accel(세전 금액에서 % 차감). options 가 있으면 선택지로 비교한다.
MODES = ("locked", "single", "multi")
COMBO_JS = r"""document.addEventListener('DOMContentLoaded',function(){var el=document.getElementById('combo');if(!el)return;
var D=JSON.parse(document.getElementById('data').textContent),G=D.promoGroups||[],P=D.commissionParts||[],X=COMBO;
var q=function(s){return el.querySelector(s)},won=function(x){return Math.round(x).toLocaleString('ko-KR')};
function esc(s){var e=document.createElement('i');e.textContent=s==null?'':String(s);return e.innerHTML}
q('#cg').innerHTML=G.map(function(g,gi){return '<fieldset class="cgrp"><legend>'+esc(g.name)+' <small>'+({locked:'항상 적용',single:'하나만',multi:'누적'})[g.mode]+'</small></legend>'+
 (g.items||[]).map(function(it,ii){var id='c'+gi+'_'+ii,t=g.mode==='single'?'radio':'checkbox';
 return '<label class="copt"><input type="'+t+'" name="g'+gi+'" id="'+id+'" data-g="'+gi+'" data-i="'+ii+'"'+(it.on||g.mode==='locked'?' checked':'')+(g.mode==='locked'?' disabled':'')+'> '+esc(it.name)+' <b>'+it.pct+'%</b>'+(it.tag?' <small>'+esc(it.tag)+'</small>':'')+'</label>'}).join('')+
 (g.mode==='single'?'<label class="copt"><input type="radio" name="g'+gi+'" data-g="'+gi+'" data-i="-1"'+((g.items||[]).some(function(i){return i.on})?'':' checked')+'> 없음</label>':'')+'</fieldset>'}).join('');
q('#cp').innerHTML=P.map(function(p,pi){var o=(p.options&&p.options.length?p.options:[p.pct]);
 return '<label class="field">'+esc(p.name)+' ('+(p.kind==='accel'?'세전 차감':'결제액 차감')+')<select data-p="'+pi+'">'+o.map(function(v){return '<option value="'+v+'"'+(v===p.pct?' selected':'')+'>'+v+'%</option>'}).join('')+'</select></label>'}).join('');
function run(){var rate=+q('#crate').value||0,ds=[];
 G.forEach(function(g,gi){var s=0;el.querySelectorAll('input[data-g="'+gi+'"]').forEach(function(c){var i=+c.dataset.i;if(c.checked&&i>=0)s+=g.items[i].pct});if(s)ds.push(s)});
 var d=X.across==='mult'?1-ds.reduce(function(a,x){return a*(1-x/100)},1):ds.reduce(function(a,x){return a+x},0)/100;
 var base=0,acc=0;el.querySelectorAll('select[data-p]').forEach(function(s){var p=P[+s.dataset.p];if(p.kind==='accel')acc+=+s.value;else base+=+s.value});
 var paid=rate*(1-d),pay=paid*(1-base/100)-paid*acc/100/(X.T||1),fl=X.floor;
 q('#cfig').textContent=won(pay);q('#cline').innerHTML='총 할인 '+(d*100).toFixed(1)+'% · 손님 결제 '+won(paid)+' · 수수료 '+base+'%'+(acc?' + '+acc+'%':'')+
  (fl==null?' · <span class="tag">하한 미지정</span>':pay>=fl?' · <span class="tag ok">하한 '+won(fl)+' 대비 +'+won(pay-fl)+'</span>':' · <span class="tag bad">하한 '+won(fl)+' 대비 -'+won(fl-pay)+'</span>')}
el.addEventListener('input',run);el.addEventListener('change',run);run()});"""
CSS += """.cgrp{border:1px solid var(--line);border-radius:7px;margin:0 0 10px;padding:8px 12px}.cgrp legend{font-weight:700;font-size:13px}
.copt{display:block;padding:3px 0;font-size:14px}.copt input{margin-right:6px}
"""


def combo_card(d, across, T=1, floor=None, rate=None):
    """promoGroups·commissionParts 가 있을 때만 나온다. 켤 수 없는 조합은 UI가 애초에 못 만든다."""
    if not d.get("promoGroups") and not d.get("commissionParts"):
        return ""
    cfg = json.dumps({"across": across, "T": T, "floor": floor}, ensure_ascii=False)
    body = (f'<div class="cols"><div><label class="field">입력 요금 (달력·판매가)<input id="crate" type="number" min="0" step="100" value="{rate or 0}"></label>'
            '<div id="cg"></div><div class="row2" id="cp"></div></div>'
            '<div><small>입금가 (조합 계산값)</small><div class="fig" id="cfig">—</div><p class="note" id="cline"></p>'
            f'<p class="note">그룹 안 「하나만」은 라디오라 두 개를 동시에 켤 수 없다. 그룹끼리는 {"곱해서" if across == "mult" else "더해서"} 합친다. 수수료 선택지를 바꿔 조합을 비교한다.</p></div></div>')
    return (f'<section class="card" id="combo"><h2>조합 비교 (중복 규칙 · 수수료)</h2><div class="body">{body}</div></section>'
            f'<script>var COMBO={cfg};</script>')


def combo_script(d):
    return f"<script>{COMBO_JS}</script>" if d.get("promoGroups") or d.get("commissionParts") else ""


def combo_check(d, errors, warns):
    for g in d.get("promoGroups") or []:
        if g.get("mode") not in MODES:
            errors.append(f'프로모션 그룹 {g.get("name")}: mode 는 {"·".join(MODES)} 중 하나다.')
        for it in g.get("items") or []:
            if not isinstance(it.get("pct"), (int, float)):
                errors.append(f'프로모션 그룹 {g.get("name")} · {it.get("name")}: pct 는 숫자다. 모르면 그 항목을 빼라.')
        if g.get("mode") == "single" and sum(1 for it in g.get("items") or [] if it.get("on")) > 1:
            warns.append(f'프로모션 그룹 {g.get("name")}: 하나만 붙는 그룹에 on 이 2개다. 하나에만 on 을 주고 나머지는 tag 에 「적용 중」을 적는다.')
    for p in d.get("commissionParts") or []:
        if not isinstance(p.get("pct"), (int, float)):
            errors.append(f'수수료 항목 {p.get("name")}: pct 는 숫자다. 모르면 그 항목을 빼라.')
        if p.get("kind") not in ("base", "accel"):
            errors.append(f'수수료 항목 {p.get("name")}: kind 는 base·accel 중 하나다.')
        if p.get("options") and p.get("pct") not in p["options"]:
            warns.append(f'수수료 항목 {p.get("name")}: 현재 값 {p.get("pct")} 가 선택지에 없다.')


def open_card(d):
    items = "".join(f'<li>{esc(o.get("item"))}<br><small>{esc(o.get("how"))}</small></li>' for o in d.get("open") or [])
    return card("미확인 항목", f'<div class="body"><ul>{items}</ul></div>') if items else ""


def render(d):
    p = d.get("property") or {}
    payload = dict(d)
    payload.pop("_note", None)
    payload["leads"] = lead_points(d.get("promotions") or [])
    data = json.dumps(payload, ensure_ascii=False).replace("</", "<\\/")
    parts = [paged([("현재 설정", [summary_tiles(d), findings_card(d), audit_card(d), programs_card(d), content_card(d), plans_card(d), promo_card(d), open_card(d)]),
                    ("계산기", [coef_card(d), calc_card(), combo_card(d, "mult", 1, (d.get("coef") or {}).get("floor"), next((v for r in d.get("rooms") or [] for v in (r.get("rates") or {}).values() if isinstance(v, (int, float))), None))]),
                    ("요금표", [grid_card(), floor_card(d)]),
                    ("실측 기록", [measure_card(d), ledger_card(d)])]), combo_script(d)]
    title = esc(p.get("name") or "숙소")
    return f"""<!doctype html><html lang="ko"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>{title} 부킹 콘솔</title><style>{CSS}</style></head><body><div class="wrap">
<header><div><h1>{title}</h1><div class="sub">부킹닷컴 {esc(p.get("bookingId"))} · 조사일 {esc(p.get("surveyedAt"))}</div></div>
<div class="formula">판매가 × 요금제 × 인원 × (1−타겟) × (1−포트폴리오) × k = 입금가</div></header>
{"".join(parts)}</div><script type="application/json" id="data">{data}</script><script>{JS}</script></body></html>"""


def tier(promos, cond, member):
    """순서 제약 비교용. 그 층에서 가장 깊은 할인율을 돌려준다."""
    vals = [p["pct"] for p in promos if p.get("cat") == "portfolio" and p.get("status", "적용") == "적용"
            and p.get("cond", "base") == cond and bool(p.get("member")) == member]
    return max(vals) if vals else None


def check(d):
    """비어 있거나 어긋난 값을 알린다. 오류가 있으면 생성하지 않는다."""
    errors, warns = [], []
    c = d.get("coef") or {}
    has_k = isinstance(c.get("k"), (int, float))
    if not has_k:
        warns.append("입금 계수 k 가 비어 계산기가 꺼진다.")
    elif not 0 < c["k"] <= 1:
        errors.append("입금 계수 k 는 0 초과 1 이하다.")
    promos = d.get("promotions") or []
    for m in promos:
        if m.get("cat") not in CATS:
            errors.append(f'{m.get("name")}: cat 은 {"·".join(CATS)} 중 하나다.')
        if not isinstance(m.get("pct"), (int, float)):
            errors.append(f'{m.get("name")}: pct 가 숫자가 아니다.')
        if m.get("cat") == "target" and m.get("pos") not in ("domestic", "international", "mobile"):
            errors.append(f'{m.get("name")}: pos 는 domestic·international·mobile 중 하나다.')
    for p in d.get("plans") or []:
        if not isinstance(p.get("mult"), (int, float)) or p["mult"] <= 0:
            errors.append(f'{p.get("name")}: mult 는 양수다.')
    for r in d.get("rooms") or []:
        if not isinstance(r.get("base"), int) or r["base"] < 1:
            errors.append(f'{r.get("name")}: 기준 인원 base 가 없다.')
    for a in d.get("audit") or []:
        if a.get("status") not in AUDIT:
            errors.append(f'점검 {a.get("item")}: status 는 {"·".join(AUDIT)} 중 하나다.')
        elif a["status"] in ("bad", "warn"):
            warns.append(f'점검 {"위험" if a["status"] == "bad" else "주의"}: {a.get("area")} · {a.get("item")} = {a.get("value")}')
    combo_check(d, errors, warns)
    inspect_check(d, errors, warns)
    if errors:
        return errors, warns
    # 어기면 비회원이 회원보다 싸지거나 사전예약이 평시보다 비싸진다
    bp, bs, ep, es = tier(promos, "base", False), tier(promos, "base", True), tier(promos, "advance", False), tier(promos, "advance", True)
    for name_a, a, name_b, b in (("베이직공개", bp, "조기공개", ep), ("조기공개", ep, "조기시크릿", es), ("베이직공개", bp, "베이직시크릿", bs), ("베이직시크릿", bs, "조기시크릿", es)):
        if a is not None and b is not None and a > b:
            warns.append(f"순서 제약 위반: {name_a} {a}% > {name_b} {b}%")
    if has_k and d.get("rooms") and d.get("plans") and isinstance(c.get("floor"), (int, float)):
        for x in floor_cells(d):
            if x["payout"] < c["floor"]:
                warns.append(f'하한 미달: {x["room"]} {x["set"]} {x["plan"]} D-{x["lead"]} 입금 {x["payout"]:,.0f}')
    for r, calc in ledger_rows(d):
        if calc is not None and r.get("payout") is not None and abs(calc - r["payout"]) > r.get("nights", 1):
            warns.append(f'{r.get("label")}: 공식과 실입금이 {calc - r["payout"]:+,.0f}원 어긋난다.')
    return errors, warns


def main():
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, ValueError) as err:
            print(f"[경고] 출력 인코딩을 UTF-8로 바꾸지 못했다: {err}", file=sys.stderr)
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("property")
    ap.add_argument("-o", "--out")
    ap.add_argument("--check", action="store_true", help="검사만 하고 파일을 만들지 않는다")
    a = ap.parse_args()
    try:
        d = json.loads(pathlib.Path(a.property).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as err:
        print(f"[오류] 입력을 읽지 못했다: {err}", file=sys.stderr)
        return 1
    errors, warns = check(d)
    for w in warns:
        print(f"[주의] {w}")
    for e in errors:
        print(f"[오류] {e}", file=sys.stderr)
    if errors:
        return 1
    if a.check:
        print("검사 끝")
        return 0
    if not a.out:
        print("[오류] -o 로 저장 경로를 주거나 --check 를 써라.", file=sys.stderr)
        return 1
    try:
        pathlib.Path(a.out).write_text(render(d), encoding="utf-8")
    except OSError as err:
        print(f"[오류] 저장 실패: {err}", file=sys.stderr)
        return 1
    print(f"완료: {a.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
