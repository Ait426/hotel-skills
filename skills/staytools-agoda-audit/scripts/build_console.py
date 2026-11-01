#!/usr/bin/env python3
"""property.json → 자체 완결 HTML 콘솔 한 장.

외부 참조는 구글 폰트뿐이라 어디에 올려도 깨지지 않는다.
없는 섹션은 자동으로 빠지므로 부분 조사여도 돌아간다.

  python build_console.py property.json -o 콘솔.html [--check] [--artifact]
"""
import argparse, html, json, math, pathlib, sys

# ── 색: 청록 잉크 + 황동 악센트. 라이트/다크 둘 다 토큰으로 정의한다 ──────────
CSS = """:root{
  --ground:#ECEFEA; --surface:#F6F8F4; --sunk:#E1E6DE;
  --line:#CBD3C9; --line-soft:#DCE2D8;
  --text:#0F1A1C; --text-dim:#4C5A57; --text-faint:#75837E;
  --brass:#8F6516; --brass-soft:#EFE2C6;
  --ok:#256B4B; --ok-soft:#D3E7DB;
  --warn:#9C6112; --warn-soft:#F5E4C8;
  --bad:#973129; --bad-soft:#F3D8D4;
  --shadow:0 1px 2px rgba(15,26,28,.06), 0 8px 24px -16px rgba(15,26,28,.22);
}
@media (prefers-color-scheme:dark){
  :root:not([data-theme="light"]){
    --ground:#0C1214; --surface:#141D1E; --sunk:#0A0F11;
    --line:#2A3739; --line-soft:#1E2A2B;
    --text:#E2E8E2; --text-dim:#9DAAA6; --text-faint:#71807C;
    --brass:#D5A244; --brass-soft:#3A2E16;
    --ok:#5CBF92; --ok-soft:#12291F;
    --warn:#DFA85A; --warn-soft:#2E2312;
    --bad:#E08078; --bad-soft:#2E1715;
    --shadow:0 1px 2px rgba(0,0,0,.4), 0 8px 24px -16px rgba(0,0,0,.7);
  }
}
:root[data-theme="dark"]{
  --ground:#0C1214; --surface:#141D1E; --sunk:#0A0F11;
  --line:#2A3739; --line-soft:#1E2A2B;
  --text:#E2E8E2; --text-dim:#9DAAA6; --text-faint:#71807C;
  --brass:#D5A244; --brass-soft:#3A2E16;
  --ok:#5CBF92; --ok-soft:#12291F;
  --warn:#DFA85A; --warn-soft:#2E2312;
  --bad:#E08078; --bad-soft:#2E1715;
  --shadow:0 1px 2px rgba(0,0,0,.4), 0 8px 24px -16px rgba(0,0,0,.7);
}

*{box-sizing:border-box}
body{
  margin:0; background:var(--ground); color:var(--text);
  font-family:"IBM Plex Sans KR",system-ui,-apple-system,"Malgun Gothic",sans-serif;
  font-size:15px; line-height:1.55; -webkit-font-smoothing:antialiased;
}
.mono{font-family:"IBM Plex Mono","SFMono-Regular",ui-monospace,monospace;font-variant-numeric:tabular-nums}
.wrap{max-width:1180px;margin:0 auto;padding:28px 20px 72px}

/* ── header ─────────────────────────────── */
header{display:flex;flex-wrap:wrap;align-items:flex-end;gap:16px;
  padding-bottom:18px;border-bottom:2px solid var(--text);margin-bottom:26px}
h1{margin:0;font-size:27px;font-weight:700;letter-spacing:-.02em;line-height:1.15}
.formula{margin-left:auto;font-size:12px;color:var(--text-dim);
  background:var(--sunk);border:1px solid var(--line-soft);border-radius:5px;padding:7px 12px}
.formula b{color:var(--brass);font-weight:600}

/* ── mode switch ────────────────────────── */
.modes{display:inline-flex;background:var(--sunk);border:1px solid var(--line);
  border-radius:7px;padding:3px;gap:3px;margin-bottom:22px}
.modes button{font:inherit;font-size:13px;font-weight:500;border:0;cursor:pointer;
  padding:7px 18px;border-radius:5px;background:transparent;color:var(--text-dim)}
.modes button[aria-pressed="true"]{background:var(--surface);color:var(--text);
  box-shadow:var(--shadow);font-weight:600}
.modes button:focus-visible{outline:2px solid var(--brass);outline-offset:2px}

/* ── grid ───────────────────────────────── */
.cols{display:grid;grid-template-columns:minmax(0,1fr);gap:20px}
.cols > *{min-width:0}
/* 좁은 화면: 결과를 위로 */
.col-input{order:2} .col-out{order:1}
@media(min-width:940px){
  .cols{grid-template-columns:minmax(0,1fr) 400px;align-items:start}
  .col-input{order:1} .col-out{order:2}
}
@media(max-width:939px){
  .readout{position:static}
  .wrap{padding-left:14px;padding-right:14px}
  h1{font-size:23px}
  .formula{margin-left:0;font-size:11px}
  .big .fig{font-size:38px}
  .opt .id{display:none}
  .grp-head{flex-wrap:wrap;row-gap:2px}
  .rule{flex-basis:100%;order:3}
}

.card{background:var(--surface);border:1px solid var(--line);border-radius:9px;
  box-shadow:var(--shadow);overflow:hidden;max-width:100%}
.card + .card{margin-top:18px}
.card h2{margin:0;font-size:12px;font-weight:600;letter-spacing:.09em;text-transform:uppercase;
  color:var(--text-dim);padding:13px 18px;border-bottom:1px solid var(--line-soft);
  background:var(--sunk);display:flex;align-items:center;gap:9px}
.card h2 .tally{margin-left:auto;color:var(--brass);letter-spacing:0;font-size:13px}
.card .body{padding:16px 18px}

/* ── promo rows ─────────────────────────── */
.grp{border-top:1px solid var(--line-soft)}
.grp:first-child{border-top:0}
.grp-head{display:flex;align-items:baseline;gap:9px;padding:13px 18px 7px}
.grp-name{font-size:13px;font-weight:600}
.rule{font-size:11px;color:var(--text-faint)}
.grp-sum{margin-left:auto;font-size:13px;font-weight:600}
.opts{padding:0 18px 13px;display:flex;flex-direction:column;gap:2px}
.opts.scroll-y{max-height:268px;overflow-y:auto;margin:0 4px 9px;padding:0 14px 4px;
  border:1px solid var(--line-soft);border-radius:6px;background:var(--ground)}
.opt{display:flex;align-items:center;gap:10px;padding:5px 8px;border-radius:5px;cursor:pointer}
.opt:hover{background:var(--sunk)}
.opt input{accent-color:var(--brass);width:15px;height:15px;margin:0;flex:none;cursor:pointer}
.opt input:focus-visible{outline:2px solid var(--brass);outline-offset:2px}
.opt .nm{flex:1;min-width:0;font-size:13.5px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.opt .id{font-size:11px;color:var(--text-faint);flex:none}
.opt .pct{width:62px;flex:none;text-align:right;padding:3px 7px;font-size:13px;
  border:1px solid var(--line);border-radius:4px;background:var(--ground);color:var(--text)}
.opt .pct:disabled{opacity:.35;background:transparent;border-color:transparent}
.opt.on{background:var(--brass-soft)}
.opt.on .nm{font-weight:600}
.opt.risk .nm::after{content:" 위험";color:var(--bad);font-size:11px;font-weight:600}
.locked .opt{cursor:default;background:var(--brass-soft)}
.locked .opt .nm{font-weight:600}
.locked .dot{width:15px;height:15px;flex:none;border-radius:50%;background:var(--brass);
  position:relative}
.locked .dot::after{content:"";position:absolute;inset:4px;border-radius:50%;background:var(--surface)}
.locked .pct{opacity:1;color:var(--text)}

/* ── commission ─────────────────────────── */
.crow{display:flex;align-items:center;gap:12px;padding:8px 0;border-top:1px solid var(--line-soft)}
.crow:first-child{border-top:0}
.crow .lab{flex:1;min-width:0;font-size:13.5px}
.crow .lab small{display:block;color:var(--text-faint);font-size:11px}
.crow select,.crow input[type="number"]{font:inherit;font-size:13px;padding:5px 8px;
  border:1px solid var(--line);border-radius:5px;background:var(--ground);color:var(--text)}
.crow select{max-width:180px}
.crow .val{width:56px;text-align:right;font-size:13.5px;font-weight:600}
input[type="range"]{accent-color:var(--brass);flex:1;min-width:80px}
.hint{margin:12px 0 0;padding:10px 12px;background:var(--sunk);border-left:3px solid var(--brass);
  border-radius:0 5px 5px 0;font-size:12px;line-height:1.6;color:var(--text-dim)}
.hint b{color:var(--text);font-weight:600}

/* ── readout ────────────────────────────── */
.readout{position:sticky;top:18px}
.big{padding:22px 20px;text-align:center;border-bottom:1px solid var(--line-soft)}
.big .cap{font-size:11px;letter-spacing:.09em;text-transform:uppercase;color:var(--text-dim)}
.big .fig{font-size:44px;font-weight:600;line-height:1.05;margin-top:5px;letter-spacing:-.02em}
.big .unit{font-size:20px;color:var(--text-dim);margin-left:3px}
.big .note{font-size:12px;color:var(--text-dim);margin-top:6px}
.big.bad{background:var(--bad-soft)} .big.bad .fig{color:var(--bad)}
.big.warn{background:var(--warn-soft)} .big.warn .fig{color:var(--warn)}
.big.ok .fig{color:var(--text)}

.target{display:flex;align-items:center;gap:10px;padding:14px 18px;background:var(--sunk);
  border-bottom:1px solid var(--line-soft)}
.target label{font-size:12.5px;font-weight:600;flex:none}
.target input{font:inherit;font-size:17px;font-weight:600;width:100%;padding:7px 11px;
  border:1px solid var(--line);border-radius:6px;background:var(--surface);color:var(--text);
  text-align:right;font-family:"IBM Plex Mono",ui-monospace,monospace;font-variant-numeric:tabular-nums}
.target input:focus{outline:2px solid var(--brass);outline-offset:0}
.chips{display:flex;gap:5px;padding:0 18px 13px;background:var(--sunk);flex-wrap:wrap}
.chips button{font:inherit;font-size:11.5px;padding:4px 10px;border-radius:20px;cursor:pointer;
  border:1px solid var(--line);background:var(--surface);color:var(--text-dim)}
.chips button:hover{border-color:var(--brass);color:var(--brass)}
.chips button:focus-visible{outline:2px solid var(--brass);outline-offset:2px}

/* ── chain ──────────────────────────────── */
.chain{padding:6px 18px 16px}
.step{display:flex;align-items:baseline;gap:10px;padding:7px 0;font-size:13px;
  border-bottom:1px dashed var(--line-soft)}
.step:last-child{border-bottom:0}
.step .k{color:var(--text-dim);flex:1;min-width:0}
.step .k em{font-style:normal;color:var(--text-faint);font-size:11.5px;display:block}
.step .v{font-weight:600;white-space:nowrap}
.step.hi{background:var(--sunk);margin:0 -18px;padding:8px 18px;border-bottom:0}
.step.hi .v{color:var(--brass)}

/* ── bars ───────────────────────────────── */
.bar{display:flex;height:26px;border-radius:5px;overflow:hidden;border:1px solid var(--line);margin-top:4px}
.seg{display:flex;align-items:center;justify-content:center;font-size:10.5px;font-weight:600;
  color:#fff;min-width:0;overflow:hidden;white-space:nowrap;
  font-family:"IBM Plex Mono",ui-monospace,monospace}
.legend{display:flex;flex-wrap:wrap;gap:12px;margin-top:8px;font-size:11.5px;color:var(--text-dim)}
.legend i{display:inline-block;width:9px;height:9px;border-radius:2px;margin-right:5px;vertical-align:baseline}

/* ── table ──────────────────────────────── */
.scroll{overflow-x:auto;max-width:100%}
table{border-collapse:collapse;width:100%;font-size:13px}
th,td{padding:8px 12px;text-align:right;white-space:nowrap;border-bottom:1px solid var(--line-soft)}
th{font-size:11px;letter-spacing:.05em;text-transform:uppercase;color:var(--text-dim);
  font-weight:600;background:var(--sunk);position:sticky;top:0}
th:first-child,td:first-child{text-align:left}
tbody tr:hover{background:var(--sunk)}
td.num{font-family:"IBM Plex Mono",ui-monospace,monospace;font-variant-numeric:tabular-nums}
.pill{display:inline-block;padding:1px 8px;border-radius:20px;font-size:11px;font-weight:600}
.pill.ok{background:var(--ok-soft);color:var(--ok)}
.pill.warn{background:var(--warn-soft);color:var(--warn)}
.pill.bad{background:var(--bad-soft);color:var(--bad)}

.foot{margin-top:26px;padding-top:16px;border-top:1px solid var(--line);
  font-size:12px;color:var(--text-faint);display:flex;flex-wrap:wrap;gap:18px}
.foot b{color:var(--text-dim);font-weight:600}
@media (prefers-reduced-motion:reduce){*{transition:none!important;animation:none!important}}

/* ══ 사이트 셸 ══════════════════════════════════════════════ */
.topbar{position:sticky;top:0;z-index:50;background:color-mix(in srgb, var(--ground) 88%, transparent);
  backdrop-filter:saturate(1.4) blur(12px);border-bottom:1px solid var(--line-soft)}
.topbar-in{max-width:1180px;margin:0 auto;padding:0 20px;display:flex;align-items:center;
  gap:26px;min-height:54px;flex-wrap:wrap}
.brand{font-weight:700;font-size:14px;letter-spacing:-.01em;white-space:nowrap;
  display:flex;align-items:baseline;gap:8px}
.brand em{font-style:normal;font-size:11px;color:var(--text-faint);font-weight:500}
.nav{display:flex;gap:2px;flex-wrap:wrap;margin-left:auto}
.nav a{font-size:13px;color:var(--text-dim);text-decoration:none;padding:7px 11px;
  border-radius:7px;transition:background .12s,color .12s;white-space:nowrap}
.nav a:hover{background:var(--sunk);color:var(--text)}
.nav a[aria-current="page"]{background:var(--brass-soft);color:var(--brass);font-weight:600}
.nav a:focus-visible{outline:2px solid var(--brass);outline-offset:2px}

/* 채널 탭 */
.chtabs{display:flex;gap:6px;flex-wrap:wrap;margin:0 0 22px}
.chtab{font:inherit;font-size:13px;padding:8px 14px;border-radius:9px;cursor:pointer;
  border:1px solid var(--line);background:var(--surface);color:var(--text-dim);
  display:flex;align-items:center;gap:7px;transition:all .12s}
.chtab:hover:not(:disabled){border-color:var(--brass);color:var(--text)}
.chtab[aria-pressed="true"]{background:var(--brass);border-color:var(--brass);color:#fff;font-weight:600}
.chtab:disabled{opacity:.5;cursor:not-allowed}
.chtab .dot{width:6px;height:6px;border-radius:50%;background:var(--text-faint)}
.chtab[data-status="live"] .dot{background:var(--ok)}
.chtab[data-status="partial"] .dot{background:var(--warn)}
.chtab[aria-pressed="true"] .dot{background:#fff}

/* 상태 배지 */
.badge{display:inline-flex;align-items:center;gap:5px;font-size:11px;font-weight:600;
  padding:3px 9px;border-radius:999px;letter-spacing:.02em;vertical-align:middle}
.badge.live{background:var(--ok-soft);color:var(--ok)}
.badge.partial{background:var(--warn-soft);color:var(--warn)}
.badge.planned{background:var(--sunk);color:var(--text-faint)}

/* 문서형 페이지 */
.doc{max-width:1180px;margin:0 auto;padding:34px 20px 90px}
.doc h1{font-size:27px;letter-spacing:-.022em;margin:0 0 6px;text-wrap:balance}
.doc .lede{font-size:14.5px;color:var(--text-dim);margin:0 0 34px;max-width:66ch;line-height:1.62}
.doc h2{font-size:17px;letter-spacing:-.014em;margin:44px 0 4px;text-wrap:balance}
.doc h2:first-of-type{margin-top:34px}
.doc h2 + .sub{font-size:12.5px;color:var(--text-faint);margin:0 0 16px;max-width:70ch;line-height:1.6}
.doc h3{font-size:14px;margin:26px 0 10px;color:var(--text-dim);letter-spacing:.01em}
.doc p{max-width:70ch;line-height:1.7;margin:0 0 12px;font-size:13.5px}
.doc ul{max-width:70ch;line-height:1.7;font-size:13.5px;padding-left:20px;margin:0 0 12px}
.doc li{margin-bottom:5px}
.doc .card{padding:0;overflow:hidden}
.doc table{font-size:13px}
.doc .scroll{max-height:none}

/* 콜아웃 */
.call{border-left:3px solid var(--line);background:var(--surface);border-radius:0 10px 10px 0;
  padding:14px 18px;margin:16px 0;max-width:74ch;font-size:13px;line-height:1.68}
.call b{font-weight:600}
.call.ok{border-color:var(--ok);background:var(--ok-soft)}
.call.warn{border-color:var(--warn);background:var(--warn-soft)}
.call.bad{border-color:var(--bad);background:var(--bad-soft)}
.call .lbl{display:block;font-size:11px;font-weight:700;letter-spacing:.07em;
  text-transform:uppercase;margin-bottom:5px;opacity:.85}

/* 수치 타일 */
.tiles{display:grid;grid-template-columns:repeat(auto-fit,minmax(158px,1fr));gap:12px;margin:18px 0}
.tile{background:var(--surface);border:1px solid var(--line-soft);border-radius:12px;padding:14px 16px}
.tile .k{font-size:11px;letter-spacing:.06em;text-transform:uppercase;color:var(--text-faint);
  margin-bottom:7px;line-height:1.35}
.tile .v{font-size:22px;font-weight:600;letter-spacing:-.02em;
  font-family:"IBM Plex Mono",ui-monospace,monospace;font-variant-numeric:tabular-nums}
.tile .n{font-size:11.5px;color:var(--text-dim);margin-top:5px;line-height:1.5}
.tile.ok .v{color:var(--ok)} .tile.warn .v{color:var(--warn)} .tile.bad .v{color:var(--bad)}

/* 할 일 목록 */
.todo{list-style:none;padding:0;margin:12px 0;max-width:74ch}
.todo li{display:flex;gap:11px;align-items:flex-start;padding:9px 0;
  border-bottom:1px solid var(--line-soft);font-size:13px;line-height:1.6}
.todo li:last-child{border-bottom:0}
.todo li::before{content:"";flex:0 0 15px;height:15px;margin-top:2px;border-radius:4px;
  border:1.5px solid var(--line);background:var(--surface)}

.doc .foot{max-width:none}

/* ── build_console 전용 보강 ─────────────── */
.page[hidden]{display:none}
.pgtab{font:inherit;font-size:13px;color:var(--text-dim);padding:7px 12px;border-radius:7px;
  border:0;background:transparent;cursor:pointer;white-space:nowrap;transition:background .12s,color .12s}
.pgtab:hover{background:var(--sunk);color:var(--text)}
.pgtab[aria-pressed="true"]{background:var(--brass-soft);color:var(--brass);font-weight:600}
.pgtab:focus-visible{outline:2px solid var(--brass);outline-offset:2px}
.topbar{position:sticky;top:0;z-index:50;background:var(--surface);
  border-bottom:1px solid var(--line);padding:0 20px}
.topbar-in{max-width:1180px;margin:0 auto;display:flex;align-items:center;
  gap:20px;min-height:56px;flex-wrap:wrap}
.brand{font-weight:700;font-size:15px;white-space:nowrap}
.brand em{font-style:normal;color:var(--text-faint);font-weight:400;margin-left:8px;font-size:13px}
.nav{display:flex;gap:2px;flex-wrap:wrap;margin-left:auto}
h2{font-size:19px;margin:34px 0 6px;letter-spacing:-.01em;text-wrap:balance}
h2:first-child{margin-top:0}
h3{font-size:15px;margin:26px 0 8px}
table{border-collapse:collapse;width:100%;font-size:13.5px;min-width:420px}
th,td{padding:9px 13px;text-align:left;border-bottom:1px solid var(--line-soft);white-space:nowrap}
th{background:var(--sunk);font-weight:600;font-size:12px;color:var(--text-dim);
  text-transform:uppercase;letter-spacing:.05em}
tbody tr:last-child td{border-bottom:0}
td.num,th.num{text-align:right}
.tiles{display:grid;grid-template-columns:repeat(auto-fit,minmax(178px,1fr));gap:12px;margin:14px 0}
.tile{background:var(--surface);border:1px solid var(--line);border-radius:11px;padding:14px 16px}
.tile .k{font-size:11.5px;color:var(--text-faint);text-transform:uppercase;letter-spacing:.06em}
.tile .v{font-family:"IBM Plex Mono",monospace;font-size:23px;font-weight:600;margin-top:3px;
  font-variant-numeric:tabular-nums}
.tile .n{font-size:12px;color:var(--text-dim);margin-top:3px}
.call{border-left:3px solid var(--line);background:var(--surface);padding:13px 16px;
  border-radius:0 9px 9px 0;margin:14px 0;font-size:13.5px;max-width:88ch}
.call .lbl{display:block;font-weight:600;margin-bottom:5px}
.call.ok{border-color:var(--ok);background:var(--ok-soft)}
.call.warn{border-color:var(--warn);background:var(--warn-soft)}
.call.bad{border-color:var(--bad);background:var(--bad-soft)}
.badge{display:inline-block;font-size:11px;padding:2px 8px;border-radius:99px;
  font-weight:600;vertical-align:2px;margin-left:6px}
.badge.live,.badge.high{background:var(--bad-soft);color:var(--bad)}
.badge.med{background:var(--warn-soft);color:var(--warn)}
.badge.info,.badge.planned{background:var(--sunk);color:var(--text-faint)}
.badge.good{background:var(--ok-soft);color:var(--ok)}
ul.plain{padding-left:19px;margin:8px 0;max-width:84ch}
ul.plain li{margin:5px 0;font-size:13.5px}
code{font-family:"IBM Plex Mono",monospace;font-size:12.5px;background:var(--sunk);
  padding:1px 6px;border-radius:4px}
.foot{margin-top:44px;padding-top:16px;border-top:1px solid var(--line);
  font-size:12px;color:var(--text-faint)}
label.fld{display:block;font-size:12px;color:var(--text-dim);margin:11px 0 4px}
input[type=number],input[type=text]{font:inherit;font-family:"IBM Plex Mono",monospace;
  background:var(--ground);color:var(--text);border:1px solid var(--line);
  border-radius:7px;padding:7px 10px;width:100%;font-variant-numeric:tabular-nums}
input:focus{outline:2px solid var(--brass);outline-offset:1px;border-color:transparent}
"""


