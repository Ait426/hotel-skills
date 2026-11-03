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

from payout import route_sigma

# 화면 원문의 「안 겹침」 목록이다. 시점값이라 숙소 화면과 다르면 화면이 우선이다.
NO_STACK = {("xpos", "package"), ("xpos", "campaign"), ("xpos", "mobile"), ("package", "campaign"),
            ("minStay", "package"), ("minStay", "campaign"), ("minStay", "base")}
TYPES = ("campaign", "package", "xpos", "minStay", "base", "flash", "mobile")

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
const P=Object.fromEntries((D.promotions||[]).map(p=>[p.name,p]));
function option(o,room){let t=0,u=[];for(const n of o.parts||[]){const p=P[n];if(!p||(p.status||'적용')!=='적용'||(p.rooms&&p.rooms.length&&!p.rooms.includes(room)))continue;t+=p.pct;u.push(n+' '+p.pct)}
 if(o.member){t+=C.m||0;u.push('회원 '+(C.m||0))}return{t,u}}
function sigma(rt,room){let b=null;for(const o of rt.options||[]){const x=option(o,room);if(!b||x.t>b.t)b=x}return b||{t:0,u:[]}}
function calc(rate,r,s,a){const pp=rate*r,orig=pp*(1-C.c/100),fin=orig*(1-s/100);return{pp,shown:pp*(1-s/100),orig,fin,pay:fin-a}}
function need(t,r,s,a){const u=(D.property&&D.property.roundUnit)||1000;return Math.ceil(+((t+a)/(r*(1-C.c/100)*(1-s/100))).toFixed(6)/u)*u}
function target(room,set){const h=(D.targets||[]).filter(t=>(!t.room||t.room===room)&&(!t.set||t.set===set));return h.length?Math.max(...h.map(t=>t.payout)):null}
const room=()=>D.rooms[+$('#room').value],plan=()=>D.plans[+$('#plan').value],rate=()=>+$('#rate').value||0,extra=()=>+$('#extra').value||0;
function fillSets(){const r=room().rates,s=$('#set');s.innerHTML=Object.keys(r).filter(k=>r[k]!=null).map(k=>`<option>${esc(k)}</option>`).join('');fillRate()}
function fillRate(){$('#rate').value=room().rates[$('#set').value]||0;render()}
function render(){const nm=room().name,set=$('#set').value,rt=D.routes[+$('#route').value],r=plan().r,a=extra(),x=sigma(rt,nm),o=calc(rate(),r,x.t,a),t=target(nm,set);
 $('#fig').textContent=won(o.pay);$('#promo').textContent=(x.u.join(' + ')||'할인 없음')+' · Σ '+x.t+'%';
 $('#lines').innerHTML=[["P' 취소선 정가",o.pp],['노출가 (쿠폰 전)',o.shown],['원래 객실 요금',o.orig],['최종 객실 요금',o.fin],['프로그램 차감 A',a]]
  .map(([p,q])=>`<div class="line"><span>${p}</span><b>${won(q)}</b></div>`).join('');
 $('#verdict').innerHTML=t==null?'<span class="tag">목표 미지정</span>':o.pay>=t?`<span class="tag ok">목표 ${won(t)} 대비 +${won(o.pay-t)}</span>`
  :`<span class="tag bad">목표 ${won(t)} 대비 -${won(t-o.pay)}</span> <small>필요 판매가 ${won(need(t,r,x.t,a))}</small>`;
 const rows=D.routes.map(q=>{const s=sigma(q,nm),v=calc(rate(),r,s.t,a);return{q,s,v}}),low=Math.min(...rows.map(z=>z.v.pay));
 $('#routeBody').innerHTML=rows.map(({q,s,v})=>{const lo=v.pay===low;
  const st=t==null?'<span class="tag">미지정</span>':v.pay>=t?'<span class="tag ok">충족</span>':`<span class="tag bad">미달</span><br><small>판매가 ${won(need(t,r,s.t,a))}</small>`;
  return `<tr class="${lo?'gap':''}"><td>${esc(q.name)}${lo?' <span class="tag warn">최저</span>':''}</td><td class="l">${esc(s.u.join(' + ')||'할인 없음')}</td><td>${s.t}%</td><td>${won(v.shown)}</td><td><b>${won(v.pay)}</b></td><td>${t==null?'—':won(t)}</td><td>${st}</td></tr>`}).join('')}
