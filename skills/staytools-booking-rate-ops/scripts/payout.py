#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""부킹닷컴 입금가 계산기.

    기존 요금 = 판매가 × 요금제 배수 × 인원 계수 × (1 − 타겟 요금)
    노출가    = 기존 요금 × (1 − 포트폴리오형)
    입금가    = 노출가 × 입금 계수 k

단계 사이는 곱셈이고 같은 카테고리 안에서는 큰 할인 하나만 걸린다.
캠페인과 집중형 특가는 조합을 대체해 큰 쪽 하나만 걸리고, Genius 는 집중형 특가를 뺀 나머지에 더 곱해진다.
금액은 반올림 전 노출가에 k 를 곱한 뒤 반올림한다.

배수·할인율·k·하한은 숙소마다 다르다. 기본값이 없으니 그 숙소의 화면과 실예약에서 확인한 값을 넣어라.
아래 숫자는 형식 예시다.

사용 예
    payout.py forward --rate 200000 --plan 0.95 --target 25 --portfolio 20 --k 0.82 --floor 90000
    payout.py reverse --target-payout 90000 --plan 0.95 --target 25 --portfolio 20 --k 0.82
    payout.py check   --rate 200000 --plan 0.95 --target 25 --portfolio 20 --add 3 5 --k 0.82 --floor 90000
    payout.py restore --original 142500 --plan 0.95 --target 25
    payout.py booking --shown 114000 --payout 93480
    payout.py cells   --property property.json --room 스탠다드 --set WEEK --plan Non-refundable
    payout.py floor   --property property.json
