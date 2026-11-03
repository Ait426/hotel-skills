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


def open_card(d):
    items = "".join(f'<li>{esc(o.get("item"))}<br><small>{esc(o.get("how"))}</small></li>' for o in d.get("open") or [])
    return card("미확인 항목", f'<div class="body"><ul>{items}</ul></div>') if items else ""


def render(d):
    p = d.get("property") or {}
    payload = dict(d)
    payload.pop("_note", None)
    payload["leads"] = lead_points(d.get("promotions") or [])
    data = json.dumps(payload, ensure_ascii=False).replace("</", "<\\/")
    parts = [audit_card(d), coef_card(d), calc_card(), grid_card(), floor_card(d), promo_card(d), ledger_card(d), open_card(d)]
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