const ready=typeof C.c==='number'&&(D.rooms||[]).length>0&&(D.plans||[]).length>0&&(D.routes||[]).length>0;
if(ready){$('#room').innerHTML=D.rooms.map((r,i)=>`<option value="${i}">${esc(r.name)}</option>`).join('');
 $('#plan').innerHTML=D.plans.map((r,i)=>`<option value="${i}">${esc(r.name)} (r ${r.r})</option>`).join('');
 $('#route').innerHTML=D.routes.map((r,i)=>`<option value="${i}">${esc(r.name)}</option>`).join('');
 $('#room').onchange=fillSets;$('#set').onchange=fillRate;['#rate','#plan','#route','#extra'].forEach(s=>$(s).oninput=render);fillSets()}
else{$('#calc').innerHTML='<div class="body"><span class="tag bad">계산 불가</span> c, 객실 판매가, 요금제, 경로 중 빈 값이 있습니다. 아래 미확인 항목을 먼저 채우세요.</div>'}
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
    rows = [("c 수수료율 %", c.get("c"), v.get("c")), ("m 회원 할인 %", c.get("m"), v.get("m"))]
    rows += [(f'r {p.get("name")}', p.get("r"), p.get("verified")) for p in d.get("plans") or []]
    body = "".join(f'<tr><td>{esc(n)}</td><td>{"—" if x is None else x}</td><td>{badge(o)}</td></tr>' for n, x, o in rows)
    note = f'<p class="note">근거: {esc(c.get("source"))}</p>' if c.get("source") else ""
    return card("계수", f'<div class="body">{table(["항목", "값", "상태"], [body])}{note}</div>')


def calc_card():
    body = """<div class="cols"><div>
<div class="row2"><label class="field">객실<select id="room"></select></label><label class="field">요금세트<select id="set"></select></label>
<label class="field">요금제<select id="plan"></select></label></div>
<label class="field">기준 판매가<input id="rate" type="number" min="0" step="1000"></label>
<div class="row2"><label class="field">경로<select id="route"></select></label>
<label class="field">프로그램 차감 A (원)<input id="extra" type="number" min="0" step="100" value="0"></label></div>
</div><div><small>지급액 (계산값)</small><div class="fig" id="fig">—</div><div id="verdict"></div><p class="note" id="promo"></p><div id="lines"></div></div></div>"""
    return f'<section class="card" id="calc"><h2>계산기</h2><div class="body">{body}</div></section>'


def route_card():
    heads = ["경로", '<span class="l">걸리는 할인</span>', "Σ", "노출가", "지급액", "목표", "판정"]
    head = "".join(f"<th>{h}</th>" for h in heads)
    return card("경로별 지급액 (위 객실·세트·요금제 기준)",
                f'<div class="body"><div class="scroll"><table><thead><tr>{head}</tr></thead><tbody id="routeBody"></tbody></table></div>'
                '<p class="note">최저 경로로 역산한다. 판매가 하나가 전 경로를 같이 움직인다. 모두 계산값이고 "입금가 확정"은 예약 지급액으로만 한다.</p></div>')


def promo_card(d):
    label = {"campaign": "캠페인", "package": "Package", "xpos": "XPOS", "minStay": "연박", "base": "기본", "flash": "기간 한정", "mobile": "모바일"}
    rows = []
    for m in d.get("promotions") or []:
        rooms = ", ".join(m.get("rooms") or []) or "전 객실"
        rows.append(f'<tr><td>{esc(m.get("name"))}</td><td class="l">{esc(label.get(m.get("type"), m.get("type")))}</td><td>{esc(m.get("pct"))}%</td>'
                    f'<td class="l">{esc(m.get("countries"))}</td><td class="l">{esc(rooms)}</td><td class="l">{esc(m.get("status", "적용"))}</td></tr>')
    return card("프로모션 (OFF 칸 기준)", f'<div class="body">{table(["이름", "유형", "OFF", "적용 국가", "대상 객실", "상태"], rows)}'
                '<p class="note">스냅샷이다. 켜고 끄기 전에 OFF 칸과 Logs를 다시 읽는다.</p></div>') if rows else ""


def ledger_rows(d):
    """원장 한 줄마다 달력값에서 낸 공식 지급액과 실제 지급액의 차이를 계산한다."""
    c = (d.get("coef") or {}).get("c")
    out = []
    for r in d.get("ledger") or []:
        calc = None
        if isinstance(c, (int, float)) and r.get("pprime") and r.get("sigma") is not None:
            calc = r["pprime"] * (1 - c / 100) * (1 - r["sigma"] / 100) - (r.get("extra") or 0)
        out.append((r, calc))
    return out


