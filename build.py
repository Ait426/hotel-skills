"""스킬 폴더를 읽어 사이트 데이터(data.js)와 스킬별 다운로드 zip을 만드는 빌드 스크립트.

사용법:
    python build.py [스킬_루트_폴더]

인자를 생략하면 DEFAULT_SOURCE 경로를 쓴다.
실행 로그는 콘솔과 build.log에 함께 남는다.
"""

import json
import logging
import re
import sys
import zipfile
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent
DOWNLOAD_DIR = ROOT / "downloads"
DATA_FILE = ROOT / "data.js"
LOG_FILE = ROOT / "build.log"

DEFAULT_SOURCE = ROOT / "skills"

# 공개 대상 스킬과 카테고리 (실제 숙소 ID가 들어간 개인용 스킬은 넣지 않는다)
SKILLS = {
    "staytools-agoda-audit": "요금·입금가",
    "staytools-booking-rate-ops": "요금·입금가",
    "staytools-expedia-payout": "요금·입금가",
    "staytools-trip-payout": "요금·입금가",
    "staytools-ota-payout-floor-design": "요금·입금가",
    "staytools-sales-analysis": "매출 분석",
    "staytools-ota-inventory-audit": "재고·운영",
    "staytools-hotel-cleaning-assignment-manager": "재고·운영",
    "staytools-product-planning": "기획",
}

GUIDE_NAME = "사용 안내.md"

BROWSER_NOTE = "화면 조회·수정은 브라우저 조작 도구가 있는 환경에서만 됩니다."

# 스킬별 사용 조건 (각 스킬의 SKILL.md·사용 안내 내용을 근거로 적는다)
REQUIREMENTS = {
    "staytools-agoda-audit": {
        "target": "아고다 입점 숙소",
        "systems": ["아고다 파트너 포털"],
        "notes": [
            BROWSER_NOTE + " 도구가 없으면 가져온 자료로 계산합니다.",
            "채널 매니저가 있으면 채널별 요금 비교까지 됩니다. 절차는 YFlux·WINGSCMS 기준 예시입니다.",
            "세금 배수 기본값은 한국 부가세(1.1)입니다. 다른 나라 숙소는 값을 바꿔야 합니다.",
        ],
    },
    "staytools-booking-rate-ops": {
        "target": "부킹닷컴 입점 숙소",
        "systems": ["부킹닷컴 익스트라넷", "Python 3 (계산기·HTML 콘솔)"],
        "notes": [
            BROWSER_NOTE,
            "판매가 변경 절차는 WINGSCMS 계열 예시입니다. 다른 채널 매니저는 화면이 다릅니다.",
        ],
    },
    "staytools-expedia-payout": {
        "target": "익스피디아 입점 숙소",
        "systems": ["익스피디아 파트너센트럴", "Python 3 (계산기·HTML 콘솔)"],
        "notes": [
            BROWSER_NOTE,
            "프로모션 구성 예시는 한국 POS 기준이고, 세금 배수도 한국 부가세(1.1) 예시입니다.",
            "채널 매니저 절차는 WINGSCMS 계열 예시입니다.",
        ],
    },
    "staytools-trip-payout": {
        "target": "트립닷컴 입점 숙소 (판매가 입력 방식)",
        "systems": ["트립닷컴 eBooking", "Python 3 (계산기·HTML 콘솔)"],
        "notes": [
            BROWSER_NOTE,
            "판매가 입력 방식만 검증했습니다. 넷가·후불·VCC 계약은 미검증입니다.",
            "캠페인과 회원 할인의 중복, 프로모션 적용 기준은 숙소마다 실예약으로 확인해야 합니다.",
        ],
    },
    "staytools-ota-payout-floor-design": {
        "target": "OTA 할인 구조를 설계하는 숙소",
        "systems": [],
        "notes": ["채널 화면을 읽지 않는 계산·설계 스킬입니다. 실측 확인은 소비자 페이지에서 따로 해야 합니다."],
    },
    "staytools-sales-analysis": {
        "target": "PMS 예약 내보내기 엑셀이 있는 숙소",
        "systems": ["PMS 예약 내보내기 엑셀", "Python (pandas, numpy, openpyxl)"],
        "notes": [
            "YFlux 내보내기로만 실제 검증했습니다. 다른 PMS는 열 매핑을 직접 맞춰야 하고 미검증으로 표시됩니다.",
            "수수료·쿠폰·부가세는 표시용이며 실수령 계산에 쓰지 않습니다.",
            "고객명·연락처가 든 원본 파일은 공유하지 마세요.",
        ],
    },
    "staytools-ota-inventory-audit": {
        "target": "OTA 채널 재고를 PMS와 직접 대조해야 하는 숙소",
        "systems": ["PMS(또는 엑셀로 내보낸 잔여표)", "야놀자·여기어때 모텔 등 파트너센터"],
        "notes": [
            BROWSER_NOTE + " 도구가 없으면 받은 표로 판정과 조치안까지 작성합니다.",
            "화면 절차는 YFlux PMS·야놀자·여기어때 모텔 기준입니다. 다른 시스템은 절차를 맞춰야 합니다.",
        ],
    },
    "staytools-hotel-cleaning-assignment-manager": {
        "target": "청소 직원을 배정하는 호텔",
        "systems": [],
        "notes": ["대화로 알려 준 내용으로 배정합니다. 외부 시스템 연결은 필요 없습니다."],
        # 사용 안내에 입력 항목이 없어 SKILL.md의 필수 입력을 옮겨 적는다
        "inputs": ["청소 가능한 직원 수 또는 명단", "청소할 객실 목록"],
    },
    "staytools-product-planning": {
        "target": "호텔과 무관하게 누구나",
        "systems": [],
        "notes": ["대화형 사고 보조 스킬입니다. 시장 수요나 매출을 보장하지 않습니다."],
    },
}

