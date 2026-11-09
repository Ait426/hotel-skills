#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""손님 유형 → OTA 설정 추천 1.0.0 (staytools-guest-mix)
예약 내보내기(PMS 필수, 채널 파일 선택)로 손님 유형을 나누고, 빈 날·꽉 찬 날을 찾고,
유형에 맞는 OTA 설정을 추천한 뒤 각 OTA property.json 으로 입금가 하한을 검산한다.

사용:
  python segment_report.py --pms 예약.xlsx --mapping mapping.json --profile profile.json --out-dir 결과
      [--month YYYY-MM | --start YYYY-MM-DD --end YYYY-MM-DD]
      [--extra 트립닷컴=trip.csv --extra 부킹닷컴=booking.csv ...] [--log 로그] [--debug]

결과: 결과/segments.json, 결과/report.html
예약번호·이름·연락처 열은 읽지 않는다. 매핑한 열만 남기고 나머지는 읽자마자 버린다.
필요한 패키지: pandas (xlsx 를 읽으면 openpyxl 도)
"""
import argparse, html, json, logging, math, os, re, sys
from collections import OrderedDict
import pandas as pd

log = logging.getLogger('guest_mix')

# 개인정보·식별번호 열은 매핑하면 멈춘다. 앞부분은 staytools-sales-analysis/scripts/sales_report.py 의 PII_RE 를 옮겨 왔다.
PII_RE = re.compile(r'이름|성명|고객명|투숙객|예약자|전화|휴대폰|연락처|이메일|주민|여권|e-?mail|phone|mobile|guest.?name|passport'
                    r'|예약\s?번호|확정\s?번호|주문\s?번호|res_?id|booking.?id|confirmation', re.I)
PMS_COLS = ['거래처', '체크인', '체크아웃', '예약 생성일', '예약 상태', '총 청구 금액', '잔액', '이용 유형', '객실 타입', '성인', '유아동', '요금 유형']
PMS_REQUIRED = ['거래처', '체크인', '체크아웃', '예약 생성일', '예약 상태', '총 청구 금액']
EXTRA_COLS = ['체크인', '체크아웃', '이용 기간', '예약일', '상태', '금액', '국적', '요금제', '식사', '프로모션', '인원', '객실 타입', '투숙유형', '회원등급', '쿠폰']
WD = ['월', '화', '수', '목', '금', '토', '일']
LB = ['당일', '1~3일', '4~7일', '8~30일', '31일+']
LOS = ['대실', '1박', '2박', '3~6박', '7박+']
NAT_SKIP = re.compile(r'^\((없음|모름)\)$|기타|other|unknown|미상', re.I)
DEFAULT_TH = {'min_n': 20, 'full_occ': 0.9, 'empty_occ': 0.6, 'short_lead_share': 0.5, 'long_lead_share': 0.2,
              'long_stay_share': 0.12, 'cancel_rate': 0.2, 'nat_share': 0.3, 'family_share': 0.2, 'dayuse_share': 0.3, 'step_pct': 5}
# 추천 규칙이 찾는 프로모션 이름 (property.json promoGroups 항목 이름)
KW = {'last': r'마감|당일|라스트|막판|last|same.?day|late',   # 모바일 요금은 접속 기기 타깃이라 막판 할인으로 보지 않는다
      'early': r'얼리|조기|사전|early|advance',
      'los': r'연박|장기|주간|위클리|long|los|weekly|multi.?night',
      'country': r'국가|타깃|타겟|지역|country|target|international'}


class ConfigError(Exception):
    """사용자가 고칠 수 있는 입력·설정 오류"""


def read_json(path, label):
    """UTF-8 JSON 읽기 (BOM 허용). 실패하면 어느 파일인지 알려 준다. (sales_report.read_json 과 같은 방식)"""
    try:
        with open(path, encoding='utf-8-sig') as fh:
            return json.load(fh)
    except FileNotFoundError:
        raise ConfigError(f'{label} 파일이 없습니다: {path}')
    except json.JSONDecodeError as e:
        raise ConfigError(f'{label} 파일이 올바른 JSON이 아닙니다: {path} ({e.lineno}행 {e.colno}열)')


def check_columns(cols, allowed, label):
    """매핑 검증: 모르는 표준 항목·개인정보 열을 막는다."""
    if not isinstance(cols, dict):
        raise ConfigError(f'{label} 에 columns 가 없습니다 (표준 항목 -> 내 파일 열 이름)')
    cols = {k: v for k, v in cols.items() if v}
    extra = [k for k in cols if k not in allowed]
    if extra:
        raise ConfigError(f'{label} columns 에 모르는 표준 항목이 있습니다: {extra}')
    pii = [v for v in cols.values() if PII_RE.search(str(v))]
    if pii:
        raise ConfigError(f'{label}: 개인정보·예약번호로 보이는 열은 매핑할 수 없습니다: {pii}')
    return cols


def read_table(path, sec, label):
    """csv·xlsx 를 읽어 표준 항목 이름으로 바꾼다. 매핑하지 않은 열은 버린다. (sales_report.read_export 를 옮겨 와 csv 를 더함)"""
    cols = sec['columns']
    header = int(sec.get('header_row') or 1) - 1
    try:
        if str(path).lower().endswith('.csv'):
            raw = None
            for enc in ([sec['encoding']] if sec.get('encoding') else ['utf-8-sig', 'cp949']):
                try:
                    raw = pd.read_csv(path, header=header, dtype=str, encoding=enc, usecols=lambda c: str(c).strip() in cols.values())
                    break
                except UnicodeDecodeError:
                    log.info('%s: %s 인코딩이 아님, 다음 인코딩 시도', label, enc)
            if raw is None:
                raise ConfigError(f'{label} 의 글자 인코딩을 알 수 없습니다. 매핑에 encoding 을 적으세요')
        else:
            raw = pd.read_excel(path, sheet_name=sec.get('sheet') or 0, header=header, dtype=str, usecols=lambda c: str(c).strip() in cols.values())
    except FileNotFoundError:
        raise ConfigError(f'{label} 파일이 없습니다: {path}')
    except ValueError as e:
        raise ConfigError(f'{label} 을 읽지 못했습니다: {e}')
    raw = raw.fillna('')
    raw.columns = [str(c).strip() for c in raw.columns]
    miss = [v for v in cols.values() if v not in raw.columns]
    if miss:
        raise ConfigError(f'{label} 에 매핑한 열이 없습니다: {miss} (header_row·열 이름 확인)')
    out = pd.DataFrame({k: raw[v] for k, v in cols.items()})
    del raw   # 매핑하지 않은 열은 여기서 버린다
    log.info('%s 읽음: %d행, 매핑 %d열', label, len(out), len(cols))
    return out


def to_dt(s):
    """날짜 열: 'YYYY-MM-DD', 'YYYY년 M월 D일 HH:MM', 'YYYY-MM-DDTHH:MM' 모두 받는다."""
    s = s.astype(str).str.replace(r'\s*년\s*|\s*월\s*', '-', regex=True).str.replace(r'\s*일', '', regex=True)
    # '2026.10.01' · '2026/10/01' · '2026. 10. 01.' 도 '2026-10-01' 로 맞춘다
    s = s.str.replace(r'(\d{4})\s*[./]\s*(\d{1,2})\s*[./]\s*(\d{1,2})\.?', r'\1-\2-\3', regex=True)
    # 뒤에 붙은 글자(예: '<미리예약고객>')는 버리고 날짜·시각만 꺼낸다
    s = s.str.extract(r'(\d{4}-\d{1,2}-\d{1,2}(?:[ T]\d{1,2}:\d{2}(?::\d{2})?)?)', expand=False)
    return pd.to_datetime(s.str.replace('T', ' ', regex=False), errors='coerce', format='mixed')


def num(x):
    m = re.sub(r'[^\d.\-]', '', str(x))
    try:
        return float(m) if m not in ('', '-', '.') else 0.0
    except ValueError:
        log.debug('숫자로 못 읽음: %r', x)
        return 0.0


def find_channel(acc, rules, unmatched=None):
    """거래처 -> 채널 (정확히 같은 이름 먼저, 그다음 포함). sales_report.find_rule 과 같은 순서.
    규칙에 없는 거래처는 unmatched(기본 '기타 거래처')로 묶는다. 거래처 이름은 개인 이름일 수 있어 결과에 쓰지 않는다."""
    for r in rules:
        if acc in (r.get('match') or []):
            return r['channel'], r.get('group', '')
    for r in rules:
        if any(k and k in str(acc) for k in (r.get('contains') or [])):
            return r['channel'], r.get('group', '')
    return (unmatched or '기타 거래처'), '미분류'


def add_dims(df, stay, cancel):
    """공통 파생 열: 취소·리드타임·박수·요일."""
    df['_can'] = cancel
    df['_stay'] = stay
    df['_n'] = ((df['_co'].dt.normalize() - df['_ci'].dt.normalize()).dt.days).clip(lower=0).fillna(0).astype(int)
    df.loc[df['_stay'] & (df['_n'] < 1), '_n'] = 1
    df.loc[~df['_stay'], '_n'] = 0
    lead = (df['_ci'].dt.normalize() - df['_cr'].dt.normalize()).dt.days
    df['_lead'] = lead
    df['_lb'] = pd.cut(lead, [-10**6, 0, 3, 7, 30, 10**6], labels=LB).astype(str).replace('nan', '(모름)')
    df['_wd'] = df['_ci'].dt.weekday.map(lambda i: WD[int(i)] if pd.notna(i) else '(모름)')
    n = df['_n']
    df['_los'] = ['대실' if not s else '1박' if k == 1 else '2박' if k == 2 else '3~6박' if k <= 6 else '7박+' for s, k in zip(df['_stay'], n)]
    return df


def load_pms(path, mp):
    sec = mp.get('pms') or {}
    sec['columns'] = check_columns(sec.get('columns'), PMS_COLS, '매핑 pms')
    miss = [k for k in PMS_REQUIRED if k not in sec['columns']]
    if miss:
        raise ConfigError(f'매핑 pms.columns 에 필수 항목이 없습니다: {miss}')
    df = read_table(path, sec, 'PMS 내보내기')
    vals = sec.get('values') or {}
    stay_vals = vals.get('stay') or ['숙박']
    ckw = vals.get('cancel_keywords') or ['취소', '노쇼']
    df['_ci'], df['_co'], df['_cr'] = to_dt(df['체크인']), to_dt(df['체크아웃']), to_dt(df['예약 생성일'])
    bad = df['_ci'].isna() | df['_cr'].isna()
    if bad.any():
        log.warning('PMS: 체크인·예약 생성일을 읽지 못한 %d행을 뺐습니다', int(bad.sum()))
        df = df[~bad].reset_index(drop=True)
    if df.empty:
        raise ConfigError('PMS 에서 읽을 수 있는 예약이 없습니다 (날짜 열 매핑 확인)')
    df['_amt'] = df['총 청구 금액'].map(num) + (df['잔액'].map(num) if '잔액' in df else 0)
    stay = df['이용 유형'].isin(stay_vals) if '이용 유형' in df else pd.Series(True, index=df.index)
    cancel = df['예약 상태'].str.contains('|'.join(re.escape(k) for k in ckw), case=False, regex=True)
    df = add_dims(df, stay, cancel)
    ch = [find_channel(a, sec.get('channels') or [], sec.get('unmatched')) for a in df['거래처']]
    df['_ch'] = [c for c, _ in ch]
    df['_room'] = df['객실 타입'].replace('', '(미지정)') if '객실 타입' in df else '(미지정)'
    if '성인' in df or '유아동' in df:
        ad = df['성인'].map(num) if '성인' in df else 0
        kid = df['유아동'].map(num) if '유아동' in df else 0
        tot = ad + kid
        df['_party'] = ['(모름)' if t <= 0 else '1인' if t == 1 else '2인' if t == 2 else '3인+' for t in tot]
    df['_plan'] = df['요금 유형'].replace('', '(없음)') if '요금 유형' in df else None
    df = df.drop(columns=[c for c in ('거래처',) if c in df])
    n_unk = sum(1 for _, g in ch if g == '미분류')
    if n_unk:   # 거래처 이름은 기업명일 수 있어 로그에 남기지 않는다
        log.warning("채널 규칙에 없는 거래처 예약 %d건을 '%s'로 묶었습니다", n_unk, sec.get('unmatched') or '기타 거래처')
    return df


def load_extra(chan, path, mp):
    secs = {s.get('channel'): s for s in (mp.get('extras') or [])}
    if chan not in secs:
        raise ConfigError(f"--extra {chan}: 매핑 extras 에 channel '{chan}' 항목이 없습니다")
    sec = dict(secs[chan])
    sec['columns'] = check_columns(sec.get('columns'), EXTRA_COLS, f'매핑 extras[{chan}]')
    c = sec['columns']
    if '이용 기간' not in c and not ('체크인' in c and '체크아웃' in c):
        raise ConfigError(f'매핑 extras[{chan}]: 체크인·체크아웃 또는 이용 기간이 필요합니다')
    df = read_table(path, sec, f'{chan} 파일')
    if '이용 기간' in df:   # 'a ~ b' 형태 (국내 OTA)
        sp = df['이용 기간'].str.split('~', n=1, expand=True)
        df['체크인'], df['체크아웃'] = sp[0].str.strip(), sp[1].fillna('').str.strip()
    df['_ci'], df['_co'] = to_dt(df['체크인']), to_dt(df['체크아웃'])
    df['_cr'] = to_dt(df['예약일']) if '예약일' in df else pd.Series(pd.NaT, index=df.index, dtype='datetime64[ns]')
    df = df[df['_ci'].notna()].reset_index(drop=True)
    vals = sec.get('values') or {}
    if '투숙유형' in df:
        stay = ~df['투숙유형'].isin(vals.get('dayuse') or ['대실'])
    else:
        stay = pd.Series(True, index=df.index)
    if '상태' in df:
        ckw = vals.get('cancel_keywords') or ['취소', '노쇼']
        exact = set(vals.get('cancel_values') or [])
        cancel = df['상태'].str.contains('|'.join(re.escape(k) for k in ckw), case=False, regex=True) | df['상태'].isin(exact)
    else:
        cancel = pd.Series(False, index=df.index)
    df['_amt'] = df['금액'].map(num) if '금액' in df else 0.0
    df = add_dims(df, stay, cancel)
    if '인원' in df:
        t = df['인원'].map(num)
        df['_party'] = ['(모름)' if v <= 0 else '1인' if v == 1 else '2인' if v == 2 else '3인+' for v in t]
    df['_ch'] = chan
    return df


def parse_day(v, label):
    """명령 인자의 날짜 → Timestamp. 잘못된 값은 어느 인자인지 알려 준다."""
    try:
        return pd.Timestamp(v).normalize()
    except (ValueError, TypeError):
        raise ConfigError(f'{label} 날짜를 읽지 못했습니다: {v!r} (YYYY-MM-DD)')


def period_of(A, df):
    if A.month:
        try:
            p = pd.Period(A.month, 'M')
        except ValueError:
            raise ConfigError(f'--month 를 읽지 못했습니다: {A.month!r} (YYYY-MM)')
        return p.start_time.normalize(), p.end_time.normalize()
    if A.start or A.end:
        if not (A.start and A.end):
            raise ConfigError('--start 와 --end 는 함께 적어야 합니다')
        return parse_day(A.start, '--start'), parse_day(A.end, '--end')
    v = df[~df['_can']]
    return v['_ci'].min().normalize(), (v['_co'].max().normalize() - pd.Timedelta(days=1))


def agg(g, all_rows=None):
    """건수·박수·매출·1박 평균·취소율. g 는 유효(취소 제외) 행, all_rows 는 취소 포함 행."""
    s = g[g['_stay']]
    sp = s[s['_amt'] > 0]
    nights = int(s['_n'].sum())
    out = {'n': int(len(g)), 'nights': nights, 'revenue': int(round(g['_amt'].sum())),
           'adr': int(round(sp['_amt'].sum() / sp['_n'].sum())) if len(sp) and sp['_n'].sum() else None}
    if all_rows is not None and len(all_rows):
        out['cancel_rate'] = round(float(all_rows['_can'].mean()), 3)
    return out


def dist(df, col, order=None):
    """한 축의 분포: 값별 지표와 비중 (취소 제외 기준)."""
    v = df[~df['_can']]
    tot = max(1, len(v))
    keys = [k for k in (order or []) if k in set(df[col])] + sorted(set(df[col]) - set(order or []), key=str)
    rows = []
    for k in keys:
        g, a = v[v[col] == k], df[df[col] == k]
        if not len(a):
            continue
        r = {'key': str(k), **agg(g, a), 'share': round(len(g) / tot, 3)}
        rows.append(r)
    return rows


def cross(df, row, col, order=None):
    """채널×축 비중표: 행(채널)마다 가로 합 100%."""
    v = df[~df['_can']]
    cols = [k for k in (order or []) if k in set(v[col])] + sorted(set(v[col]) - set(order or []), key=str)
    out = OrderedDict()
    for r, g in v.groupby(row, sort=False):
        out[str(r)] = {'n': int(len(g)), **{str(c): round(float((g[col] == c).mean()), 3) for c in cols}}
    return {'cols': [str(c) for c in cols], 'rows': out}


def occupancy(df, start, end, rooms):
    """날짜×객실 타입 판매 객실박수 → 요일별·객실별 점유율, RevPAR. 대실은 점유율에서 뺀다.
    프로필 rooms 에 없는 객실 타입은 분모(객실 수)에 없으므로 분자에서도 빼고 박수를 경고로 알린다."""
    days = pd.date_range(start, end, freq='D')
    cap_total = sum(int(v) for v in rooms.values())
    v = df[(~df['_can']) & df['_stay']]
    day_sold, day_rev, room_wd = {}, {}, {}   # 날짜별 판매·매출, (객실, 요일)별 판매를 한 번에 모은다
    skipped = {}
    for ci, n, room, amt in zip(v['_ci'].dt.normalize(), v['_n'], v['_room'], v['_amt']):
        per = amt / n if n else 0
        for i in range(int(n)):
            d = ci + pd.Timedelta(days=i)
            if not (start <= d <= end):
                continue
            if room not in rooms:
                skipped[room] = skipped.get(room, 0) + 1
                continue
            day_sold[d] = day_sold.get(d, 0) + 1
            day_rev[d] = day_rev.get(d, 0) + per
            k = (room, d.weekday())
            room_wd[k] = room_wd.get(k, 0) + 1
    if skipped:
        log.warning('프로필 rooms 에 없는 객실 타입 %d개(객실박 %d)를 점유율에서 뺐습니다', len(skipped), sum(skipped.values()))
    ndays = {w: sum(1 for d in days if d.weekday() == w) for w in range(7)}
    by_wd, by_room_wd = OrderedDict(), OrderedDict()
    for w in range(7):
        if not ndays[w]:
            continue
        s = sum(c for d, c in day_sold.items() if d.weekday() == w)
        rv = sum(x for d, x in day_rev.items() if d.weekday() == w)
        cap = cap_total * ndays[w]
        by_wd[WD[w]] = {'days': ndays[w], 'sold': s, 'occ': round(s / cap, 3) if cap else None,
                        'revpar': int(round(rv / cap)) if cap else None, 'adr': int(round(rv / s)) if s else None}
        for room, cnt in rooms.items():
            by_room_wd.setdefault(room, OrderedDict())[WD[w]] = round(room_wd.get((room, w), 0) / (int(cnt) * ndays[w]), 3) if cnt else None
    s_all, r_all = sum(day_sold.values()), sum(day_rev.values())
    cap_all = cap_total * len(days)
    daily = [{'date': d.strftime('%Y-%m-%d'), 'wd': WD[d.weekday()], 'sold': day_sold.get(d, 0),
              'occ': round(day_sold.get(d, 0) / cap_total, 3) if cap_total else None} for d in days]
    return {'days': len(days), 'capacity': cap_total, 'sold': s_all, 'occ': round(s_all / cap_all, 3) if cap_all else None,
            'revpar': int(round(r_all / cap_all)) if cap_all else None, 'adr': int(round(r_all / s_all)) if s_all else None,
            'by_weekday': by_wd, 'by_room_weekday': by_room_wd, 'daily': daily,
            'unknown_rooms': sorted(skipped), 'unknown_nights': sum(skipped.values())}


# ---------------------------------------------------------------- 입금가 검산
def ota_model(name, conf, base_dir):
    """OTA property.json → 할인 그룹·수수료·판매가·하한. 각 OTA 콘솔 계산기(combo_card)와 같은 공식이다.
    부킹 = 그룹끼리 곱, 익스·트립·아고다 = 더함. 익스는 가속 수수료를 세전(T=1.1)에서 뺀다."""
    kind = conf.get('kind') or ''
    m = {'name': name, 'kind': kind, 'groups': [], 'b': 0.0, 'a': 0.0, 'T': 1.1 if kind == 'expedia' else 1.0,
         'across': 'mult' if kind == 'booking' else 'add', 'rate': conf.get('rate'), 'floor': conf.get('floor'),
         'countries': [], 'src': conf.get('property') or '', 'ok': False, 'why': ''}
    if not conf.get('property'):
        m['why'] = '프로필에 property 경로가 없음'
        return m
    p = conf['property'] if os.path.isabs(conf['property']) else os.path.join(base_dir, conf['property'])
    d = read_json(p, f'{name} property')
    if kind == 'agoda':
        for g in ((d.get('promotions') or {}).get('groups') or []):
            m['groups'].append({'name': g.get('name', ''), 'mode': g.get('mode', 'single'),
                                'items': [{'name': it.get('nm') or it.get('name', ''), 'pct': pct_of(it.get('pct'), f"{name} promotions.groups '{g.get('name', '')}'"),
                                           'on': bool(it.get('on'))} for it in g.get('items') or []]})
        parts = (d.get('commission') or {}).get('parts') or []
        m['b'] = sum(pct_of(x['pct'], f"{name} commission.parts '{x.get('name', '')}'") for x in parts if x.get('pct') not in (None, '') and x.get('on', True))
        if m['floor'] is None:
            m['floor'] = (d.get('property') or {}).get('floor')
        if m['rate'] is None:
            m['rate'] = next((w['cms'] for w in d.get('weekly') or [] if isinstance(w.get('cms'), (int, float))), None)
    else:
        for g in d.get('promoGroups') or []:
            m['groups'].append({'name': g.get('name', ''), 'mode': g.get('mode', 'single'),
                                'items': [{'name': it.get('name', ''), 'pct': pct_of(it.get('pct'), f"{name} promoGroups '{g.get('name', '')}'"),
                                           'on': bool(it.get('on'))} for it in g.get('items') or []]})
        for x in d.get('commissionParts') or []:
            if x.get('pct') in (None, '') or x.get('on') is False:
                continue
            v = pct_of(x['pct'], f"{name} commissionParts '{x.get('name', '')}'")
            if x.get('kind') == 'accel':
                m['a'] += v
            else:
                m['b'] += v
        if m['floor'] is None:
            m['floor'] = (d.get('property') or {}).get('floor') or (d.get('coef') or {}).get('floor')
        if m['rate'] is None:
            for r in d.get('rooms') or []:
                v = next((x for x in (r.get('rates') or {}).values() if isinstance(x, (int, float))), None)
                if v:
                    m['rate'] = v
                    break
        for pr in d.get('promotions') or []:
            if isinstance(pr, dict) and pr.get('countries'):
                m['countries'] += [c.strip() for c in re.split(r'[,/·]', str(pr['countries'])) if c.strip()]
    if not m['groups'] and not m['b']:
        m['why'] = 'property.json 에 promoGroups·commissionParts 가 비어 있음'
    elif not m['rate']:
        m['why'] = '판매가(rooms.rates 또는 프로필 rate)가 없음'
    else:
        m['ok'] = True
    return m


def pct_of(v, where):
    """property.json 의 할인·수수료 값 → 숫자. '10%' 같은 문자열도 받고, 못 읽으면 어느 칸인지 알려 준다."""
    if v is None or v == '':
        return 0.0
    if isinstance(v, (int, float)):
        return float(v)
    try:
        return float(str(v).replace('%', '').strip())
    except ValueError:
        raise ConfigError(f'{where} 의 값을 숫자로 읽지 못했습니다: {v!r}')


def gsum(g):
    on = [it for it in g['items'] if g['mode'] == 'locked' or it['on']]
    if g['mode'] == 'single':
        return on[0]['pct'] if on else 0.0
    return sum(it['pct'] for it in on)


def total_disc(m):
    ds = [gsum(g) for g in m['groups'] if gsum(g)]
    if m['across'] == 'mult':
        return 1 - math.prod(1 - x / 100 for x in ds)
    return sum(ds) / 100


def comm_factor(m):
    return (1 - m['b'] / 100) - m['a'] / 100 / m['T']


def payout(m, D):
    return m['rate'] * (1 - D) * comm_factor(m)


def with_extra(m, D, x):
    """현재 할인 D 에 x(0~1)를 더하거나 뺀 할인 합계.
    추가(x>0)는 새 프로모션이 붙는 것이라 부킹(곱셈)은 1−(1−D)(1−x), 나머지는 D+x.
    축소(x<0)는 화면의 할인 합계를 그대로 x%p 줄이는 것이라 두 구조 모두 D+x."""
    if x > 0 and m['across'] == 'mult':
        return 1 - (1 - D) * (1 - x)
    return D + x


def max_extra(m, D):
    """하한을 지키며 더 줄 수 있는 최대 할인(0~1). ota-payout-floor-design 의 총 할인 예산 = 1 − 하한/계수/판매가."""
    if m.get('floor') in (None, 0) or not m['ok']:
        return None
    cf = comm_factor(m)
    if cf <= 0:
        return None
    dmax = 1 - m['floor'] / (m['rate'] * cf)
    return (1 - (1 - dmax) / (1 - D)) if m['across'] == 'mult' else dmax - D


def find_item(m, kw):
    rx = re.compile(KW[kw], re.I)
    for g in m['groups']:
        for it in g['items']:
            if rx.search(it['name']):
                return g, it
    return None, None


def check(m, x):
    """할인 x(+면 추가, −면 축소)를 넣었을 때의 입금가와 하한 판정."""
    if not m or not m['ok']:
        return {'verdict': '확인 필요', 'why': (m or {}).get('why') or '이 채널의 OTA 프로필이 없음'}
    D = total_disc(m)
    D2 = min(0.99, max(0.0, with_extra(m, D, x)))
    now, new = payout(m, D), payout(m, D2)
    mx = max_extra(m, D)
    r = {'disc_now': round(D * 100, 1), 'disc_new': round(D2 * 100, 1), 'payout_now': int(round(now)), 'payout_new': int(round(new)),
         'rate': m['rate'], 'floor': m['floor'], 'max_extra': None if mx is None else round(mx * 100, 1)}
    if m['floor'] in (None, 0):
        r['verdict'] = '하한 미지정'
    elif new < m['floor']:
        r['verdict'] = '불가'
    elif new < m['floor'] * 1.05:
        r['verdict'] = '턱걸이'
    else:
        r['verdict'] = 'OK'
    return r


# ---------------------------------------------------------------- 추천 규칙 (references/rules.md 와 같은 표)
def recommend(S, models, th):
    recs = []
    step = th['step_pct'] / 100
    occ = S['occupancy']['by_weekday']
    empty = [w for w, v in occ.items() if v['occ'] is not None and v['occ'] <= th['empty_occ']]
    full = [w for w, v in occ.items() if v['occ'] is not None and v['occ'] >= th['full_occ']]

    def add(ch, rule, signal, action, setting, x=None, kw=None, note=''):
        m = models.get(ch)
        cur = ''
        if m and m['ok'] and kw == 'country':
            cur = '국가 타깃 중: ' + ('·'.join(m['countries']) if m['countries'] else '없음') + ' (새 국가 프로모션으로 계산)'
        elif m and m['ok'] and kw:
            g, it = find_item(m, kw)
            cur = f"{g['name']} › {it['name']} {it['pct']:g}%{'' if (g['mode'] == 'locked' or it['on']) else ' (꺼짐)'}" if it else '해당 프로모션 없음 — 새로 만들어야 함'
        r = {'channel': ch, 'rule': rule, 'signal': signal, 'action': action, 'setting': setting, 'current': cur, 'note': note}
        if x is not None:
            r['check'] = check(m, x)
            if r['check'].get('verdict') == '불가' and r['check'].get('max_extra') is not None:
                r['note'] = (note + ' ' if note else '') + f"하한을 지키는 최대 추가 할인 {max(0, r['check']['max_extra']):g}%p"
        recs.append(r)

    lead = S['cross']['channel_lead']['rows']
    los = S['cross']['channel_los']['rows']
    chs = {r['key']: r for r in S['dims']['channel']}
    for ch, row in lead.items():
        if ch not in models or row['n'] < th['min_n']:   # 프로필 ota 에 적은 채널만 (직접 판매 등은 뺀다)
            continue
        short = row.get('당일', 0) + row.get('1~3일', 0)
        if empty and short >= th['short_lead_share']:
            add(ch, '막판 할인', f"비는 요일 {'·'.join(empty)} · 이 채널 3일 이내 예약 {short:.0%}",
                f"{'·'.join(empty)} 투숙에 마감임박 할인 +{th['step_pct']}%p", '마감임박·당일·모바일 프로모션', step, 'last')
        if empty and row.get('31일+', 0) >= th['long_lead_share']:
            add(ch, '얼리버드', f"31일+ 전 예약 {row['31일+']:.0%} · 비는 요일 {'·'.join(empty)}",
                f"{'·'.join(empty)} 투숙에 얼리버드 +{th['step_pct']}%p", '얼리버드(사전 예약) 프로모션', step, 'early')
        lr = los.get(ch, {})
        longs = lr.get('3~6박', 0) + lr.get('7박+', 0)
        if longs >= th['long_stay_share']:
            add(ch, '연박', f"3박 이상 {longs:.0%}", f"연박 할인 또는 주간 요금제 +{th['step_pct']}%p", '연박·주간 요금제(ratePlans)', step, 'los')
        c = chs.get(ch, {}).get('cancel_rate')
        if c is not None and c >= th['cancel_rate']:
            add(ch, '취소율', f"취소율 {c:.0%}", '환불불가 요금제 비중을 늘리거나 무료 취소 기한을 앞당김', '요금제 취소 규정(ratePlans)')
    if full:   # 꽉 찬 요일마다 그 요일 비중이 큰 채널 3곳. 같은 채널은 요일을 묶어 한 건으로 낸다
        top = S['cross']['channel_weekday']['rows']
        hit = OrderedDict()
        for w in full:
            cand = sorted(((ch, r.get(w, 0)) for ch, r in top.items() if ch in models and r['n'] >= th['min_n']), key=lambda x: -x[1])[:3]
            for ch, sh in cand:
                hit.setdefault(ch, []).append((w, sh))
        for ch, ws in hit.items():
            days = '·'.join(w for w, _ in ws)
            add(ch, '꽉 찬 요일', ' · '.join(f"{w} 점유율 {occ[w]['occ']:.0%}, 이 채널 {w} 체크인 {sh:.0%}" for w, sh in ws),
                f"{days} 투숙 할인 −{th['step_pct']}%p (또는 요금 인상)", '해당 요일 프로모션·요금', -step)
    pr = S['dims'].get('party')
    if pr:
        big = sum(r['share'] for r in pr if r['key'] == '3인+')
        if big >= th['family_share']:
            add('전체', '가족·다인', f"3인 이상 예약 {big:.0%}", '다인 객실 노출과 인원별 요금(추가 인원 요금)을 점검', '객실·인원 요금')
    for ch, ex in S['extras'].items():
        if ch not in models or ex['n'] < th['min_n']:
            continue
        nat = ex['dims'].get('nationality')
        nat = [r for r in (nat or []) if not NAT_SKIP.search(r['key'])]   # 미상·묶음 값은 국가 타깃 대상이 아니다
        if nat:
            topn = max(nat, key=lambda r: r['share'])
            m = models.get(ch)
            nat_key = re.sub(r'\(.*?\)', '', topn['key']).strip()   # '중국(중화권)' → '중국'
            on_names = [it['name'] for g in (m or {}).get('groups', []) for it in g['items'] if g['mode'] == 'locked' or it['on']]
            done = bool(m and nat_key and any(nat_key in c for c in (m.get('countries') or []) + on_names))
            if topn['share'] >= th['nat_share']:
                if done:
                    add(ch, '국적 쏠림', f"{topn['key']} {topn['share']:.0%}", f"{topn['key']} 대상 프로모션이 이미 있음 — 할인율·기간만 점검", '국가 타깃 프로모션')
                else:
                    add(ch, '국적 쏠림', f"{topn['key']} {topn['share']:.0%}", f"{topn['key']} 대상 국가 타깃 프로모션 +{th['step_pct']}%p",
                        '국가 타깃 프로모션(promotions[].countries)', step, 'country')
        st = ex['dims'].get('los')
        if st:
            du = sum(r['share'] for r in st if r['key'] == '대실')
            if du >= th['dayuse_share']:
                add(ch, '대실 비중', f"대실 {du:.0%}", '비는 요일 대실 판매 시간(입실·퇴실 시각)과 대실 요금 조정을 검토 (제안만)', '국내 OTA 대실 상품')
        plan = ex['dims'].get('plan')
        if plan:
            for r in plan:
                if r['n'] >= th['min_n'] and (r.get('cancel_rate') or 0) >= th['cancel_rate']:
                    add(ch, '취소율', f"요금제 '{r['key']}' 취소율 {r['cancel_rate']:.0%}", '이 요금제의 무료 취소 기한을 앞당기거나 환불불가 요금제를 함께 노출', '요금제 취소 규정(ratePlans)')
    return recs


# ---------------------------------------------------------------- HTML
CSS = """:root{--bg:#f7f7f5;--surface:#fff;--text:#1d1d1b;--dim:#6b6b66;--line:#e2e1dc;--accent:#2a6fdb;--ok:#1f8a4c;--warn:#b7791f;--bad:#c53030;--sunk:#f0efeb}
@media (prefers-color-scheme:dark){:root:not([data-theme="light"]){--bg:#161615;--surface:#1f1f1d;--text:#ecebe6;--dim:#a3a29c;--line:#34332f;--accent:#6ea2f5;--ok:#58c58a;--warn:#e0b25a;--bad:#f07a7a;--sunk:#262624}}
:root[data-theme="dark"]{--bg:#161615;--surface:#1f1f1d;--text:#ecebe6;--dim:#a3a29c;--line:#34332f;--accent:#6ea2f5;--ok:#58c58a;--warn:#e0b25a;--bad:#f07a7a;--sunk:#262624}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--text);font:15px/1.55 -apple-system,'Segoe UI','Malgun Gothic',sans-serif}
main{max-width:1100px;margin:0 auto;padding:20px 16px 60px}h1{font-size:22px;margin:0 0 4px}h2{font-size:17px;margin:26px 0 8px}.sub{color:var(--dim);font-size:13px}
.tabs{display:flex;gap:6px;margin:18px 0;flex-wrap:wrap}.tabs button{font:inherit;padding:7px 14px;border:1px solid var(--line);border-radius:7px;background:var(--surface);color:var(--text);cursor:pointer}
.tabs button[aria-selected=true]{background:var(--accent);border-color:var(--accent);color:#fff}
.tiles{display:grid;grid-template-columns:repeat(auto-fill,minmax(150px,1fr));gap:10px}.tile{background:var(--surface);border:1px solid var(--line);border-radius:8px;padding:10px 12px}
.tile b{display:block;font-size:20px;font-variant-numeric:tabular-nums}.tile span{font-size:12px;color:var(--dim)}
.wrap{overflow-x:auto;background:var(--surface);border:1px solid var(--line);border-radius:8px}table{border-collapse:collapse;width:100%;font-size:13.5px}
th,td{padding:6px 9px;border-bottom:1px solid var(--line);text-align:right;white-space:nowrap;font-variant-numeric:tabular-nums}th{background:var(--sunk);font-weight:600}td.l,th.l{text-align:left;white-space:normal}
.tag{display:inline-block;padding:1px 7px;border-radius:9px;font-size:12px;border:1px solid currentColor}.ok{color:var(--ok)}.warn{color:var(--warn)}.bad{color:var(--bad)}.dim{color:var(--dim)}
.card{background:var(--surface);border:1px solid var(--line);border-radius:8px;padding:10px 14px;margin:0 0 10px}.ch{display:flex;justify-content:space-between;align-items:center;gap:8px;margin-bottom:6px}
.kv{display:flex;gap:10px;padding:3px 0;font-size:14px}.kv>span{flex:0 0 72px;color:var(--dim);font-size:12.5px;padding-top:2px}.kv>div{flex:1;min-width:0}
.note{font-size:12.5px;color:var(--dim);margin:6px 0}section[hidden]{display:none}"""


def esc(x):
    return html.escape('' if x is None else str(x))


def won(x):
    return '—' if x is None else f'{x:,.0f}'


def pct(x):
    return '—' if x is None else f'{x * 100:.0f}%'


def heat(x):
    """비중 칸 배경 (진할수록 큼)"""
    if not x:
        return ''
    return f' style="background:color-mix(in srgb,var(--accent) {min(60, int(x * 80))}%,transparent)"'


def table(head, rows, left=1):
    h = ''.join(f'<th{" class=l" if i < left else ""}>{esc(c)}</th>' for i, c in enumerate(head))
    b = ''.join('<tr>' + ''.join(c if str(c).startswith('<td') else f'<td{" class=l" if i < left else ""}>{c}</td>' for i, c in enumerate(r)) + '</tr>' for r in rows)
    return f'<div class="wrap"><table><thead><tr>{h}</tr></thead><tbody>{b}</tbody></table></div>'


def dist_table(rows, min_n):
    return table(['구분', '예약', '비중', '박수', '매출', '1박 평균', '취소율'],
                 [[esc(r['key']) + (' <span class="dim">(표본 적음)</span>' if r['n'] < min_n else ''), r['n'], pct(r['share']), r['nights'], won(r['revenue']), won(r['adr']), pct(r.get('cancel_rate'))] for r in rows])


def cross_table(cx, label):
    return table([label] + cx['cols'] + ['예약'], [[esc(k)] + [f'<td{heat(v.get(c))}>{pct(v.get(c))}</td>' for c in cx['cols']] + [v['n']] for k, v in cx['rows'].items()])


def render(S, recs, hotel, th):
    o = S['occupancy']
    tiles = [('기간', f"{S['period'][0]} ~ {S['period'][1]}"), ('유효 예약', f"{S['totals']['n']:,}건"), ('숙박 박수', f"{S['totals']['nights']:,}박"),
             ('매출', won(S['totals']['revenue']) + '원'), ('점유율', pct(o['occ'])), ('RevPAR', won(o['revpar']) + '원'), ('객단가(1박)', won(o['adr']) + '원')]
    t1 = '<div class="tiles">' + ''.join(f'<div class="tile"><span>{esc(a)}</span><b>{esc(b)}</b></div>' for a, b in tiles) + '</div>'
    names = {'channel': '채널', 'lead': '예약 시점(리드타임)', 'los': '박수', 'weekday': '체크인 요일', 'room': '객실 타입', 'party': '인원', 'plan': '요금 유형'}
    t1 += '<p class="note">취소 제외 기준. 취소율만 취소 포함. 1박 평균 = 숙박 금액 ÷ 박수(0원 예약 제외). 대실은 박수·점유율에서 뺀다.</p>'
    for k, label in names.items():
        if S['dims'].get(k):
            t1 += f'<h2>{label}</h2>' + dist_table(S['dims'][k], th['min_n'])
    for k, label in (('channel_lead', '채널 × 예약 시점'), ('channel_los', '채널 × 박수'), ('channel_weekday', '채널 × 체크인 요일')):
        t1 += f'<h2>{label}</h2><p class="note">행마다 가로 합 100%. 진할수록 비중이 크다.</p>' + cross_table(S['cross'][k], '채널')
    if S.get('monthly'):
        mo = S['monthly']
        t1 += '<h2>월별 추이 (체크인 월, 유효 예약 건수)</h2>' + table(['채널'] + mo['cols'], [[esc(k)] + [v.get(c, 0) for c in mo['cols']] for k, v in mo['rows'].items()])
    for ch, ex in S['extras'].items():
        t1 += f'<h2>{esc(ch)} 파일 — {ex["n"]:,}건 ({ex["period"][0]} ~ {ex["period"][1]} 체크인)</h2>'
        for k, label in (('nationality', '국적'), ('plan', '요금제'), ('meal', '식사'), ('promo', '프로모션'), ('party', '인원'), ('member', '회원등급'), ('coupon', '쿠폰'), ('los', '박수'), ('lead', '예약 시점')):
            if ex['dims'].get(k):
                t1 += f'<h3>{label}</h3>' + dist_table(ex['dims'][k], th['min_n'])
        if ex.get('nat_plan'):
            t1 += '<h3>국적 × 요금제</h3>' + cross_table(ex['nat_plan'], '국적')
    # 탭 2: 빈 객실
    def cls(v):
        return '' if v is None else ' class="bad"' if v <= th['empty_occ'] else ' class="ok"' if v >= th['full_occ'] else ''
    wd = o['by_weekday']
    t2 = (f'<p class="note">객실 {o["capacity"]}실 × {o["days"]}일. 빨강 = 점유율 {th["empty_occ"]:.0%} 이하(비는 날), 초록 = {th["full_occ"]:.0%} 이상(꽉 찬 날).</p>'
          + table(['요일', '날 수', '판매 객실박', '점유율', 'RevPAR', '객단가'],
                  [[w, v['days'], v['sold'], f'<td{cls(v["occ"])}>{pct(v["occ"])}</td>', won(v['revpar']), won(v['adr'])] for w, v in wd.items()]))
    if o['by_room_weekday']:
        cols = list(wd.keys())
        t2 += '<h2>객실 타입 × 요일 점유율</h2>' + table(['객실 타입'] + cols, [[esc(r)] + [f'<td{cls(v.get(c))}>{pct(v.get(c))}</td>' for c in cols] for r, v in o['by_room_weekday'].items()])
    if o['unknown_rooms']:
        t2 += f'<p class="note warn">프로필 rooms 에 없는 객실 타입은 점유율에서 뺐다 (객실박 {o["unknown_nights"]:,}): {esc(", ".join(o["unknown_rooms"]))}</p>'
    t2 += '<h2>날짜별</h2>' + table(['날짜', '요일', '판매 객실박', '점유율'], [[d['date'], d['wd'], d['sold'], f'<td{cls(d["occ"])}>{pct(d["occ"])}</td>'] for d in o['daily']])
    # 탭 3: 채널별 할 일
    vc = {'OK': 'ok', '턱걸이': 'warn', '불가': 'bad'}
    cards = []
    order = list(OrderedDict.fromkeys(r['channel'] for r in recs))
    for ch in order:   # 채널별로 묶어 카드로 보여 준다 (표는 열이 많아 좁은 화면에서 읽기 어렵다)
        cards.append(f'<h2>{esc(ch)}</h2>')
        for r in [x for x in recs if x['channel'] == ch]:
            c = r.get('check') or {}
            ver = c.get('verdict', '')
            lines = [('근거', esc(r['signal'])), ('할 일', f"<b>{esc(r['action'])}</b>"), ('대상 설정', esc(r['setting']))]
            if r['current']:
                lines.append(('지금 설정', esc(r['current'])))
            if 'payout_new' in c:
                lines.append(('할인 합계', f"{c['disc_now']:g}% → {c['disc_new']:g}%"))
                lines.append(('입금가', f"{won(c['payout_now'])}원 → <b>{won(c['payout_new'])}원</b> (판매가 {won(c['rate'])}원 · 하한 {won(c['floor'])}원)"))
            elif c.get('why'):
                lines.append(('검산', esc(c['why'])))
            if r['note']:
                lines.append(('메모', esc(r['note'])))
            body = ''.join(f'<div class="kv"><span>{a}</span><div>{b}</div></div>' for a, b in lines)
            cards.append(f'<div class="card"><div class="ch"><b>{esc(r["rule"])}</b><span class="tag {vc.get(ver, "dim")}">{esc(ver or "정보")}</span></div>{body}</div>')
    t3 = ('<p class="note">실제 설정은 바꾸지 않는다. 각 OTA 콘솔에서 값을 넣어 다시 확인한 뒤 사용자가 직접 적용한다. '
          f'입금가 = 판매가 × (1 − 할인 합계) × 수수료 계수. 할인 폭 기본값 {th["step_pct"]}%p. '
          '판정: OK = 하한보다 5% 이상 여유 · 턱걸이 = 5% 이내 · 불가 = 하한 미달 · 확인 필요 = OTA 값이 없어 검산 못 함 · 정보 = 할인과 관계없는 제안.</p>'
          + (''.join(cards) if cards else '<p>규칙에 걸린 항목이 없다. 프로필 thresholds 를 확인하라.</p>'))
    m = S['models']
    t3 += '<h2>검산에 쓴 OTA 값</h2>' + table(['채널', '종류', '판매가', '할인 합계', '수수료', '하한', '상태'],
        [[esc(k), esc(v['kind']), won(v['rate']), f"{v['disc']:g}%" if v.get('disc') is not None else '—', f"{v['b']:g}%" + (f" + {v['a']:g}%" if v['a'] else ''),
          won(v['floor']), esc('사용' if v['ok'] else v['why'])] for k, v in m.items()])
    warn = ''.join(f'<p class="note warn">{esc(w)}</p>' for w in S['warnings'])
    return f"""<!doctype html><html lang="ko"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>손님 유형 분석</title><style>{CSS}</style></head><body><main>
<h1>{esc(hotel)} 손님 유형 → OTA 설정</h1><div class="sub">만든 시각 {esc(S['generated'])} · 판단 지표 RevPAR(판매 가능 객실 1실당 매출) · 예약번호·이름은 들어 있지 않음</div>{warn}
<div class="tabs" role="tablist"><button role="tab" aria-selected="true" data-t="a">손님 분포</button><button role="tab" aria-selected="false" data-t="b">빈 객실</button><button role="tab" aria-selected="false" data-t="c">채널별 할 일 ({len(recs)})</button></div>
<section id="a">{t1}</section><section id="b" hidden>{t2}</section><section id="c" hidden>{t3}</section>
<script>document.querySelector('.tabs').onclick=function(e){{var b=e.target.closest('button');if(!b)return;
document.querySelectorAll('.tabs button').forEach(function(x){{x.setAttribute('aria-selected',String(x===b))}});
document.querySelectorAll('main>section').forEach(function(s){{s.hidden=s.id!==b.dataset.t}})}};</script></main></body></html>"""


# ---------------------------------------------------------------- 실행
def build(A):
    mp = read_json(A.mapping, '--mapping')
    prof = read_json(A.profile, '--profile')
    base_dir = os.path.dirname(os.path.abspath(A.profile))
    th = {**DEFAULT_TH, **(prof.get('thresholds') or {})}
    rooms = {k: int(v) for k, v in (prof.get('rooms') or {}).items() if v}
    warnings = []
    if not rooms:
        warnings.append('프로필 rooms(객실 타입별 실수)가 없어 점유율·RevPAR 를 계산하지 못했다.')
    df = load_pms(A.pms, mp)
    start, end = period_of(A, df)
    log.info('기간 %s ~ %s', start.date(), end.date())
    inp = df[(df['_ci'].dt.normalize() >= start) & (df['_ci'].dt.normalize() <= end)].copy()
    if inp.empty:
        raise ConfigError(f'{start.date()} ~ {end.date()} 에 체크인한 예약이 없습니다')
    v = inp[~inp['_can']]
    S = {'generated': pd.Timestamp.now().strftime('%Y-%m-%d %H:%M'), 'period': [str(start.date()), str(end.date())],
         'totals': agg(v, inp), 'dims': {}, 'cross': {}, 'extras': {}, 'warnings': warnings}
    S['dims']['channel'] = sorted(dist(inp, '_ch'), key=lambda r: -r['n'])
    S['dims']['lead'] = dist(inp[inp['_stay']], '_lb', LB)
    S['dims']['los'] = dist(inp, '_los', LOS)
    S['dims']['weekday'] = dist(inp, '_wd', WD)
    S['dims']['room'] = sorted(dist(inp, '_room'), key=lambda r: -r['n'])
    if '_party' in inp:
        S['dims']['party'] = dist(inp, '_party', ['1인', '2인', '3인+'])
    if inp.get('_plan') is not None and '요금 유형' in inp:
        S['dims']['plan'] = sorted(dist(inp, '_plan'), key=lambda r: -r['n'])
    st = inp[inp['_stay']]
    S['cross']['channel_lead'] = cross(st, '_ch', '_lb', LB)
    S['cross']['channel_los'] = cross(inp, '_ch', '_los', LOS)
    S['cross']['channel_weekday'] = cross(inp, '_ch', '_wd', WD)
    months = df['_ci'].dt.to_period('M').astype(str)
    if months.nunique() > 1:
        mm = df.assign(_m=months)
        S['monthly'] = cross(mm, '_ch', '_m', sorted(set(months)))
        for k, r in S['monthly']['rows'].items():   # 비중 대신 건수
            g = mm[(~mm['_can']) & (mm['_ch'] == k)]
            for c in S['monthly']['cols']:
                r[c] = int((g['_m'] == c).sum())
    S['occupancy'] = occupancy(df, start, end, rooms) if rooms else {'by_weekday': {}, 'by_room_weekday': {}, 'daily': [], 'unknown_rooms': [], 'unknown_nights': 0, 'occ': None, 'revpar': None, 'adr': None, 'capacity': 0, 'days': 0, 'sold': 0}
    for spec in A.extra or []:
        if '=' not in spec:
            raise ConfigError(f'--extra 는 채널=파일 형식입니다: {spec}')
        ch, path = spec.split('=', 1)
        ex = load_extra(ch.strip(), path.strip(), mp)
        xs = parse_day(A.extra_start, '--extra-start') if A.extra_start else start   # 국적처럼 표본이 적은 축은 더 긴 기간으로 본다
        ex = ex[(ex['_ci'].dt.normalize() >= xs) & (ex['_ci'].dt.normalize() <= end)]
        if ex.empty:
            warnings.append(f'{ch} 파일에 {xs.date()} ~ {end.date()} 체크인이 없다.')
            continue
        e = {'n': int((~ex['_can']).sum()), 'dims': {}, 'period': [str(xs.date()), str(end.date())]}
        for col, key in (('국적', 'nationality'), ('요금제', 'plan'), ('식사', 'meal'), ('프로모션', 'promo'), ('회원등급', 'member'), ('쿠폰', 'coupon')):
            if col in ex:
                e['dims'][key] = sorted(dist(ex.assign(**{col: ex[col].replace('', '(없음)')}), col), key=lambda r: -r['n'])[:15]
        if '_party' in ex:
            e['dims']['party'] = dist(ex, '_party', ['1인', '2인', '3인+'])
        e['dims']['los'] = dist(ex, '_los', LOS)
        if ex['_cr'].notna().any():
            e['dims']['lead'] = dist(ex[ex['_stay']], '_lb', LB)
        if '국적' in ex and '요금제' in ex:
            e['nat_plan'] = cross(ex, '국적', '요금제')
        S['extras'][ch.strip()] = e
    models = {}
    for name, conf in (prof.get('ota') or {}).items():
        try:
            models[name] = ota_model(name, conf, base_dir)
        except ConfigError as err:
            warnings.append(str(err))
            log.warning('%s', err)
    S['models'] = {k: {kk: m[kk] for kk in ('kind', 'rate', 'floor', 'b', 'a', 'ok', 'why')} | {'disc': round(total_disc(m) * 100, 1) if m['ok'] else None}
                   for k, m in models.items()}
    recs = recommend(S, models, th)
    log.info('추천 %d건', len(recs))
    os.makedirs(A.out_dir, exist_ok=True)
    out = {**S, 'recommendations': recs, 'thresholds': th}
    with open(os.path.join(A.out_dir, 'segments.json'), 'w', encoding='utf-8') as fh:
        json.dump(out, fh, ensure_ascii=False, indent=1, default=str)
    with open(os.path.join(A.out_dir, 'report.html'), 'w', encoding='utf-8') as fh:
        fh.write(render(S, recs, prof.get('hotel') or mp.get('hotel_name') or '숙소', th))
    log.info('저장: %s', os.path.abspath(A.out_dir))
    return out


def parse_args():
    ap = argparse.ArgumentParser(description='예약 데이터 → 손님 유형 → OTA 설정 추천')
    ap.add_argument('--pms', required=True, help='PMS 예약 내보내기 (xlsx·csv)')
    ap.add_argument('--mapping', required=True, help='열 매핑 JSON (scripts/mapping-template.json)')
    ap.add_argument('--profile', required=True, help='숙소 프로필 JSON (assets/profile.example.json)')
    ap.add_argument('--out-dir', required=True)
    ap.add_argument('--month', help='YYYY-MM (체크인 기준)')
    ap.add_argument('--start')
    ap.add_argument('--end')
    ap.add_argument('--extra', action='append', help='채널=파일 (매핑 extras 에 같은 channel 항목 필요). 여러 번 쓸 수 있다')
    ap.add_argument('--extra-start', help='채널 파일만 이 날짜(YYYY-MM-DD)부터 본다. 끝은 분석 기간 끝과 같다')
    ap.add_argument('--log')
    ap.add_argument('--debug', action='store_true')
    return ap.parse_args()


def main():
    try:
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
        sys.stderr.reconfigure(encoding='utf-8', errors='replace')
    except AttributeError as e:
        print(f'출력 인코딩을 바꾸지 못했습니다: {e}', file=sys.stderr)
    A = parse_args()
    handlers = [logging.StreamHandler(sys.stderr)] + ([logging.FileHandler(A.log, encoding='utf-8')] if A.log else [])
    logging.basicConfig(level=logging.DEBUG if A.debug else logging.INFO, format='%(asctime)s %(levelname)s %(message)s', handlers=handlers)
    try:
        build(A)
    except ConfigError as e:
        log.error('%s', e)
        return 2
    except PermissionError as e:
        log.error('파일을 쓸 수 없습니다 (다른 프로그램에서 열려 있는지 확인): %s', e.filename)
        return 1
    except Exception as e:   # 예상 못 한 오류: 값이 로그에 새지 않게 종류만 남기고, --debug 때만 전체 추적
        log.error('처리 실패: %s (자세히 보려면 --debug)', type(e).__name__)
        log.debug('추적', exc_info=True)
        return 1
    return 0


if __name__ == '__main__':
    sys.exit(main())