def esc(x):
    return html.escape(str(x if x is not None else ""))


def dash(x, unit=""):
    """None/빈값은 '—'. 화면에 None 이 찍히는 걸 막는다."""
    if x is None or x == "":
        return "—"
    return f"{x}{unit}"


def won(n):
    return "—" if n is None else f"{round(n):,}"


def parts_sum(parts):
    """보수 구성 합계. pct 가 숫자인 항목만 더한다 (비어 있는 항목은 건너뛴다)."""
    total = sum(x["pct"] for x in parts
                if x.get("on", True) and isinstance(x.get("pct"), (int, float)))
    return round(total, 4)


# ── 섹션 렌더러 ─────────────────────────────────────────────────────────────
def calc_model(d):
    """property.json → 계산기 데이터 모델. groups 가 없으면 sigmaBreakdown 으로 합성한다."""
    prom = d.get("promotions") or {}
    groups = prom.get("groups")
    if not groups:
        groups = []
        for b in (prom.get("sigmaBreakdown") or []):
            key = str(b.get("label", "g")).replace(" ", "")
            groups.append({
                "key": key, "name": b.get("label"), "rule": b.get("rule", ""),
                "mode": b.get("mode", "single"),
                "items": [{"id": key + "0", "nm": "없음", "pct": 0}] +
                         [{"id": key + "1", "nm": b.get("label"), "tag": b.get("tag", ""),
                           "pct": b.get("pct", 0), "on": True}],
            })
    c = d.get("commission") or {}
    parts = c.get("parts") or ([{"name": "보수", "pct": c.get("total")}] if c.get("total") is not None else [])
    parts = [x for x in parts if isinstance(x.get("pct"), (int, float))]
    for k, part in enumerate(parts):
        part.setdefault("id", "c%d" % k)
        part.setdefault("on", True)
    p = d.get("property") or {}
    meas = []
    tax = (d.get("tax") or {}).get("multiplier") or 1.1
    for m in (d.get("measurements") or []):
        if m.get("cms") and m.get("displayedPreTax"):
            meas.append({"d": m.get("date"), "cms": m["cms"], "pre": m["displayedPreTax"],
                         "note": m.get("note", "")})
    return {
        "groups": groups, "parts": parts, "tax": tax,
        "floor": p.get("floor"),
        "roundUnit": p.get("roundUnit") or 5000,
        # v 가 null 인 항목은 버린다. 남기면 계산기 JS 가 toLocaleString 에서 죽는다.
        "targets": [t for t in (p.get("targets") or
                    ([] if not p.get("floor") else [{"label": "하한", "v": p["floor"]}]))
                    if isinstance(t.get("v"), (int, float))],
        "cmsPresets": [v for v in (p.get("cmsPresets") or
                       sorted({r.get("cms") for r in (d.get("weekly") or []) if r.get("cms")}))
                       if isinstance(v, (int, float))],
        "weekly": [r for r in (d.get("weekly") or []) if isinstance(r.get("cms"), (int, float))],
        "meas": meas,
        "measNotes": p.get("measurementNotes") or [],
    }


