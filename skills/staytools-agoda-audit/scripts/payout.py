#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""아고다 입금가 계산기.

    고객결제 = CMS × (1 − Σ프로모션)
    입금가   = 고객결제 × (1 − 보수)
    표시가   = 고객결제 ÷ 세금배수        (--tax, 기본 1.1)

프로모션은 덧셈이다. 곱하지 마라.

보수(--commission)·하한(--floor)·목표(--targets)는 숙소마다 다르다. 기본값이 없으니
그 숙소의 정산·설정에서 확인한 값을 넣어라. 아래 숫자는 형식 예시다.

사용 예
    payout.py forward --cms 150000 --promos 55 --commission 20 --floor 50000
    payout.py forward --cms 150000 --promos 30 10 10 5 --commission 20 --floor 50000   # 개별로 줘도 됨
    payout.py reverse --target 60000 --promos 55 --commission 20
    payout.py check   --cms 150000 --promos 55 --commission 20 --floor 50000
    payout.py table   --commission 20 --targets 50000 60000 70000
    payout.py commission --sale 100000 --payout 80000                    # 실제 보수율 역산
"""
import argparse
import math
import sys

TAX = 1.1


def sigma(promos):
    """프로모션 리스트를 합계 %로. 하나만 주면 그게 이미 합계라고 본다."""
    return float(sum(promos))


def forward(cms, s, commission):
    if not math.isfinite(cms) or cms < 0:
        raise ValueError("CMS 요금은 0 이상의 숫자여야 한다.")
    if not (0 <= s < 100) or not (0 <= commission < 100):
        raise ValueError("프로모션 합계와 보수는 0 이상 100% 미만이어야 한다.")
    pay = cms * (1 - s / 100)
    return {
        "cms": cms,
        "sigma": s,
        "customer_pay": pay,
        "display": pay / TAX,
        "commission": commission,
        "payout": pay * (1 - commission / 100),
        "coef": (1 - s / 100) * (1 - commission / 100),
    }


def reverse(target, s, commission):
    if not math.isfinite(target) or target < 0:
        raise ValueError("목표 입금가는 0 이상의 숫자여야 한다.")
    if not (0 <= s < 100) or not (0 <= commission < 100):
        raise ValueError("프로모션 합계와 보수는 0 이상 100% 미만이어야 한다.")
    coef = (1 - s / 100) * (1 - commission / 100)
    if coef <= 0:
        raise ValueError("프로모션 합계가 100% 이상이다. 계산 불가.")
    cms = target / coef
    return {"target": target, "sigma": s, "commission": commission,
            "coef": coef, "cms": cms, "customer_pay": cms * (1 - s / 100)}


def won(x):
    return f"{x:,.0f}"


def up100(x):
    """하한을 지켜야 하는 값은 100원 단위로 올림한다.
    반올림하면 195,100 × 0.205 = 39,995처럼 목표선을 몇 원 밑돌 수 있다."""
    return math.ceil(x / 100) * 100


def cmd_forward(a):
    s = sigma(a.promos)
    r = forward(a.cms, s, a.commission)
    print(f"CMS 요금        {won(r['cms']):>12}")
    print(f"프로모션 합계    {s:>11.0f}%")
    print(f"고객 결제        {won(r['customer_pay']):>12}   (기준 판매 요금)")
    print(f"아고다 표시가    {won(r['display']):>12}   (고객결제 ÷ {TAX:g})")
    print(f"아고다 보수      {a.commission:>11.0f}%")
    print(f"입금가          {won(r['payout']):>12}   (입금계수 {r['coef']:.4f})")
    if r["payout"] < a.floor:
        gap = a.floor / r["coef"] - a.cms
        print(f"\n[미달] 하한 {won(a.floor)} 대비 {won(a.floor - r['payout'])} 부족")
        print(f"       CMS를 {won(up100(a.floor / r['coef']))} 이상으로 (+{won(gap)})")
    else:
        print(f"\n[OK] 하한 {won(a.floor)} 대비 {won(r['payout'] - a.floor)} 여유")


def cmd_reverse(a):
    s = sigma(a.promos)
    r = reverse(a.target, s, a.commission)
    need = up100(r["cms"])
    print(f"목표 입금가      {won(r['target']):>12}")
    print(f"프로모션 합계    {s:>11.0f}%")
    print(f"아고다 보수      {a.commission:>11.0f}%")
    print(f"입금계수        {r['coef']:>12.4f}")
    print(f"필요 CMS 요금    {won(need):>12}")
    # 올림한 CMS 기준으로 다시 계산해서 보여준다 (올림 전 값과 섞이지 않게)
    rounded = forward(need, s, a.commission)
    print(f"그때 고객 결제    {won(rounded['customer_pay']):>12}")
    print(f"그때 입금가      {won(rounded['payout']):>12}")


def cmd_check(a):
    """프로모션을 하나 더 켰을 때 어떻게 되는지 비교."""
    s = sigma(a.promos)
    base = forward(a.cms, s, a.commission)
    print(f"현재:  Σ {s:.0f}%  →  입금 {won(base['payout'])}  "
          f"({'OK' if base['payout'] >= a.floor else '미달'})")
    if a.add:
        for extra in a.add:
            s2 = s + extra
            r = forward(a.cms, s2, a.commission)
            loss = base["payout"] - r["payout"]
            need = a.floor / r["coef"]
            flag = "OK" if r["payout"] >= a.floor else "미달"
            print(f"  +{extra:>2.0f}%p → Σ {s2:>3.0f}%  입금 {won(r['payout']):>9}  "
                  f"(-{won(loss)})  [{flag}]  하한 사수 CMS {won(up100(need))}")


def cmd_table(a):
    print(f"보수 {a.commission:.0f}% 기준 — 목표 입금가별 필요 CMS\n")
    hdr = f"{'Σ':>5} {'입금계수':>9}" + "".join(f"{'입금 ' + won(t):>14}" for t in a.targets)
    print(hdr)
    print("-" * len(hdr))
    for s in a.sigmas:
        coef = (1 - s / 100) * (1 - a.commission / 100)
        cells = "".join(f"{won(up100(t / coef)):>16}" for t in a.targets)
        print(f"{s:>4.0f}% {coef:>9.4f}{cells}")
    print("\n프로모션 10%p 추가 = 입금가에서 CMS의 "
          f"{0.10 * (1 - a.commission / 100) * 100:.1f}%가 사라진다")


def cmd_commission(a):
    """실제 예약 한 건에서 보수율을 역산한다. 가정보다 이게 확실하다."""
    rate = 1 - a.payout / a.sale
    print(f"기준 판매 요금   {won(a.sale):>12}   (아고다 포털)")
    print(f"입금가          {won(a.payout):>12}   (정산 금액 또는 PMS 총 청구 금액)")
    print(f"실제 보수율      {rate * 100:>11.2f}%")
    print("                 → 포털 표기 보수(계약 수수료 + 프로그램 수수료)와 다르면")
    print("                   개시일이 다른 프로그램 수수료가 얹혔는지 확인해라")


def validate(p, a):
    """입력 검증. 틀린 입력으로 그럴듯한 숫자가 나오는 걸 막는다."""
    global TAX
    if hasattr(a, "tax"):
        if not math.isfinite(a.tax) or a.tax <= 0:
            p.error("세금 배수(--tax)는 양수여야 한다.")
        TAX = a.tax
    if hasattr(a, "floor") and (not math.isfinite(a.floor) or a.floor < 0):
        p.error("하한(--floor)은 0 이상이어야 한다.")
    if hasattr(a, "commission") and not (0 <= a.commission < 100):
        p.error("보수(--commission)는 0 이상 100% 미만이어야 한다.")
    if hasattr(a, "promos"):
        if any(not math.isfinite(x) or x < 0 for x in a.promos) or sum(a.promos) >= 100:
            p.error("프로모션은 각각 0 이상, 합계 100% 미만이어야 한다.")
    if hasattr(a, "add"):
        if any(not math.isfinite(x) or x < 0 or sum(a.promos) + x >= 100 for x in a.add):
            p.error("추가 프로모션(--add)은 0 이상, 기존 합계와 더해 100% 미만이어야 한다.")
    if hasattr(a, "sigmas") and any(not math.isfinite(x) or not (0 <= x < 100) for x in a.sigmas):
        p.error("Σ(--sigmas)는 0 이상 100% 미만이어야 한다.")
    if hasattr(a, "targets") and any(not math.isfinite(x) or x <= 0 for x in a.targets):
        p.error("목표 입금가(--targets)는 양수여야 한다.")
    if a.cmd == "commission":
        if not math.isfinite(a.sale) or a.sale <= 0:
            p.error("기준 판매 요금(--sale)은 양수여야 한다.")
        if not math.isfinite(a.payout) or not (0 <= a.payout <= a.sale):
            p.error("입금가(--payout)는 0 이상, 기준 판매 요금 이하여야 한다.")


def main():
    # 윈도우 기본 콘솔(cp949)에서도 한글·기호 출력이 깨지지 않게 한다
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, ValueError) as err:
            print(f"[경고] 출력 인코딩을 UTF-8로 바꾸지 못했다: {err}", file=sys.stderr)

    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd", required=True)

    def add_common(sp, need_floor=True):
        sp.add_argument("--promos", type=float, nargs="+", required=True,
                        help="프로모션 %%. 합계 하나 또는 개별 여러 개 (덧셈)")
        sp.add_argument("--commission", type=float, required=True,
                        help="아고다 보수 %% (계약 수수료 + 프로그램 수수료). 숙소별 값")
        if need_floor:
            sp.add_argument("--floor", type=float, required=True,
                            help="입금가 하한(원). 숙소가 정한 값")
        sp.add_argument("--tax", type=float, default=1.1,
                        help="세금 배수. 기본 1.1 (한국 부가세)")

    f = sub.add_parser("forward", help="CMS → 입금가")
    f.add_argument("--cms", type=float, required=True)
    add_common(f)
    f.set_defaults(func=cmd_forward)

    r = sub.add_parser("reverse", help="목표 입금가 → 필요 CMS")
    r.add_argument("--target", type=float, required=True)
    add_common(r, need_floor=False)
    r.set_defaults(func=cmd_reverse)

    c = sub.add_parser("check", help="프로모션 추가 시 영향 비교")
    c.add_argument("--cms", type=float, required=True)
    c.add_argument("--add", type=float, nargs="*", default=[5, 10, 20],
                   help="추가로 켤 프로모션 %%들")
    add_common(c)
    c.set_defaults(func=cmd_check)

    t = sub.add_parser("table", help="Σ별 안전선 표")
    t.add_argument("--commission", type=float, required=True,
                   help="아고다 보수 %%. 숙소별 값")
    t.add_argument("--targets", type=float, nargs="+", required=True,
                   help="비교할 목표 입금가들(원). 숙소의 하한·요일별 목표")
    t.add_argument("--sigmas", type=float, nargs="+",
                   default=[45, 55, 60, 65, 70, 75, 85])
    t.set_defaults(func=cmd_table)

    m = sub.add_parser("commission", help="실제 예약에서 보수율 역산")
    m.add_argument("--sale", type=float, required=True, help="아고다 기준 판매 요금")
    m.add_argument("--payout", type=float, required=True, help="정산 금액 또는 PMS 총 청구 금액")
    m.set_defaults(func=cmd_commission)

    a = p.parse_args()
    validate(p, a)
    try:
        a.func(a)
    except ValueError as err:
        # 계산 불가 입력은 추적 로그 대신 사유를 남기고 종료 코드 2로 끝낸다
        p.error(str(err))


if __name__ == "__main__":
    sys.exit(main())
