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

from payout import coef, lead_segments

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
tr.gap td{background:var(--warn-soft)}.note{font-size:12.5px;color:var(--dim);margin:10px 0 0}
small{color:var(--dim)}ul{margin:0;padding-left:18px}
@media(max-width:640px){.wrap{padding:18px 16px 56px}.formula{margin-left:0}.fig{font-size:32px}}
"""

JS = r"""
const D=JSON.parse(document.getElementById('data').textContent);
const C=D.coef,$=s=>document.querySelector(s),won=x=>Math.round(x).toLocaleString('ko-KR');
const esc=s=>{const e=document.createElement('i');e.textContent=s==null?'':String(s);return e.innerHTML};
const on=(D.promotions||[]).filter(m=>(m.status||'적용')==='적용');
const extra=Math.max(0,...on.filter(m=>m.scope==='member').map(m=>m.pct));
const K=C.T*(1-C.c/100)-C.a/100;
function apply(m,lead){return m.cond==='sameDay'?lead===0:lead>=(m.minDays||0)}
function tier(lead,pos,pkg){let b=null;for(const m of on){if(m.scope==='member'||m.scope==='mobile'||(m.scope==='package'&&!pkg)||(m.scope==='pos'&&!pos))continue;
 if(apply(m,lead)&&(!b||m.pct>b.pct))b=m}return b}
function disc(m,member){const base=m?m.pct:0;if(!member||(m&&m.scope==='package'))return base;
 if(m&&m.memberPct!=null)return m.memberPct;return base+extra}
function calc(rate,d,p){const list=rate*p/C.T,after=list*(1-d/100),paid=after*C.T;
 return{list,after,paid,comp:paid*C.c/100,accel:after*C.a/100,payout:after*K,eff:(1-p*(1-d/100))*100}}
function need(t,d,p){const unit=(D.property&&D.property.roundUnit)||100;
 return Math.ceil(+(t*C.T/(K*(1-d/100)*p)).toFixed(6)/unit)*unit}
function target(from,to){const hit=(D.targets||[]).filter(t=>(to==null||t.from<=to)&&(t.to==null||t.to>=from));
 return hit.length?Math.max(...hit.map(t=>t.payout)):null}
const room=()=>D.rooms[+$('#room').value],rate=()=>+$('#rate').value||0,path=()=>$('#path').value==='P'?C.p:1;
function fillSets(){const r=room().rates,s=$('#set');s.innerHTML=Object.keys(r).filter(k=>r[k]!=null).map(k=>`<option>${esc(k)}</option>`).join('');fillRate()}
function fillRate(){$('#rate').value=room().rates[$('#set').value]||0;render()}
function render(){const pkg=$('#path').value==='P',lead=+$('#lead').value,pos=$('#pos').value==='1',mem=$('#mem').value==='1',m=tier(lead,pos,pkg),d=disc(m,mem),r=calc(rate(),d,path());
 const t=target(lead,lead);$('#fig').textContent=won(r.payout);
 $('#promo').textContent=(m?m.name:'1층 프로모션 없음')+' · 적용 할인 '+d+'%'+(path()!==1?' · 실효 '+r.eff.toFixed(1)+'%':'');
 $('#lines').innerHTML=[['세전 정가',r.list],['할인 후 세전',r.after],['손님 결제',r.paid],['기본 보수 차감',r.comp],['엑셀러레이터 차감',r.accel]]
  .map(([a,b])=>`<div class="line"><span>${a}</span><b>${won(b)}</b></div>`).join('');
 $('#verdict').innerHTML=t==null?'<span class="tag">목표 미지정</span>':r.payout>=t?`<span class="tag ok">목표 ${won(t)} 대비 +${won(r.payout-t)}</span>`
  :`<span class="tag bad">목표 ${won(t)} 대비 -${won(t-r.payout)}</span> <small>필요 달력 ${won(need(t,d,path()))}</small>`;
 const cell=(mm,me)=>{const dd=disc(mm,me),x=calc(rate(),dd,path());return `<td>${dd}%<br><small>결제 ${won(x.paid)}</small><br><b>${won(x.payout)}</b></td>`};
 $('#leadBody').innerHTML=D.segments.map(s=>{const a=tier(s.from,true,pkg),b=tier(s.from,false,pkg),tg=target(s.from,s.to),mine=calc(rate(),disc(a,true),path()).payout;
  const gap=!a||!b,span='D-'+s.from+(s.to==null?'+':s.to!==s.from?'~'+s.to:'');
  const st=tg==null?'<span class="tag">미지정</span>':mine>=tg?'<span class="tag ok">충족</span>':`<span class="tag bad">미달</span><br><small>달력 ${won(need(tg,disc(a,true),path()))}</small>`;
  return `<tr class="${gap?'gap':''}"><td>${span}${gap?' <span class="tag warn">빈 구간</span>':''}</td><td class="l">${esc(a?a.name:'없음')}<br><small>${esc(b?b.name:'없음')}</small></td>${cell(a,true)}${cell(a,false)}${cell(b,true)}${cell(b,false)}<td>${tg==null?'—':won(tg)}</td><td>${st}</td></tr>`}).join('')}
