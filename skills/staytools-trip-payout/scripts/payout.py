#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""트립닷컴 입금가 계산기.

    P'           = 기준 판매가 × r
    노출가        = P' × (1 − Σ)        트립 부담 쿠폰을 빼기 전 손님 가격
    원래 객실 요금 = P' × (1 − c)
    최종 객실 요금 = 원래 객실 요금 × (1 − Σ)
    지급액        = 최종 객실 요금 − A

할인은 덧셈이다. 프로모션 40% + 회원 10% = 50%. 곱하지 마라.
겹치지 않는 조합끼리는 합계가 큰 쪽 하나만 걸린다. r 은 판매가 단계의 곱셈이고 Σ 와 섞지 않는다.
A 는 예약 지급액에서 읽는다. 비율로 만들지 마라.

c·r·Σ·목표는 숙소마다 다르다. 기본값이 없으니 그 숙소의 예약 지급액에서 확인한 값을 넣어라.
아래 숫자는 형식 예시다.

사용 예
    payout.py forward --rate 200000 --r 0.9 --sigma 40 10 --c 15 --floor 70000
    payout.py reverse --target 70000 --r 0.9 --sigma 50 --c 15
    payout.py check   --rate 200000 --r 0.9 --sigma 50 --add 3 5 10 --c 15 --floor 70000
    payout.py table   --r 0.9 --c 15 --targets 60000 70000
    payout.py restore --payout 76500 --disc 76500 --c 15 --r 0.9
    payout.py booking --orig 153000 --disc 76500 --payout 76500 --pprime 180000
    payout.py routes  --property property.json