log = logging.getLogger("build")


def setup_logging():
    """콘솔과 파일에 동시에 로그를 남긴다."""
    # Windows 콘솔(cp949)에서 한글이 깨지지 않도록 UTF-8로 맞춘다
    sys.stdout.reconfigure(encoding="utf-8")
    fmt = logging.Formatter("%(asctime)s [%(levelname)s] %(message)s")
    log.setLevel(logging.INFO)
    for handler in (logging.StreamHandler(sys.stdout), logging.FileHandler(LOG_FILE, encoding="utf-8")):
        handler.setFormatter(fmt)
        log.addHandler(handler)


def parse_frontmatter(text):
    """SKILL.md 머리말(--- 블록)에서 name/description을 꺼내고 본문을 돌려준다."""
    match = re.match(r"^---\s*\n(.*?)\n---\s*\n?", text, re.S)
    if not match:
        return {}, text
    meta = {}
    for line in match.group(1).splitlines():
        if ":" not in line or line.startswith((" ", "\t")):
            continue
        key, value = line.split(":", 1)
        value = value.strip()
        # 따옴표로 감싼 값은 따옴표와 이스케이프를 벗겨 낸다
        if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
            value = value[1:-1].replace('\\"', '"')
        meta[key.strip()] = value
    return meta, text[match.end():]


def parse_inputs(guide):
    """사용 안내의 '준비할 입력' 절에서 목록 항목만 꺼낸다."""
    match = re.search(r"^## 준비할 입력\s*\n(.*?)(?=^## |\Z)", guide, re.S | re.M)
    if not match:
        return []
    return [line[2:].strip() for line in match.group(1).splitlines() if line.startswith("- ")]


def make_zip(skill_dir, name):
    """스킬 폴더 전체를 <스킬명>/... 구조로 압축한다."""
    DOWNLOAD_DIR.mkdir(exist_ok=True)
    zip_path = DOWNLOAD_DIR / f"{name}.zip"
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for file in sorted(skill_dir.rglob("*")):
            if file.is_file():
                zf.write(file, Path(name) / file.relative_to(skill_dir))
    return zip_path


def build_skill(source, name, category):
    """스킬 하나의 메타데이터를 만들고 zip을 생성한다."""
    skill_dir = source / name
    skill_md = skill_dir / "SKILL.md"
    if not skill_md.is_file():
        raise FileNotFoundError(f"SKILL.md 없음: {skill_md}")

    meta, body = parse_frontmatter(skill_md.read_text(encoding="utf-8"))
    guide_path = skill_dir / GUIDE_NAME
    guide = guide_path.read_text(encoding="utf-8") if guide_path.is_file() else ""

    files = sorted(f for f in skill_dir.rglob("*") if f.is_file())
    latest = max(f.stat().st_mtime for f in files)
    zip_path = make_zip(skill_dir, name)

    req = REQUIREMENTS[name]
    inputs = parse_inputs(guide) or req.get("inputs", [])
    if not inputs:
        log.warning("준비할 입력 항목 없음: %s", name)

    return {
        "name": meta.get("name", name),
        "slug": name,
        "category": category,
        "target": req["target"],
        "systems": req["systems"],
        "notes": req["notes"],
        "inputs": inputs,
        "description": meta.get("description", ""),
        "body": body.strip(),
        "guide": guide.strip(),
        "files": [f.relative_to(skill_dir).as_posix() for f in files],
        "lines": len(body.splitlines()),
        "updated": datetime.fromtimestamp(latest).strftime("%Y-%m-%d"),
        "zip": f"downloads/{zip_path.name}",
        "zipSize": zip_path.stat().st_size,
    }


def main():
    setup_logging()
    source = Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_SOURCE
    log.info("스킬 원본 폴더: %s", source)
    if not source.is_dir():
        log.error("원본 폴더가 없습니다: %s", source)
        return 1

    skills = []
    for name, category in SKILLS.items():
        try:
            skills.append(build_skill(source, name, category))
            log.info("완료: %s", name)
        except Exception:
            # 한 스킬이 실패해도 나머지는 계속 빌드하고, 원인은 로그에 남긴다
            log.exception("실패: %s", name)

    payload = json.dumps(skills, ensure_ascii=False, indent=1)
    DATA_FILE.write_text(f"// build.py가 생성한 파일 — 직접 수정하지 말 것\nwindow.SKILLS = {payload};\n", encoding="utf-8")
    log.info("data.js 생성: 스킬 %d/%d개", len(skills), len(SKILLS))
    return 0 if len(skills) == len(SKILLS) else 1


if __name__ == "__main__":
    sys.exit(main())