const ready=[C.T,C.c,C.a].every(v=>typeof v==='number')&&(D.rooms||[]).length>0;
if(ready){const leads=D.segments.map(s=>s.from);
 $('#room').innerHTML=D.rooms.map((r,i)=>`<option value="${i}">${esc(r.name)}</option>`).join('');
 $('#lead').innerHTML=leads.map(l=>`<option value="${l}">D-${l}${l===leads[leads.length-1]&&l>0?' 이상':''}</option>`).join('');
 if(typeof C.p!=='number')$('#path').querySelector('[value=P]').disabled=true;
 $('#room').onchange=fillSets;$('#set').onchange=fillRate;
 ['#rate','#lead','#pos','#mem','#path'].forEach(s=>$(s).oninput=render);fillSets()}
else{$('#calc').innerHTML='<div class="body"><span class="tag bad">계산 불가</span> T·c·a 또는 객실 요금이 비어 있습니다. 아래 미확인 항목을 먼저 채우세요.</div>'}
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


def has_rates(d):
    c = d.get("coef") or {}
    return all(isinstance(c.get(x), (int, float)) for x in "Tca")


def coef_card(d):
    c, v = d.get("coef") or {}, (d.get("coef") or {}).get("verified") or {}
    k = coef(c["T"], c["c"], c["a"]) if has_rates(d) else None
    rows = [("T 세금 배수", c.get("T"), v.get("T")), ("c 기본 보수 %", c.get("c"), v.get("c")),
            ("a 엑셀러레이터 %", c.get("a"), v.get("a")), ("p 패키지 배수", c.get("p"), v.get("p"))]
    body = "".join(f'<tr><td>{n}</td><td>{"—" if x is None else x}</td><td>{badge(o)}</td></tr>' for n, x, o in rows)
    body += f'<tr><td><b>k 입금 계수</b></td><td><b>{"—" if k is None else f"{k:.4f}"}</b></td><td><span class="tag">계산</span></td></tr>'
    note = f'<p class="note">근거: {esc(c.get("source"))}</p>' if c.get("source") else ""
    hist = d.get("acceleratorHistory") or []
    if hist:
        note += '<p class="note">엑셀러레이터 이력: ' + " · ".join(f'{esc(h.get("period"))} {esc(h.get("rate"))}%' for h in hist) + "</p>"
    return card("계수", f'<div class="body">{table(["항목", "값", "상태"], [body])}{note}</div>')


def calc_card():
    body = """<div class="cols"><div>
<div class="row2"><label class="field">객실<select id="room"></select></label><label class="field">요금세트<select id="set"></select></label></div>
<label class="field">달력요금 (부가세 포함)<input id="rate" type="number" min="0" step="100"></label>
<div class="row2"><label class="field">리드타임<select id="lead"></select></label>
<label class="field">POS<select id="pos"><option value="1">자국 POS</option><option value="0">그 외</option></select></label>
<label class="field">손님<select id="mem"><option value="1">회원</option><option value="0">비회원</option></select></label>
<label class="field">경로<select id="path"><option value="S">직판 (S)</option><option value="P">패키지·B2B (P)</option></select></label></div>
</div><div><small>입금가 (계산값)</small><div class="fig" id="fig">—</div><div id="verdict"></div><p class="note" id="promo"></p><div id="lines"></div></div></div>"""
    return f'<section class="card" id="calc"><h2>계산기</h2><div class="body">{body}</div></section>'


def lead_card():
    heads = ["구간", '<span class="l">자국 / 그 외 프로모션</span>', "자국 회원", "자국 비회원", "그 외 회원", "그 외 비회원", "목표", "판정"]
    head = "".join(f"<th>{h}</th>" for h in heads)
    return card("리드타임별 입금가 (위 객실·세트·경로 기준)",
                f'<div class="body"><div class="scroll"><table><thead><tr>{head}</tr></thead><tbody id="leadBody"></tbody></table></div>'
                '<p class="note">셀 순서: 적용 할인 · 손님 결제 · 입금가. 판정은 자국 POS 회원 기준. 모두 계산값이고 "입금가 확정"은 예약 결제 내역으로만 한다.</p></div>')