def sec_calc(d):
    m = calc_model(d)
    return ('<div class="wrap">\n'
            '<header><div><h1>입금가 역산기</h1>'
            '<p class="sub" id="subline">프로모션을 고르고 목표 입금가를 넣으면 CMS 설정값이 나옵니다</p></div>'
            '<div class="formula">입금가 = CMS × (1 − <b>Σ</b>) × (1 − <b>보수</b>)</div></header>\n'
            '<div class="modes" style="margin-bottom:18px">'
            '<button id="mRev" aria-pressed="true">목표 입금가 → CMS</button>'
            '<button id="mFwd" aria-pressed="false">CMS → 입금가</button></div>\n'
            '<div class="cols"><div class="col-input">\n'
            '  <section class="card"><h2>프로모션 <span class="tally mono" id="sigTally">Σ 0%</span></h2>'
            '    <div id="promoGroups"></div></section>\n'
            '  <section class="card" style="margin-top:16px"><h2>보수 <span class="tally mono" id="commTally">0%</span></h2>'
            '    <div class="body" id="commBody"></div></section>\n'
            '  <section class="card" id="measCard" style="margin-top:16px"><h2>실측 대조 '
            '    <span class="tally mono" id="measTally"></span></h2><div class="body" id="measBody"></div></section>\n'
            '  <section class="card" id="weekCard" style="margin-top:16px"><h2>요일별 일괄 '
            '    <span class="tally mono" id="tableTally"></span></h2>'
            '    <div class="scroll"><table id="dayTable"><thead></thead><tbody></tbody></table></div></section>\n'
            '</div>\n'
            '<div class="col-out"><div class="readout">\n'
            '  <div class="target"><label for="tgt" id="tgtLabel">목표 입금가</label>'
            '    <input id="tgt" class="mono" type="text" inputmode="numeric" value=""></div>\n'
            '  <div class="chips" id="chips"></div>\n'
            '  <div class="big" id="bigBox"><div class="cap" id="bigCap">필요 CMS 설정값</div>'
            '    <div class="fig mono"><span id="bigFig">—</span><span class="unit">원</span></div>'
            '    <div class="note" id="bigNote"></div></div>\n'
            '  <div class="chain" id="chain"></div>\n'
            '  <div style="padding:14px 18px"><div class="bar" id="splitBar"></div>'
            '    <div class="legend" id="splitLegend"></div></div>\n'
            '</div></div></div>\n'
            '<script>\nvar M = ' + json.dumps(m, ensure_ascii=False) + ';\n' + CALC_JS + '\n</script>\n</div>')


