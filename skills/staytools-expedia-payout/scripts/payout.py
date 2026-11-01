#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""익스피디아 입금가 계산기.

    세전 정가   = 달력 ÷ T                (패키지 경로면 달력 × p ÷ T)
    할인 후 세전 = 세전 정가 × (1 − d)
    손님 결제   = 할인 후 세전 × T
    입금 계수 k = T × (1 − c) − a
    입금가     = 할인 후 세전 × k

할인은 덧셈이다. 일반 23% + 회원 10% = 33%. 곱하지 마라.
c 는 세금 포함 결제 총액 기준, a 는 할인 후 세전 기준이다. 그냥 더하면 틀린다.

c·a·p·하한·목표는 숙소마다 다르다. 기본값이 없으니 그 숙소의 예약 결제 내역에서 확인한 값을 넣어라.
아래 숫자는 형식 예시다.

사용 예
    payout.py forward --rate 165000 --discount 20 10 --c 15 --a 5 --floor 90000
    payout.py forward --rate 165000 --discount 30 --c 15 --a 5 --p 0.9       # 패키지 경로
    payout.py reverse --target 92925 --discount 30 --c 15 --a 5
    payout.py check   --rate 165000 --discount 30 --add 3 7 --c 15 --a 5 --floor 90000
    payout.py table   --c 15 --a 5 --targets 82000 90000
    payout.py coef    --c 15 --rates 0 1 5 7
    payout.py booking --after 105000 --paid 115500 --comp 17325 --accel 5250 --payout 92925
    payout.py leadmap --property property.json