def promo_card(d):
    rows = []
    label = {"pos": "자국 POS", "base": "받침대", "member": "2층 회원", "package": "패키지 전용", "mobile": "모바일 전용 (계산 제외)"}
    for m in d.get("promotions") or []:
        cond = "당일" if m.get("cond") == "sameDay" else (f'최소 {m.get("minDays", 0)}일 전' if m.get("cond") == "advance" else "—")
        if m.get("period"):
            cond += f' · {m["period"]}'
        pct = f'{m.get("pct")} / {m["memberPct"]}%' if "memberPct" in m else f'{m.get("pct")}%'
        rows.append(f'<tr><td>{esc(m.get("name"))}</td><td class="l">{label.get(m.get("scope"), esc(m.get("scope")))}</td>'
                    f'<td class="l">{cond}</td><td>{esc(pct)}</td><td class="l">{esc(m.get("status", "적용"))}</td></tr>')
    return card("프로모션 (비회원 / 회원)", f'<div class="body">{table(["이름", "분류", "조건", "할인", "상태"], rows)}'
                '<p class="note">스냅샷이다. 켜고 끄기 전에 허브에서 다시 읽는다.</p></div>') if rows else ""


def ledger_rows(d):
    """원장 한 줄마다 공식 입금가와 실입금의 차이를 계산한다."""
    c = d.get("coef") or {}
    out = []
    for r in d.get("ledger") or []:
        calc = None
        if isinstance(c.get("T"), (int, float)) and isinstance(c.get("c"), (int, float)) and r.get("after") and r.get("accelRate") is not None:
            calc = r["after"] * coef(c["T"], c["c"], r["accelRate"])
        out.append((r, calc))
    return out


def ledger_card(d):
    rows = []
    for r, calc in ledger_rows(d):
        gap = None if calc is None or r.get("payout") is None else calc - r["payout"]
        tag = "—" if gap is None else f'<span class="tag {"ok" if abs(gap) <= r.get("nights", 1) else "bad"}">{gap:+,.0f}원</span>'
        rows.append(f'<tr><td>{esc(r.get("label"))}</td><td class="l">{esc(r.get("bookedOn"))}</td><td class="l">{esc(r.get("promo"))}</td>'
                    f'<td>{num(r.get("pretax"))}</td><td>{num(r.get("after"))}</td><td>{num(r.get("paid"))}</td>'
                    f'<td>{esc(r.get("accelRate"))}%</td><td><b>{num(r.get("payout"))}</b></td><td>{tag}</td></tr>')
    return card("실측 원장 (예약 결제 내역)", f'<div class="body">{table(["예약", "예약일", "붙은 프로모션", "세전", "할인후", "결제", "엑셀", "실입금", "공식과 차이"], rows)}</div>') if rows else ""


def open_card(d):
    items = "".join(f'<li>{esc(o.get("item"))}<br><small>{esc(o.get("how"))}</small></li>' for o in d.get("open") or [])
    return card("미확인 항목", f'<div class="body"><ul>{items}</ul></div>') if items else ""


def render(d):
    p = d.get("property") or {}
    payload = dict(d)
    payload.pop("_note", None)
    payload["segments"] = [{"from": s["from"], "to": s["to"]} for s in lead_segments(d.get("promotions") or [])]
    data = json.dumps(payload, ensure_ascii=False).replace("</", "<\\/")
    parts = [coef_card(d), calc_card(), lead_card(), promo_card(d), ledger_card(d), open_card(d)]
    title = esc(p.get("name") or "숙소")
    return f"""<!doctype html><html lang="ko"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>{title} 익스 콘솔</title><style>{CSS}</style></head><body><div class="wrap">
<header><div><h1>{title}</h1><div class="sub">익스피디아 {esc(p.get("expediaId"))} · 조사일 {esc(p.get("surveyedAt"))}</div></div>
<div class="formula">달력 ÷ T × (1−d) × k = 입금가 · k = T×(1−c)−a</div></header>
{"".join(parts)}</div><script type="application/json" id="data">{data}</script><script>{JS}</script></body></html>"""


def check(d):
    """비어 있거나 어긋난 값을 알린다. 오류가 있으면 생성하지 않는다."""
    errors, warns = [], []
    c = d.get("coef") or {}
    if not has_rates(d):
        warns.append("T·c·a 중 빈 값이 있어 계산기가 꺼진다.")
    elif coef(c["T"], c["c"], c["a"]) <= 0:
        errors.append("입금 계수 k 가 0 이하다.")
    for m in d.get("promotions") or []:
        if m.get("scope") not in ("pos", "base", "member", "package", "mobile"):
            errors.append(f'{m.get("name")}: scope 는 pos·base·member·package·mobile 중 하나다.')
        if m.get("scope") in ("pos", "base") and m.get("cond") not in ("sameDay", "advance"):
            errors.append(f'{m.get("name")}: cond 는 sameDay·advance 중 하나다.')
        if not isinstance(m.get("pct"), (int, float)):
            errors.append(f'{m.get("name")}: pct 가 숫자가 아니다.')
    if errors:
        return errors, warns
    for s in lead_segments(d.get("promotions") or []):
        if s["pos"] is None or s["other"] is None:
            end = "+" if s["to"] is None else ("" if s["to"] == s["from"] else f'~{s["to"]}')
            warns.append(f'빈 구간 D-{s["from"]}{end}: 1층 프로모션이 없다.')
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
