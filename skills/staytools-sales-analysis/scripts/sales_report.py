#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""숙소 월간 매출분석 빌더 1.0.0 (staytools-sales-analysis)
PMS 예약 내보내기(xlsx) -> 채널별 매출분석 엑셀 (대시보드 + 차트 + 히트맵 + 전월 대비)

사용:
  python sales_report.py --input 예약내보내기.xlsx --config mapping.json --out 분석.xlsx
      [--month YYYY-MM] [--basis sched|pms] [--hotel 숙소명]
      [--prev prev.json] [--sched sched.json] [--prod prod.json] [--nat nat.json]
      [--billing billing.json] [--billing-acc billing_acc.json]
      [--findings findings.json] [--summary summary.json] [--agg-out agg.json]
      [--min-n 20] [--exported-at "YYYY-MM-DD HH:MM"] [--log 로그파일] [--debug]

  재계산 뒤 처리 (LibreOffice 재계산이 있을 때만):
  python sales_report.py --postfix 재계산.xlsx 최종.xlsx [summary.json]

  --config   열 매핑·채널 규칙·객실 타입·숙소명·기준 월 JSON (mapping-yflux.json, mapping-template.json 참고)
  --month    YYYY-MM  예정 체크인일(보정 후)이 이 달인 예약만 남김. 없으면 설정의 month, 그것도 없으면 파일 전체
  --basis    sched(기본) = 예정 체크인일로 달을 나눔 / pms = 내보내기의 체크인 열 그대로 (PMS 화면 검색과 같음)
  --sched    {"예약번호": {"a": "YYYY-MM-DD", "n": 박수}}  내보내기의 체크인이 실제 입실 시각일 때 쓰는 예정일 보정
  --prod     {"예약번호": {"p": "상품명", "t": "판매 객실"}}  내보내기의 객실 타입이 배정 방일 때 쓰는 판매 기준 자료
  --nat      {"예약번호": "KOR"}  채널이 넘겨준 국적 코드
  --prev     전월 거래처별 집계 (전 달의 --agg-out 결과를 그대로 쓸 수 있음)
  --billing  청구(매출) 보고서 대조 {"total":..,"parts":[["객실",..],..],"conditions":..,"fetched_at":..,
             "lines":[{"id":예약번호,"acc":거래처,"stay":"MM/DD~MM/DD","b":그 달 보고서 금액,"why":"next|prev|walkin|late|early|etc"}]}
  --billing-acc  청구 보고서 거래처별 매출 {"cur":{거래처:원},"prev":{거래처:원},"cur_total":..,"prev_total":..}
             넣으면 대시보드 매출이 보고서 기준(손님이 묵은 날)이 됨