"""
import argparse
import json
import math
import pathlib
import sys


def require(c, r, sigma=0.0):
    if not (0 <= c < 100):
        raise ValueError("수수료율 c 는 0 이상 100% 미만이어야 한다.")
    if not math.isfinite(r) or r <= 0:
        raise ValueError("파생 배수 r 은 양수여야 한다.")
    if not (0 <= sigma < 100):
        raise ValueError("할인 합계 Σ 는 0 이상 100% 미만이어야 한다.")


def forward(rate, sigma, c, r=1.0, extra=0.0):
    require(c, r, sigma)
    if not math.isfinite(rate) or rate < 0:
        raise ValueError("판매가는 0 이상의 숫자여야 한다.")
    pprime = rate * r
    orig = pprime * (1 - c / 100)
    final = orig * (1 - sigma / 100)
    return {"rate": rate, "r": r, "c": c, "sigma": sigma, "extra": extra, "pprime": pprime,
            "shown": pprime * (1 - sigma / 100), "orig": orig, "final": final, "payout": final - extra}


def reverse(target, sigma, c, r=1.0, extra=0.0):
    require(c, r, sigma)
    if not math.isfinite(target) or target < 0:
        raise ValueError("목표 입금가는 0 이상의 숫자여야 한다.")
    return (target + extra) / (r * (1 - c / 100) * (1 - sigma / 100))


def round_up(x, unit=1000):
    """목표를 지켜야 하는 판매가는 올림한다. 부동소수점 오차로 한 단위 뛰지 않게 먼저 다듬는다."""
    return math.ceil(round(x, 6) / unit) * unit


def option_sigma(option, promos, m, room=None):
    """후보 하나의 합계. 비활성이거나 그 객실이 대상이 아닌 프로모션은 빠지고 회원 가산만 남을 수 있다."""
    total, used = 0.0, []
    for name in option.get("parts") or []:
        promo = promos.get(name)
        if promo is None:
            raise ValueError(f"경로가 없는 프로모션을 가리킨다: {name}")
        if promo.get("status", "적용") != "적용":
            continue
        rooms = promo.get("rooms")
        if room is not None and rooms and room not in rooms:
            continue
        total += promo["pct"]
        used.append(f"{name} {promo['pct']:g}")
    if option.get("member"):
        total += m or 0
        used.append(f"회원 {m or 0:g}")
    return total, used


def route_sigma(route, promotions, m, room=None):
    """겹치지 않는 후보끼리는 합계가 큰 쪽 하나만 걸린다."""
    promos = {p["name"]: p for p in promotions}
    best, label = 0.0, []
    for option in route.get("options") or []:
        total, used = option_sigma(option, promos, m, room)
        if total > best or not label:
            best, label = total, used
    return best, label


def won(x):
    return f"{x:,.0f}"


def print_result(x):
    print(f"기준 판매가      {won(x['rate']):>12}")
    print(f"P' (취소선 정가) {won(x['pprime']):>12}   (r {x['r']:g})")
    print(f"Σ 호텔 부담 할인 {x['sigma']:>11g}%")
    print(f"노출가           {won(x['shown']):>12}   (트립 부담 쿠폰 전)")
    print(f"원래 객실 요금   {won(x['orig']):>12}   (수수료 {x['c']:g}% 차감)")
    print(f"최종 객실 요금   {won(x['final']):>12}")
    if x["extra"]:
        print(f"프로그램 차감 A  {won(x['extra']):>12}")
    print(f"지급액(계산값)   {won(x['payout']):>12}")


def rate_args(a):
    return {"c": a.c, "r": a.r, "extra": a.extra}


def cmd_forward(a):
    s = float(sum(a.sigma))
    x = forward(a.rate, s, **rate_args(a))
    print_result(x)
    if a.floor is not None:
        if x["payout"] < a.floor:
            need = round_up(reverse(a.floor, s, **rate_args(a)), a.unit)
            print(f"\n[미달] 목표 {won(a.floor)} 대비 {won(a.floor - x['payout'])} 부족. 판매가를 {won(need)} 이상으로")
        else:
            print(f"\n[OK] 목표 {won(a.floor)} 대비 {won(x['payout'] - a.floor)} 여유")


def cmd_reverse(a):
    s = float(sum(a.sigma))
    need = round_up(reverse(a.target, s, **rate_args(a)), a.unit)
    x = forward(need, s, **rate_args(a))
    print(f"목표 입금가      {won(a.target):>12}")
    print(f"최저경로 Σ       {s:>11g}%")
    print(f"필요 판매가      {won(need):>12}   ({a.unit:,}원 올림)")
    print(f"그때 노출가      {won(x['shown']):>12}")
    print(f"그때 지급액      {won(x['payout']):>12}")


def cmd_check(a):
    """Σ 가 바뀔 때의 영향. 같은 %p라도 Σ 가 높을수록 입금이 많이 줄어든다."""
    s = float(sum(a.sigma))
    base = forward(a.rate, s, **rate_args(a))
    print(f"현재: Σ {s:g}% → 지급액 {won(base['payout'])}")
    for add in a.add:
        x = forward(a.rate, s + add, **rate_args(a))
        rate = (1 - (1 - (s + add) / 100) / (1 - s / 100)) * 100
        line = f"  +{add:g}%p → Σ {s + add:g}%  지급액 {won(x['payout'])}  (-{won(base['payout'] - x['payout'])}, 입금 -{rate:.1f}%)"
        if a.floor is not None:
            ok = x["payout"] >= a.floor
            line += "  [OK]" if ok else f"  [미달] 필요 판매가 {won(round_up(reverse(a.floor, s + add, **rate_args(a)), a.unit))}"
        print(line)


def cmd_table(a):
    print(f"c {a.c:g}% · r {a.r:g} — 목표 입금가별 필요 판매가\n")
    print(f"{'Σ':>6}" + "".join(f"{'입금 ' + won(t):>16}" for t in a.targets))
    for s in a.sigmas:
        print(f"{s:>5g}%" + "".join(f"{won(round_up(reverse(t, s, **rate_args(a)), a.unit)):>18}" for t in a.targets))


def cmd_restore(a):
    """실입금에서 판매가를 복원한다. 이 값은 그 날짜의 달력값과 대조해야 뜻이 있다."""
    require(a.c, a.r)
    pprime = (a.payout + a.disc + a.extra) / (1 - a.c / 100)
    print(f"P' (취소선 정가) {won(pprime):>12}")
    print(f"기준 판매가      {won(pprime / a.r):>12}   (r {a.r:g})")
    print("달력값과 같으면 요금 문제가 아니라 할인 문제다.")


def cmd_booking(a):
    """예약 지불 정보 1건에서 Σ 와 c 를 역산하고 공식과 대조한다. 지급액은 실측값이다."""
    if a.orig <= 0:
        raise ValueError("원래 객실 요금은 양수여야 한다.")
    print(f"Σ (할인 ÷ 원래)  {a.disc / a.orig * 100:>11.2f}%")
    if a.pprime is not None:
        if a.pprime <= 0:
            raise ValueError("P' 는 양수여야 한다.")
        print(f"c (1 − 원래 ÷ P') {(1 - a.orig / a.pprime) * 100:>10.2f}%")
    calc = a.orig - a.disc - a.extra
    print(f"공식 지급액      {won(calc):>12}")
    print(f"실제 지급액      {won(a.payout):>12}   (오차 {calc - a.payout:+,.0f}원)")
    # 금액은 박별로 반올림되어 합산되므로 허용 오차도 박수만큼 커진다
    if abs(calc - a.payout) > a.nights:
        print(f"[주의] {a.nights}박 허용 오차 {a.nights}원을 넘게 어긋난다. 「추가 요금」 줄과 날짜별 명세를 다시 읽어라.")


def cmd_routes(a):
    path = pathlib.Path(a.property)
    try:
        d = json.loads(path.read_text(encoding="utf-8"))
        c, m, routes = d["coef"]["c"], d["coef"].get("m"), d["routes"]
        promotions, rooms, plans = d["promotions"], d["rooms"], d["plans"]
    except (OSError, json.JSONDecodeError, KeyError) as err:
        raise ValueError(f"프로퍼티 파일을 읽지 못했다: {err}") from err
    for room in rooms:
        for key, rate in (room.get("rates") or {}).items():
            if rate is None:
                continue
            for plan in plans:
                rows = []
                for route in routes:
                    s, used = route_sigma(route, promotions, m, room["name"])
                    rows.append((route["name"], s, forward(rate, s, c, plan["r"])["payout"], used))
                low = min(x[2] for x in rows)
                print(f"\n{room['name']} · {key} · {plan['name']} (판매가 {won(rate)})")
                for name, s, pay, used in rows:
                    print(f"  {s:>5g}%  {won(pay):>10}  {name}  [{' + '.join(used) or '할인 없음'}]{'  ← 최저' if pay == low else ''}")


def main():
    # 윈도우 기본 콘솔(cp949)에서도 한글·기호 출력이 깨지지 않게 한다
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, ValueError) as err:
            print(f"[경고] 출력 인코딩을 UTF-8로 바꾸지 못했다: {err}", file=sys.stderr)

    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd", required=True)

    def common(sp, floor=True):
        sp.add_argument("--c", type=float, required=True, help="수수료율 %%")
        sp.add_argument("--r", type=float, default=1.0, help="파생 배수(환불불가·인원별). 없으면 1")
        sp.add_argument("--extra", type=float, default=0.0, help="프로그램 차감 A(원). 예약에서 읽은 값")
        sp.add_argument("--unit", type=int, default=1000, help="판매가 올림 단위. 기본 1000")
        if floor:
            sp.add_argument("--floor", type=float, help="목표 입금가(원). 숙소가 정한 값")

    f = sub.add_parser("forward", help="판매가 → 지급액")
    f.add_argument("--rate", type=float, required=True)
    f.add_argument("--sigma", type=float, nargs="+", required=True, help="호텔 부담 할인 %%. 합계 또는 항목별 (덧셈)")
    common(f)
    f.set_defaults(func=cmd_forward)

    r = sub.add_parser("reverse", help="목표 입금가 → 필요 판매가")
    r.add_argument("--target", type=float, required=True)
    r.add_argument("--sigma", type=float, nargs="+", required=True, help="최저경로 Σ")
    common(r, floor=False)
    r.set_defaults(func=cmd_reverse)

    c = sub.add_parser("check", help="Σ 가 깊어질 때의 영향")
    c.add_argument("--rate", type=float, required=True)
    c.add_argument("--sigma", type=float, nargs="+", required=True)
    c.add_argument("--add", type=float, nargs="+", default=[3, 5, 10])
    common(c)
    c.set_defaults(func=cmd_check)

    t = sub.add_parser("table", help="Σ 별 필요 판매가 표")
    t.add_argument("--targets", type=float, nargs="+", required=True)
    t.add_argument("--sigmas", type=float, nargs="+", default=[20, 30, 40, 45, 50, 55, 60])
    common(t, floor=False)
    t.set_defaults(func=cmd_table)

    o = sub.add_parser("restore", help="실입금 + 할인 → 판매가 복원")
    o.add_argument("--payout", type=float, required=True, help="지급액")
    o.add_argument("--disc", type=float, required=True, help="할인 합계")
    common(o, floor=False)
    o.set_defaults(func=cmd_restore)

    b = sub.add_parser("booking", help="예약 지불 정보로 Σ·c 역산·대조")
    b.add_argument("--orig", type=float, required=True, help="원래 객실 요금")
    b.add_argument("--disc", type=float, required=True, help="할인 합계")
    b.add_argument("--payout", type=float, required=True, help="지급액")
    b.add_argument("--pprime", type=float, help="그 예약의 P' 합계. 달력값 × r × 박수")
    b.add_argument("--extra", type=float, default=0.0, help="「추가 요금」 줄")
    b.add_argument("--nights", type=int, default=1, help="박수. 박별 반올림 허용 오차에 쓴다")
    b.set_defaults(func=cmd_booking)

    m = sub.add_parser("routes", help="객실 × 요금제 × 경로별 지급액과 최저 경로")
    m.add_argument("--property", required=True)
    m.set_defaults(func=cmd_routes)

    a = p.parse_args()
    try:
        a.func(a)
    except (ValueError, ZeroDivisionError) as err:
        # 계산 불가 입력은 추적 로그 대신 사유를 남기고 종료 코드 2로 끝낸다
        p.error(str(err))


if __name__ == "__main__":
    sys.exit(main())