def ledger_card(d):
    rows = []
    for r, calc in ledger_rows(d):
        gap = None if calc is None or r.get("payout") is None else calc - r["payout"]
        tag = "—" if gap is None else f'<span class="tag {"ok" if abs(gap) <= r.get("nights", 1) else "bad"}">{gap:+,.0f}원</span>'
        rows.append(f'<tr><td>{esc(r.get("label"))}</td><td class="l">{esc(r.get("bookedOn"))}</td><td class="l">{esc(r.get("path"))}</td><td class="l">{esc(r.get("promo"))}</td>'
                    f'<td>{num(r.get("pprime"))}</td><td>{esc(r.get("sigma"))}%</td><td>{num(r.get("extra"))}</td><td><b>{num(r.get("payout"))}</b></td><td>{tag}</td></tr>')
    return card("실측 원장 (예약 지불 정보)", f'<div class="body">{table(["예약", "예약일", "경로", "붙은 할인", "P 합계", "Σ", "A", "지급액", "공식과 차이"], rows)}</div>') if rows else ""


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
    data = json.dumps(payload, ensure_ascii=False).replace("</", "<\\/")
    parts = [audit_card(d), coef_card(d), calc_card(), route_card(), promo_card(d), ledger_card(d), open_card(d)]
    title = esc(p.get("name") or "숙소")
    return f"""<!doctype html><html lang="ko"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>{title} 트립 콘솔</title><style>{CSS}</style></head><body><div class="wrap">
<header><div><h1>{title}</h1><div class="sub">트립닷컴 {esc(p.get("tripId"))} · 조사일 {esc(p.get("surveyedAt"))}</div></div>
<div class="formula">판매가 × r × (1−c) × (1−Σ) − A = 지급액</div></header>
{"".join(parts)}</div><script type="application/json" id="data">{data}</script><script>{JS}</script></body></html>"""


def check(d):
    """비어 있거나 어긋난 값을 알린다. 오류가 있으면 생성하지 않는다."""
    errors, warns = [], []
    c = d.get("coef") or {}
    if not isinstance(c.get("c"), (int, float)):
        warns.append("수수료율 c 가 비어 계산기가 꺼진다.")
    elif not 0 <= c["c"] < 100:
        errors.append("수수료율 c 는 0 이상 100% 미만이다.")
    promos = {m.get("name"): m for m in d.get("promotions") or []}
    for m in promos.values():
        if m.get("type") not in TYPES:
            errors.append(f'{m.get("name")}: type 은 {"·".join(TYPES)} 중 하나다.')
        if not isinstance(m.get("pct"), (int, float)):
            errors.append(f'{m.get("name")}: pct 가 숫자가 아니다.')
    for p in d.get("plans") or []:
        if not isinstance(p.get("r"), (int, float)) or p["r"] <= 0:
            errors.append(f'{p.get("name")}: r 은 양수다.')
    for rt in d.get("routes") or []:
        for o in rt.get("options") or []:
            parts = o.get("parts") or []
            for n in parts:
                if n not in promos:
                    errors.append(f'{rt.get("name")}: 없는 프로모션 {n}')
            types = [promos[n].get("type") for n in parts if n in promos]
            for i, a in enumerate(types):
                for b in types[i + 1:]:
                    if (a, b) in NO_STACK or (b, a) in NO_STACK:
                        warns.append(f'{rt.get("name")}: {a} 와 {b} 는 화면 원문상 겹치지 않는다. 후보를 나눠 적어라.')
            if o.get("member") and "campaign" in types:
                warns.append(f'{rt.get("name")}: 캠페인 + 회원 중복은 확인 필요 항목이다. 실예약으로 확인했는지 본다.')
    for a in d.get("audit") or []:
        if a.get("status") not in AUDIT:
            errors.append(f'점검 {a.get("item")}: status 는 {"·".join(AUDIT)} 중 하나다.')
        elif a["status"] in ("bad", "warn"):
            warns.append(f'점검 {"위험" if a["status"] == "bad" else "주의"}: {a.get("area")} · {a.get("item")} = {a.get("value")}')
    if errors:
        return errors, warns
    for rt in d.get("routes") or []:
        s, _ = route_sigma(rt, d.get("promotions") or [], c.get("m"))
        if s >= 100:
            errors.append(f'{rt.get("name")}: Σ 가 100% 이상이다.')
    for r, calc in ledger_rows(d):
        if calc is not None and r.get("payout") is not None and abs(calc - r["payout"]) > r.get("nights", 1):
            warns.append(f'{r.get("label")}: 공식과 지급액이 {calc - r["payout"]:+,.0f}원 어긋난다.')
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