CALC_JS = r"""
(function(){
"use strict";
var FLOOR = M.floor, TAX = M.tax, roundUnit = M.roundUnit, mode = "reverse", useMeas = false;
var GROUPS = M.groups, PARTS = M.parts, state = {};
GROUPS.forEach(function(g){
  if (g.mode === "multi") g.items.forEach(function(it){ state[it.id] = {on:!!it.on, pct:it.pct}; });
  else { var on = g.items.filter(function(i){return i.on})[0] || g.items[0];
         state[g.key] = {sel:on.id}; g.items.forEach(function(it){ state[it.id] = {pct:it.pct}; }); }
});
var q = function(i){ return document.getElementById(i) };
var won = function(n){ return Math.round(n).toLocaleString("ko-KR") };
var ceilTo = function(n,u){ return Math.ceil(n/u)*u };
var num = function(s){ return Number(String(s).replace(/[^\d.-]/g,"")) || 0 };

/* 실측 Σ 평균 */
var measSigma = null;
if (M.meas.length){
  var acc = M.meas.map(function(p){ return (1 - p.pre*TAX/p.cms)*100 });
  measSigma = acc.reduce(function(a,b){return a+b},0)/acc.length;
}
function theorySigma(){
  var t = 0;
  GROUPS.forEach(function(g){
    if (g.mode === "multi") g.items.forEach(function(it){ if (state[it.id].on) t += state[it.id].pct; });
    else { var id = state[g.key].sel; t += state[id] ? state[id].pct : 0; }
  });
  return Math.round(t*1000)/1000;
}
function sigma(){ return (useMeas && measSigma !== null) ? measSigma : theorySigma() }
function commission(){ return PARTS.reduce(function(a,p){ return a + (p.on ? (+p.pct||0) : 0) }, 0) }
function coef(){ return (1 - sigma()/100) * (1 - commission()/100) }

function renderPromos(){
  var root = q("promoGroups"); root.innerHTML = "";
  GROUPS.forEach(function(g){
    var wrap = document.createElement("div");
    wrap.className = "grp" + (g.mode === "locked" ? " locked" : "");
    var sum = 0;
    if (g.mode === "multi") g.items.forEach(function(it){ if (state[it.id].on) sum += state[it.id].pct; });
    else if (g.mode === "locked") sum = g.items[0].pct;
    else { var id = state[g.key].sel; sum = state[id] ? state[id].pct : 0; }
    var head = document.createElement("div");
    head.className = "grp-head";
    head.innerHTML = '<span class="grp-name"></span><span class="rule"></span><span class="grp-sum mono">+'+sum+'%</span>';
    head.querySelector(".grp-name").textContent = g.name || "";
    head.querySelector(".rule").textContent = g.rule || "";
    if (!sum) head.querySelector(".grp-sum").style.color = "var(--text-faint)";
    wrap.appendChild(head);
    var opts = document.createElement("div");
    opts.className = "opts" + (g.scroll ? " scroll-y" : "");
    g.items.forEach(function(it){
      var isMulti = g.mode === "multi";
      var on = g.mode === "locked" ? true : isMulti ? state[it.id].on : state[g.key].sel === it.id;
      var row = document.createElement("label");
      row.className = "opt" + (on && it.pct > 0 ? " on" : "") + (it.risk ? " risk" : "");
      var inp;
      if (g.mode === "locked"){ inp = document.createElement("span"); inp.className = "dot";
        inp.setAttribute("role","img"); inp.setAttribute("aria-label","항상 적용됨"); }
      else { inp = document.createElement("input"); inp.type = isMulti ? "checkbox" : "radio";
        if (!isMulti) inp.name = g.key; inp.checked = on;
        inp.addEventListener("change", function(){
          if (isMulti) state[it.id].on = inp.checked; else state[g.key].sel = it.id; recalc(); }); }
      var nm = document.createElement("span"); nm.className = "nm"; nm.textContent = it.nm;
      var tag = document.createElement("span"); tag.className = "id mono"; tag.textContent = it.tag || "";
      var pct = document.createElement("input");
      pct.type = "number"; pct.className = "pct mono"; pct.min = "0"; pct.max = "99"; pct.step = "1";
      pct.value = state[it.id].pct; pct.disabled = (it.pct === 0);
      if (g.mode === "locked"){ pct.disabled = false; pct.readOnly = true; }
      pct.setAttribute("aria-label", it.nm + " 할인율");
      pct.addEventListener("input", function(){
        state[it.id].pct = Math.max(0, Math.min(99, num(pct.value))); recalc(); });
      row.appendChild(inp); row.appendChild(nm); row.appendChild(tag); row.appendChild(pct);
      opts.appendChild(row);
    });
    wrap.appendChild(opts); root.appendChild(wrap);
  });
}

function renderComm(){
  var b = q("commBody"); b.innerHTML = "";
  PARTS.forEach(function(p){
    var row = document.createElement("div"); row.className = "crow";
    var lab = document.createElement("span"); lab.className = "lab";
    lab.textContent = p.name;
    if (p.note){ var sm = document.createElement("small"); sm.textContent = p.note; lab.appendChild(sm); }
    row.appendChild(lab);
    if (p.options){
      var sel = document.createElement("select");
      p.options.forEach(function(o){
        var v = (typeof o === "object") ? o.v : o, t = (typeof o === "object") ? o.label : (o + "%");
        var op = document.createElement("option"); op.value = v; op.textContent = t; sel.appendChild(op); });
      sel.value = String(p.pct);
      sel.onchange = function(){ p.pct = num(sel.value); recalc(); };
      row.appendChild(sel);
    } else if (p.range){
      var ck = document.createElement("input"); ck.type = "checkbox"; ck.checked = !!p.on;
      ck.style.cssText = "accent-color:var(--brass);width:16px;height:16px";
      var rg = document.createElement("input"); rg.type = "range";
      rg.min = p.range[0]; rg.max = p.range[1]; rg.step = p.range[2] || 1; rg.value = p.pct;
      rg.disabled = !p.on;
      ck.onchange = function(){ p.on = ck.checked; recalc(); };
      rg.oninput = function(){ p.pct = num(rg.value); recalc(); };
      row.appendChild(ck); row.appendChild(rg);
    }
    var val = document.createElement("span"); val.className = "val mono";
    val.textContent = p.on ? ((+p.pct) + "%") : "—";
    row.appendChild(val); b.appendChild(row);
  });
  if (!PARTS.length) b.innerHTML = '<p class="rule">commission.parts 가 비어 있다.</p>';
}

function renderMeas(){
  var card = q("measCard");
  if (!M.meas.length){ card.hidden = true; return; }
  var t = theorySigma(), b = q("measBody");
  var rows = M.meas.map(function(p){
    var real = Math.round(p.pre * TAX), calc = Math.round(p.cms * (1 - t/100)), gap = real - calc;
    return '<tr><td>'+p.d+'</td><td class="num mono">'+won(p.cms)+'</td>'+
      '<td class="num mono">'+won(calc)+'</td><td class="num mono">'+won(real)+'</td>'+
      '<td class="num mono" style="color:'+(Math.abs(gap) > real*0.005 ? "var(--warn)" : "var(--text-dim)")+'">'+
      (gap >= 0 ? "+" : "") + won(gap)+'</td></tr>';
  }).join("");
  b.innerHTML =
    '<label style="display:flex;gap:10px;align-items:flex-start;cursor:pointer;margin-bottom:14px">'+
    '<input type="checkbox" id="measOn"'+(useMeas?" checked":"")+' style="margin-top:3px">'+
    '<span>Σ를 <b>실측 '+measSigma.toFixed(2)+'%</b>로 고정<em style="display:block;font-style:normal;'+
    'font-size:11px;color:var(--text-faint);margin-top:3px">'+
    '켜면 위에서 고른 프로모션 대신 실제로 관측된 할인율을 씁니다</em></span></label>'+
    '<div class="scroll"><table><thead><tr><th>날짜</th><th class="num">CMS</th>'+
    '<th class="num">이론 Σ'+t+'%</th><th class="num">실측</th><th class="num">차이</th></tr></thead>'+
    '<tbody>'+rows+'</tbody></table></div>'+
    (M.measNotes.length ? '<p style="font-size:11.5px;color:var(--text-faint);line-height:1.65;margin:12px 0 0">'
      + M.measNotes.join("<br>") + '</p>' : '');
  q("measOn").onchange = function(e){ useMeas = e.target.checked; recalc(); };
  q("measTally").textContent = useMeas ? ("Σ "+measSigma.toFixed(2)+"% 적용 중") : ("Σ "+measSigma.toFixed(2)+"%");
}

function renderTable(){
  var card = q("weekCard");
  if (!M.weekly.length){ card.hidden = true; return; }
  var k = coef(), t = q("dayTable");
  q("tableTally").textContent = k > 0 ? "입금계수 " + k.toFixed(4) : "";
  t.querySelector("thead").innerHTML =
    '<tr><th>요일</th><th>요금세트</th><th class="num">현재 CMS</th><th class="num">지금 입금가</th>'+
    '<th class="num">목표</th><th class="num">목표용 CMS</th><th class="num">차이</th><th>판정</th></tr>';
  var tb = t.querySelector("tbody"); tb.innerHTML = "";
  if (k <= 0) return;
  M.weekly.forEach(function(r){
    var po = r.cms * k, need = r.tgt ? ceilTo(r.tgt/k, roundUnit) : null;
    var diff = need === null ? null : need - r.cms;
    var cls = (FLOOR && po < FLOOR) ? "bad" : (FLOOR && po < FLOOR*1.05 ? "warn" : "ok");
    var lab = (FLOOR && po < FLOOR) ? "하한 미달" : (FLOOR && po < FLOOR*1.05 ? "턱걸이" : "OK");
    tb.innerHTML += '<tr><td>'+r.d+'</td><td class="num">'+(r.set||"")+'</td>'+
      '<td class="num mono">'+won(r.cms)+'</td><td class="num mono">'+won(po)+'</td>'+
      '<td class="num mono">'+(r.tgt?won(r.tgt):"—")+'</td>'+
      '<td class="num mono"><b>'+(need===null?"—":won(need))+'</b></td>'+
      '<td class="num mono">'+(diff===null?"—":(diff===0?"—":(diff>0?"+":"")+won(diff)))+'</td>'+
      '<td><span class="pill '+cls+'">'+lab+'</span></td></tr>';
  });
}

function renderChips(){
  var c = q("chips"); c.innerHTML = "";
  var list = mode === "reverse"
    ? M.targets.map(function(t){ return [t.label + " " + t.v.toLocaleString("ko-KR"), t.v] })
    : M.cmsPresets.map(function(v){ return [won(v), v] });
  list.forEach(function(pair){
    var b = document.createElement("button"); b.textContent = pair[0];
    b.onclick = function(){ q("tgt").value = pair[1].toLocaleString("ko-KR"); recalc(); };
    c.appendChild(b);
  });
  var r = document.createElement("button");
  r.textContent = "올림 " + roundUnit.toLocaleString("ko-KR") + "원";
  r.style.marginLeft = "auto"; r.style.borderColor = "var(--brass)"; r.style.color = "var(--brass)";
  r.onclick = function(){ roundUnit = roundUnit === 5000 ? 1000 : roundUnit === 1000 ? 100 : 5000;
                          renderChips(); recalc(); };
  c.appendChild(r);
}

function recalc(){
  var s = sigma(), cm = commission(), k = coef();
  q("sigTally").textContent = "Σ " + theorySigma() + "%" + (useMeas ? " · 미사용" : "");
  q("commTally").textContent = (cm % 1 ? cm.toFixed(1) : cm) + "%";
  renderPromos(); renderComm();
  var box = q("bigBox"), fig = q("bigFig"), note = q("bigNote"), chain = q("chain");
  var input = num(q("tgt").value), cms, payout, cls, noteTxt;

  if (k <= 0){
    box.className = "big bad"; fig.textContent = "계산 불가";
    note.textContent = "Σ와 보수의 합이 100%를 넘습니다.";
    chain.innerHTML = ""; q("splitBar").innerHTML = ""; q("splitLegend").innerHTML = "";
    renderTable(); renderMeas(); return;
  }
  if (mode === "reverse"){
    cms = ceilTo(input/k, roundUnit); payout = cms*k;
    fig.textContent = won(cms);
    noteTxt = roundUnit.toLocaleString("ko-KR")+"원 올림 · 실제 입금 "+won(payout)+"원 (목표 +"+won(payout-input)+")";
    cls = (FLOOR && input < FLOOR) ? "warn" : "ok";
    if (FLOOR && input < FLOOR) noteTxt = "목표가 하한 "+won(FLOOR)+"원보다 낮습니다 · " + noteTxt;
  } else {
    cms = input; payout = cms*k; fig.textContent = won(payout);
    cls = !FLOOR ? "ok" : payout < FLOOR ? "bad" : payout < FLOOR*1.05 ? "warn" : "ok";
    noteTxt = !FLOOR ? "" : payout < FLOOR
      ? "하한 "+won(FLOOR)+"원에서 "+won(FLOOR-payout)+"원 부족 · CMS "+won(ceilTo(FLOOR/k,roundUnit))+"원 필요"
      : "하한 "+won(FLOOR)+"원 대비 "+won(payout-FLOOR)+"원 여유";
  }
  box.className = "big " + cls; note.textContent = noteTxt;

  var pay = cms * (1 - s/100);
  chain.innerHTML = "";
  [["CMS 설정값","채널 매니저에 넣는 금액",won(cms),true],
   ["프로모션 −"+s+"%","카테고리 규칙대로 합산","−"+won(cms-pay),false],
   ["고객 결제","아고다 '기준 판매 요금'",won(pay),false],
   ["아고다 표시가","고객 결제 ÷ "+TAX,won(pay/TAX),false],
   ["아고다 보수 −"+cm+"%",PARTS.map(function(p){return p.name}).join(" + "),"−"+won(pay-payout),false],
   ["입금가","실제로 들어오는 돈",won(payout),true]
  ].forEach(function(a){
    var dv = document.createElement("div"); dv.className = "step" + (a[3] ? " hi" : "");
    dv.innerHTML = '<span class="k"><em></em></span><span class="v mono"></span>';
    dv.querySelector(".k").prepend(a[0]); dv.querySelector("em").textContent = a[1];
    dv.querySelector(".v").textContent = a[2] + "원"; chain.appendChild(dv);
  });
  var kd = document.createElement("div"); kd.className = "step";
  kd.innerHTML = '<span class="k">입금계수</span><span class="v mono">'+k.toFixed(4)+'</span>';
  chain.appendChild(kd);

  var pPromo = s, pComm = (100-s)*cm/100, pNet = 100 - pPromo - pComm;
  var bar = q("splitBar"); bar.innerHTML = "";
  [[pNet,"var(--ok)","입금 "+pNet.toFixed(1)+"%"],
   [pComm,"var(--brass)","보수 "+pComm.toFixed(1)+"%"],
   [pPromo,"var(--text-dim)","할인 "+pPromo.toFixed(0)+"%"]].forEach(function(a){
    if (a[0] <= 0) return;
    var el = document.createElement("div"); el.className = "seg";
    el.style.flex = a[0]; el.style.background = a[1];
    el.textContent = a[0] >= 11 ? a[2] : ""; el.title = a[2]; bar.appendChild(el);
  });
  q("splitLegend").innerHTML =
    '<span><i style="background:var(--ok)"></i>우리 입금 '+pNet.toFixed(1)+'%</span>'+
    '<span><i style="background:var(--brass)"></i>아고다 보수 '+pComm.toFixed(1)+'%</span>'+
    '<span><i style="background:var(--text-dim)"></i>손님 할인 '+pPromo.toFixed(0)+'%</span>';
  renderTable(); renderMeas();
}

function setMode(m){
  mode = m;
  q("mRev").setAttribute("aria-pressed", String(m === "reverse"));
  q("mFwd").setAttribute("aria-pressed", String(m === "forward"));
  q("tgtLabel").textContent = m === "reverse" ? "목표 입금가" : "CMS 설정값";
  q("bigCap").textContent = m === "reverse" ? "필요 CMS 설정값" : "예상 입금가";
  var dflt = m === "reverse" ? (M.targets[0] ? M.targets[0].v : (FLOOR || 0))
                             : (M.cmsPresets[0] || 0);
  q("tgt").value = dflt ? dflt.toLocaleString("ko-KR") : "";
  renderChips(); recalc();
}
q("mRev").onclick = function(){ setMode("reverse") };
q("mFwd").onclick = function(){ setMode("forward") };
q("tgt").addEventListener("input", function(e){
  var v = num(e.target.value), pos = e.target.selectionStart, before = e.target.value.length;
  e.target.value = v ? v.toLocaleString("ko-KR") : "";
  var after = e.target.value.length;
  try { e.target.setSelectionRange(pos+(after-before), pos+(after-before)); } catch(_){}
  recalc();
});
setMode("reverse");
})();
"""