"""
import argparse
import json
import math
import pathlib
import sys


def require_rates(t, c, a, p=1.0):
    if not math.isfinite(t) or t < 1:
        raise ValueError("세금 배수 T 는 1 이상이어야 한다.")
    if not (0 <= c < 100) or not (0 <= a < 100):
        raise ValueError("c 와 a 는 0 이상 100% 미만이어야 한다.")
    if not math.isfinite(p) or p <= 0:
        raise ValueError("패키지 배수 p 는 양수여야 한다.")


def coef(t, c, a):
    """세전 기준 입금 계수 k."""
    return t * (1 - c / 100) - a / 100


def forward(rate, discount, t, c, a, p=1.0):
    require_rates(t, c, a, p)
    if not math.isfinite(rate) or rate < 0:
        raise ValueError("달력요금은 0 이상의 숫자여야 한다.")
    if not (0 <= discount < 100):
        raise ValueError("할인 합계는 0 이상 100% 미만이어야 한다.")
    k = coef(t, c, a)
    if k <= 0:
        raise ValueError("입금 계수가 0 이하다. c 와 a 를 확인해라.")
    list_pretax = rate * p / t
    after = list_pretax * (1 - discount / 100)
    paid = after * t
    return {"rate": rate, "discount": discount, "p": p, "k": k, "list_pretax": list_pretax, "after": after,
            "paid": paid, "comp": paid * c / 100, "accel": after * a / 100, "payout": after * k,
            "effective": (1 - p * (1 - discount / 100)) * 100}


def reverse(target, discount, t, c, a, p=1.0):
    require_rates(t, c, a, p)
    if not math.isfinite(target) or target < 0:
        raise ValueError("목표 입금가는 0 이상의 숫자여야 한다.")
    if not (0 <= discount < 100):
        raise ValueError("할인 합계는 0 이상 100% 미만이어야 한다.")
    k = coef(t, c, a)
    if k <= 0:
        raise ValueError("입금 계수가 0 이하다. c 와 a 를 확인해라.")
    return target * t / (k * (1 - discount / 100) * p)


def up100(x):
    """목표를 지켜야 하는 달력은 100원 단위로 올림한다. 부동소수점 오차로 한 단위 뛰지 않게 먼저 다듬는다."""
    return math.ceil(round(x, 6) / 100) * 100


def promo_applies(promo, lead):
    if promo.get("status", "적용") != "적용":
        return False
    if promo.get("cond") == "sameDay":
        return lead == 0
    return lead >= int(promo.get("minDays", 0))


def tier1(promos, lead, pos, package=False):
    """그 리드타임에 걸리는 1층 최댓값. pos=True 면 자국 POS, False 면 그 외 POS.
    자국 POS 전용 프로모션은 그 외 손님에게 걸리지 않는다.
    package 전용 프로모션은 패키지 경로에서만, mobile 전용은 기기를 알 수 없어 계산에서 뺀다."""
    best = None
    for promo in promos:
        scope = promo.get("scope")
        if scope in ("member", "mobile") or (scope == "package" and not package):
            continue
        if scope == "pos" and not pos:
            continue
        if promo_applies(promo, lead) and (best is None or promo["pct"] > best["pct"]):
            best = promo
    return best


def member_add(promos):
    """프로모션과 묶이지 않은 별도 회원 가산(2층). 없으면 0."""
    vals = [m["pct"] for m in promos if m.get("scope") == "member" and m.get("status", "적용") == "적용"]
    return max(vals) if vals else 0


def discount_for(promo, member, extra):
    """1층 + 2층. 화면에 프로모션별 회원 합계(memberPct)가 있으면 그 값이 정답이다.
    2층은 같은 층이므로 별도 회원 프로모션을 더 얹지 않는다. 패키지 전용에는 회원 가산을 붙이지 않는다."""
    base = promo["pct"] if promo else 0
    if not member or (promo and promo.get("scope") == "package"):
        return base
    if promo and "memberPct" in promo:
        return promo["memberPct"]
    return base + extra


def lead_segments(promos):
    """D-0부터 가장 긴 조건까지 펼쳐 같은 조합끼리 구간으로 묶는다."""
    longest = max([int(m.get("minDays", 0)) for m in promos if m.get("scope") in ("pos", "base")] + [0])
    rows = []
    for lead in range(longest + 1):
        pos, other = tier1(promos, lead, True), tier1(promos, lead, False)
        key = (pos["name"] if pos else None, other["name"] if other else None)
        if rows and rows[-1]["key"] == key:
            rows[-1]["to"] = lead
        else:
            rows.append({"key": key, "from": lead, "to": lead, "pos": pos, "other": other})
    if rows:
        rows[-1]["to"] = None
    return rows


def won(x):
    return f"{x:,.0f}"


def rate_args(a):
    return {"t": a.t, "c": a.c, "a": a.a, "p": a.p}


def print_result(r):
    print(f"달력요금        {won(r['rate']):>12}")
    if r["p"] != 1:
        print(f"패키지 배수      {r['p']:>12g}   (실효 할인 {r['effective']:.1f}%)")
    print(f"세전 정가        {won(r['list_pretax']):>12}")
    print(f"적용 할인        {r['discount']:>11g}%")
    print(f"할인 후 세전     {won(r['after']):>12}")
    print(f"손님 결제        {won(r['paid']):>12}")
    print(f"기본 보수 차감   {won(r['comp']):>12}")
    print(f"엑셀러레이터 차감 {won(r['accel']):>11}")
    print(f"입금가(계산값)   {won(r['payout']):>12}   (k {r['k']:.4f})")


def cmd_forward(a):
    d = float(sum(a.discount))
    r = forward(a.rate, d, **rate_args(a))
    print_result(r)
    if a.floor is not None:
        if r["payout"] < a.floor:
            need = up100(reverse(a.floor, d, **rate_args(a)))
            print(f"\n[미달] 목표 {won(a.floor)} 대비 {won(a.floor - r['payout'])} 부족. 달력을 {won(need)} 이상으로")
        else:
            print(f"\n[OK] 목표 {won(a.floor)} 대비 {won(r['payout'] - a.floor)} 여유")


def cmd_reverse(a):
    d = float(sum(a.discount))
    need = up100(reverse(a.target, d, **rate_args(a)))
    r = forward(need, d, **rate_args(a))
    print(f"목표 입금가      {won(a.target):>12}")
    print(f"적용 할인        {d:>11g}%")
    print(f"필요 달력요금    {won(need):>12}   (100원 올림)")
    print(f"그때 손님 결제   {won(r['paid']):>12}")
    print(f"그때 입금가      {won(r['payout']):>12}")


def cmd_check(a):
    """1층 최댓값이 바뀔 때의 영향. 프로모션 개수가 아니라 가장 깊은 값으로 넣어라."""
    d = float(sum(a.discount))
    base = forward(a.rate, d, **rate_args(a))
    print(f"현재: 할인 {d:g}% → 입금 {won(base['payout'])}")
    for extra in a.add:
        r = forward(a.rate, d + extra, **rate_args(a))
        line = f"  +{extra:g}%p → 할인 {d + extra:g}%  입금 {won(r['payout'])}  (-{won(base['payout'] - r['payout'])})"
        if a.floor is not None:
            ok = r["payout"] >= a.floor
            line += "  [OK]" if ok else f"  [미달] 사수 달력 {won(up100(reverse(a.floor, d + extra, **rate_args(a))))}"
        print(line)


def cmd_table(a):
    print(f"c {a.c:g}% · a {a.a:g}% · k {coef(a.t, a.c, a.a):.4f} — 목표 입금가별 필요 달력\n")
    print(f"{'할인':>6}" + "".join(f"{'입금 ' + won(t):>16}" for t in a.targets))
    for d in a.discounts:
        print(f"{d:>5g}%" + "".join(f"{won(up100(reverse(t, d, **rate_args(a)))):>18}" for t in a.targets))


def cmd_coef(a):
    print(f"T {a.t:g} · c {a.c:g}%\n{'a':>6} {'세전 k':>10} {'결제액 k÷T':>12}")
    for x in a.rates:
        k = coef(a.t, a.c, x)
        print(f"{x:>5g}% {k:>10.3f} {k / a.t:>12.6f}")


def cmd_booking(a):
    """예약 결제 내역 1건에서 요율을 역산하고 공식과 대조한다. 실측값이다."""
    if a.after <= 0 or a.paid <= 0:
        raise ValueError("할인 후 세전과 손님 결제는 양수여야 한다.")
    t, c, x = a.paid / a.after, a.comp / a.paid * 100, a.accel / a.after * 100
    calc = a.after * coef(t, c, x)
    print(f"세금 배수 T      {t:>12.4f}")
    print(f"기본 보수 c      {c:>11.2f}%   (결제 총액 기준)")
    print(f"엑셀러레이터 a   {x:>11.2f}%   (할인 후 세전 기준)")
    print(f"입금 계수 k      {a.payout / a.after:>12.4f}")
    print(f"공식 입금가      {won(calc):>12}")
    print(f"실입금           {won(a.payout):>12}   (오차 {calc - a.payout:+,.0f}원)")
    # 금액은 박별로 반올림되어 합산되므로 허용 오차도 박수만큼 커진다
    if abs(calc - a.payout) > a.nights:
        print(f"[주의] {a.nights}박 허용 오차 {a.nights}원을 넘게 어긋난다. 입력 금액과 추가 차감 항목을 다시 읽어라.")


def cmd_leadmap(a):
    path = pathlib.Path(a.property)
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        promos = data["promotions"]
    except (OSError, json.JSONDecodeError, KeyError) as err:
        raise ValueError(f"프로퍼티 파일을 읽지 못했다: {err}") from err
    extra = member_add(promos)
    print(f"{'구간':<12}{'자국 POS 1층':<30}{'그 외 1층':<30}비고")
    for s in lead_segments(promos):
        span = f"D-{s['from']}" + (f"~{s['to']}" if s["to"] != s["from"] and s["to"] is not None else "") + ("+" if s["to"] is None else "")
        gaps = [n for n, m in (("자국", s["pos"]), ("그 외", s["other"])) if m is None]
        note = f"빈 구간: {', '.join(gaps)} (회원 가산 {extra:g}%만)" if gaps else ""
        show = lambda m: f"{m['name']} {discount_for(m, False, extra):g}/{discount_for(m, True, extra):g}%" if m else "없음"
        print(f"{span:<12}{show(s['pos']):<30}{show(s['other']):<30}{note}")


def main():
    # 윈도우 기본 콘솔(cp949)에서도 한글·기호 출력이 깨지지 않게 한다
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, ValueError) as err:
            print(f"[경고] 출력 인코딩을 UTF-8로 바꾸지 못했다: {err}", file=sys.stderr)

    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd", required=True)

    def common(sp, target_opt=True):
        sp.add_argument("--c", type=float, required=True, help="기본 보수 %%. 결제 총액 기준")
        sp.add_argument("--a", type=float, required=True, help="엑셀러레이터 %%. 할인 후 세전 기준")
        sp.add_argument("--t", type=float, default=1.1, help="세금 배수. 기본 1.1 (한국 부가세)")
        sp.add_argument("--p", type=float, default=1.0, help="패키지 배수. 직판이면 1")
        if target_opt:
            sp.add_argument("--floor", type=float, help="목표 입금가(원). 숙소가 정한 값")

    f = sub.add_parser("forward", help="달력 → 입금가")
    f.add_argument("--rate", type=float, required=True)
    f.add_argument("--discount", type=float, nargs="+", required=True, help="할인 %%. 합계 또는 1층·2층 (덧셈)")
    common(f)
    f.set_defaults(func=cmd_forward)

    r = sub.add_parser("reverse", help="목표 입금가 → 필요 달력")
    r.add_argument("--target", type=float, required=True)
    r.add_argument("--discount", type=float, nargs="+", required=True)
    common(r, target_opt=False)
    r.set_defaults(func=cmd_reverse)

    c = sub.add_parser("check", help="할인을 더 깊게 할 때의 영향")
    c.add_argument("--rate", type=float, required=True)
    c.add_argument("--discount", type=float, nargs="+", required=True)
    c.add_argument("--add", type=float, nargs="+", default=[3, 5, 10])
    common(c)
    c.set_defaults(func=cmd_check)

    t = sub.add_parser("table", help="할인별 필요 달력 표")
    t.add_argument("--targets", type=float, nargs="+", required=True)
    t.add_argument("--discounts", type=float, nargs="+", default=[15, 20, 25, 30, 33, 37, 40])
    common(t, target_opt=False)
    t.set_defaults(func=cmd_table)

    k = sub.add_parser("coef", help="엑셀러레이터별 입금 계수 표")
    k.add_argument("--c", type=float, required=True)
    k.add_argument("--t", type=float, default=1.1)
    k.add_argument("--rates", type=float, nargs="+", default=[0, 1, 3, 5, 7])
    k.set_defaults(func=cmd_coef)

    b = sub.add_parser("booking", help="예약 결제 내역으로 요율 역산·대조")
    for name, text in (("after", "할인 후 세전"), ("paid", "손님 결제 총액"), ("comp", "기본 보수 금액"),
                       ("accel", "엑셀러레이터 금액"), ("payout", "실입금")):
        b.add_argument(f"--{name}", type=float, required=True, help=text)
    b.add_argument("--nights", type=int, default=1, help="박수. 박별 반올림 허용 오차에 쓴다")
    b.set_defaults(func=cmd_booking)

    m = sub.add_parser("leadmap", help="리드타임별 1층 최댓값과 빈 구간")
    m.add_argument("--property", required=True)
    m.set_defaults(func=cmd_leadmap)

    a = p.parse_args()
    try:
        a.func(a)
    except (ValueError, ZeroDivisionError) as err:
        # 계산 불가 입력은 추적 로그 대신 사유를 남기고 종료 코드 2로 끝낸다
        p.error(str(err))


if __name__ == "__main__":
    sys.exit(main())
