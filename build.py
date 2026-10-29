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

DEFAULT_SOURCE = Path(
    r"C:\Users\user\AppData\Roaming\Claude\local-agent-mode-sessions\skills-plugin"
    r"\f9f7daa0-8632-45cb-aee6-7de9b0e31391\14b0145a-01ad-43db-aabd-af9c29038afb\skills"
)

# 공개 대상 스킬과 카테고리 (실제 숙소 ID가 들어간 개인용 스킬은 넣지 않는다)
SKILLS = {
    "staytools-agoda-audit": "요금·입금가",
    "staytools-booking-rate-ops": "요금·입금가",
    "staytools-expedia-payout": "요금·입금가",
    "staytools-ota-payout-floor-design": "요금·입금가",
    "staytools-ota-inventory-audit": "재고·운영",
    "staytools-hotel-cleaning-assignment-manager": "재고·운영",
    "staytools-product-planning": "기획",
}

GUIDE_NAME = "사용 안내.md"

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

    return {
        "name": meta.get("name", name),
        "slug": name,
        "category": category,
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