"""
import argparse
import json
import math
import pathlib
import sys


def require(k, plan=1.0, occ=1.0, *pcts):
    if not math.isfinite(k) or not 0 < k <= 1:
        raise ValueError("입금 계수 k 는 0 초과 1 이하여야 한다.")
    if plan <= 0 or occ <= 0:
        raise ValueError("요금제 배수와 인원 계수는 양수여야 한다.")
    for p in pcts:
        if not 0 <= p < 100:
            raise ValueError("할인율은 0 이상 100% 미만이어야 한다.")


def forward(rate, target, portfolio, k, plan=1.0, occ=1.0):
    require(k, plan, occ, target, portfolio)
    if not math.isfinite(rate) or rate < 0:
        raise ValueError("판매가는 0 이상의 숫자여야 한다.")
    original = rate * plan * occ * (1 - target / 100)
    shown = original * (1 - portfolio / 100)
    return {"rate": rate, "plan": plan, "occ": occ, "target": target, "portfolio": portfolio, "k": k,
            "original": original, "shown": shown, "payout": shown * k}


def reverse(goal, target, portfolio, k, plan=1.0, occ=1.0):
    require(k, plan, occ, target, portfolio)
    return goal / (plan * occ * (1 - target / 100) * (1 - portfolio / 100) * k)


def round_up(x, unit=100):
    """목표를 지켜야 하는 판매가는 올림한다. 부동소수점 오차로 한 단위 뛰지 않게 먼저 다듬는다."""
    return math.ceil(round(x, 6) / unit) * unit


def occ_factor(step, base, pax):
    """기준 인원보다 1명 적을 때마다 감액폭을 뺀다. 곱셈이 아니라 뺄셈이다."""
    return 1 - (step or 0) * max(0, base - pax)


def active(promos, cat):
    return [p for p in promos if p.get("cat") == cat and p.get("status", "적용") == "적용"]


def applies(promo, lead, member):
    if promo.get("member") and not member:
        return False
    cond = promo.get("cond", "base")
    if cond == "advance":
        return lead >= int(promo.get("minDays", 0))
    if cond == "lastMinute":
        return lead <= int(promo.get("maxDays", 0))
    return True


def deepest(items):
    return max(items, key=lambda p: p["pct"]) if items else None


def pick_target(promos, pos, mobile):
    """접속 위치 요금과 모바일 요금 중 큰 할인 하나."""
    return deepest([p for p in active(promos, "target") if p.get("pos") == pos or (mobile and p.get("pos") == "mobile")])


def pick_portfolio(promos, lead, member):
    return deepest([p for p in active(promos, "portfolio") if applies(p, lead, member)])


def best_cell(rate, promos, k, plan, occ, pos, mobile, lead, member):
    """그 손님에게 걸리는 가장 낮은 값. 캠페인·집중형은 조합을 대체한다."""
    base = rate * plan * occ
    t, p = pick_target(promos, pos, mobile), pick_portfolio(promos, lead, member)
    tp, pp = t["pct"] if t else 0, p["pct"] if p else 0
    options = [{"names": [x["name"] for x in (t, p) if x], "original": base * (1 - tp / 100), "shown": base * (1 - tp / 100) * (1 - pp / 100), "genius": True}]
    for c in active(promos, "campaign"):
        if applies(c, lead, member):
            options.append({"names": [c["name"]], "original": base, "shown": base * (1 - c["pct"] / 100), "genius": True})
    gen = deepest(active(promos, "genius")) if member else None
    for o in options:
        if gen:
            o["shown"] *= 1 - gen["pct"] / 100
            o["names"] = o["names"] + [gen["name"]]
    for f in active(promos, "focus"):
        if applies(f, lead, member):
            options.append({"names": [f["name"]], "original": base, "shown": base * (1 - f["pct"] / 100)})
    best = min(options, key=lambda o: o["shown"])
    return {"names": best["names"], "original": best["original"], "shown": best["shown"], "payout": best["shown"] * k}


def lead_points(promos):
    """결과가 바뀔 수 있는 리드타임 경계. 막바지 끝 다음 날과 조기예약 시작일이다."""
    pts = {0}
    for p in promos:
        if p.get("cond") == "advance":
            pts.add(int(p.get("minDays", 0)))
        elif p.get("cond") == "lastMinute":
            pts.add(int(p.get("maxDays", 0)) + 1)
    return sorted(pts)


def floor_cells(d):
    """객실 × 세트마다 기준 인원의 가장 낮은 칸을 찾는다."""
    promos, k = d.get("promotions") or [], d["coef"]["k"]
    out = []
    for room in d.get("rooms") or []:
        for key, rate in (room.get("rates") or {}).items():
            if rate is None:
                continue
            low = None
            for plan in d.get("plans") or []:
                for lead in lead_points(promos):
                    for pos in ("domestic", "international"):
                        for mobile in (False, True):
                            for member in (False, True):
                                c = best_cell(rate, promos, k, plan["mult"], 1.0, pos, mobile, lead, member)
                                if low is None or c["payout"] < low["payout"]:
                                    low = dict(c, plan=plan["name"], lead=lead, pos=pos, mobile=mobile, member=member)
            if low:
                out.append(dict(low, room=room["name"], set=key, rate=rate))
    return out


def won(x):
    return f"{x:,.0f}"


def rate_args(a):
    return {"k": a.k, "plan": a.plan, "occ": a.occ}


def cmd_forward(a):
    x = forward(a.rate, a.target, a.portfolio, **rate_args(a))
    print(f"판매가           {won(x['rate']):>12}")
    print(f"요금제 × 인원     {a.plan * a.occ:>12g}")
    print(f"타겟 요금        {a.target:>11g}%")
    print(f"기존 요금        {won(x['original']):>12}")
    print(f"포트폴리오형     {a.portfolio:>11g}%")
    print(f"노출가           {won(x['shown']):>12}")
    print(f"입금가(계산값)   {won(x['payout']):>12}   (k {a.k:g})")
    if a.floor is not None:
        if x["payout"] < a.floor:
            need = round_up(reverse(a.floor, a.target, a.portfolio, **rate_args(a)), a.unit)
            print(f"\n[미달] 하한 {won(a.floor)} 대비 {won(a.floor - x['payout'])} 부족. 판매가를 {won(need)} 이상으로")
        else:
            print(f"\n[OK] 하한 {won(a.floor)} 대비 {won(x['payout'] - a.floor)} 여유")


def cmd_reverse(a):
    need = round_up(reverse(a.target_payout, a.target, a.portfolio, **rate_args(a)), a.unit)
    x = forward(need, a.target, a.portfolio, **rate_args(a))
    print(f"목표 입금가      {won(a.target_payout):>12}")
    print(f"필요 판매가      {won(need):>12}   ({a.unit:,}원 올림)")
    print(f"그때 노출가      {won(x['shown']):>12}")
    print(f"그때 입금가      {won(x['payout']):>12}")


def cmd_check(a):
    """포트폴리오형을 더 깊게 할 때의 영향. 판매가도 같이 제시한다."""
    base = forward(a.rate, a.target, a.portfolio, **rate_args(a))
    print(f"현재: 포트폴리오 {a.portfolio:g}% → 입금 {won(base['payout'])}")
    for add in a.add:
        p = a.portfolio + add
        x = forward(a.rate, a.target, p, **rate_args(a))
        line = f"  +{add:g}%p → {p:g}%  입금 {won(x['payout'])}  (-{won(base['payout'] - x['payout'])})"
        if a.floor is not None:
            ok = x["payout"] >= a.floor
            line += "  [OK]" if ok else f"  [미달] 필요 판매가 {won(round_up(reverse(a.floor, a.target, p, **rate_args(a)), a.unit))}"
        print(line)


def cmd_restore(a):
    """소비자 페이지 「기존 요금」에서 판매가를 복원한다. 객실 매핑과 판매가 대조에 쓴다."""
    require(0.5, a.plan, a.occ, a.target)
    print(f"판매가           {won(a.original / (a.plan * a.occ * (1 - a.target / 100))):>12}")


def cmd_booking(a):
    """예약 1건의 실입금에서 입금 계수를 역산한다. 판매가가 아니라 그 예약의 노출가로 나눈다."""
    if a.shown <= 0:
        raise ValueError("노출가는 양수여야 한다.")
    k = a.payout / a.shown
    print(f"입금 계수 k      {k:>12.4f}   (실입금 ÷ 노출가)")
    if a.k is not None:
        calc = a.shown * a.k
        print(f"k {a.k:g} 공식      {won(calc):>12}   (오차 {calc - a.payout:+,.0f}원)")
        if abs(calc - a.payout) > a.nights:
            print(f"[주의] {a.nights}박 허용 오차를 넘게 어긋난다. 정산 내역의 추가 항목과 입금 계수를 다시 읽어라.")


def load(path):
    try:
        d = json.loads(pathlib.Path(path).read_text(encoding="utf-8"))
        d["coef"]["k"]
    except (OSError, json.JSONDecodeError, KeyError) as err:
        raise ValueError(f"프로퍼티 파일을 읽지 못했다: {err}") from err
    if not isinstance(d["coef"]["k"], (int, float)):
        raise ValueError("입금 계수 k 가 비어 있다.")
    return d


def pos_name(c):
    return ("국내" if c["pos"] == "domestic" else "해외") + (" 모바일" if c["mobile"] else "") + (" 회원" if c["member"] else " 비회원")


def cmd_cells(a):
    d = load(a.property)
    promos, k = d.get("promotions") or [], d["coef"]["k"]
    room = next((r for r in d["rooms"] if r["name"] == a.room), None)
    plan = next((p for p in d["plans"] if p["name"] == a.plan), None)
    if room is None or plan is None or room["rates"].get(a.set) is None:
        raise ValueError("객실·세트·요금제 이름을 확인해라.")
    rate = room["rates"][a.set]
    print(f"{a.room} · {a.set} · {a.plan} (판매가 {won(rate)})")
    for lead in lead_points(promos):
        for pos in ("domestic", "international"):
            for member in (False, True):
                c = best_cell(rate, promos, k, plan["mult"], 1.0, pos, False, lead, member)
                print(f"  D-{lead:<3} {pos_name(dict(c, pos=pos, mobile=False, member=member)):<10} 기존 {won(c['original']):>9}  노출 {won(c['shown']):>9}  입금 {won(c['payout']):>9}  [{' · '.join(c['names']) or '할인 없음'}]")


def cmd_floor(a):
    d = load(a.property)
    limit = d["coef"].get("floor")
    for c in floor_cells(d):
        mark = "" if limit is None else ("  [OK]" if c["payout"] >= limit else "  [미달]")
        print(f"{c['room']} · {c['set']}: {won(c['payout'])}  ({c['plan']} · D-{c['lead']} · {pos_name(c)}){mark}")


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
        sp.add_argument("--target", type=float, default=0.0, help="타겟 요금 %%")
        sp.add_argument("--portfolio", type=float, default=0.0, help="포트폴리오형 %%")
        sp.add_argument("--k", type=float, required=True, help="입금 계수. 실예약으로 역산한 값")
        sp.add_argument("--plan", type=float, default=1.0, help="요금제 배수")
        sp.add_argument("--occ", type=float, default=1.0, help="인원 계수")
        sp.add_argument("--unit", type=int, default=100, help="판매가 올림 단위. 기본 100")
        if floor:
            sp.add_argument("--floor", type=float, help="입금가 하한(원). 숙소가 정한 값")

    f = sub.add_parser("forward", help="판매가 → 입금가")
    f.add_argument("--rate", type=float, required=True)
    common(f)
    f.set_defaults(func=cmd_forward)

    r = sub.add_parser("reverse", help="목표 입금가 → 필요 판매가")
    r.add_argument("--target-payout", dest="target_payout", type=float, required=True)
    common(r, floor=False)
    r.set_defaults(func=cmd_reverse)

    c = sub.add_parser("check", help="포트폴리오형이 깊어질 때의 영향")
    c.add_argument("--rate", type=float, required=True)
    c.add_argument("--add", type=float, nargs="+", default=[3, 5, 10])
    common(c)
    c.set_defaults(func=cmd_check)

    o = sub.add_parser("restore", help="기존 요금 → 판매가 복원")
    o.add_argument("--original", type=float, required=True)
    o.add_argument("--plan", type=float, default=1.0)
    o.add_argument("--occ", type=float, default=1.0)
    o.add_argument("--target", type=float, default=0.0)
    o.set_defaults(func=cmd_restore)

    b = sub.add_parser("booking", help="예약 1건으로 입금 계수 역산·대조")
    b.add_argument("--shown", type=float, required=True, help="그 예약의 노출가")
    b.add_argument("--payout", type=float, required=True, help="실입금")
    b.add_argument("--k", type=float, help="대조할 입금 계수")
    b.add_argument("--nights", type=int, default=1, help="박수. 허용 오차에 쓴다")
    b.set_defaults(func=cmd_booking)

    m = sub.add_parser("cells", help="리드타임 × 접속 × 회원 칸별 표")
    m.add_argument("--property", required=True)
    m.add_argument("--room", required=True)
    m.add_argument("--set", required=True)
    m.add_argument("--plan", required=True)
    m.set_defaults(func=cmd_cells)

    w = sub.add_parser("floor", help="객실 × 세트별 최심 칸과 하한 판정")
    w.add_argument("--property", required=True)
    w.set_defaults(func=cmd_floor)

    a = p.parse_args()
    try:
        a.func(a)
    except (ValueError, ZeroDivisionError) as err:
        # 계산 불가 입력은 추적 로그 대신 사유를 남기고 종료 코드 2로 끝낸다
        p.error(str(err))


if __name__ == "__main__":
    sys.exit(main())