수식이 들어간 파일이므로 엑셀에서 열면 계산됨. 표준 라이브러리 외에 pandas, numpy, openpyxl 이 필요함.
고객 이름·연락처 열은 읽지 않음. 설정에 매핑된 열만 메모리에 남긴다.
"""
import argparse, json, logging, math, os, re, sys
from collections import OrderedDict
import numpy as np
import pandas as pd
from openpyxl import Workbook
from openpyxl.chart import BarChart, Reference
from openpyxl.chart.label import DataLabelList
from openpyxl.chart.legend import Legend
from openpyxl.chart.marker import DataPoint
from openpyxl.chart.shapes import GraphicalProperties
from openpyxl.chart.text import RichText
from openpyxl.drawing.line import LineProperties
from openpyxl.drawing.text import CharacterProperties, Font as DFont, Paragraph, ParagraphProperties
from openpyxl.formatting.rule import CellIsRule, ColorScaleRule, DataBarRule, FormulaRule
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter as L
from openpyxl.worksheet.pagebreak import Break

log = logging.getLogger('sales_report')

# 표준 항목: 필수 / 선택 (설정 columns 의 왼쪽 이름)
REQUIRED_COLS = ['예약 번호', '거래처', '체크인', '체크아웃', '예약 생성일', '예약 상태']
OPTIONAL_COLS = {'이용 유형': '', '객실': '', '객실 타입': '(미지정)', '예약 생성 경로': '', '성인': '0', '유아동': '0', '잔액': '0'}
AMOUNT_COLS = ['총 청구 금액', '예약 금액']   # 둘 중 하나는 필수. 예약 금액 = 잔액 없이 금액 열 하나로 끝나는 PMS
# 개인정보 열을 잘못 매핑하면 멈춘다
PII_RE = re.compile(r'이름|성명|고객명|투숙객|예약자|전화|휴대폰|연락처|이메일|주민|여권|e-?mail|phone|mobile|guest.?name|passport', re.I)
DEFAULT_GROUPS = ['국내 OTA', '해외 OTA', '직접 판매', '기업·기관']


class ConfigError(Exception):
    """사용자가 고칠 수 있는 입력·설정 오류"""


def read_json(path, label):
    """UTF-8 JSON 읽기 (메모장이 붙인 BOM 허용). 실패하면 어느 파일인지 알려 준다."""
    try:
        with open(path, encoding='utf-8-sig') as fh:
            return json.load(fh)
    except FileNotFoundError:
        raise ConfigError(f'{label} 파일이 없습니다: {path}')
    except json.JSONDecodeError as e:
        raise ConfigError(f'{label} 파일이 올바른 JSON이 아닙니다: {path} ({e.lineno}행 {e.colno}열)')


def opt_json(path, label):
    return read_json(path, label) if path else None


def write_json(path, obj, **kw):
    with open(path, 'w', encoding='utf-8') as fh:
        json.dump(obj, fh, ensure_ascii=False, indent=1, **kw)


def load_config(path):
    """매핑 JSON을 읽어 검증하고 기본값을 채운다."""
    cfg = read_json(path, '--config')
    if not isinstance(cfg, dict):
        raise ConfigError('--config 는 JSON 객체여야 합니다')
    cols = cfg.get('columns')
    if not isinstance(cols, dict):
        raise ConfigError('설정에 columns 가 없습니다 (표준 항목 -> 내 PMS 열 이름)')
    cols = {k: v for k, v in cols.items() if v}   # 빈 칸 = 그 열이 없는 PMS
    miss = [k for k in REQUIRED_COLS if k not in cols]
    if miss:
        raise ConfigError(f'설정 columns 에 필수 항목이 없습니다: {miss}')
    if not any(k in cols for k in AMOUNT_COLS):
        raise ConfigError(f'설정 columns 에 금액 항목이 없습니다: {AMOUNT_COLS} 중 하나를 넣으세요')
    allowed = set(REQUIRED_COLS) | set(OPTIONAL_COLS) | set(AMOUNT_COLS)
    extra = [k for k in cols if k not in allowed]
    if extra:
        raise ConfigError(f'설정 columns 에 모르는 표준 항목이 있습니다: {extra}')
    pii = [v for v in cols.values() if PII_RE.search(str(v))]
    if pii:
        raise ConfigError(f'개인정보로 보이는 열은 매핑할 수 없습니다: {pii}')
    cfg['columns'] = cols
    vals = cfg.get('values') or {}
    cfg['stay_values'] = list(vals.get('stay') or ['숙박'])
    cfg['cancel_keywords'] = list(vals.get('cancel_keywords') or ['취소', '노쇼'])
    cfg['channel_booking_values'] = list(vals.get('channel_booking') or ['채널 예약'])
    cfg['groups'] = list(cfg.get('groups') or DEFAULT_GROUPS)
    cfg['room_types'] = list(cfg.get('room_types') or [])
    cfg['product_families'] = list(cfg.get('product_families') or [])
    cfg['corporate_accounts'] = set(cfg.get('corporate_accounts') or [])
    rules = cfg.get('channels') or []
    for i, rule in enumerate(rules):
        if not rule.get('channel') or not rule.get('group'):
            raise ConfigError(f'설정 channels {i + 1}번째 줄에 channel·group 이 없습니다')
        if not rule.get('match') and not rule.get('contains'):
            raise ConfigError(f"설정 channels '{rule['channel']}' 에 match·contains 가 모두 없습니다")
    cfg['channels'] = rules
    cfg['verified'] = bool(cfg.get('verified', False))
    cfg['pms_name'] = cfg.get('pms_name') or '미지정 PMS'
    return cfg


def find_rule(acc, rules):
    """거래처 -> 채널 규칙 (정확히 같은 이름 먼저, 그다음 포함). 반환: (순번, 규칙) 또는 (None, None)"""
    for i, rule in enumerate(rules):
        if acc in (rule.get('match') or []):
            return i, rule
    for i, rule in enumerate(rules):
        if any(k and k in str(acc) for k in (rule.get('contains') or [])):
            return i, rule
    return None, None


def rule_memo(rule):
    """근거·메모 칸: 숙소가 입력한 수수료·쿠폰 부담·부가세 기준을 그대로 보여 준다 (계산에는 쓰지 않음)."""
    parts = [rule.get('note') or '']
    for key, label in (('commission', '수수료'), ('coupon_burden', '쿠폰 부담'), ('vat', '부가세')):
        if rule.get(key):
            parts.append(f'{label}: {rule[key]}')
    return ' · '.join(p for p in parts if p)


def rk(x):
    """예약번호 비교 키: 숫자면 앞 0·소수점 없는 문자열, 아니면 글자 그대로"""
    s = str(x).strip()
    return str(int(s.split('.')[0])) if re.fullmatch(r'\d+(\.0+)?', s) else s


def rid(x):
    """엑셀에 넣을 예약번호 값"""
    k = rk(x)
    return int(k) if k.isdigit() else k


def dtv(v):
    """날짜 셀 값 (빈 날짜는 빈칸)"""
    return None if pd.isna(v) else v.to_pydatetime()


def read_export(path, cfg):
    """내보내기를 읽어 표준 항목 이름으로 바꾼다. 매핑하지 않은 열은 버린다."""
    cols = cfg['columns']
    header = int(cfg.get('header_row') or 1) - 1
    try:
        raw = pd.read_excel(path, sheet_name=cfg.get('sheet') or 0, header=header, dtype=str).fillna('')
    except FileNotFoundError:
        raise ConfigError(f'--input 파일이 없습니다: {path}')
    except ValueError as e:
        raise ConfigError(f'--input 을 읽지 못했습니다: {e}')
    raw.columns = [str(c).strip() for c in raw.columns]
    miss = [v for v in cols.values() if v not in raw.columns]
    if miss:
        raise ConfigError(f'내보내기 파일에 매핑한 열이 없습니다: {miss} (header_row·열 이름 확인)')
    out = pd.DataFrame({k: raw[v] for k, v in cols.items()})
    for k, default in OPTIONAL_COLS.items():
        if k not in out.columns:
            out[k] = default
    if '총 청구 금액' not in out.columns:
        out['총 청구 금액'] = out['예약 금액']
    log.info('내보내기 읽음: %d행, 매핑 %d열', len(out), len(cols))
    return out


def postfix(src, dst, summary=None):
    """LibreOffice 재계산 뒤 처리: 차트 데이터 레이블의 사용자 서식(예: 7% 미만 숨김, '건')이
    LO 저장 시 '원본 연결(sourceLinked=1)'로 바뀌어 무시되는 것을 되돌리고, KPI를 pandas 요약과 대조."""
    import zipfile
    from openpyxl import load_workbook
    n = 0
    with zipfile.ZipFile(src) as zin, zipfile.ZipFile(dst + '.tmp', 'w', zipfile.ZIP_DEFLATED) as zout:
        for item in zin.infolist():
            data = zin.read(item.filename)
            if item.filename.startswith('xl/charts/chart') and item.filename.endswith('.xml'):
                t, k = re.subn(r'(<c:dLbls><c:numFmt formatCode="[^"]*" sourceLinked=")1(")', r'\g<1>0\2', data.decode('utf-8'))
                n += k
                data = t.encode('utf-8')
            zout.writestr(item, data)
    os.replace(dst + '.tmp', dst)
    log.info('차트 레이블 서식 복구: %d곳', n)
    if summary:
        s = read_json(summary, 'summary')['total']
        wb_ = load_workbook(dst, data_only=True, read_only=True)
        kv = {r[0]: r[1] for r in wb_['차트데이터'].iter_rows(min_row=5, max_row=10, max_col=2, values_only=True)}
        chk = [('총 매출(만원)', (kv.get('총 매출(만원)') or 0) * 10000, s['매출'], 1), ('유효 예약(건)', kv.get('유효 예약(건)'), s['유효'], 0),
               ('숙박 박수(박)', kv.get('숙박 박수(박)'), s['박수'], 0), ('1박 평균(원)', kv.get('1박 평균(원)'), s['1박평균'], 1),
               ('취소율', kv.get('취소율'), s['취소율'], 0.0001), ('당일 예약 비중(숙박)', kv.get('당일 예약 비중(숙박)'), s['당일비중'], 0.0001)]
        bad = [k for k, a, b, tol in chk if a is None or abs(a - b) > tol]
        errs = 0
        for ws_ in wb_.worksheets:
            for row in ws_.iter_rows(values_only=True):
                errs += sum(1 for v in row if isinstance(v, str) and v.startswith('#') and v.rstrip('!?/0').upper() in ('#REF', '#DIV', '#VALUE', '#NAME', '#N/A', '#NUM', '#NULL'))
        print('KPI 대조:', '일치' if not bad else f'불일치 {bad}', '| 오류 셀:', errs)


def parse_args():
    ap = argparse.ArgumentParser(description='PMS 예약 내보내기 -> 월간 채널별 매출분석 엑셀')
    ap.add_argument('--input', required=True, help='PMS 예약 내보내기 xlsx')
    ap.add_argument('--config', required=True, help='열 매핑·채널 규칙 JSON')
    ap.add_argument('--out', required=True, help='만들 엑셀 경로')
    ap.add_argument('--nat')
    ap.add_argument('--sched')
    ap.add_argument('--prod')
    ap.add_argument('--month')
    ap.add_argument('--basis', choices=['sched', 'pms'], default='sched')
    ap.add_argument('--prev')
    ap.add_argument('--billing')
    ap.add_argument('--billing-acc')
    ap.add_argument('--findings')
    ap.add_argument('--summary')
    ap.add_argument('--agg-out')
    ap.add_argument('--hotel')
    ap.add_argument('--exported-at')
    ap.add_argument('--min-n', type=int, default=20)
    ap.add_argument('--log', help='로그를 파일에도 남길 경로')
    ap.add_argument('--debug', action='store_true', help='오류의 전체 추적 내용을 로그에 남김')
    return ap.parse_args()


def build(A, CFG):
    """매출분석 엑셀을 만든다. 숫자는 대부분 엑셀 수식이고 pandas 집계는 정렬·요약용."""
    MIN_N = A.min_n
    HOTEL = A.hotel or CFG.get('hotel_name') or '우리 숙소'
    MONTH = A.month or CFG.get('month') or None
    RULES = CFG['channels']
    CORP_KNOWN = CFG['corporate_accounts']
    CANCEL_KW = CFG['cancel_keywords']
    CHAN_VALUES = CFG['channel_booking_values']
    HAS_PATH = '예약 생성 경로' in CFG['columns']
    FAMILIES = CFG['product_families']
    PMS_LABEL = CFG['pms_name']
    if not CFG['verified']:
        log.warning('미검증 매핑입니다 (%s). 결과를 PMS 보고서 합계와 대조하세요.', PMS_LABEL)

    # =====================================================================
    # 1) 분류 기준 (거래처 -> 채널, 대분류, 금액 기준): 설정 channels 에서 옴
    #    기준코드: 입금가(OTA 수수료 뗀 뒤 받는 돈) / 판매가(손님 결제액, 수수료 별도 청구) / 실수령(직접 받은 돈) / 확인필요
    # =====================================================================
    GROUP_ORDER = CFG['groups']
    COUNTRY = {'KOR': '한국', 'CHN': '중국', 'USA': '미국', 'JPN': '일본', 'TWN': '대만', 'HKG': '홍콩', 'MAC': '마카오', 'THA': '태국',
               'VNM': '베트남', 'PHL': '필리핀', 'SGP': '싱가포르', 'MYS': '말레이시아', 'IDN': '인도네시아', 'IND': '인도', 'MNG': '몽골',
               'AUS': '호주', 'NZL': '뉴질랜드', 'GBR': '영국', 'DEU': '독일', 'FRA': '프랑스', 'ITA': '이탈리아', 'ESP': '스페인',
               'NLD': '네덜란드', 'CAN': '캐나다', 'MEX': '멕시코', 'BRA': '브라질', 'RUS': '러시아', 'KAZ': '카자흐스탄',
               'UZB': '우즈베키스탄', 'GUM': '괌(미국령)', 'ZAF': '남아공', 'ARE': 'UAE', 'TUR': '튀르키예'}


    def classify(acc, chan_share=0.0):
        """반환: (채널, 대분류, 금액기준, 기준코드, 근거, 자동분류여부)"""
        _i, rule = find_rule(acc, RULES)
        if rule:
            return (rule['channel'], rule['group'], rule.get('basis_text') or '확인 필요', rule.get('basis') or '확인필요', rule_memo(rule), False)
        if acc in CORP_KNOWN:
            return ('기업·기관', '기업·기관', '실수령 (청구 금액)', '실수령', '', False)
        if chan_share >= 0.5:
            return (acc, '기타 OTA', '확인 필요', '확인필요', '자동 분류 — 채널 예약으로 들어온 처음 보는 거래처. 맞는 채널·대분류로 고치세요', True)
        if not HAS_PATH:
            return (acc, '기타', '확인 필요', '확인필요', '자동 분류 — 처음 보는 거래처. 맞는 채널·대분류로 고치세요', True)
        return ('기업·기관', '기업·기관', '실수령 (청구 금액) 추정', '실수령', '자동 분류 — 처음 보는 거래처라 기업·기관으로 넣음. 다르면 고치세요', True)


    # =====================================================================
    # 2) 데이터 읽기
    # =====================================================================
    df = read_export(A.input, CFG)
    num = lambda s: int(round(float(re.sub(r'[^\d.\-]', '', str(s)) or 0)))
    df['_paid'] = df['총 청구 금액'].map(num)   # 내보내기의 '총 청구 금액'은 실제로 받은(결제된) 금액
    df['_bal'] = df['잔액'].map(num)            # 잔액 = 매출 - 받은 돈 (덜 받으면 +, 더 받으면 -)
    df['_amt'] = df['_paid'] + df['_bal']       # 매출 = 받은 돈 + 잔액
    df['_ci'] = pd.to_datetime(df['체크인'], errors='coerce', format='mixed')
    df['_co'] = pd.to_datetime(df['체크아웃'], errors='coerce', format='mixed')
    df['_cr'] = pd.to_datetime(df['예약 생성일'], errors='coerce', format='mixed')
    _bad = df['_ci'].isna() | df['_cr'].isna()
    N_BAD = int(_bad.sum())
    if N_BAD:   # 합계 줄·날짜 없는 줄은 건수만 남기고 뺀다
        log.warning('체크인·예약 생성일을 읽지 못한 %d행을 뺐습니다', N_BAD)
        df = df[~_bad].reset_index(drop=True)
    if df.empty:
        raise ConfigError('읽을 수 있는 예약이 없습니다 (날짜 열 매핑을 확인하세요)')
    df['_can'] = df['예약 상태'].str.contains('|'.join(re.escape(k) for k in CANCEL_KW), case=False, regex=True)
    df['_stay'] = df['이용 유형'].isin(CFG['stay_values']) if '이용 유형' in CFG['columns'] else pd.Series(True, index=df.index)
    df['_type'] = np.where(df['_stay'], '숙박', df['이용 유형'].replace('', '대실'))
    sched = {rk(k): v for k, v in (opt_json(A.sched, '--sched') or {}).items()}


    def sched_row(rw):
        k = rk(rw['예약 번호'])
        ci, co = rw['_ci'].normalize(), rw['_co'].normalize()
        if rw['_stay']:
            if k in sched:
                a = pd.Timestamp(sched[k]['a'])
                n = max(1, int(sched[k]['n']))
                return a, a + pd.Timedelta(days=n), n, 1
            n = max(1, (co - ci).days)
            return ci, ci + pd.Timedelta(days=n), n, 0
        return ci, co, 0, 0


    _t = df.apply(sched_row, axis=1, result_type='expand')
    df['_sa'], df['_sd'], df['_n'], df['_fix'] = _t[0], _t[1], _t[2].astype(int), _t[3].astype(int)
    df = df.sort_values(['_sa', '예약 번호']).reset_index(drop=True)
    PMS_BASIS = A.basis == 'pms'
    df['_pd'] = df['_ci'].dt.normalize() if PMS_BASIS else df['_sa']   # 기간을 거르는 날짜
    N_OUT = 0
    if MONTH:
        _keep = df['_pd'].dt.to_period('M') == pd.Period(MONTH, 'M')
        N_OUT = int((~_keep).sum())
        df = df[_keep].reset_index(drop=True)
        if df.empty:
            raise ConfigError(f'{MONTH} 에 해당하는 예약이 없습니다 (기준 월·파일 기간을 확인하세요)')
    N_FIX = int(df['_fix'].sum())
    df['_lead'] = (df['_sa'] - df['_cr'].dt.normalize()).dt.days
    LB = ['당일', '1~3일', '4~7일', '8~30일', '31일+']
    df['_lb'] = pd.cut(df['_lead'], [-10**6, 0, 3, 7, 30, 10**6], labels=LB).astype(str)
    WD = ['월', '화', '수', '목', '금', '토', '일']
    df['_wd'] = df['_sa'].dt.weekday.map(lambda i: WD[i])
    LOS = ['1박', '2박', '3~6박', '7박+']
    df['_los'] = np.where(~df['_stay'], '대실', np.where(df['_n'] == 1, '1박', np.where(df['_n'] == 2, '2박', np.where(df['_n'] <= 6, '3~6박', '7박+'))))
    prod = {}
    prod = {rk(k): v for k, v in (opt_json(A.prod, '--prod') or {}).items()}
    _pk = df['예약 번호'].map(rk)
    df['_prod'] = [prod.get(k, {}).get('p', '') for k in _pk]
    df['_sold'] = [prod[k]['t'] if k in prod and prod[k].get('t') else t for k, t in zip(_pk, df['객실 타입'])]
    df['_moved'] = (df['_prod'] != '') & (df['_sold'] != df['객실 타입'])


    def pfam(pn, sold):  # 상품 묶음: 설정 product_families 에 걸리면 그 이름, 아니면 판매 객실 타입 그대로
        if not pn:
            return ''
        for fam in FAMILIES:
            if any(k in pn for k in fam.get('contains', [])):
                return fam['name']
        return sold


    df['_pfam'] = [pfam(pn, so) for pn, so in zip(df['_prod'], df['_sold'])]
    nat = {rk(k): v for k, v in (opt_json(A.nat, '--nat') or {}).items() if v}
    df['_cc'] = df['예약 번호'].map(lambda x: nat.get(rk(x), ''))
    df['_nat'] = df['_cc'].map(lambda c: COUNTRY.get(c, c) if c else '')
    N = len(df)

    per = df['_pd'].dt.to_period('M').mode()[0]
    Y, M = per.year, per.month
    p0, p1 = df['_pd'].min().normalize(), df['_pd'].max().normalize()
    PERIOD = f'{p0.month}/{p0.day}~{p1.month}/{p1.day}'
    PERIOD_TXT = f'{PERIOD} 체크인' + ('(PMS 화면 기준)' if PMS_BASIS else '')
    last_day = (per.to_timestamp(how='end')).day
    exported_at = A.exported_at
    if not exported_at:
        mm = re.search(r'(20\d{6})_(\d{4})', os.path.basename(A.input))
        exported_at = f'{mm.group(1)[:4]}-{mm.group(1)[4:6]}-{mm.group(1)[6:]} {mm.group(2)[:2]}:{mm.group(2)[2:]}' if mm else ''
    DAYS_WD = pd.Series(pd.date_range(p0, p1).weekday).map(lambda i: WD[i]).value_counts().reindex(WD).fillna(0).astype(int).to_dict()

    prev = opt_json(A.prev, '--prev')
    BILL = opt_json(A.billing, '--billing')
    BACC = opt_json(A.billing_acc, '--billing-acc')
    if BACC:
        BACC['cur'] = {k: int(v) for k, v in BACC['cur'].items()}
        BACC['prev'] = {k: int(v) for k, v in (BACC.get('prev') or {}).items()}
        if 'cur_total' in BACC and sum(BACC['cur'].values()) != int(BACC['cur_total']):
            raise ConfigError('--billing-acc: 거래처별 합계가 cur_total과 다릅니다')
        if BILL and int(BILL['total']) != sum(BACC['cur'].values()):
            raise ConfigError('--billing-acc 합계와 --billing 청구 보고서 합계가 다릅니다 (같은 달·같은 조건인지 확인)')
        if prev and not BACC['prev']:
            raise ConfigError('--billing-acc 에 전월(prev) 거래처별 매출이 없습니다 — 전월 대비가 기준이 섞이므로 전월 청구 보고서도 받을 것')
    BREV = BACC is not None   # True = 매출을 PMS 청구 보고서(손님이 묵은 날) 기준으로
    PM_LABEL = (f"{int(prev['month'][5:7])}월" if prev else '')
    PMB = PM_LABEL or f'{(M - 2) % 12 + 1}월'   # 청구 보고서 전월 표기

    # 거래처 분류 (이번 달 + 전월 거래처 모두, 청구 보고서에만 있는 거래처 포함)
    chan_share = df.groupby('거래처')['예약 생성 경로'].apply(lambda s: s.isin(CHAN_VALUES).mean()).to_dict()
    accounts = list(OrderedDict.fromkeys(list(df['거래처'].unique()) + ([r['거래처'] for r in prev['rows']] if prev else [])
                                         + (list(BACC['cur']) + list(BACC['prev']) if BACC else [])))
    CLS = {acc: classify(acc, chan_share.get(acc, 0.0)) for acc in accounts}
    df['_ch'] = df['거래처'].map(lambda a: CLS[a][0])
    df['_grp'] = df['거래처'].map(lambda a: CLS[a][1])
    CH_BASIS = {}
    for acc, c in CLS.items():
        CH_BASIS.setdefault(c[0], c[3])
    GROUPS = GROUP_ORDER + sorted({c[1] for c in CLS.values()} - set(GROUP_ORDER))


    # =====================================================================
    # 3) pandas 집계 (정렬·소표본 판단·요약용. 엑셀 숫자는 모두 수식)
    # =====================================================================
    def agg_rows(d, key):
        out = OrderedDict()
        for k, g in d.groupby(key, sort=False):
            v = g[~g['_can']]; s = v[v['_stay']]; sp = s[s['_amt'] > 0]
            out[k] = dict(전체=len(g), 취소=int(g['_can'].sum()), 유효=len(v), 숙박=len(s), 대실=int((~v['_stay']).sum()),
                          박수=int(s['_n'].sum()), 매출=int(v['_amt'].sum()), 숙박매출_금액있음=int(sp['_amt'].sum()),
                          박수_금액있음=int(sp['_n'].sum()), 당일_숙박=int((s['_lead'] <= 0).sum()), 숙박_금액있음=len(sp))
        return out


    cur_acc = agg_rows(df, '거래처')
    cur_ch = agg_rows(df, '_ch')
    prev_ch = {}
    if prev:
        for r in prev['rows']:
            ch = CLS[r['거래처']][0]
            t = prev_ch.setdefault(ch, {k: 0 for k in ['전체', '취소', '유효', '숙박', '대실', '박수', '매출', '숙박매출_금액있음', '박수_금액있음', '당일_숙박']})
            for k in t:
                t[k] += int(r.get(k, 0))
    bcur_ch, bprev_ch = {}, {}   # 청구 보고서 기준 채널별 매출 (BREV일 때)
    if BREV:
        for a_, v_ in BACC['cur'].items():
            bcur_ch[CLS[a_][0]] = bcur_ch.get(CLS[a_][0], 0) + v_
        for a_, v_ in BACC['prev'].items():
            bprev_ch[CLS[a_][0]] = bprev_ch.get(CLS[a_][0], 0) + v_
    all_ch = list(OrderedDict.fromkeys(list(cur_ch) + list(prev_ch) + list(bcur_ch) + list(bprev_ch)))
    z = lambda d, k: (d or {}).get(k, 0)
    REV = lambda c: bcur_ch.get(c, 0) if BREV else z(cur_ch.get(c), '매출')     # 이번 달 매출 (정렬·요약용)
    REVP = lambda c: bprev_ch.get(c, 0) if BREV else z(prev_ch.get(c), '매출')  # 전월 매출
    alive = [c for c in all_ch if z(cur_ch.get(c), '유효') or z(cur_ch.get(c), '매출') or z(prev_ch.get(c), '유효') or z(prev_ch.get(c), '매출')
             or REV(c) or REVP(c)]
    MAJOR = sorted([c for c in alive if z(cur_ch.get(c), '유효') >= MIN_N], key=lambda c: -REV(c))
    MINOR = sorted([c for c in alive if c not in MAJOR], key=lambda c: (-REV(c), -REVP(c)))
    STAY_MAJOR = [c for c in MAJOR if z(cur_ch.get(c), '숙박') >= MIN_N]
    STAY_ALL = [c for c in MAJOR + MINOR if z(cur_ch.get(c), '숙박') > 0]
    ADR_CH = sorted([c for c in MAJOR if z(cur_ch.get(c), '숙박_금액있음') >= MIN_N],
                    key=lambda c: (CH_BASIS.get(c) == '판매가', -cur_ch[c]['숙박매출_금액있음'] / max(1, cur_ch[c]['박수_금액있음'])))

    V = df[~df['_can']]
    S = V[V['_stay']]
    SP = S[S['_amt'] > 0]
    _rts = set(df['객실 타입']) | set(df['_sold'])
    _rc = pd.concat([df['객실 타입'], df['_sold']]).value_counts()
    RT_ORDER = [x for x in CFG['room_types'] if x in _rts] + [x for x in _rc.index if x not in CFG['room_types']]
    BASE_RT = CFG.get('base_room_type') or RT_ORDER[0]   # '주력 객실': 판매→배정 표의 기준


    def share_tab(col, cats, chans):
        t = {}
        for c in ['전체'] + chans:
            s = S if c == '전체' else S[S['_ch'] == c]
            vc = s[col].value_counts()
            t[c] = {k: (vc.get(k, 0) / len(s) if len(s) else 0) for k in cats}
        return t


    LEAD_SH = share_tab('_lb', LB, STAY_MAJOR)
    ROOM_SH = share_tab('_sold', RT_ORDER, STAY_MAJOR)   # 판매 기준, 객실 타입 그대로 (묶지 않음)
    CHS = S[S['_prod'] != '']                                # 채널 상품이 있는 숙박
    STD = CHS[CHS['_sold'] == BASE_RT]
    CHP = [c for c in STAY_MAJOR if (CHS['_ch'] == c).sum() >= MIN_N]   # 채널 상품 숙박이 충분한 채널
    PROD_ORDER = list(CHS['_prod'].value_counts().index)
    _fams = set(CHS['_pfam'])
    _fam_before = [f['name'] for f in FAMILIES if not f.get('after_rooms')]
    _fam_after = [f['name'] for f in FAMILIES if f.get('after_rooms')]
    FAM_ORDER = [x for x in _fam_before + RT_ORDER + _fam_after if x in _fams] + sorted(_fams - set(_fam_before + RT_ORDER + _fam_after))
    LEAD_SORT = sorted(STAY_MAJOR, key=lambda c: -LEAD_SH[c]['당일'])
    ROOM_SORT = sorted(STAY_MAJOR, key=lambda c: -ROOM_SH[c][RT_ORDER[0]])
    NATV = V[V['_nat'] != '']
    NAT_ORDER = list(NATV['_nat'].value_counts().index)
    NAT_CH = list(NATV['_ch'].value_counts().index)
    NAT_TOP = NAT_ORDER[:5]
    FOREIGN_CH = [c for c in MAJOR + MINOR if any(CLS[a][0] == c and CLS[a][1] == '해외 OTA' for a in CLS)]
    NAT_COVER_CH = list(OrderedDict.fromkeys(NAT_CH + FOREIGN_CH))
    CORP_ACC = [a for a in accounts if CLS[a][0] == '기업·기관' and (z(cur_acc.get(a), '유효') or (prev and any(r['거래처'] == a and r['유효'] for r in prev['rows']))
                                                                  or (BREV and (BACC['cur'].get(a) or BACC['prev'].get(a))))]
    CORP_ACC.sort(key=lambda a: -(BACC['cur'].get(a, 0) if BREV else z(cur_acc.get(a), '매출')))
    AUTO = [a for a in accounts if CLS[a][5]]

    # =====================================================================
    # 4) 스타일
    # =====================================================================
    F = '맑은 고딕'
    INK, INK2, MUTED, GRID, BASE = '0B0B0B', '52514E', '898781', 'E1E0D9', 'C3C2B7'
    BLUE, BLUE_L, GRAYBAR = '2A78D6', '86B6EF', 'C3C2B7'
    ORD5 = ['86B6EF', '5598E7', '2A78D6', '1C5CAB', '0D366B']        # 순서형(리드타임): 연한->진한
    ORD5_TXT = [INK, INK, 'FFFFFF', 'FFFFFF', 'FFFFFF']
    CAT = ['2A78D6', 'EB6834', '1BAF7A', 'EDA100', 'E87BA4', '008300', '6250D6', 'E34948']  # 범주형 고정 순서
    CAT_TXT = ['FFFFFF', INK, INK, INK, INK, 'FFFFFF', 'FFFFFF', 'FFFFFF']
    GOOD, BAD = '006300', 'D03B3B'


    def fnt(sz=10, b=False, c=INK, i=False):
        return Font(name=F, size=sz, bold=b, color=c, italic=i)


    S_HAIR = Side(style='thin', color=GRID)
    S_MID = Side(style='thin', color=MUTED)
    S_HDR = Side(style='medium', color=BASE)
    FILL_H = PatternFill('solid', fgColor='EEF2F8')
    FILL_T = PatternFill('solid', fgColor='F6F6F4')
    FILL_TILE = PatternFill('solid', fgColor='F3F6FA')
    FILL_WARN = PatternFill('solid', fgColor='FFF4D6')
    AL_C = Alignment(horizontal='center', vertical='center', wrap_text=True)
    AL_L = Alignment(horizontal='left', vertical='center', wrap_text=False)
    AL_LW = Alignment(horizontal='left', vertical='center', wrap_text=True)
    AL_R = Alignment(horizontal='right', vertical='center')
    NUM = '#,##0;-#,##0;"-"'
    PCT0 = '0%;-0%;"-"'
    PCT_HEAT = '[=0]"-";[<0.01]0.0%;0%'   # 비중표: 0 = '-', 1% 미만은 소수 한 자리 (3건인데 0%로 보이지 않게)
    PCT1 = '0.0%;-0.0%;"-"'
    DEC1 = '0.0;-0.0;"-"'
    DELTA = '"▲ "0%;"▼ "0%;"0%"'
    DELTA_PP = '"▲ "0.0%"p";"▼ "0.0%"p";"0.0%p"'

    wb = Workbook()
    VIEW_SHEETS = ['대시보드', '채널별', '리드타임', '객실', '요일', '투숙일수', '국적', '기업기관'] + (['청구대조'] if BILL else [])
    SHEETS = VIEW_SHEETS + ['채널구분표', '전월', '차트데이터', '원본']
    W = {}
    for i, name in enumerate(SHEETS):
        W[name] = wb.active if i == 0 else wb.create_sheet(name)
        if i == 0:
            W[name].title = name
    for name in VIEW_SHEETS:
        W[name].sheet_view.showGridLines = False
    W['대시보드'].sheet_properties.tabColor = '1C5CAB'
    for name in ['채널구분표', '전월', '차트데이터', '원본']:
        W[name].sheet_properties.tabColor = 'C3C2B7'


    def put(ws, r, c, v, fmt=None, b=False, color=INK, fill=None, al=None, sz=10, i=False, border='hair'):
        x = ws.cell(row=r, column=c, value=v)
        x.font = fnt(sz, b, color, i)
        if fmt:
            x.number_format = fmt
        if fill:
            x.fill = fill
        if al is None:
            al = AL_L if (isinstance(v, str) and not v.startswith('=')) else AL_R
        x.alignment = al
        if border == 'hair':
            x.border = Border(bottom=S_HAIR)
        elif border == 'total':
            x.border = Border(top=S_MID, bottom=S_MID)
        return x


    def header(ws, r, c, labels, widths=None):
        for j, t in enumerate(labels):
            x = ws.cell(row=r, column=c + j, value=t)
            x.font = fnt(9.5, True, INK)
            x.fill = FILL_H
            x.alignment = AL_C
            x.border = Border(bottom=S_HDR)
        ws.row_dimensions[r].height = 30
        if widths:
            for j, w in enumerate(widths):
                ws.column_dimensions[L(c + j)].width = w


    def title(ws, text, sub=None, sub2=None):
        ws['A1'] = text
        ws['A1'].font = fnt(14, True)
        ws.row_dimensions[1].height = 26
        if sub:
            ws['A2'] = sub
            ws['A2'].font = fnt(9.5, c=INK2)
        if sub2:
            ws['A3'] = sub2
            ws['A3'].font = fnt(9.5, c=INK2)


    def section(ws, r, text, sub=None):
        ws.cell(row=r, column=1, value=text).font = fnt(11.5, True)
        ws.row_dimensions[r].height = 22
        if sub:
            ws.cell(row=r + 1, column=1, value=sub).font = fnt(9.5, c=INK2)


    def esc(s):  # COUNTIFS 조건의 ~ 는 와일드카드 이스케이프 문자 -> ~~
        return str(s).replace('~', '~~').replace('*', '~*').replace('?', '~?')


    def q(s):  # 수식 안 문자열 리터럴
        return '"' + str(s).replace('"', '""') + '"'


    # =====================================================================
    # 5) 채널구분표
    # =====================================================================
    ws = W['채널구분표']
    title(ws, '채널 구분표 — 거래처를 분석용 채널·대분류로 묶는 기준', '여기 값을 고치면 모든 탭 숫자가 따라 바뀝니다. 노란 줄 = 처음 보는 거래처라 자동 분류함 (확인 필요).',
          (f'G·H열 = 거래처별 매출, PMS 청구 보고서 그대로 (손님이 묵은 날 기준, 부대 매출 포함) — 대시보드·채널별·기업기관의 매출은 이 숫자를 더한 것. '
           f"{BACC.get('conditions', '')} · {BACC.get('fetched_at', '')}") if BREV else None)
    _mh = ['거래처 (PMS)', '채널 (분석용)', '대분류', '금액 기준 (추정)', '기준 코드', '근거·메모']
    _mw = [30, 16, 11, 40, 10, 56]
    if BREV:
        _mh += [f'{M}월 매출(원)\nPMS 청구 보고서', f'{PMB} 매출(원)\nPMS 청구 보고서']
        _mw += [16, 16]
    header(ws, 4, 1, _mh, _mw)
    _ri = lambda a: find_rule(a, RULES)[0]
    order_key = lambda a: (GROUPS.index(CLS[a][1]) if CLS[a][1] in GROUPS else 99, 999 if _ri(a) is None else _ri(a), a)
    MAP_ACC = sorted(accounts, key=order_key)
    for i, acc in enumerate(MAP_ACC):
        r = 5 + i
        c = CLS[acc]
        for j, v in enumerate([acc, c[0], c[1], c[2], c[3], c[4]]):
            put(ws, r, 1 + j, v, fill=FILL_WARN if c[5] else None, al=AL_L)
        if BREV:
            put(ws, r, 7, BACC['cur'].get(acc, 0), NUM)
            put(ws, r, 8, BACC['prev'].get(acc, 0), NUM, color=INK2)
    MAPL = 5 + len(MAP_ACC) + 50
    CC_LIST = list(OrderedDict.fromkeys([c for c in df['_cc'] if c] + list(COUNTRY)))
    header(ws, 4, 10, ['국적 코드', '국가명'], [11, 14])   # v2.5: H·I -> J·K (G·H열은 청구 보고서 매출)
    ws.column_dimensions['I'].width = 3
    for i, cc in enumerate(CC_LIST):
        put(ws, 5 + i, 10, cc, al=AL_L)
        put(ws, 5 + i, 11, COUNTRY.get(cc, cc), al=AL_L)
    CCL = 5 + len(CC_LIST) + 30
    ws.freeze_panes = 'B5'   # 오른쪽(G·H 청구 보고서 매출)으로 넘겨도 거래처 이름이 보이게
    MAPR = lambda col: f'채널구분표!${col}$5:${col}${MAPL}'

    # =====================================================================
    # 6) 원본 (행 단위 + 파생 수식 열)
    # =====================================================================
    ws = W['원본']
    RAW = ['예약번호', '거래처', '채널', '대분류', '이용유형', '객실', '배정 객실(실제 들어간 방)', '예약생성경로', '성인', '유아동', '투숙일(예정 체크인)', '예정 체크아웃',
           '예약생성일', '예약상태', '취소(1=취소·노쇼)', '박수', '총 청구 금액(원)', '잔액(원)', '리드타임(일)', '리드구간', '체크인요일',
           '투숙구간', '국적코드', '국적', '금액있음(1)', '실제 체크인', '실제 체크아웃', '예정일 보정(1)',
           '판매 객실(손님이 산 것)', '판매 상품(채널)', '다른 방 배정(1)', '상품 묶음', '예약 금액(원)=청구+잔액']
    header(ws, 1, 1, RAW, [11, 24, 13, 10, 8, 6, 15, 11, 6, 7, 12, 12, 16, 10, 10, 6, 12, 10, 9, 9, 8, 8, 8, 10, 9, 16, 16, 9, 15, 30, 9, 12, 13])
    for i, rw in df.iterrows():
        r = i + 2
        vals = {
            1: rid(rw['예약 번호']), 2: rw['거래처'],
            3: f'=IFERROR(INDEX({MAPR("B")},MATCH(B{r},{MAPR("A")},0)),B{r})',
            4: f'=IFERROR(INDEX({MAPR("C")},MATCH(B{r},{MAPR("A")},0)),"기타")',
            5: rw['_type'], 6: rw['객실'], 7: rw['객실 타입'], 8: rw['예약 생성 경로'],
            9: num(rw['성인']), 10: num(rw['유아동']),
            11: dtv(rw['_sa']), 12: dtv(rw['_sd']), 13: dtv(rw['_cr']),
            14: rw['예약 상태'],
            15: '=IF(OR(' + ','.join(f'ISNUMBER(SEARCH({q(esc(k_))},N{r}))' for k_ in CANCEL_KW) + '),1,0)',
            16: f'=IF(E{r}="숙박",MAX(1,INT(L{r})-INT(K{r})),0)',
            17: int(rw['_paid']), 18: int(rw['_bal']),
            19: f'=INT(K{r})-INT(M{r})',
            20: f'=IF(S{r}<=0,"당일",IF(S{r}<=3,"1~3일",IF(S{r}<=7,"4~7일",IF(S{r}<=30,"8~30일","31일+"))))',
            21: f'=CHOOSE(WEEKDAY(K{r},2),"월","화","수","목","금","토","일")',
            22: f'=IF(E{r}<>"숙박","대실",IF(P{r}=1,"1박",IF(P{r}=2,"2박",IF(P{r}<=6,"3~6박","7박+"))))',
            23: rw['_cc'] or None,
            24: f'=IF(W{r}="","",IFERROR(INDEX(채널구분표!$K$5:$K${CCL},MATCH(W{r},채널구분표!$J$5:$J${CCL},0)),W{r}))',
            25: f'=IF(AG{r}>0,1,0)',
            26: dtv(rw['_ci']), 27: dtv(rw['_co']), 28: int(rw['_fix']),
            29: rw['_sold'], 30: rw['_prod'] or None,
            31: f'=IF(AND(AD{r}<>"",AC{r}<>G{r}),1,0)',
            32: rw['_pfam'] or None,
            33: f'=Q{r}+R{r}',
        }
        for c, v in vals.items():
            x = ws.cell(row=r, column=c, value=v)
            x.font = fnt(9.5)
            if c in (11, 12):
                x.number_format = 'yyyy-mm-dd'
            elif c in (13, 26, 27):
                x.number_format = 'yyyy-mm-dd hh:mm'
            elif c in (17, 18, 33):
                x.number_format = '#,##0'
    ws.freeze_panes = 'C2'
    ws.auto_filter.ref = f'A1:{L(len(RAW))}{N + 1}'
    RMAX = (N // 1000 + 3) * 1000
    R = lambda col: f'원본!${col}${2}:${col}${RMAX}'
    ACC, CH, GRP, TYPE, RT, ADU, CAN, NN, AMT, LEAD, LBC, WDC, LOSC, CCC, NATC, HAS = (
        R('B'), R('C'), R('D'), R('E'), R('G'), R('I'), R('O'), R('P'), R('AG'), R('S'), R('T'), R('U'), R('V'), R('W'), R('X'), R('Y'))
    SOLD, PRODC, MOVED, FAMC = R('AC'), R('AD'), R('AE'), R('AF')   # v2.5.1: 객실그룹 열 삭제 (객실은 타입 그대로)
    VALID = f'{CAN},0'
    STAYC = f'{CAN},0,{TYPE},"숙박"'

    # =====================================================================
    # 7) 전월
    # =====================================================================
    ws = W['전월']
    PCOLS = ['거래처', '채널', '대분류', '전체', '취소', '유효', '숙박', '대실', '박수', '매출(원)', '숙박매출(금액>0)', '박수(금액>0)', '당일 숙박']
    PKEYS = ['전체', '취소', '유효', '숙박', '대실', '박수', '매출', '숙박매출_금액있음', '박수_금액있음', '당일_숙박']
    if prev:
        title(ws, f"전월({prev['month']}) 거래처별 집계 — 전월 대비 계산용", f"{prev.get('period', '')} · 출처: {prev.get('source', '')}",
              ('취소 = 취소+노쇼. 예약 수·박수·단가의 전월 대비에 씀. 전월 매출은 [채널구분표] H열(PMS 청구 보고서)로 계산 — 이 표의 매출(체크인 기준 예약 금액)은 참고용.'
               if BREV else '취소 = 취소+노쇼. 매출 = 유효 예약 청구 금액 합. 채널·대분류는 [채널구분표]를 따라감.'))
        header(ws, 5, 1, PCOLS, [30, 16, 11, 8, 8, 8, 8, 8, 8, 13, 15, 12, 10])
        for i, rr in enumerate(prev['rows']):
            r = 6 + i
            put(ws, r, 1, rr['거래처'], al=AL_L)
            put(ws, r, 2, f'=IFERROR(INDEX({MAPR("B")},MATCH(A{r},{MAPR("A")},0)),A{r})', al=AL_L)
            put(ws, r, 3, f'=IFERROR(INDEX({MAPR("C")},MATCH(A{r},{MAPR("A")},0)),"기타")', al=AL_L)
            for j, k in enumerate(PKEYS):
                put(ws, r, 4 + j, int(rr.get(k, 0)), NUM)
        PL = 6 + len(prev['rows']) - 1
        PT = PL + 1
        put(ws, PT, 1, '합계', b=True, fill=FILL_T, border='total')
        put(ws, PT, 2, '', fill=FILL_T, border='total')
        put(ws, PT, 3, '', fill=FILL_T, border='total')
        for j in range(len(PKEYS)):
            put(ws, PT, 4 + j, f'=SUM({L(4 + j)}6:{L(4 + j)}{PL})', NUM, b=True, fill=FILL_T, border='total')
        ws.freeze_panes = 'B6'
        PR = lambda col: f'전월!${col}$6:${col}${PL}'
        PTOT = lambda col: f'전월!${col}${PT}'
    else:
        title(ws, '전월 자료 없음', '전월 거래처별 집계(--prev)를 넣지 않아 전월 대비를 계산하지 않았습니다.')

    # =====================================================================
    # 8) 채널별
    # =====================================================================
    ws = W['채널별']
    title(ws, f'채널별 실적 — {Y}년 {M}월',
          (f'매출 = PMS 청구 보고서 기준 ({M}/1~{M}/{last_day}에 손님이 묵은 날) · 예약 수·박수·단가·비중 = {PERIOD_TXT} 예약, 취소 제외 · 매출은 만원'
           if BREV else f'{PERIOD_TXT} · 취소 제외 · 매출은 만원 단위') + (f' · 전월 = {PM_LABEL}' if prev else ''),
          '1박 평균은 채널마다 금액 기준이 달라 I열을 같이 볼 것 (입금가 = 수수료 뗀 돈, 판매가 = 수수료 떼기 전, 실수령 = 직접 받은 돈). 회색 글씨 = 판매가.')
    CCOLS = ['채널', '대분류', '유효 예약', '매출(만원)', '매출 비중', '전월 매출(만원)', '전월 대비', '1박 평균(원)', '금액 기준',
             '평균 박수', '당일 예약 비중', '취소율']
    header(ws, 5, 1, CCOLS, [14, 11, 10, 13, 9, 13, 10, 12, 10, 9, 12, 9])
    r0 = 6
    CH_ROW = {}


    def ch_row(ws, r, ch, tot_row, bold=False):
        a = f'$A{r}'
        put(ws, r, 1, ch, b=True, al=AL_L)
        put(ws, r, 2, f'=IFERROR(INDEX({MAPR("C")},MATCH({a},{MAPR("B")},0)),"")', al=AL_L, color=INK2)
        put(ws, r, 3, f'=COUNTIFS({CH},{a},{VALID})', NUM)
        put(ws, r, 4, f'=SUMIFS({MAPR("G")},{MAPR("B")},{a})/10000' if BREV else f'=SUMIFS({AMT},{CH},{a},{VALID})/10000', NUM)
        put(ws, r, 5, f'=IFERROR(D{r}/$D${tot_row},0)', PCT1)
        if prev:
            put(ws, r, 6, f'=SUMIFS({MAPR("H")},{MAPR("B")},{a})/10000' if BREV else f'=SUMIFS({PR("J")},{PR("B")},{a})/10000', NUM, color=INK2)
            put(ws, r, 7, f'=IF(F{r}=0,IF(D{r}>0,"신규","-"),IF(F{r}<100,"-",D{r}/F{r}-1))', DELTA)
        else:
            put(ws, r, 6, '', color=INK2)
            put(ws, r, 7, '')
        put(ws, r, 8, f'=IFERROR(SUMIFS({AMT},{CH},{a},{STAYC},{HAS},1)/SUMIFS({NN},{CH},{a},{STAYC},{HAS},1),0)', NUM)
        put(ws, r, 9, f'=IFERROR(INDEX({MAPR("E")},MATCH({a},{MAPR("B")},0)),"")', al=AL_C, color=INK2)
        put(ws, r, 10, f'=IFERROR(SUMIFS({NN},{CH},{a},{STAYC})/COUNTIFS({CH},{a},{STAYC}),0)', DEC1)
        put(ws, r, 11, f'=IFERROR(COUNTIFS({CH},{a},{STAYC},{LEAD},"<=0")/COUNTIFS({CH},{a},{STAYC}),0)', PCT0)
        put(ws, r, 12, f'=IFERROR(COUNTIFS({CH},{a},{CAN},1)/COUNTIFS({CH},{a}),0)', PCT1)
        CH_ROW[ch] = r


    n_major = len(MAJOR)
    has_minor = len(MINOR) > 0
    ETC = r0 + n_major if has_minor else None
    TOT = r0 + n_major + (1 if has_minor else 0)
    MINOR_H = TOT + 4
    MINOR_R0 = MINOR_H + 1
    for i, ch in enumerate(MAJOR):
        ch_row(ws, r0 + i, ch, TOT)
    if has_minor:
        m0, m1 = MINOR_R0, MINOR_R0 + len(MINOR) - 1
        put(ws, ETC, 1, f'기타 채널 ({len(MINOR)}개)', b=True, al=AL_L)
        put(ws, ETC, 2, '아래 표 참고', al=AL_L, color=MUTED, i=True)
        put(ws, ETC, 3, f'=SUM(C{m0}:C{m1})', NUM)
        put(ws, ETC, 4, f'=SUM(D{m0}:D{m1})', NUM)
        put(ws, ETC, 5, f'=IFERROR(D{ETC}/$D${TOT},0)', PCT1)
        if prev:
            put(ws, ETC, 6, f'=SUM(F{m0}:F{m1})', NUM, color=INK2)
            put(ws, ETC, 7, f'=IF(F{ETC}=0,IF(D{ETC}>0,"신규","-"),IF(F{ETC}<100,"-",D{ETC}/F{ETC}-1))', DELTA)
        else:
            put(ws, ETC, 6, ''); put(ws, ETC, 7, '')
        for c in range(8, 13):
            put(ws, ETC, c, '', color=MUTED)
    # 합계
    t = TOT
    put(ws, t, 1, '합계', b=True, fill=FILL_T, border='total', al=AL_L)
    put(ws, t, 2, '', fill=FILL_T, border='total')
    put(ws, t, 3, f'=SUM(C{r0}:C{t - 1})', NUM, b=True, fill=FILL_T, border='total')
    put(ws, t, 4, f'=SUM(D{r0}:D{t - 1})', NUM, b=True, fill=FILL_T, border='total')
    put(ws, t, 5, f'=IFERROR(D{t}/D{t},0)', PCT1, b=True, fill=FILL_T, border='total')
    if prev:
        put(ws, t, 6, f'=SUM(F{r0}:F{t - 1})', NUM, b=True, fill=FILL_T, border='total', color=INK2)
        put(ws, t, 7, f'=IF(F{t}=0,"-",D{t}/F{t}-1)', DELTA, b=True, fill=FILL_T, border='total')
    else:
        put(ws, t, 6, '', fill=FILL_T, border='total'); put(ws, t, 7, '', fill=FILL_T, border='total')
    put(ws, t, 8, f'=IFERROR(SUMIFS({AMT},{STAYC},{HAS},1)/SUMIFS({NN},{STAYC},{HAS},1),0)', NUM, b=True, fill=FILL_T, border='total')
    put(ws, t, 9, '', fill=FILL_T, border='total')
    put(ws, t, 10, f'=IFERROR(SUMIFS({NN},{STAYC})/COUNTIFS({STAYC}),0)', DEC1, b=True, fill=FILL_T, border='total')
    put(ws, t, 11, f'=IFERROR(COUNTIFS({STAYC},{LEAD},"<=0")/COUNTIFS({STAYC}),0)', PCT0, b=True, fill=FILL_T, border='total')
    put(ws, t, 12, f'=IFERROR(COUNTIFS({CAN},1)/COUNTA(원본!$A$2:$A${RMAX}),0)', PCT1, b=True, fill=FILL_T, border='total')
    # 기타 채널 내역
    if has_minor:
        section(ws, MINOR_H - 2, f'기타 채널 내역 — 유효 예약 {MIN_N}건 미만', '건수가 적어 비율·단가가 크게 흔들리므로 위 표와 차트에서는 한 줄로 묶었음.')
        header(ws, MINOR_H, 1, CCOLS)
        for i, ch in enumerate(MINOR):
            ch_row(ws, MINOR_R0 + i, ch, TOT)
        after_minor = MINOR_R0 + len(MINOR) + 2
    else:
        after_minor = TOT + 3
    # 조건부 서식
    last_main = (ETC or (TOT - 1))
    ws.conditional_formatting.add(f'D{r0}:D{last_main}', DataBarRule(start_type='num', start_value=0, end_type='max', color=BLUE_L, showValue=True))
    if MAJOR:   # 주요 채널이 없으면 범위가 뒤집힘
        ws.conditional_formatting.add(f'K{r0}:K{TOT - 1 if not has_minor else ETC - 1}',
                                      ColorScaleRule(start_type='num', start_value=0, start_color='FCFCFB', end_type='num', end_value=1, end_color='6DA7EC'))
    for rng in [f'G{r0}:G{TOT}'] + ([f'G{MINOR_R0}:G{MINOR_R0 + len(MINOR) - 1}'] if has_minor else []):
        ws.conditional_formatting.add(rng, CellIsRule(operator='greaterThan', formula=['0'], font=Font(color=GOOD, bold=True)))
        ws.conditional_formatting.add(rng, CellIsRule(operator='lessThan', formula=['0'], font=Font(color=BAD, bold=True)))
    ws.conditional_formatting.add(f'H{r0}:H{TOT}', FormulaRule(formula=[f'$I{r0}="판매가"'], font=Font(color=MUTED, italic=True)))
    # 대분류
    G_H = after_minor + 2
    section(ws, G_H - 2, '대분류별', ' / '.join(f"{g_} = {'·'.join(_gn)}" + (' 등' if len(_gn) == 4 else '') for g_, _gn in ((g_, list(OrderedDict.fromkeys(c_[0] for c_ in CLS.values() if c_[1] == g_))[:4]) for g_ in GROUPS) if _gn))
    header(ws, G_H, 1, ['대분류', '', '유효 예약', '매출(만원)', '매출 비중', '전월 매출(만원)', '전월 대비', '1박 평균(원)'])
    G_ROW = {}
    for i, g in enumerate(GROUPS):
        r = G_H + 1 + i
        a = f'$A{r}'
        G_ROW[g] = r
        put(ws, r, 1, g, b=True, al=AL_L)
        put(ws, r, 2, '')
        put(ws, r, 3, f'=COUNTIFS({GRP},{a},{VALID})', NUM)
        put(ws, r, 4, f'=SUMIFS({MAPR("G")},{MAPR("C")},{a})/10000' if BREV else f'=SUMIFS({AMT},{GRP},{a},{VALID})/10000', NUM)
        put(ws, r, 5, f'=IFERROR(D{r}/$D${G_H + 1 + len(GROUPS)},0)', PCT1)
        if prev:
            put(ws, r, 6, f'=SUMIFS({MAPR("H")},{MAPR("C")},{a})/10000' if BREV else f'=SUMIFS({PR("J")},{PR("C")},{a})/10000', NUM, color=INK2)
            put(ws, r, 7, f'=IF(F{r}=0,IF(D{r}>0,"신규","-"),IF(F{r}<100,"-",D{r}/F{r}-1))', DELTA)
        else:
            put(ws, r, 6, ''); put(ws, r, 7, '')
        put(ws, r, 8, f'=IFERROR(SUMIFS({AMT},{GRP},{a},{STAYC},{HAS},1)/SUMIFS({NN},{GRP},{a},{STAYC},{HAS},1),0)', NUM)
    GT = G_H + 1 + len(GROUPS)
    put(ws, GT, 1, '합계', b=True, fill=FILL_T, border='total', al=AL_L)
    put(ws, GT, 2, '', fill=FILL_T, border='total')
    for c in (3, 4):
        put(ws, GT, c, f'=SUM({L(c)}{G_H + 1}:{L(c)}{GT - 1})', NUM, b=True, fill=FILL_T, border='total')
    put(ws, GT, 5, f'=IFERROR(D{GT}/D{GT},0)', PCT1, b=True, fill=FILL_T, border='total')
    if prev:
        put(ws, GT, 6, f'=SUM(F{G_H + 1}:F{GT - 1})', NUM, b=True, fill=FILL_T, border='total', color=INK2)
        put(ws, GT, 7, f'=IF(F{GT}=0,"-",D{GT}/F{GT}-1)', DELTA, b=True, fill=FILL_T, border='total')
    else:
        put(ws, GT, 6, '', fill=FILL_T, border='total'); put(ws, GT, 7, '', fill=FILL_T, border='total')
    put(ws, GT, 8, f'=IFERROR(SUMIFS({AMT},{STAYC},{HAS},1)/SUMIFS({NN},{STAYC},{HAS},1),0)', NUM, b=True, fill=FILL_T, border='total')
    ws.conditional_formatting.add(f'G{G_H + 1}:G{GT}', CellIsRule(operator='greaterThan', formula=['0'], font=Font(color=GOOD, bold=True)))
    ws.conditional_formatting.add(f'G{G_H + 1}:G{GT}', CellIsRule(operator='lessThan', formula=['0'], font=Font(color=BAD, bold=True)))
    nr = GT + 2
    for line in (['• 유효 예약 = 전체 예약 − 취소·노쇼. 박수·단가·리드타임·당일 비중·취소율은 체크인 예약으로 계산.',
                  f'• 매출 = PMS 청구 보고서 금액 (매출 인식 일자 = 손님이 묵은 날 기준, 객실 서비스·음식 등 부대 매출 포함) → PMS 청구 보고서 숫자와 같음. 거래처별 금액은 [채널구분표] G·H열.',
                  '• 1박 평균 = 숙박 예약 금액(총 청구 금액 + 잔액) ÷ 숙박 박수. 0원 숙박(단체 금액 미확정, 무료 등)은 단가 계산에서 뺌.']
                 if BREV else
                 ['• 유효 예약 = 전체 예약 − 취소·노쇼. 매출·박수·단가·리드타임은 모두 유효 예약만 계산.',
                  '• 매출 = PMS 총 청구 금액 + 잔액 (= PMS 매출액). 내보내기의 총 청구 금액은 받은 돈이라 덜/더 받은 예약은 잔액만큼 다름. 체크인 기준 — 장기 투숙은 체크인한 달에 전액.',
                  '• 1박 평균 = 숙박 매출 ÷ 숙박 박수. 0원 숙박(단체 금액 미확정, 무료 등)은 단가 계산에서 뺌.']) + [
                 '• 당일 예약 비중 = 숙박 중 체크인 당일에 예약한 비율.  • 평균 박수 = 숙박 1건당 묵은 밤 수.']:
        ws.cell(row=nr, column=1, value=line).font = fnt(9.5, c=INK2)
        nr += 1
    ws.freeze_panes = 'B6'


    # =====================================================================
    # 9) 비중 히트맵 표 공통
    # =====================================================================
    def heat_table(ws, top, ttl, sub, crit_rng, cats, chans, extra_cols=None, color_end='6DA7EC'):
        """채널 x 범주 비중표 (가로 합 100%). 반환: (헤더행, {채널: 행}, 첫 범주 열)"""
        section(ws, top, ttl, sub)
        h = top + 3
        extra_cols = extra_cols or []
        labels = ['채널', '숙박 건수'] + [e[0] for e in extra_cols] + cats
        header(ws, h, 1, labels, [14, 10] + [12] * len(extra_cols) + [10] * len(cats))
        rows = {}
        c0 = 3 + len(extra_cols)
        for i, ch in enumerate(chans + ['전체']):
            r = h + 1 + i
            rows[ch] = r
            tot = ch == '전체'
            chc = '' if tot else f'{CH},$A{r},'
            kw = dict(fill=FILL_T, border='total', b=True) if tot else {}
            put(ws, r, 1, ch, al=AL_L, **({'b': True} if not tot else kw))
            put(ws, r, 2, f'=COUNTIFS({chc}{STAYC})', NUM, **kw)
            for j, (lab, fml, fmt) in enumerate(extra_cols):
                put(ws, r, 3 + j, fml(chc, r), fmt, **kw)
            for j, cat in enumerate(cats):
                put(ws, r, c0 + j, f'=IFERROR(COUNTIFS({chc}{STAYC},{crit_rng},{q(esc(cat))})/$B{r},0)', PCT_HEAT, al=AL_C, **kw)
        last = h + len(chans) + 1
        ws.conditional_formatting.add(f'{L(c0)}{h + 1}:{L(c0 + len(cats) - 1)}{last}',
                                      ColorScaleRule(start_type='num', start_value=0, start_color='FCFCFB', end_type='max', end_color=color_end))
        return h, rows, c0, last


    def count_table(ws, top, ttl, crit_rng, cats, chans):
        section(ws, top, ttl, '숙박만, 취소 제외. 건수가 적은 채널까지 모두 표시 (비율 비교는 위 표만).')
        h = top + 3
        header(ws, h, 1, ['채널'] + cats + ['합계'])
        for i, ch in enumerate(chans + ['전체']):
            r = h + 1 + i
            tot = ch == '전체'
            chc = '' if tot else f'{CH},$A{r},'
            kw = dict(fill=FILL_T, border='total', b=True) if tot else {}
            put(ws, r, 1, ch, al=AL_L, **({'b': True} if not tot else kw))
            for j, cat in enumerate(cats):
                put(ws, r, 2 + j, f'=COUNTIFS({chc}{STAYC},{crit_rng},{q(esc(cat))})', NUM, al=AL_C, **kw)
            put(ws, r, 2 + len(cats), f'=SUM(B{r}:{L(1 + len(cats))}{r})', NUM, al=AL_C, b=True, fill=FILL_T)
        return h + len(chans) + 1


    small_note = f'숙박 {MIN_N}건 미만 채널은 비율이 크게 흔들려 이 표에서 뺐음 → 아래 건수 표에 있음.'
    # 리드타임
    ws = W['리드타임']
    title(ws, '예약 시점 — 체크인 며칠 전에 예약했나 (리드타임)', '숙박만 · 취소 제외 · 칸 안의 % = 그 채널 숙박 중 비중 (가로로 더하면 100%) · 색이 진할수록 큼', small_note)
    avg_lead = ('평균 리드타임(일)', lambda chc, r: f'=IFERROR(AVERAGEIFS({LEAD},{chc}{STAYC}),0)', DEC1)
    LH, LROWS, LC0, LLAST = heat_table(ws, 5, '채널별 예약 시점 비중', None, LBC, LB, STAY_MAJOR, [avg_lead])
    count_table(ws, LLAST + 3, '건수 (참고)', LBC, LB, STAY_ALL)
    ws.freeze_panes = ws.cell(row=LH + 1, column=2)
    # 객실 — 판매 기준(채널에서 산 객실) + 판매→배정
    ws = W['객실']
    title(ws, '객실 — 무엇이 팔렸고(판매) 어느 방에 묵었나(배정)',
          '판매 = 손님이 채널에서 산 객실·상품 (--prod 자료) · 배정 = 실제 들어간 방 · 자료가 없는 예약은 판매 = 배정으로 봄',
          f'숙박만 · 취소 제외 · 객실 타입 {len(RT_ORDER)}개를 묶지 않고 그대로 · ' + small_note)
    OH, OROWS, OC0, OLAST = heat_table(ws, 5, '채널별 판매 객실 구성 비중 (판매 기준, 객실 타입별)', None, SOLD, RT_ORDER, STAY_MAJOR)
    top = OLAST + 3
    if prod:
        section(ws, top, '판매 → 배정 (채널 예약 숙박 건수)', '세로 = 손님이 산 객실, 가로 = 실제 배정한 객실. 굵은 글씨(대각선) = 산 객실 그대로, 나머지 = 다른 방 배정(업그레이드 등).')
        h = top + 3
        header(ws, h, 1, ['산 객실 ↓  /  배정 →'] + RT_ORDER + ['합계', '다른 방 비율'])
        cs = 2 + len(RT_ORDER)
        for i, st in enumerate(RT_ORDER):
            r = h + 1 + i
            put(ws, r, 1, st, b=True, al=AL_L)
            for j, at in enumerate(RT_ORDER):
                put(ws, r, 2 + j, f'=COUNTIFS({PRODC},"?*",{STAYC},{SOLD},{q(esc(st))},{RT},{q(esc(at))})', NUM, al=AL_C, b=(i == j))
            put(ws, r, cs, f'=SUM(B{r}:{L(cs - 1)}{r})', NUM, al=AL_C, b=True, fill=FILL_T)
            put(ws, r, cs + 1, f'=IFERROR(1-{L(2 + i)}{r}/{L(cs)}{r},0)', PCT0, al=AL_C)
        r = h + 1 + len(RT_ORDER)
        put(ws, r, 1, '합계', b=True, fill=FILL_T, border='total', al=AL_L)
        for j in range(len(RT_ORDER) + 1):
            put(ws, r, 2 + j, f'=SUM({L(2 + j)}{h + 1}:{L(2 + j)}{r - 1})', NUM, al=AL_C, b=True, fill=FILL_T, border='total')
        put(ws, r, cs + 1, f'=IFERROR(COUNTIFS({PRODC},"?*",{STAYC},{MOVED},1)/{L(cs)}{r},0)', PCT0, al=AL_C, b=True, fill=FILL_T, border='total')
        ws.conditional_formatting.add(f'B{h + 1}:{L(cs - 1)}{r - 1}', ColorScaleRule(start_type='num', start_value=0, start_color='FCFCFB', end_type='max', end_color='6DA7EC'))
        top = r + 3
        section(ws, top, '채널별 — 산 객실과 다른 방에 배정한 비율', '채널 상품이 있는 숙박만 (직접 판매·기업 제외).')
        h = top + 3
        header(ws, h, 1, ['채널', '숙박 (채널 상품)', '다른 방 배정', '비율', f'{BASE_RT} 판매', '그중 다른 방', '비율'])
        for i, ch in enumerate(CHP + ['전체']):
            r = h + 1 + i
            tot = ch == '전체'
            chc = '' if tot else f'{CH},$A{r},'
            kw = dict(fill=FILL_T, border='total', b=True) if tot else {}
            put(ws, r, 1, ch, al=AL_L, **({'b': True} if not tot else kw))
            put(ws, r, 2, f'=COUNTIFS({chc}{PRODC},"?*",{STAYC})', NUM, **kw)
            put(ws, r, 3, f'=COUNTIFS({chc}{PRODC},"?*",{STAYC},{MOVED},1)', NUM, **kw)
            put(ws, r, 4, f'=IFERROR(C{r}/B{r},0)', PCT0, **kw)
            put(ws, r, 5, f'=COUNTIFS({chc}{PRODC},"?*",{STAYC},{SOLD},{q(esc(BASE_RT))})', NUM, **kw)
            put(ws, r, 6, f'=COUNTIFS({chc}{PRODC},"?*",{STAYC},{SOLD},{q(esc(BASE_RT))},{MOVED},1)', NUM, **kw)
            put(ws, r, 7, f'=IFERROR(F{r}/E{r},0)', PCT0, **kw)
        last = h + 1 + len(CHP)
        for col in ('D', 'G') if CHP else ():   # 채널이 없으면 범위가 뒤집힘
            ws.conditional_formatting.add(f'{col}{h + 1}:{col}{last - 1}', DataBarRule(start_type='num', start_value=0, end_type='num', end_value=1, color=BLUE_L, showValue=True))
        top = last + 3
        section(ws, top, '채널별 판매 상품 묶음 — 비중', '묶음 = 설정 product_families 기준 · 나머지 = 묶음에 안 걸린 상품을 판매 객실 타입 그대로. 세로로 더하면 100%.')
        h = top + 3
        header(ws, h, 1, ['상품 묶음'] + CHP + ['전체'])
        r = h + 1
        put(ws, r, 1, '숙박 건수 (채널 상품)', b=True, al=AL_L, fill=FILL_T)
        for j, ch in enumerate(CHP + ['전체']):
            chc = '' if ch == '전체' else f'{CH},{q(ch)},'
            put(ws, r, 2 + j, f'=COUNTIFS({chc}{PRODC},"?*",{STAYC})', NUM, al=AL_C, b=True, fill=FILL_T)
        nrow = r
        for i, fm in enumerate(FAM_ORDER):
            r = nrow + 1 + i
            put(ws, r, 1, fm, b=True, al=AL_L)
            for j, ch in enumerate(CHP + ['전체']):
                chc = '' if ch == '전체' else f'{CH},{q(ch)},'
                put(ws, r, 2 + j, f'=IFERROR(COUNTIFS({chc}{FAMC},{q(esc(fm))},{STAYC})/{L(2 + j)}${nrow},0)', PCT0, al=AL_C, b=(ch == '전체'))
        ws.conditional_formatting.add(f'B{nrow + 1}:{L(1 + len(CHP))}{r}', ColorScaleRule(start_type='num', start_value=0, start_color='FCFCFB', end_type='max', end_color='6DA7EC'))
        top = r + 3
        section(ws, top, '상품별 자세히 (숙박 건수)', '채널에 올린 상품 이름 그대로. 칸 색 = 그 채널 안에서 많이 팔린 정도.')
        h = top + 3
        header(ws, h, 1, ['상품', '판매 객실'] + CHP + ['합계'])
        for i, pn in enumerate(PROD_ORDER):
            r = h + 1 + i
            put(ws, r, 1, pn, al=AL_L)
            put(ws, r, 2, CHS[CHS['_prod'] == pn]['_sold'].mode()[0], al=AL_L, color=INK2)
            for j, ch in enumerate(CHP):
                put(ws, r, 3 + j, f'=COUNTIFS({CH},{q(ch)},{PRODC},{q(esc(pn))},{STAYC})', NUM, al=AL_C)
            put(ws, r, 3 + len(CHP), f'=SUM(C{r}:{L(2 + len(CHP))}{r})', NUM, al=AL_C, b=True, fill=FILL_T)
        r = h + 1 + len(PROD_ORDER)
        put(ws, r, 1, '합계', b=True, fill=FILL_T, border='total', al=AL_L)
        put(ws, r, 2, '', fill=FILL_T, border='total')
        for j in range(len(CHP) + 1):
            put(ws, r, 3 + j, f'=SUM({L(3 + j)}{h + 1}:{L(3 + j)}{r - 1})', NUM, al=AL_C, b=True, fill=FILL_T, border='total')
        for j in range(len(CHP)):
            ws.conditional_formatting.add(f'{L(3 + j)}{h + 1}:{L(3 + j)}{r - 1}', ColorScaleRule(start_type='num', start_value=0, start_color='FCFCFB', end_type='max', end_color='6DA7EC'))
        ws.column_dimensions['A'].width = 30
        top = r + 3
    else:
        ws.cell(row=top, column=1, value='판매 상품 자료(--prod)가 없어 위 표는 내보내기의 객실 타입 그대로임 — 이 열이 배정 방이면 낮은 객실로 팔고 윗 객실에 넣은 예약이 윗 객실로 잡힘.').font = fnt(10, True, BAD)
        top += 2
    section(ws, top, '판매 객실 타입별 1박 평균 금액(원)', '같은 줄(채널) 안에서 비교할 것 — 채널마다 금액 기준(수수료 전/후)이 다름. "-" = 판매 없음.')
    h = top + 3
    header(ws, h, 1, ['채널'] + RT_ORDER + ['전체'])
    for i, ch in enumerate(STAY_MAJOR + ['전체']):
        r = h + 1 + i
        tot = ch == '전체'
        chc = '' if tot else f'{CH},$A{r},'
        kw = dict(fill=FILL_T, border='total', b=True) if tot else {}
        put(ws, r, 1, ch, al=AL_L, **({'b': True} if not tot else kw))
        for j, rt in enumerate(RT_ORDER):
            put(ws, r, 2 + j, f'=IFERROR(SUMIFS({AMT},{chc}{STAYC},{HAS},1,{SOLD},{q(esc(rt))})/SUMIFS({NN},{chc}{STAYC},{HAS},1,{SOLD},{q(esc(rt))}),0)', NUM, **kw)
        put(ws, r, 2 + len(RT_ORDER), f'=IFERROR(SUMIFS({AMT},{chc}{STAYC},{HAS},1)/SUMIFS({NN},{chc}{STAYC},{HAS},1),0)', NUM, b=True, fill=FILL_T)
    count_table(ws, h + len(STAY_MAJOR) + 4, '판매 객실 타입별 건수 (참고)', SOLD, RT_ORDER, STAY_ALL)
    ws.freeze_panes = ws.cell(row=OH + 1, column=2)
    # 요일
    ws = W['요일']
    title(ws, '체크인 요일 — 언제 들어오나', '숙박만 · 취소 제외 · 요일 = 체크인한 날 (공휴일 구분 없음)', f'기간 {PERIOD} 동안 요일마다 날짜 수가 달라(4~5번) 아래 첫 표는 하루 평균으로 비교.')
    section(ws, 5, '요일별 하루 평균 (전체)')
    h = 7
    header(ws, h, 1, ['요일', '기간 중 날짜 수', '체크인 숙박 건수', '하루 평균 건수', '1박 평균(원)'], [14, 12, 13, 12, 12])
    WD_ROW = {}
    for i, d in enumerate(WD):
        r = h + 1 + i
        WD_ROW[d] = r
        put(ws, r, 1, d, b=True, al=AL_C)
        put(ws, r, 2, int(DAYS_WD.get(d, 0)), NUM, al=AL_C)
        put(ws, r, 3, f'=COUNTIFS({STAYC},{WDC},"{d}")', NUM, al=AL_C)
        put(ws, r, 4, f'=IFERROR(C{r}/B{r},0)', DEC1, al=AL_C)
        put(ws, r, 5, f'=IFERROR(SUMIFS({AMT},{STAYC},{HAS},1,{WDC},"{d}")/SUMIFS({NN},{STAYC},{HAS},1,{WDC},"{d}"),0)', NUM, al=AL_C)
    ws.conditional_formatting.add(f'D{h + 1}:D{h + 7}', DataBarRule(start_type='num', start_value=0, end_type='max', color=BLUE_L, showValue=True))
    WH, WROWS, WC0, WLAST = heat_table(ws, h + 10, '채널별 체크인 요일 비중', '가로로 더하면 100%. 요일마다 날짜 수가 달라 4~5% 차이는 의미 없음.', WDC, WD, STAY_MAJOR)
    top = WLAST + 3
    section(ws, top, '요일별 1박 평균 금액(원)', '같은 줄(채널) 안에서 요일 간 비교용.')
    h2 = top + 3
    header(ws, h2, 1, ['채널'] + WD + ['전체'])
    for i, ch in enumerate(STAY_MAJOR + ['전체']):
        r = h2 + 1 + i
        tot = ch == '전체'
        chc = '' if tot else f'{CH},$A{r},'
        kw = dict(fill=FILL_T, border='total', b=True) if tot else {}
        put(ws, r, 1, ch, al=AL_L, **({'b': True} if not tot else kw))
        for j, d in enumerate(WD):
            put(ws, r, 2 + j, f'=IFERROR(SUMIFS({AMT},{chc}{STAYC},{HAS},1,{WDC},"{d}")/SUMIFS({NN},{chc}{STAYC},{HAS},1,{WDC},"{d}"),0)', NUM, **kw)
        put(ws, r, 9, f'=IFERROR(SUMIFS({AMT},{chc}{STAYC},{HAS},1)/SUMIFS({NN},{chc}{STAYC},{HAS},1),0)', NUM, b=True, fill=FILL_T)
    # 투숙일수
    ws = W['투숙일수']
    title(ws, '투숙일수 — 몇 박 묵었나', '숙박만 · 취소 제외 · 가로로 더하면 100% · 색이 진할수록 비중이 큼', small_note)
    avg_n = ('평균 박수', lambda chc, r: f'=IFERROR(SUMIFS({NN},{chc}{STAYC})/COUNTIFS({chc}{STAYC}),0)', DEC1)
    SH, SROWS, SC0, SLAST = heat_table(ws, 5, '채널별 투숙일수 비중', None, LOSC, LOS, STAY_MAJOR, [avg_n])
    count_table(ws, SLAST + 3, '건수 (참고)', LOSC, LOS, STAY_ALL)

    # =====================================================================
    # 10) 국적
    # =====================================================================
    ws = W['국적']
    title(ws, '국적 — 해외 OTA 손님은 어디서 왔나', '채널이 PMS에 넘겨준 국적 코드 기준 (--nat 자료). 취소 제외.',
          '국적이 넘어오는 채널: ' + (', '.join(NAT_CH) if NAT_CH else '없음') + ' · 국적을 넘겨주지 않는 채널은 표에서 빠짐.')
    section(ws, 5, '국적별 건수 (국적이 확인된 예약)')
    h = 7
    header(ws, h, 1, ['국적', '건수', '비중'], [14, 10, 9])
    NAT_ROW = {}
    for i, n in enumerate(NAT_ORDER):
        r = h + 1 + i
        NAT_ROW[n] = r
        put(ws, r, 1, n, b=True, al=AL_L)
        put(ws, r, 2, f'=COUNTIFS({NATC},$A{r},{VALID})', NUM)
        put(ws, r, 3, f'=IFERROR(B{r}/$B${h + 1 + len(NAT_ORDER)},0)', PCT0)
    NT = h + 1 + len(NAT_ORDER)
    put(ws, NT, 1, '합계', b=True, fill=FILL_T, border='total', al=AL_L)
    put(ws, NT, 2, f'=SUM(B{h + 1}:B{NT - 1})' if NAT_ORDER else 0, NUM, b=True, fill=FILL_T, border='total')
    put(ws, NT, 3, f'=IFERROR(B{NT}/B{NT},0)', PCT0, b=True, fill=FILL_T, border='total')
    if NAT_ORDER:
        ws.conditional_formatting.add(f'B{h + 1}:B{NT - 1}', DataBarRule(start_type='num', start_value=0, end_type='max', color=BLUE_L, showValue=True))
    top = NT + 3
    section(ws, top, '채널별 국적 확인 비율', '국적이 비어 있는 예약은 위 표에서 빠짐 → 확인 비율이 낮은 채널은 해석 주의.')
    h = top + 3
    header(ws, h, 1, ['채널', '유효 예약', '국적 확인', '확인 비율'])
    COV_ROW = {}
    for i, ch in enumerate(NAT_COVER_CH):
        r = h + 1 + i
        COV_ROW[ch] = r
        put(ws, r, 1, ch, b=True, al=AL_L)
        put(ws, r, 2, f'=COUNTIFS({CH},$A{r},{VALID})', NUM)
        put(ws, r, 3, f'=COUNTIFS({CH},$A{r},{VALID},{CCC},"?*")', NUM)
        put(ws, r, 4, f'=IFERROR(C{r}/B{r},0)', PCT0)
    top = h + len(NAT_COVER_CH) + 3
    if NAT_CH:
        section(ws, top, '채널 × 국적 건수')
        h = top + 2
        header(ws, h, 1, ['국적'] + NAT_CH + ['합계'])
        for i, n in enumerate(NAT_ORDER):
            r = h + 1 + i
            put(ws, r, 1, n, b=True, al=AL_L)
            for j, ch in enumerate(NAT_CH):
                put(ws, r, 2 + j, f'=COUNTIFS({CH},{L(2 + j)}${h},{NATC},$A{r},{VALID})', NUM, al=AL_C)
            put(ws, r, 2 + len(NAT_CH), f'=SUM(B{r}:{L(1 + len(NAT_CH))}{r})', NUM, al=AL_C, b=True, fill=FILL_T)
        top = h + len(NAT_ORDER) + 3
    for line in ['• 국적을 PMS에 넘겨주지 않는 채널은 그 채널의 관리 화면에서만 확인할 수 있음.',
                 '• 이름 표기(로마자·한자)로 국적을 추정하지 않음 — 오분류가 나기 쉬움.']:
        ws.cell(row=top, column=1, value=line).font = fnt(9.5, c=INK2)
        top += 1

    # =====================================================================
    # 11) 기업기관
    # =====================================================================
    ws = W['기업기관']
    title(ws, '기업·기관 — 업체별', ('매출 = PMS 청구 보고서 기준 (그 달에 묵은 만큼만) · 유효 예약·박수·1박 평균은 체크인 기준 예약, 취소 제외 · 매출은 만원'
                                 if BREV else '취소 제외 · 금액은 체크인 기준 전액 (다음 달로 이어지는 장기 투숙 포함) · 매출은 만원'))
    h = 4
    RGH = RT_ORDER   # 판매 객실 타입 그대로
    header(ws, h, 1, ['업체 (거래처)', '유효 예약', '숙박 박수', '매출(만원)', '전월 매출(만원)', '1박 평균(원)', '평균 박수'] + RGH,
           [30, 9, 9, 11, 13, 11, 9] + [10] * len(RGH))
    for i, acc in enumerate(CORP_ACC):
        r = h + 1 + i
        a = f'$A{r}'
        put(ws, r, 1, acc, b=True, al=AL_L)
        put(ws, r, 2, f'=COUNTIFS({ACC},{a},{VALID})', NUM)
        put(ws, r, 3, f'=SUMIFS({NN},{ACC},{a},{VALID})', NUM)
        put(ws, r, 4, f'=SUMIFS({MAPR("G")},{MAPR("A")},{a})/10000' if BREV else f'=SUMIFS({AMT},{ACC},{a},{VALID})/10000', NUM)
        put(ws, r, 5, f'=SUMIFS({MAPR("H")},{MAPR("A")},{a})/10000' if BREV else (f'=SUMIFS({PR("J")},{PR("A")},{a})/10000' if prev else ''), NUM, color=INK2)
        put(ws, r, 6, f'=IFERROR(SUMIFS({AMT},{ACC},{a},{VALID},{HAS},1)/SUMIFS({NN},{ACC},{a},{VALID},{HAS},1),0)', NUM)
        put(ws, r, 7, f'=IFERROR(C{r}/COUNTIFS({ACC},{a},{STAYC}),0)', DEC1)
        for j, g in enumerate(RGH):
            put(ws, r, 8 + j, f'=COUNTIFS({ACC},{a},{STAYC},{SOLD},{q(esc(g))})', NUM, al=AL_C)
    CT = h + 1 + len(CORP_ACC)
    put(ws, CT, 1, '합계', b=True, fill=FILL_T, border='total', al=AL_L)
    for c in [2, 3, 4, 5] + list(range(8, 8 + len(RGH))):
        put(ws, CT, c, f'=SUM({L(c)}{h + 1}:{L(c)}{CT - 1})' if CORP_ACC else 0, NUM, b=True, fill=FILL_T, border='total', al=AL_C if c >= 8 else AL_R)
    put(ws, CT, 6, f'=IFERROR(SUMIFS({AMT},{CH},"기업·기관",{VALID},{HAS},1)/SUMIFS({NN},{CH},"기업·기관",{VALID},{HAS},1),0)', NUM, b=True, fill=FILL_T, border='total')
    put(ws, CT, 7, f'=IFERROR(C{CT}/COUNTIFS({CH},"기업·기관",{STAYC}),0)', DEC1, b=True, fill=FILL_T, border='total')
    if CORP_ACC:
        ws.conditional_formatting.add(f'D{h + 1}:D{CT - 1}', DataBarRule(start_type='num', start_value=0, end_type='max', color=BLUE_L, showValue=True))
    ws.freeze_panes = 'B5'

    # =====================================================================
    # 11b) 청구대조 — PMS 청구 보고서(매출 인식 일자)와 이 분석(체크인한 달에 예약 전액) 맞추기
    # =====================================================================
    def man(v, sign=False):
        """원 -> 'N만' / '−N만' (만 원 반올림, 대시보드 KPI와 같은 표기)"""
        s = '−' if v < 0 else ('+' if sign and v > 0 else '')
        return s + f'{int(round(abs(int(v)) / 10000)):,}만'


    BILL_SUM = None
    if BILL:
        ws = W['청구대조']
        NM, PMM = M % 12 + 1, (M - 2) % 12 + 1
        PLD = (per.to_timestamp(how='start') - pd.Timedelta(days=1)).day   # 전달 말일
        WHY = OrderedDict([('next', f'{NM}월까지 이어진 숙박 — {NM}월분은 {NM}월 매출로 잡힘'),
                           ('early', f'{PMM}/{PLD} 밤 손님인데 {M}/1 새벽 입실 — 그 밤은 {PMM}월 매출'),
                           ('prev', f'{PMM}월에 들어와 {M}월까지 묵은 손님 — {M}월분'),
                           ('late', f'{M}/{last_day} 밤 손님인데 {NM}/1 새벽 입실 — PMS 검색은 {NM}월, 청구 보고서는 {M}월'),
                           ('walkin', f'{NM}/1 새벽 워크인 — {M}/{last_day} 영업일 매출로 잡힘'),
                           ('etc', '기타 — 달을 넘겨 붙은 추가 요금 등')])
        WHY_SHORT = {'next': f'{NM}월까지 이어진 숙박 {{n}}건의 {NM}월분', 'early': f'{PMM}/{PLD} 밤·{M}/1 새벽 입실 {{n}}건',
                     'prev': f'{PMM}월에 들어온 손님 {{n}}건의 {M}월분', 'late': f'{M}/{last_day} 밤·{NM}/1 새벽 입실 {{n}}건',
                     'walkin': f'{NM}/1 새벽 워크인 {{n}}건', 'etc': '기타 {n}건'}
        amt_by_id = {rk(k): int(v) for k, v in zip(V['예약 번호'], V['_amt'])}
        blines = []
        for ln in BILL['lines']:
            a_ = amt_by_id.get(rk(ln['id']), 0)
            blines.append(dict(ln, a=a_, d=int(ln['b']) - a_, why=ln['why'] if ln['why'] in WHY else 'etc'))
        blines.sort(key=lambda l: (list(WHY).index(l['why']), -abs(l['d'])))
        ana_total = int(V['_amt'].sum())
        b_total = int(BILL['total'])
        bk = OrderedDict()
        for l in blines:
            t_ = bk.setdefault(l['why'], [0, 0])
            t_[0] += 1
            t_[1] += l['d']
        BILL_OK = ana_total + sum(l['d'] for l in blines) == b_total
        _room = next((v for k, v in BILL['parts'] if k == '객실'), 0)
        BILL_SUM = dict(total=b_total, analysis=ana_total, diff=b_total - ana_total, ok=BILL_OK, parts=BILL['parts'],
                        extra=b_total - int(_room), buckets=OrderedDict((k, dict(label=WHY[k], n=v[0], amount=v[1])) for k, v in bk.items()))
        title(ws, (f'청구대조 — PMS 청구 보고서(이 파일의 매출)와 체크인 기준 예약 금액 맞추기 ({Y}년 {M}월)' if BREV
                   else f'청구대조 — PMS 청구 보고서와 이 분석 매출 맞추기 ({Y}년 {M}월)'),
              f"PMS 청구 보고서: {BILL.get('conditions', '')} · {BILL.get('fetched_at', '')}",
              ('청구 보고서 = 손님이 묵은 날짜(영업일)마다 매출을 나눠 그 달에 넣음 (이 파일의 매출) · 예약 금액 = 체크인한 달에 예약 전액 → 달을 넘겨 묵은 손님에서 차이가 남' if BREV
               else '청구 보고서 = 손님이 묵은 날짜(영업일)마다 매출을 나눠 그 달에 넣음 · 이 분석 = 체크인한 달에 예약 매출 전액 → 달을 넘겨 묵은 손님에서 차이가 남'))
        ws.column_dimensions['A'].width = 54
        for col, w_ in zip('BCDEFG', [14, 26, 14, 16, 18, 16]):
            ws.column_dimensions[col].width = w_
        section(ws, 5, '1. PMS 청구 보고서 구성', '객실 = 객실 요금 · 나머지 = 부대 매출 (객실 서비스·음식·음료·기타)')
        h = 7
        header(ws, h, 1, ['항목', '금액(원)', '비중'])
        BT = h + 1 + len(BILL['parts'])
        for i, (k, v) in enumerate(BILL['parts']):
            r = h + 1 + i
            put(ws, r, 1, k, b=True, al=AL_L)
            put(ws, r, 2, int(v), NUM)
            put(ws, r, 3, f'=IFERROR(B{r}/$B${BT},0)', PCT1)
        put(ws, BT, 1, '청구 금액 합계', b=True, fill=FILL_T, border='total', al=AL_L)
        put(ws, BT, 2, f'=SUM(B{h + 1}:B{BT - 1})', NUM, b=True, fill=FILL_T, border='total')
        put(ws, BT, 3, f'=IFERROR(B{BT}/B{BT},0)', PCT1, b=True, fill=FILL_T, border='total')
        top = BT + 3
        section(ws, top, '2. 체크인 기준 예약 금액 → PMS 청구 보고서' if BREV else '2. 이 분석 매출 → PMS 청구 보고서',
                '아래 3번 예약별 내역을 이유별로 더한 것 (청구 − 예약 금액). 마지막 줄이 0이면 1원까지 맞음.')
        h = top + 3
        header(ws, h, 1, ['구분', '금액(원)', '예약 수'])
        RA = h + 1
        RB0 = RA + 1
        RCALC = RB0 + len(bk)
        RBILL, RCHK = RCALC + 1, RCALC + 2
        TOP3 = RCHK + 3
        H3 = TOP3 + 3
        D0, D1 = H3 + 1, H3 + len(blines)
        put(ws, RA, 1, f'체크인 기준 예약 금액 ({M}월 체크인, 취소 제외)' if BREV else '이 분석 매출 (체크인한 달 기준, 취소 제외)', b=True, al=AL_L)
        put(ws, RA, 2, f'=SUMIFS({AMT},{VALID})', NUM, b=True)
        put(ws, RA, 3, f'=COUNTIFS({VALID})', NUM)
        for i, (k, v) in enumerate(bk.items()):
            r = RB0 + i
            put(ws, r, 1, ('   + ' if v[1] >= 0 else '   − ') + WHY[k], al=AL_L)
            put(ws, r, 2, f'=SUMIFS($G${D0}:$G${D1},$A${D0}:$A${D1},{q(esc(WHY[k]))})', NUM)
            put(ws, r, 3, f'=COUNTIFS($A${D0}:$A${D1},{q(esc(WHY[k]))})', NUM)
        put(ws, RCALC, 1, '→ 예약 금액 + 차이 = 계산한 청구 보고서 매출' if BREV else '→ 분석 매출 + 차이 = 계산한 청구 보고서 매출', b=True, fill=FILL_T, border='total', al=AL_L)
        put(ws, RCALC, 2, f'=B{RA}+SUM(B{RB0}:B{RCALC - 1})', NUM, b=True, fill=FILL_T, border='total')
        put(ws, RCALC, 3, '', fill=FILL_T, border='total')
        put(ws, RBILL, 1, 'PMS 청구 보고서 합계 (위 1번)', b=True, al=AL_L)
        put(ws, RBILL, 2, f'=B{BT}', NUM, b=True)
        put(ws, RCHK, 1, '차이 (0이면 1원까지 맞음)', al=AL_L, color=INK2)
        put(ws, RCHK, 2, f'=B{RCALC}-B{RBILL}', '#,##0;-#,##0;"0 (1원까지 맞음)"', b=True)
        ws.conditional_formatting.add(f'B{RCHK}', CellIsRule(operator='equal', formula=['0'], font=Font(color=GOOD, bold=True)))
        ws.conditional_formatting.add(f'B{RCHK}', CellIsRule(operator='notEqual', formula=['0'], font=Font(color=BAD, bold=True)))
        section(ws, TOP3, '3. 예약별 내역 — 두 금액이 다른 예약만', '예약번호로 PMS에서 바로 확인 가능 · 분석 매출은 [원본]에서 자동 계산 · 손님 이름은 넣지 않음')
        header(ws, H3, 1, ['이유', '예약번호', '거래처', '숙박(예정)', '예약 금액(원)' if BREV else '이 분석 매출(원)', f'청구 보고서 {M}월분(원)', '차이(청구−예약)' if BREV else '차이(청구−분석)'])
        for i, l in enumerate(blines):
            r = D0 + i
            put(ws, r, 1, WHY[l['why']], al=AL_L, color=INK2, sz=9.5)
            put(ws, r, 2, rid(l['id']), '0', al=AL_C)
            put(ws, r, 3, l['acc'], al=AL_L)
            put(ws, r, 4, l.get('stay', ''), al=AL_C)
            put(ws, r, 5, f'=SUMIFS({AMT},원본!$A$2:$A${RMAX},B{r},{VALID})', NUM)
            put(ws, r, 6, int(l['b']), NUM)
            put(ws, r, 7, f'=F{r}-E{r}', NUM)
        if blines:
            ws.conditional_formatting.add(f'G{D0}:G{D1}', CellIsRule(operator='lessThan', formula=['0'], font=Font(color=BAD)))
            ws.conditional_formatting.add(f'G{D0}:G{D1}', CellIsRule(operator='greaterThan', formula=['0'], font=Font(color=GOOD)))
        ws.cell(row=D1 + 2, column=1, value=('• 이 파일의 매출(대시보드·채널별·기업기관)은 위 1번 PMS 청구 보고서 기준. 이 탭은 체크인 기준 예약 금액([원본] AG열 합계)과 왜 다른지 보여 줌.'
                                             if BREV else '• 월 매출 보고·회계·작년 대비는 PMS 청구 보고서 숫자, 채널·손님·객실 분석은 이 분석(예약 단위)을 볼 것.')).font = fnt(9.5, c=INK2)
        ws.cell(row=D1 + 3, column=1, value='• 객실 서비스·음식·음료·기타 요금은 예약 매출(PMS 매출액)에 이미 들어 있음 — 같은 달 안에 끝난 예약은 두 금액이 같음.').font = fnt(9.5, c=INK2)

    # =====================================================================
    # 12) 차트데이터 (대시보드 차트의 원본 숫자 — 모두 다른 탭 참조)
    # =====================================================================
    ws = W['차트데이터']
    title(ws, '차트데이터 — 대시보드 차트와 KPI가 읽는 숫자 (다른 탭 참조, 직접 고치지 말 것)')
    ws.column_dimensions['A'].width = 18
    for c in range(2, 10):
        ws.column_dimensions[L(c)].width = 12
    CD = {}
    r = 3
    # KPI
    put(ws, r, 1, 'KPI', b=True, border=None)
    header(ws, r + 1, 1, ['지표', '이번 달', '전월', '변화'])
    CT_ = TOT
    kpis = [
        ('총 매출(만원)', f'=채널별!D{CT_}', (f'=채널별!F{CT_}' if BREV else f'={PTOT("J")}/10000') if prev else '', 'ratio'),
        ('유효 예약(건)', f'=채널별!C{CT_}', f'={PTOT("F")}' if prev else '', 'ratio'),
        ('숙박 박수(박)', f'=SUMIFS({NN},{STAYC})', f'={PTOT("I")}' if prev else '', 'ratio'),
        ('1박 평균(원)', f'=채널별!H{CT_}', f'=IFERROR({PTOT("K")}/{PTOT("L")},0)' if prev else '', 'ratio'),
        ('취소율', f'=채널별!L{CT_}', f'=IFERROR({PTOT("E")}/{PTOT("D")},0)' if prev else '', 'pp'),
        ('당일 예약 비중(숙박)', f'=채널별!K{CT_}', f'=IFERROR({PTOT("M")}/{PTOT("G")},0)' if prev else '', 'pp'),
    ]
    KPI_ROW = {}
    for i, (k, cur, pv, kind) in enumerate(kpis):
        rr = r + 2 + i
        KPI_ROW[k] = (rr, kind)
        fmt = PCT1 if kind == 'pp' else NUM
        put(ws, rr, 1, k, al=AL_L)
        put(ws, rr, 2, cur, fmt)
        put(ws, rr, 3, pv, fmt)
        if prev:
            put(ws, rr, 4, f'=IFERROR(B{rr}/C{rr}-1,"")' if kind == 'ratio' else f'=B{rr}-C{rr}', DELTA_PP if kind == 'pp' else '0.0%')
        else:
            put(ws, rr, 4, '전월 자료 없음', al=AL_L)
    r = r + 2 + len(kpis) + 2
    # 1. 채널별 매출 (이번 달 vs 전월)
    put(ws, r, 1, '1. 채널별 매출(만원)', b=True, border=None)
    header(ws, r + 1, 1, ['채널', f'{M}월'] + ([PM_LABEL] if prev else []))
    c1_rows = MAJOR + (['__ETC__'] if has_minor else [])
    for i, ch in enumerate(c1_rows):
        rr = r + 2 + i
        src = ETC if ch == '__ETC__' else CH_ROW[ch]
        put(ws, rr, 1, '기타' if ch == '__ETC__' else f'=채널별!A{src}', al=AL_L)
        put(ws, rr, 2, f'=채널별!D{src}', NUM)
        if prev:
            put(ws, rr, 3, f'=채널별!F{src}', NUM)
    CD['c1'] = (r + 1, r + 1 + len(c1_rows), 3 if prev else 2)
    r = r + 2 + len(c1_rows) + 2
    # 2. 대분류 구성 (비중)
    put(ws, r, 1, '2. 대분류별 매출 비중', b=True, border=None)
    header(ws, r + 1, 1, ['월'] + GROUPS)
    mrows = [(f'{M}월', 'D', 'D')] + ([(PM_LABEL, 'F', 'F')] if prev else [])
    for i, (lab, col, _) in enumerate(mrows):
        rr = r + 2 + i
        put(ws, rr, 1, lab, al=AL_L)
        for j, g in enumerate(GROUPS):
            put(ws, rr, 2 + j, f'=IFERROR(채널별!{col}{G_ROW[g]}/채널별!{col}{GT},0)', PCT0)
    CD['c2'] = (r + 1, r + 1 + len(mrows), 1 + len(GROUPS))
    r = r + 2 + len(mrows) + 2
    # 3. 1박 평균
    put(ws, r, 1, '3. 채널별 1박 평균(원)', b=True, border=None)
    header(ws, r + 1, 1, ['채널', '1박 평균(원)', '금액 기준'])
    for i, ch in enumerate(ADR_CH):
        rr = r + 2 + i
        put(ws, rr, 1, f'=채널별!A{CH_ROW[ch]}', al=AL_L)
        put(ws, rr, 2, f'=채널별!H{CH_ROW[ch]}', NUM)
        put(ws, rr, 3, f'=채널별!I{CH_ROW[ch]}', al=AL_C)
    CD['c3'] = (r + 1, r + 1 + len(ADR_CH), 2)
    r = r + 2 + len(ADR_CH) + 2
    # 4. 리드타임 구성
    put(ws, r, 1, '4. 채널별 예약 시점 비중', b=True, border=None)
    header(ws, r + 1, 1, ['채널'] + LB)
    c4 = ['전체'] + LEAD_SORT
    for i, ch in enumerate(c4):
        rr = r + 2 + i
        put(ws, rr, 1, f'=리드타임!A{LROWS[ch]}', al=AL_L)
        for j in range(len(LB)):
            put(ws, rr, 2 + j, f'=리드타임!{L(LC0 + j)}{LROWS[ch]}', PCT0)
    CD['c4'] = (r + 1, r + 1 + len(c4), 1 + len(LB))
    r = r + 2 + len(c4) + 2
    # 5. 객실 구성
    put(ws, r, 1, '5. 채널별 판매 객실 구성 비중', b=True, border=None)
    header(ws, r + 1, 1, ['채널'] + RT_ORDER)
    c5 = ['전체'] + ROOM_SORT
    for i, ch in enumerate(c5):
        rr = r + 2 + i
        put(ws, rr, 1, f'=객실!A{OROWS[ch]}', al=AL_L)
        for j in range(len(RT_ORDER)):
            put(ws, rr, 2 + j, f'=객실!{L(OC0 + j)}{OROWS[ch]}', PCT0)
    CD['c5'] = (r + 1, r + 1 + len(c5), 1 + len(RT_ORDER))
    r = r + 2 + len(c5) + 2
    # 6. 국적
    put(ws, r, 1, '6. 국적 (해외 OTA, 국적 확인분)', b=True, border=None)
    header(ws, r + 1, 1, ['국적', '건수'])
    c6 = NAT_TOP + (['기타'] if len(NAT_ORDER) > len(NAT_TOP) else [])
    for i, n in enumerate(c6):
        rr = r + 2 + i
        if n == '기타':
            put(ws, rr, 1, '기타', al=AL_L)
            put(ws, rr, 2, f'=국적!B{NT}-SUM(B{r + 2}:B{rr - 1})', NUM)
        else:
            put(ws, rr, 1, f'=국적!A{NAT_ROW[n]}', al=AL_L)
            put(ws, rr, 2, f'=국적!B{NAT_ROW[n]}', NUM)
    CD['c6'] = (r + 1, r + 1 + len(c6), 2)
    r = r + 2 + len(c6) + 2
    # 7. 요일
    put(ws, r, 1, '7. 요일별 하루 평균 체크인(숙박)', b=True, border=None)
    header(ws, r + 1, 1, ['요일', '하루 평균'])
    for i, d in enumerate(WD):
        rr = r + 2 + i
        put(ws, rr, 1, d, al=AL_C)
        put(ws, rr, 2, f'=요일!D{WD_ROW[d]}', DEC1)
    CD['c7'] = (r + 1, r + 1 + len(WD), 2)


    # =====================================================================
    # 13) 차트
    # =====================================================================
    def rich(sz=900, color=INK2, b=False):
        cp = CharacterProperties(sz=sz, b=b, solidFill=color, latin=DFont(typeface=F), ea=DFont(typeface=F))
        return RichText(p=[Paragraph(pPr=ParagraphProperties(defRPr=cp), endParaRPr=cp)])


    def labels(fmt, color=INK, sz=900, pos=None, b=False):
        d = DataLabelList()
        d.showVal = True
        d.showSerName = d.showCatName = d.showLegendKey = d.showPercent = d.showBubbleSize = False
        d.numFmt = fmt
        d.txPr = rich(sz, color, b)
        if pos:
            d.dLblPos = pos
        return d


    def base(kind='bar', stacked=False, w=13.0, h=8.0, legend=False):
        ch = BarChart()
        ch.type = kind
        ch.grouping = 'percentStacked' if stacked else 'clustered'
        if stacked:
            ch.overlap = 100
        ch.gapWidth = 40 if stacked else 55
        ch.width, ch.height = w, h
        ch.roundedCorners = False
        ch.graphical_properties = GraphicalProperties(ln=LineProperties(noFill=True))
        ch.x_axis.delete = False
        ch.x_axis.majorTickMark = 'none'
        ch.x_axis.minorTickMark = 'none'
        ch.x_axis.txPr = rich(900, INK)
        ch.x_axis.graphicalProperties = GraphicalProperties(ln=LineProperties(solidFill=BASE, w=9525))
        if kind == 'bar':
            ch.x_axis.scaling.orientation = 'maxMin'
        ch.y_axis.delete = True
        ch.y_axis.majorGridlines = None
        ch.legend = Legend(legendPos='t') if legend else None
        if legend:
            ch.legend.txPr = rich(900, INK2)
            ch.legend.overlay = False
        return ch


    def fill(s, color, gap=False):
        s.graphicalProperties = GraphicalProperties(solidFill=color)
        s.graphicalProperties.line = LineProperties(solidFill='FFFFFF', w=12700) if gap else LineProperties(noFill=True)


    def refs(key):
        h, last, ncol = CD[key]
        cd = W['차트데이터']
        cats = Reference(cd, min_col=1, min_row=h + 1, max_row=last)
        data = Reference(cd, min_col=2, max_col=ncol, min_row=h, max_row=last)
        return cats, data, last - h


    CHARTS = []
    # 1 채널별 매출
    cats, data, n = refs('c1')
    c1 = base('bar', w=13.0, h=max(7.0, 1.6 + n * (0.75 if prev else 0.5)), legend=bool(prev))
    c1.add_data(data, titles_from_data=True)
    c1.set_categories(cats)
    fill(c1.series[0], BLUE)
    c1.series[0].dLbls = labels('#,##0', INK, 850, 'outEnd')
    if prev:
        fill(c1.series[1], BLUE_L)
        c1.gapWidth = 45
        c1.overlap = -5
    CHARTS.append(('c1', c1))
    # 2 대분류 구성
    cats, data, n = refs('c2')
    c2 = base('bar', stacked=True, w=13.0, h=4.6, legend=True)
    c2.add_data(data, titles_from_data=True)
    c2.set_categories(cats)
    for j, s in enumerate(c2.series):
        fill(s, CAT[j % len(CAT)], gap=True)
        s.dLbls = labels('[<0.04]"";0%', CAT_TXT[j % len(CAT_TXT)], 850, 'ctr')
    c2.gapWidth = 35
    CHARTS.append(('c2', c2))
    # 3 1박 평균
    cats, data, n = refs('c3')
    c3 = base('bar', w=13.0, h=max(6.0, 1.4 + n * 0.62))
    c3.add_data(data, titles_from_data=True)
    c3.set_categories(cats)
    fill(c3.series[0], BLUE)
    for i, ch in enumerate(ADR_CH):
        if CH_BASIS.get(ch) == '판매가':
            dp = DataPoint(idx=i)
            dp.graphicalProperties = GraphicalProperties(solidFill=GRAYBAR)
            dp.graphicalProperties.line = LineProperties(noFill=True)
            c3.series[0].dPt.append(dp)
    c3.series[0].dLbls = labels('#,##0', INK, 850, 'outEnd')
    CHARTS.append(('c3', c3))
    # 4 리드타임
    cats, data, n = refs('c4')
    c4c = base('bar', stacked=True, w=13.0, h=max(6.5, 2.2 + n * 0.62), legend=True)
    c4c.add_data(data, titles_from_data=True)
    c4c.set_categories(cats)
    for j, s in enumerate(c4c.series):
        fill(s, ORD5[j], gap=True)
        s.dLbls = labels('[<0.07]"";0%', ORD5_TXT[j], 800, 'ctr')
    CHARTS.append(('c4', c4c))
    # 5 객실
    cats, data, n = refs('c5')
    c5c = base('bar', stacked=True, w=13.0, h=max(6.5, 2.2 + n * 0.62), legend=True)
    c5c.add_data(data, titles_from_data=True)
    c5c.set_categories(cats)
    for j, s in enumerate(c5c.series):
        fill(s, CAT[j % len(CAT)], gap=True)
        s.dLbls = labels('[<0.07]"";0%', CAT_TXT[j % len(CAT_TXT)], 800, 'ctr')
    CHARTS.append(('c5', c5c))
    # 6 국적
    cats, data, n = refs('c6')
    c6c = base('bar', w=13.0, h=max(5.0, 1.4 + n * 0.62))
    if n:
        c6c.add_data(data, titles_from_data=True)
        c6c.set_categories(cats)
        fill(c6c.series[0], BLUE)
        c6c.series[0].dLbls = labels('#,##0"건"', INK, 850, 'outEnd')
    CHARTS.append(('c6', c6c))
    # 7 요일
    cats, data, n = refs('c7')
    c7c = base('col', w=13.0, h=5.6)
    c7c.add_data(data, titles_from_data=True)
    c7c.set_categories(cats)
    fill(c7c.series[0], BLUE)
    c7c.series[0].dLbls = labels('0.0', INK, 850, 'outEnd')
    c7c.gapWidth = 60
    CHARTS.append(('c7', c7c))
    CH_OBJ = dict(CHARTS)

    # =====================================================================
    # 14) 대시보드
    # =====================================================================
    ws = W['대시보드']
    ws.column_dimensions['A'].width = 2.5
    for c in range(2, 14):
        ws.column_dimensions[L(c)].width = 11.3
    ROW_CM = 0.53  # 기본 행 높이 15pt ≈ 0.53cm
    ws.row_dimensions[1].height = 8
    ws['B2'] = f'{HOTEL} · {Y}년 {M}월 매출 분석' + (' (PMS 화면 기준)' if PMS_BASIS else '')
    ws['B2'].font = fnt(18, True)
    ws.row_dimensions[2].height = 32
    sub = (f'매출 = PMS 청구 보고서 {M}/1~{M}/{last_day} (손님이 묵은 날 기준) · 예약 수·박수·단가 = {PERIOD_TXT} 예약, 취소 제외 · 내보내기 {exported_at}'
           if BREV else f'{PERIOD_TXT} · 취소 제외 · PMS 내보내기 {exported_at} 기준')
    if p1.day < last_day:
        miss_txt = f'{M}/{last_day}' if p1.day + 1 == last_day else f'{M}/{p1.day + 1}~{M}/{last_day}'
        sub += f' · {miss_txt} 체크인은 내보내기 뒤라 빠짐'
    if prev:
        sub += f' · 전월 = {PM_LABEL}' if BREV else f" · 전월 = {prev.get('period', PM_LABEL)}"
    if not CFG['verified']:
        sub = f'[미검증 매핑: {PMS_LABEL}] ' + sub
    ws['B3'] = sub
    ws['B3'].font = fnt(9.5, c=INK2)
    ws.row_dimensions[4].height = 8
    # KPI 타일 (2열 x 6개)
    TILE = [('매출 (PMS 청구 보고서)' if BREV else '총 매출', '총 매출(만원)', '#,##0"만원"', 'up'),('유효 예약', '유효 예약(건)', '#,##0"건"', 'up'),
            ('숙박 박수', '숙박 박수(박)', '#,##0"박"', 'up'), ('1박 평균', '1박 평균(원)', '#,##0"원"', 'up'),
            ('취소율', '취소율', '0.0%', 'down'), ('당일 예약 비중', '당일 예약 비중(숙박)', '0%', 'neutral')]
    wb_side = Side(style='thick', color='FFFFFF')
    for i, (lab, key, fmt, good) in enumerate(TILE):
        c = 2 + i * 2
        kr, kind = KPI_ROW[key]
        for rr in (5, 6, 7):
            ws.merge_cells(start_row=rr, start_column=c, end_row=rr, end_column=c + 1)
            for cc in (c, c + 1):
                x = ws.cell(row=rr, column=cc)
                x.fill = FILL_TILE
                x.border = Border(left=wb_side if cc == c else None, right=wb_side if cc == c + 1 else None)
        x = ws.cell(row=5, column=c, value=lab); x.font = fnt(9.5, c=INK2); x.alignment = AL_C
        x = ws.cell(row=6, column=c, value=f'=차트데이터!B{kr}'); x.font = fnt(19, True); x.alignment = AL_C; x.number_format = fmt
        if prev:
            dfmt = ('"전월 대비 ▲ "0.0%"p";"전월 대비 ▼ "0.0%"p";"전월과 같음"' if kind == 'pp'
                    else '"전월 대비 ▲ "0.0%;"전월 대비 ▼ "0.0%;"전월과 같음"')
            x = ws.cell(row=7, column=c, value=f'=차트데이터!D{kr}'); x.number_format = dfmt
            x.font = fnt(9.5, c=INK2); x.alignment = AL_C
            rng = f'{L(c)}7'
            if good != 'neutral':
                up, dn = (GOOD, BAD) if good == 'up' else (BAD, GOOD)
                ws.conditional_formatting.add(rng, CellIsRule(operator='greaterThan', formula=['0'], font=Font(color=up, bold=True)))
                ws.conditional_formatting.add(rng, CellIsRule(operator='lessThan', formula=['0'], font=Font(color=dn, bold=True)))
        else:
            x = ws.cell(row=7, column=c, value='전월 자료 없음'); x.font = fnt(9, c=MUTED); x.alignment = AL_C
    ws.row_dimensions[5].height = 20
    ws.row_dimensions[6].height = 36
    ws.row_dimensions[7].height = 20
    ws.row_dimensions[8].height = 10
    # 이번 달 핵심
    findings = opt_json(A.findings, '--findings') or []
    if not findings:
        findings = ['(핵심 발견은 숫자 확인 후 작성)']
    r = 9
    box = []
    if BILL_SUM:   # PMS 청구 보고서와 비교 상자
        bs = BILL_SUM
        _n_extra = round(100 * bs['extra'] / max(1, bs['total']), 1)
        _why = '  ·  '.join(f"{WHY_SHORT[k].format(n=v['n'])} {man(v['amount'], True)}" for k, v in bs['buckets'].items())
        if BREV:
            box = [(f'매출은 PMS 청구 보고서와 같은 기준 (손님이 묵은 날의 매출만 그 달에 넣음)  ·  {M}월 {man(bs["total"])} 원  ·  {PMB} {man(sum(BACC["prev"].values()))} 원', True),
                   (f'{M}월에 체크인한 예약 금액으로 세면 {man(bs["analysis"])} 원 →  {_why}  → 청구 보고서 {man(bs["total"])} 원'
                    + (' (1원까지 맞음 → [청구대조])' if bs['ok'] else ' (일부 안 맞음 → [청구대조] 확인)'), False)]
        else:
            box = [(f'PMS 청구 보고서 {M}월 매출 {man(bs["total"])} 원 (손님이 묵은 날짜 기준)  ·  이 분석 {man(bs["analysis"])} 원 (체크인한 달에 예약 전액)  ·  차이 {man(bs["diff"], True)} 원', True),
                   ('차이 이유: ' + _why + ('  → 예약별로 1원까지 맞음 [청구대조]' if bs['ok'] else '  → 일부 안 맞음, [청구대조] 확인'), False)]
        box.append(('청구 보고서 구성: ' + '  ·  '.join(f'{k} {man(v)}' for k, v in bs['parts']) + f'   (객실 외 부대 매출 {man(bs["extra"])} 원, {_n_extra}%)', False))
    elif BREV:     # 청구 보고서 거래처별 매출만 있을 때
        _ct, _pt = sum(BACC['cur'].values()), sum(BACC['prev'].values())
        box = [(f'매출은 PMS 청구 보고서와 같은 기준 (손님이 묵은 날의 매출만 그 달에 넣음)  ·  {M}월 {man(_ct)} 원  ·  {PMB} {man(_pt)} 원', True),
               (f'{M}월에 체크인한 예약 금액 합계는 {man(int(V["_amt"].sum()))} 원 — 달을 넘겨 묵은 손님만큼 다름 ([원본] AG열)', False)]
        if BACC.get('cur_parts'):
            _ex = _ct - next((int(v) for k, v in BACC['cur_parts'] if k == '객실'), _ct)
            box.append(('청구 보고서 구성: ' + '  ·  '.join(f'{k} {man(v)}' for k, v in BACC['cur_parts']) + f'   (객실 외 부대 매출 {man(_ex)} 원, {round(100 * _ex / max(1, _ct), 1)}%)', False))
    if box:
        FILL_BOX = PatternFill('solid', fgColor='FBF7EC')
        box_side = Side(style='medium', color='E0B54A')
        for i, (txt, bold) in enumerate(box):
            ws.merge_cells(start_row=r, start_column=2, end_row=r, end_column=13)
            for cc in range(2, 14):
                x = ws.cell(row=r, column=cc)
                x.fill = FILL_BOX
                x.border = Border(left=box_side if cc == 2 else None, top=box_side if i == 0 else None,
                                  bottom=box_side if i == len(box) - 1 else None, right=box_side if cc == 13 else None)
            x = ws.cell(row=r, column=2, value=txt)
            x.font = fnt(10 if bold else 9.5, bold, INK if bold else INK2)
            x.alignment = AL_LW
            ws.row_dimensions[r].height = 21 if bold else (33 if len(txt) > 95 else 19)   # 긴 줄은 두 줄 높이 (잘림 방지)
            r += 1
        ws.row_dimensions[r].height = 10
        r += 1
    ws.cell(row=r, column=2, value='이번 달 핵심').font = fnt(12, True)
    ws.row_dimensions[r].height = 22
    r += 1
    for t_ in findings:
        ws.merge_cells(start_row=r, start_column=2, end_row=r, end_column=13)
        x = ws.cell(row=r, column=2, value='•  ' + t_)
        x.font = fnt(10.5)
        x.alignment = AL_LW
        ws.row_dimensions[r].height = 20
        r += 1
    r += 1


    def rows_for(cm):
        return int(math.ceil(cm / ROW_CM)) + 1


    def chart_block(r, left, right):
        """left/right = (key, 제목, 설명) — 같은 줄에 두 차트. 반환: 다음 시작 행"""
        used = 0
        for (key, ttl, cap), col in ((left, 2), (right, 8)):
            if key is None:
                continue
            ws.cell(row=r, column=col, value=ttl).font = fnt(11, True)
            ws.cell(row=r + 1, column=col, value=cap).font = fnt(9, c=INK2)
            ch = CH_OBJ[key]
            ws.add_chart(ch, f'{L(col)}{r + 2}')
            used = max(used, rows_for(ch.height))
        ws.row_dimensions[r].height = 20
        return r + 2 + used + 1


    nb = f'{MIN_N}건 미만 채널은 \'기타\'로 묶음'
    cap1 = ('PMS 청구 보고서 기준 · ' if BREV else '') + (f'막대 = 이번 달({M}월), 연한 막대 = 전월({PM_LABEL}) · ' if prev else '') + nb
    # 왼쪽 큰 차트(1) 옆에 오른쪽 작은 차트 2개(2, 7)를 위아래로
    ws.cell(row=r, column=2, value='채널별 매출 (만원)').font = fnt(11, True)
    ws.cell(row=r + 1, column=2, value=cap1).font = fnt(9, c=INK2)
    ws.add_chart(c1, f'B{r + 2}')
    ws.cell(row=r, column=8, value='매출 구성 — 어디서 팔렸나').font = fnt(11, True)
    ws.cell(row=r + 1, column=8, value='대분류별 비중' + (f' (위 {M}월, 아래 {PM_LABEL})' if prev else '')).font = fnt(9, c=INK2)
    ws.add_chart(c2, f'H{r + 2}')
    r2 = r + 2 + rows_for(c2.height) + 1
    ws.cell(row=r2, column=8, value='요일별 하루 평균 체크인 (숙박)').font = fnt(11, True)
    ws.cell(row=r2 + 1, column=8, value='요일마다 날짜 수가 달라 하루 평균으로 비교').font = fnt(9, c=INK2)
    ws.add_chart(c7c, f'H{r2 + 2}')
    ws.row_dimensions[r].height = 20
    ws.row_dimensions[r2].height = 20
    r = max(r + 2 + rows_for(c1.height), r2 + 2 + rows_for(c7c.height)) + 1
    gray_ch = [c for c in ADR_CH if CH_BASIS.get(c) == '판매가']
    cap3 = (f'회색 = {", ".join(gray_ch)}: 수수료 떼기 전 금액(판매가)으로 보여 비교 제외' if gray_ch else '대부분 수수료 뗀 뒤 금액 기준')
    ws.row_breaks.append(Break(id=r - 1))   # 인쇄: 1쪽 = KPI·비교·핵심·첫 차트 줄, 2쪽부터 나머지 차트
    r = chart_block(r, ('c3', '채널별 1박 평균 (원)', cap3),
                    ('c4', '예약 시점 — 체크인 며칠 전에 예약했나', '진할수록 일찍 예약 · 위에서부터 당일 예약이 많은 순 · ' + f'숙박 {MIN_N}건 이상 채널'))
    cov = []
    for ch in NAT_CH:
        vv = V[V['_ch'] == ch]
        cov.append(f'{ch} {int(round(100 * (vv["_nat"] != "").mean()))}%')
    cap6 = '국적 확인 비율: ' + ', '.join(cov) if cov else '국적 자료 없음'
    cap5 = (f'채널에서 산 객실 기준 · {BASE_RT} 판매 숙박의 {round(100 * STD["_moved"].mean())}%는 다른 방에 배정 → [객실] 탭' if prod and len(STD)
            else f'내보내기 객실 타입 기준 (판매 상품 자료 없음) · 위에서부터 {RT_ORDER[0]} 비중이 큰 순')
    r = chart_block(r, ('c5', '객실 구성 — 무엇이 팔렸나 (판매 기준)', cap5),
                    ('c6', '해외 OTA 손님 국적', cap6))
    # 읽는 법
    ws.cell(row=r, column=2, value='읽는 법·주의').font = fnt(11, True)
    r += 1
    notes = [(f'매출 = PMS 청구 보고서 금액 (손님이 묵은 날 기준, 객실 서비스·음식 등 부대 매출 포함) — PMS 숫자와 같음. 거래처별 금액 → [채널구분표] G·H열. '
              f'예약 수·박수·1박 평균·취소율·당일 비중·객실·국적은 {PERIOD_TXT} 예약 기준. 1박 평균 = 숙박 예약 금액 ÷ 박수 (0원 예약 제외).'
              if BREV else f'매출 = PMS 총 청구 금액 + 잔액 (= PMS 매출액), 체크인 기준 (장기 투숙은 체크인한 달에 전액). 1박 평균 = 숙박 매출 ÷ 박수 (0원 예약 제외).'),
             '금액 기준이 채널마다 다를 수 있음 (입금가 = 수수료 뗀 돈, 판매가 = 수수료 떼기 전, 실수령 = 직접 받은 돈). 같은 기준끼리만 비교 → [채널구분표].',
             f'건수가 적은 채널({MIN_N}건 미만)은 비율이 크게 흔들려 차트에서 \'기타\'로 묶거나 뺐음 → 숫자는 [채널별] 아래 표.',
             '국적은 채널이 PMS에 넘겨준 정보만 씀 (이름으로 추정하지 않음).',
             (f'리드타임·요일·박수는 PMS 예약상 체크인 예정일 기준. 내보내기의 체크인 시각은 실제 입실 시각이라 자정 넘어 입실한 {N_FIX}건은 예정일로 보정함.'
              if sched else '예정일 보정 자료(--sched)가 없어 실제 입실 날짜로 계산 — 자정 넘어 입실한 예약은 리드타임이 하루 길게, 요일이 하루 늦게 잡힘.')]
    notes.append((f'객실은 판매 기준(채널에서 산 객실). 내보내기의 객실 타입은 실제 배정한 방 — 채널 숙박의 {round(100 * CHS["_moved"].mean())}%가 산 것과 다른 방에 배정됨.'
                  if prod and len(CHS) else '판매 상품 자료(--prod)가 없어 객실은 내보내기의 객실 타입 그대로 — 이 열이 배정 방이면 낮은 객실로 팔고 윗 객실에 넣은 예약이 윗 객실로 잡힘.'))
    _adj = V[V['_bal'] != 0]
    if len(_adj):
        notes.append(f'받은 돈과 예약 금액이 다른 예약 {len(_adj)}건 (' + ', '.join(f"{c} {b:+,}원" for c, b in zip(_adj['_ch'], _adj['_bal'])) + ') — 금액은 PMS 매출액 기준, 차이는 환불하거나 더 받아야 할 돈.')
    if PMS_BASIS:
        notes.append(f'기간은 PMS 화면 기준 — PMS 예약 통합 검색에서 체크인 {M}/1~{M}/{last_day}로 찾은 결과와 건수·매출이 같음. 입실한 예약은 실제 입실 시각으로 걸러져, 자정 넘어 입실한 손님은 입실한 날의 달로 들어감'
                     + (f' (앞뒤 하루 넓게 받은 내보내기에서 다른 달 {N_OUT}건 제외).' if MONTH and N_OUT else '.'))
    elif MONTH and N_OUT:
        notes.append(f'기간은 PMS 예약상 예정 체크인일 기준. 내보내기를 앞뒤 하루 넓게 받아 {M}월 예정 체크인만 남김 (다른 달 {N_OUT}건 제외) — 자정 넘어 입실한 손님이 옆 달로 넘어가지 않게.')
    zero = S[S['_amt'] <= 0]['_ch'].value_counts()
    if len(zero):
        notes.append(f'금액 0원 숙박 {int(zero.sum())}건 (' + ', '.join(f'{k} {v}' for k, v in zero.items()) + ')'
                     + (' — 예약 금액이 없어 1박 평균 계산에서 뺌 (단체 미정산·무료 등).' if BREV else ' — 내보내기 시점에 금액이 없어 매출에서 빠짐 (단체 미정산·무료 등).'))
    if prev:
        notes.append(f'전월 매출도 PMS 청구 보고서({PMB}) 기준. 전월 예약 수·박수 등은 PMS 예약 조회(현재 상태) 기준. 전월 매출 100만 원 미만 채널은 증감률 생략("-").'
                     if BREV else '전월 대비 %는 전월 매출 100만 원 미만 채널은 생략("-"). 전월은 PMS 예약 조회(현재 상태) 기준.')
    if N_BAD:
        notes.append(f'체크인·예약 생성일을 읽지 못한 {N_BAD}행은 뺐음 (합계 줄이나 날짜 없는 줄).')
    if not CFG['verified']:
        notes.insert(0, f'미검증 매핑 ({PMS_LABEL}) — 결과가 자기 PMS 보고서 합계와 맞는지 먼저 대조할 것. 열의 뜻(받은 돈/예약 금액, 예정/실제 날짜, 판매/배정 객실)도 확인 필요.')
    if AUTO:
        notes.append('처음 보는 거래처 ' + ', '.join(AUTO) + ' → 자동 분류함. [채널구분표] 노란 줄 확인.')
    for t_ in notes:
        ws.merge_cells(start_row=r, start_column=2, end_row=r, end_column=13)
        x = ws.cell(row=r, column=2, value='• ' + t_)
        x.font = fnt(9, c=INK2)
        x.alignment = AL_LW
        r += 1
    ws.print_area = f'A1:M{r}'
    ws.page_setup.orientation = 'portrait'
    ws.page_setup.paperSize = ws.PAPERSIZE_A4
    ws.page_setup.fitToWidth = 1
    ws.page_setup.fitToHeight = 0
    ws.sheet_properties.pageSetUpPr.fitToPage = True
    ws.page_margins.left = ws.page_margins.right = 0.4
    ws.page_margins.top = ws.page_margins.bottom = 0.5

    for name in VIEW_SHEETS[1:]:
        w_ = W[name]
        w_.page_setup.orientation = 'landscape'
        w_.page_setup.paperSize = w_.PAPERSIZE_A4
        w_.page_setup.fitToWidth = 1
        w_.page_setup.fitToHeight = 0
        w_.sheet_properties.pageSetUpPr.fitToPage = True
    wb.calculation.fullCalcOnLoad = True
    wb.save(A.out)

    # =====================================================================
    # 15) 요약 / 집계 저장
    # =====================================================================
    if A.agg_out:
        write_json(A.agg_out, {'month': f'{Y}-{M:02d}', 'period': f'{Y}-{M:02d} {PERIOD_TXT}', 'basis': A.basis,
                   'source': f'PMS 예약 통합 검색 내보내기 {exported_at}',
                   'rows': [dict(거래처=k, **{kk: vv for kk, vv in v.items() if kk != '숙박_금액있음'}) for k, v in cur_acc.items()],
                   **({'billing': BACC['cur'], 'billing_total': sum(BACC['cur'].values()),
                       'billing_note': 'PMS 청구 보고서 거래처별 매출 (매출 인식 일자) — 다음 달 --billing-acc 의 prev 로 쓸 수 있음'} if BREV else {})},
                   )
    if A.summary:
        def tot(d):
            keys = ['전체', '취소', '유효', '숙박', '박수', '매출', '숙박매출_금액있음', '박수_금액있음', '당일_숙박']
            t = {k: sum(v.get(k, 0) for v in d.values()) for k in keys}
            t['1박평균'] = round(t['숙박매출_금액있음'] / max(1, t['박수_금액있음']))
            t['취소율'] = round(t['취소'] / max(1, t['전체']), 4)
            t['당일비중'] = round(t['당일_숙박'] / max(1, t['숙박']), 4)
            return t
        ct, pt = tot(cur_ch), (tot(prev_ch) if prev else None)
        if BREV:   # 매출 = 청구 보고서 기준, 예약 금액은 따로
            ct['예약매출'], ct['매출'] = ct['매출'], sum(BACC['cur'].values())
            if pt:
                pt['예약매출'], pt['매출'] = pt['매출'], sum(BACC['prev'].values())
        _gsum = lambda d, g: sum(v for a_, v in d.items() if CLS[a_][1] == g)
        summ = {'month': f'{Y}-{M:02d}', 'period': PERIOD, 'basis': A.basis, 'exported_at': exported_at, 'prev_month': prev['month'] if prev else None,
                'revenue_basis': 'billing (PMS 청구 보고서, 손님이 묵은 날)' if BREV else 'checkin (체크인한 달에 예약 전액)',
                'total': ct, 'prev_total': pt,
                'channels': {c: dict(cur=cur_ch.get(c), prev=prev_ch.get(c), basis=CH_BASIS.get(c), rev=REV(c), rev_prev=REVP(c),
                                     adr=round(cur_ch[c]['숙박매출_금액있음'] / cur_ch[c]['박수_금액있음']) if c in cur_ch and cur_ch[c]['박수_금액있음'] else None,
                                     sameday=round(cur_ch[c]['당일_숙박'] / cur_ch[c]['숙박'], 3) if c in cur_ch and cur_ch[c]['숙박'] else None)
                             for c in MAJOR + MINOR},
                'major': MAJOR, 'minor': MINOR, 'stay_major': STAY_MAJOR,
                'groups': ({g: dict(cur=_gsum(BACC['cur'], g), prev=_gsum(BACC['prev'], g)) for g in GROUPS} if BREV else
                           {g: dict(cur=int(V[V['_grp'] == g]['_amt'].sum()),
                                    prev=(sum(r['매출'] for r in prev['rows'] if CLS[r['거래처']][1] == g) if prev else None)) for g in GROUPS}),
                'lead_share': {k: {kk: round(vv, 3) for kk, vv in v.items()} for k, v in LEAD_SH.items()},
                'room_share_sold': {k: {kk: round(vv, 3) for kk, vv in v.items()} for k, v in ROOM_SH.items()},
                'moved': dict(channel_stays=len(CHS), moved=int(CHS['_moved'].sum()), std_sold=len(STD), std_moved=int(STD['_moved'].sum()),
                              std_share=round(len(STD) / max(1, len(CHS)), 3)),
                'moved_by_channel': {c: round(CHS[CHS['_ch'] == c]['_moved'].mean(), 3) for c in CHP},
                'sold_to_assigned': {f'{a}->{b}': int(n) for (a, b), n in CHS.groupby(['_sold', '객실 타입']).size().items()},
                'products_by_channel': {c: CHS[CHS['_ch'] == c]['_prod'].value_counts().head(6).to_dict() for c in CHP},
                'family_share': {c: {k: round(v, 3) for k, v in (CHS if c == '전체' else CHS[CHS['_ch'] == c])['_pfam'].value_counts(normalize=True).items()} for c in CHP + ['전체']},
                'adr_by_sold_type': {c: {t: round(g['_amt'].sum() / g['_n'].sum()) for t, g in SP[SP['_ch'] == c].groupby('_sold') if g['_n'].sum()} for c in STAY_MAJOR},
                'weekday_per_day': {d: round(len(S[S['_wd'] == d]) / max(1, DAYS_WD[d]), 1) for d in WD},
                'weekday_adr': {d: round(SP[SP['_wd'] == d]['_amt'].sum() / max(1, SP[SP['_wd'] == d]['_n'].sum())) for d in WD},
                'nationality': NATV['_nat'].value_counts().to_dict(),
                'nat_coverage': {c: round((V[V['_ch'] == c]['_nat'] != '').mean(), 3) for c in NAT_COVER_CH if len(V[V['_ch'] == c])},
                'corp': {a: (dict(cur=BACC['cur'].get(a, 0), prev=BACC['prev'].get(a, 0), booked=z(cur_acc.get(a), '매출'), nights=z(cur_acc.get(a), '박수')) if BREV else
                             dict(cur=z(cur_acc.get(a), '매출'), prev=(next((r['매출'] for r in prev['rows'] if r['거래처'] == a), 0) if prev else None),
                                  nights=z(cur_acc.get(a), '박수'))) for a in CORP_ACC},
                'auto_classified': AUTO, 'billing': BILL_SUM}
        write_json(A.summary, summ, default=int)
    print(json.dumps({'saved': A.out, 'rows': N, 'pms': PMS_LABEL, 'verified': CFG['verified'], 'month': f'{Y}-{M:02d}', 'major': MAJOR, 'minor': MINOR, 'stay_major': STAY_MAJOR,
                      'auto': AUTO, 'prev': bool(prev), 'billing_ok': (BILL_SUM or {}).get('ok'),
                      'revenue': ('청구 보고서 ' + format(sum(BACC['cur'].values()), ',') + '원 / 전월 ' + format(sum(BACC['prev'].values()), ',') + '원') if BREV else '체크인 기준'},
                     ensure_ascii=False))
    if BILL_SUM and not BILL_SUM['ok']:
        log.warning('청구 보고서 대조가 1원까지 맞지 않음 — [청구대조] 탭과 billing.json 확인')



def setup_logging(log_path=None, debug=False):
    handlers = [logging.StreamHandler(sys.stderr)]
    if log_path:
        handlers.append(logging.FileHandler(log_path, encoding='utf-8'))
    logging.basicConfig(level=logging.DEBUG if debug else logging.INFO, format='%(asctime)s %(levelname)s %(message)s', handlers=handlers)


def main():
    try:
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    except AttributeError as e:   # 표준 출력이 바뀐 환경 (테스트 등)
        print(f'표준 출력 인코딩을 바꾸지 못했습니다: {e}', file=sys.stderr)
    if len(sys.argv) > 1 and sys.argv[1] == '--postfix':
        setup_logging()
        if len(sys.argv) < 4:
            log.error('사용법: --postfix 재계산.xlsx 최종.xlsx [summary.json]')
            return 2
        try:
            postfix(sys.argv[2], sys.argv[3], sys.argv[4] if len(sys.argv) > 4 else None)
        except ConfigError as e:
            log.error('%s', e)
            return 2
        except (OSError, KeyError, ValueError) as e:
            log.error('뒤 처리 실패: %s: %s', type(e).__name__, e)
            return 1
        return 0
    A = parse_args()
    setup_logging(A.log, A.debug)
    try:
        build(A, load_config(A.config))
    except ConfigError as e:
        log.error('%s', e)
        return 2
    except PermissionError as e:
        log.error('파일을 쓸 수 없습니다 (엑셀에서 열려 있는지 확인): %s', e.filename)
        return 1
    except Exception as e:   # 예상 못 한 오류: 값이 로그에 새지 않게 종류만 남기고, --debug 때만 전체 추적
        log.error('처리 실패: %s (자세히 보려면 --debug)', type(e).__name__)
        log.debug('추적', exc_info=True)
        return 1
    return 0


if __name__ == '__main__':
    sys.exit(main())