def sec_rates(d):
    out = ['<div class="wrap"><h2>요금표</h2>']
    rooms = d.get("rooms") or []
    if rooms:
        plans = []
        for r in rooms:
            for p in (r.get("plans") or {}):
                if p not in plans:
                    plans.append(p)
        head = "".join(f'<th class="num">{esc(p)}</th>' for p in plans)
        body = "".join(
            f'<tr><td>{esc(r.get("name"))}</td>'
            + "".join(f'<td class="num">{won((r.get("plans") or {}).get(p))}</td>' for p in plans)
            + "</tr>" for r in rooms)
        out.append(f'<p class="sub">아고다가 보유한 객실 × 요금제 기준요금.</p>'
                   f'<div class="card"><div class="scroll"><table><thead><tr>'
                   f'<th>객실</th>{head}</tr></thead><tbody>{body}</tbody></table></div></div>')

    ch = d.get("channels") or []
    if ch:
        sets = []
        for c in ch:
            for k in (c.get("cms") or {}):
                if k not in sets:
                    sets.append(k)
        base = next((c for c in ch if c.get("key") == "agoda"), ch[-1])
        bv = (base.get("cms") or {}).get(sets[0]) if sets else None
        head = "".join(f'<th class="num">{esc(s)}</th>' for s in sets)
        rows = []
        first = sets[0] if sets else None
        for c in sorted(ch, key=lambda x: (x.get("cms") or {}).get(first) or 0):
            v = (c.get("cms") or {}).get(first)
            ratio = f"{round(v/bv*100)}%" if (v and bv) else "—"
            col = "var(--bad)" if (v and bv and v/bv < .6) else (
                  "var(--warn)" if (v and bv and v/bv < .85) else "var(--ok)")
            st = c.get("status")
            bdg = f'<span class="badge {"good" if st=="live" else "planned"}">{esc("검증됨" if st=="live" else "예정")}</span>' if st else ""
            rows.append(f'<tr><td>{esc(c.get("name"))}{bdg}</td>'
                        + "".join(f'<td class="num">{won((c.get("cms") or {}).get(s))}</td>' for s in sets)
                        + f'<td class="num" style="color:{col}">{ratio}</td></tr>')
        out.append(f'<h2>채널별 CMS</h2><p class="sub">같은 객실을 채널마다 얼마에 보내고 있나. '
                   f'커미션 구조가 달라 차이는 정상이지만, 폭은 알고 있어야 한다.</p>'
                   f'<div class="card"><div class="scroll"><table><thead><tr><th>채널</th>{head}'
                   f'<th class="num">{esc(base.get("name"))} 대비</th></tr></thead>'
                   f'<tbody>{"".join(rows)}</tbody></table></div></div>')
    out.append("</div>")
    return "".join(out) if (rooms or ch) else None


def sec_measure(d):
    ms = d.get("measurements") or []
    if not ms:
        return None
    tax = (d.get("tax") or {}).get("multiplier") or 1.1
    rows = []
    sigs = []
    for m in ms:
        cms, disp = m.get("cms"), m.get("displayedPreTax")
        sig = (1 - disp * tax / cms) * 100 if (cms and disp) else None
        if sig is not None:
            sigs.append(sig)
        rows.append(f'<tr><td>{esc(m.get("date"))}</td><td class="num">{won(cms)}</td>'
                    f'<td class="num">{won(disp)}</td>'
                    f'<td class="num">{won(disp*tax) if disp else "—"}</td>'
                    f'<td class="num">{f"{sig:.3f}%" if sig is not None else "—"}</td></tr>')
    verdict = ""
    if len(sigs) >= 2:
        spread = max(sigs) - min(sigs)
        cls, msg = (("ok", f"세 점의 Σ가 {spread:.3f}%p 안에서 일치한다 — 노출가는 CMS에 정확히 비례한다. 공식이 맞다.")
                    if spread < 0.5 else
                    ("warn", f"Σ가 {spread:.3f}%p 흩어진다. 요금제별 세금 처리가 다르거나 날짜별 프로모션이 다른 것이다."))
        verdict = f'<div class="call {cls}"><span class="lbl">선형성 판정</span>{msg}</div>'
    return (f'<div class="wrap"><h2>노출가 실측</h2>'
            f'<p class="sub">CMS가 다른 날짜 여러 개에서 Σ를 재서 공식이 맞는지 확인한 기록. '
            f'세금배수 {tax}.</p>'
            f'<div class="card"><div class="scroll"><table><thead><tr><th>날짜</th>'
            f'<th class="num">CMS</th><th class="num">노출가(세전)</th>'
            f'<th class="num">세금포함</th><th class="num">실측 Σ</th></tr></thead>'
            f'<tbody>{"".join(rows)}</tbody></table></div></div>{verdict}</div>')


def sec_status(d):
    out = ['<div class="wrap">']
    p = d.get("property") or {}
    c = d.get("commission") or {}
    prom = d.get("promotions") or {}
    tiles = []
    if c.get("total") is not None:
        tiles.append(("보수", f'{c["total"]}%', esc(c.get("source", "")) or ("확인됨" if c.get("verified") else "미확인")))
    if prom.get("worstCaseSigma") is not None:
        tiles.append(("최악값 Σ", f'{prom["worstCaseSigma"]}%', "모든 조건을 충족하는 손님 기준"))
    if prom.get("activeCount") is not None:
        tiles.append(("적용 중 프로모션", str(prom["activeCount"]),
                      f'중지 {prom.get("inactiveCount","—")}건'))
    if p.get("floor") is not None:
        tiles.append(("입금가 하한", won(p["floor"]), esc(p.get("floorNote", ""))))
    if tiles:
        out.append('<h2>현재 설정</h2><div class="tiles">' + "".join(
            f'<div class="tile"><div class="k">{esc(k)}</div><div class="v">{esc(v)}</div>'
            f'<div class="n">{n}</div></div>' for k, v, n in tiles) + "</div>")

    if c.get("parts"):
        out.append('<h3>보수 구성</h3><div class="card"><div class="scroll"><table>'
                   '<thead><tr><th>항목</th><th class="num">%</th></tr></thead><tbody>'
                   + "".join(f'<tr><td>{esc(x.get("name"))}</td><td class="num">{dash(x.get("pct"))}</td></tr>'
                             for x in c["parts"])
                   + f'<tr><td><b>포털 설정 합계</b></td><td class="num"><b>'
                     f'{parts_sum(c["parts"])}</b></td></tr>'
                   + (f'<tr><td>정산으로 확인된 보수</td><td class="num">{c["total"]}</td></tr>'
                      if c.get("settingTotal") and c.get("total") != c.get("settingTotal") else "")
                   + '</tbody></table></div></div>'
                   + (f'<p class="sub">{esc(c["note"])}</p>' if c.get("note") else ""))

    pr = d.get("programs") or []
    if pr:
        out.append('<h2>프로그램</h2><p class="sub">설정 가능 범위와 현재 설정은 다른 값이다. '
                   '섞으면 뭘 바꿀 수 있는지 알 수 없게 된다.</p>'
                   '<div class="card"><div class="scroll"><table><thead><tr><th>프로그램</th>'
                   '<th>상태</th><th>설정 가능 범위</th><th>현재 설정</th><th>비고</th></tr></thead><tbody>'
                   + "".join(
                       f'<tr><td>{esc(x.get("name"))}'
                       + ('' if x.get("verified", True) else '<span class="badge med">미확인</span>')
                       + f'</td><td>{esc(x.get("status"))}</td>'
                       f'<td class="mono">{dash(x.get("range"))}</td>'
                       f'<td class="mono"><b>{dash(x.get("setting"))}</b></td>'
                       f'<td style="white-space:normal;max-width:34ch">{esc(x.get("note",""))}</td></tr>'
                       for x in pr) + '</tbody></table></div></div>')

    if prom.get("active"):
        out.append('<h2>적용 중 프로모션</h2>'
                   '<div class="card"><div class="scroll"><table><thead><tr><th>프로모션</th>'
                   '<th>종류</th><th class="num">할인</th><th>기간</th></tr></thead><tbody>'
                   + "".join(f'<tr><td>{esc(x.get("name"))}</td><td>{esc(x.get("kind"))}</td>'
                             f'<td class="num">{x.get("pct")}%</td><td>{esc(x.get("window",""))}</td></tr>'
                             for x in prom["active"]) + '</tbody></table></div></div>')

    ct = d.get("content") or {}
    ph, rv, mp = ct.get("photos"), ct.get("reviews"), ct.get("mapping")
    cont = []
    if ph:
        cont.append(("사진", dash(ph.get("total"), "장"),
                     f'저해상도 {dash(ph.get("lowRes"))} · 태그누락 {dash(ph.get("untagged"))}'))
    if rv:
        det = rv.get("detail") or {}
        low = min(det, key=det.get) if det else None
        cont.append(("리뷰", dash(rv.get("score")),
                     f'{dash(rv.get("count"))}건' + (f' · 최저 {low} {det[low]}' if low else "")))
    if mp:
        tot = mp.get("total")
        cont.append(("객실 매핑",
                     f'{dash(mp.get("mapped"))}/{dash(tot)}' if tot is not None else dash(mp.get("mapped")),
                     f'미매핑 {dash(mp.get("unmapped"))}'))
    if cont:
        out.append('<h2>콘텐츠</h2><div class="tiles">' + "".join(
            f'<div class="tile"><div class="k">{esc(k)}</div><div class="v">{esc(v)}</div>'
            f'<div class="n">{esc(n)}</div></div>' for k, v, n in cont) + "</div>")

    if rv and (rv.get("detail") or {}):
        det = rv["detail"]
        lo = min(det, key=det.get)
        out.append('<h3>리뷰 세부</h3><div class="card"><div class="scroll"><table>'
                   '<thead><tr><th>항목</th><th class="num">점수</th></tr></thead><tbody>'
                   + "".join('<tr><td>' + esc(k)
                             + ('<span class="badge med">최저</span>' if k == lo else '')
                             + '</td><td class="num">' + esc(v) + '</td></tr>'
                             for k, v in sorted(det.items(), key=lambda x: -x[1]))
                   + '</tbody></table></div></div>')

    rp = d.get("ratePlans") or []
    if rp:
        out.append('<h2>요금제</h2><div class="card"><div class="scroll"><table><thead><tr>'
                   '<th>요금제</th><th>ID</th><th>객실 종류</th><th>상태</th></tr></thead><tbody>'
                   + "".join(f'<tr><td>{esc(x.get("name"))}</td><td class="mono">{dash(x.get("id"))}</td>'
                             f'<td>{dash(x.get("rooms"))}</td>'
                             f'<td><span class="pill {"ok" if x.get("status")=="적용 중" else "info"}">'
                             f'{dash(x.get("status"))}</span></td></tr>' for x in rp)
                   + '</tbody></table></div></div>')

    fs = d.get("findings") or []
    if fs:
        rank = {"high": 0, "med": 1, "info": 2}
        out.append("<h2>발견 사항</h2>")
        for f in sorted(fs, key=lambda x: rank.get(x.get("severity"), 9)):
            sev = f.get("severity", "info")
            cls = {"high": "bad", "med": "warn"}.get(sev, "")
            lbl = {"high": "높음", "med": "보통"}.get(sev, "참고")
            rev = (f'<br><br><b>정정:</b> {esc(f["revised"])}' if f.get("revised") else "")
            ev = (f'<br><br><span style="color:var(--text-faint);font-size:12.5px">근거 · {esc(f.get("evidence"))}</span>'
                  if f.get("evidence") else "")
            out.append(f'<div class="call {cls}"><span class="lbl">{esc(f.get("title"))}'
                       f'<span class="badge {sev}">{lbl}</span></span>{esc(f.get("detail",""))}{rev}{ev}</div>')

    op = d.get("open") or []
    if op:
        out.append("<h2>아직 확인 못 한 것</h2><ul class='plain'>"
                   + "".join(f"<li>{esc(x)}</li>" for x in op) + "</ul>")

    out.append(f'<div class="foot">{esc(p.get("name",""))} · 아고다 ID {esc(p.get("agodaId",""))} · '
               f'조사일 {esc(p.get("surveyedAt",""))} · 값이 바뀌면 포털에서 다시 읽어라</div></div>')
    return "".join(out)


PAGES = [("status", "현재 설정", sec_status), ("calc", "계산기", sec_calc),
         ("rates", "요금표", sec_rates), ("measured", "실측 기록", sec_measure)]


def build(d):
    made = [(k, lbl, fn(d)) for k, lbl, fn in PAGES]
    made = [(k, lbl, h) for k, lbl, h in made if h]
    if not made:
        sys.exit("렌더링할 내용이 없다. property.json 을 확인해라.")
    first = made[0][0]
    nav = "".join(f'<button class="pgtab" data-pg="{k}" '
                  f'aria-pressed="{str(k==first).lower()}">{esc(lbl)}</button>' for k, lbl, _ in made)
    body = "".join(f'<div class="page" id="pg-{k}"{"" if k==first else " hidden"}>{h}</div>'
                   for k, _, h in made)
    p = d.get("property") or {}
    title = f'{p.get("name","숙소")} OTA 콘솔'
    return title, f"""<title>{esc(title)}</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:wght@400;500;600&family=IBM+Plex+Sans+KR:wght@400;500;600;700&display=swap">
<style>{CSS}</style>
<div class="topbar"><div class="topbar-in">
  <span class="brand">{esc(p.get("name","숙소"))}<em>아고다 ID {esc(p.get("agodaId",""))}</em></span>
  <nav class="nav">{nav}</nav>
</div></div>
{body}
<script>
(function(){{
  var tabs=[].slice.call(document.querySelectorAll('.pgtab'));
  function show(k,push){{
    if(!document.getElementById('pg-'+k)) k='{first}';
    tabs.forEach(function(t){{t.setAttribute('aria-pressed',String(t.dataset.pg===k))}});
    document.querySelectorAll('.page').forEach(function(p){{p.hidden = p.id!=='pg-'+k}});
    window.scrollTo(0,0);
    if(push) history.replaceState(null,'','#'+k);
  }}
  tabs.forEach(function(t){{t.onclick=function(){{show(t.dataset.pg,true)}}}});
  show((location.hash||'#{first}').slice(1),false);
}})();
</script>
"""


def check(d):
    errs, warns = [], []
    if not (d.get("property") or {}).get("agodaId"):
        errs.append("property.agodaId 가 비어 있다")
    c = d.get("commission") or {}
    if c.get("total") is None:
        warns.append("보수(commission.total)가 없다 — parts 도 없으면 계산기의 보수가 0%로 열린다. 정산에서 확인해 채워라")
    elif not c.get("verified"):
        warns.append("보수가 verified:false 다 — open 에 확인 방법을 적었는지 봐라")
    if c.get("parts") and c.get("total") is not None:
        s = parts_sum(c["parts"])
        ref = c.get("settingTotal", c["total"])
        if abs(s - ref) > 0.01:
            errs.append(f"보수 구성 합계 {s} ≠ {'settingTotal' if c.get('settingTotal') else 'total'} {ref}")
        if c.get("settingTotal") and abs(c["settingTotal"] - c["total"]) > 0.01 and not c.get("note"):
            warns.append(f"포털 설정 {c['settingTotal']}% 와 확인된 보수 {c['total']}% 가 다른데 note 가 없다")
    prom = d.get("promotions") or {}
    bd = prom.get("sigmaBreakdown") or []
    if bd and prom.get("worstCaseSigma") is not None:
        s = sum(b.get("pct", 0) for b in bd)
        if abs(s - prom["worstCaseSigma"]) > 0.01:
            errs.append(f"sigmaBreakdown 합계 {s} ≠ worstCaseSigma {prom['worstCaseSigma']}")
    p = d.get("property") or {}
    if prom.get("worstCaseSigma") is not None and c.get("total") is not None and p.get("floor"):
        k = (1 - prom["worstCaseSigma"] / 100) * (1 - c["total"] / 100)
        need = p["floor"] / k if k > 0 else float("inf")
        warns.append(f"최악값 Σ에서 하한 {p['floor']:,}원을 지키려면 CMS ≥ {round(need):,}원")
        for r in (d.get("weekly") or []):
            if isinstance(r.get("cms"), (int, float)) and r["cms"] * k < p["floor"]:
                warns.append(f"{r.get('d', '')} {r.get('set', '')} CMS {r['cms']:,}원은 최악값 Σ에서 "
                             f"입금가 {round(r['cms'] * k):,}원 — 하한 미달")
    tax = (d.get("tax") or {}).get("multiplier") or 1.1
    sigs = [(1 - m["displayedPreTax"] * tax / m["cms"]) * 100
            for m in (d.get("measurements") or []) if m.get("cms") and m.get("displayedPreTax")]
    if len(sigs) >= 2 and max(sigs) - min(sigs) > 0.5:
        warns.append(f"실측 Σ가 {max(sigs)-min(sigs):.2f}%p 흩어진다 — 요금제별 세금 처리를 의심해라")
    if not (d.get("findings") or []):
        warns.append("findings 가 비어 있다 — 조사 결론이 없는 콘솔이 된다")

    # ── verified:false 전수 스캔 ────────────────────────────────
    # commission 뿐 아니라 verified 플래그가 붙은 모든 노드를 훑는다.
    # 미확인 항목은 findings 또는 open 중 한 곳에는 반드시 흔적이 있어야 한다.
    blob = json.dumps(d, ensure_ascii=False)
    trail = json.dumps((d.get("findings") or []) + (d.get("open") or []), ensure_ascii=False)
    unver = []

    def walk(node, path):
        if isinstance(node, dict):
            if node.get("verified") is False:
                unver.append((path, node.get("name") or node.get("key") or path, node.get("key")))
            for k, v in node.items():
                walk(v, f"{path}.{k}" if path else k)
        elif isinstance(node, list):
            for i, v in enumerate(node):
                walk(v, f"{path}[{i}]")

    walk(d, "")
    for path, name, key in unver:
        # 이름 전체가 아니라 키워드 단위로 본다. "AGX 아고다 성장 익스프레스" 를
        # open 에 "AGX 설정 가능 범위…" 로 적어도 통과해야 한다.
        # 이름 전체가 아니라 앞머리 고유어 + key 로 본다. 흔한 낱말("아고다","프로그램")로
        # 우연히 통과하는 걸 막는다.
        head = str(name).split()[0] if str(name).split() else ""
        hit = (key and key.lower() in trail.lower()) or (len(head) >= 2 and head in trail)
        if path == "tax" and "세금" in trail:
            hit = True
        if not hit:
            warns.append(f"{path} ({name}) 가 verified:false 인데 findings/open 어디에도 없다")
    if unver:
        warns.append(f"미확인(verified:false) 항목 {len(unver)}건 — 프로그램 항목은 표에 '미확인' 배지가 붙는다")

    # ── 필수 측정 영역 누락 ─────────────────────────────────────
    for key, label in [("rooms", "객실별 요금"), ("measurements", "노출가 실측"),
                       ("programs", "프로그램"), ("content", "콘텐츠(사진·리뷰·매핑)")]:
        if not d.get(key):
            warns.append(f"{label}({key}) 가 비어 있다 — 해당 섹션이 콘솔에서 빠진다")

    # ── 노출가 실측이 공식과 맞는지 ─────────────────────────────
    for m in (d.get("measurements") or []):
        if m.get("cms") and m.get("displayedPreTax"):
            sig = (1 - m["displayedPreTax"] * tax / m["cms"]) * 100
            if not (0 <= sig < 100):
                errs.append(f"{m.get('date')} 실측 Σ {sig:.1f}% — 범위를 벗어났다. CMS나 노출가가 틀렸다")
    return errs, warns


def main():
    ap = argparse.ArgumentParser(description="property.json → HTML 콘솔")
    ap.add_argument("json")
    ap.add_argument("-o", "--out", default="콘솔.html")
    ap.add_argument("--check", action="store_true", help="생성 후 자체 점검")
    ap.add_argument("--artifact", action="store_true", help="claude.ai Artifact용 조각도 함께 생성")
    a = ap.parse_args()

    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, ValueError) as err:
            print(f"[경고] 출력 인코딩을 UTF-8로 바꾸지 못했다: {err}", file=sys.stderr)

    try:
        d = json.loads(pathlib.Path(a.json).read_text(encoding="utf-8-sig"))
    except FileNotFoundError:
        sys.exit(f"입력 파일이 없다: {a.json}")
    except json.JSONDecodeError as err:
        sys.exit(f"property.json 형식 오류 — {err.lineno}행 {err.colno}열: {err.msg}")
    if not isinstance(d, dict):
        sys.exit("property.json 최상위는 객체({ })여야 한다.")
    d.pop("_note", None)
    title, frag = build(d)

    doc = ('<!doctype html>\n<html lang="ko">\n<head>\n<meta charset="utf-8">\n'
           '<meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover">\n'
           '<meta name="robots" content="noindex, nofollow">\n'
           + frag[:frag.index("<div class=\"topbar\">")]
           + "</head>\n<body>\n" + frag[frag.index("<div class=\"topbar\">"):] + "\n</body>\n</html>\n")
    out = pathlib.Path(a.out)
    out.write_text(doc, encoding="utf-8")
    print(f"{out}  {len(doc):,} chars")

    if a.artifact:
        ap2 = out.with_name(out.stem + "-artifact.html")
        ap2.write_text(frag, encoding="utf-8")
        print(f"{ap2}  {len(frag):,} chars  (Artifact용)")

    if a.check:
        errs, warns = check(d)
        print("\n── 점검 ──")
        for e in errs:
            print(f"  ✗ {e}")
        for w in warns:
            print(f"  · {w}")
        if not errs and not warns:
            print("  이상 없음")
        if errs:
            sys.exit(1)


if __name__ == "__main__":
    main()
