"""
hOCG 공식 사이트 카드 마스터정보 스크래퍼

전략: 사이트 검색/필터가 JS 전용이라 GET 요청으로 안 먹혀서,
      official_id를 순차적으로 스캔하며 yuyu-tei에서 발견된 신규 카드를 찾는 방식.

주의: get_field_text()의 라벨->값 추출 로직과 이미지 셀렉터는
      실제 페이지 HTML(class 구조)을 확인 후 정확히 교체 필요.
      지금은 텍스트 라벨 기반 추정 로직으로 작성됨.
"""

import os
import re
import time
import requests
from bs4 import BeautifulSoup
import libsql

BASE = "https://hololive-official-cardgame.com"
HEADERS = {"User-Agent": "Mozilla/5.0 (hocg-price-tracker; contact: you@example.com)"}
REQUEST_DELAY_SEC = 1.0
MAX_CONSECUTIVE_MISSES = 30  # 연속 미존재 id가 이 개수 이상이면 스캔 중단


def get_needed_card_ids(conn) -> set:
    """yuyu-tei엔 있는데 card_master엔 아직 없는 card_id 목록"""
    rows = conn.execute("""
        SELECT DISTINCT card_id FROM cards
        WHERE card_id NOT IN (SELECT card_id FROM card_master)
    """).fetchall()
    return {r[0] for r in rows}


def get_scan_start_id(conn) -> int:
    row = conn.execute("SELECT MAX(official_id) FROM card_master").fetchone()
    return (row[0] or 0) + 1


def get_field_text(soup: BeautifulSoup, label: str):
    """페이지 텍스트에서 빈 줄을 제거한 뒤, '라벨' 다음에 오는 실제 값을 추출.
    라벨과 값이 <span> 등으로 분리되어 다른 줄이 되는 경우까지 대응.
    같은 라벨이 여러 번 나와도(예: 검색 필터 쪽 빈 값) 값이 있는 걸 사용.
    """
    text = soup.get_text(separator="\n")
    lines = [l.strip() for l in text.split("\n") if l.strip()]
    for i, line in enumerate(lines):
        if line.startswith(label):
            value = line[len(label):].lstrip("：:").strip()
            if value:
                return value
            if i + 1 < len(lines):
                return lines[i + 1]
    return None


def parse_card_detail(soup: BeautifulSoup, official_id: int):
    card_id = get_field_text(soup, "カードナンバー")
    if not card_id:
        return None  # 존재하지 않는 id (빈 페이지 등) -> 스캔 miss 처리

    title_el = soup.select_one("h1.name")
    name_jp = title_el.get_text(strip=True) if title_el else None

    card_type_raw = get_field_text(soup, "カードタイプ") or ""
    parts = card_type_raw.split("・")
    card_type = parts[0] if parts else None

    data = {
        "card_id": card_id,
        "official_id": official_id,
        "name_jp": name_jp,
        "card_type": card_type,
        "rarity": get_field_text(soup, "レアリティ"),
        "image_url": None,
        "color": None,
        "bloom_stage": None,
        "hp_or_life": None,
        "has_gift": 0,
        "has_collab": 0,
        "has_bloom_effect": 0,
        "support_subtype": None,
        "is_limited": 0,
        "description_jp": get_field_text(soup, "能力テキスト"),
    }

    # 대표 이미지 (카드 아트) - 실제 class 확인 후 더 좁혀야 함
    img = soup.select_one("img[src*='/wp-content/images/cardlist/']")
    if img:
        data["image_url"] = img.get("src")

    if card_type in ("ホロメン", "Buzzホロメン", "推しホロメン"):
        color_img = soup.select_one("img[src*='texticon/type_']")
        if color_img:
            m = re.search(r"type_(\w+)\.png", color_img.get("src", ""))
            data["color"] = m.group(1) if m else None

        data["bloom_stage"] = get_field_text(soup, "Bloomレベル")
        hp = get_field_text(soup, "HP") or get_field_text(soup, "LIFE")
        data["hp_or_life"] = int(hp) if hp and hp.isdigit() else None

        for kimg in soup.select("img[src*='texticon/']"):
            src = kimg.get("src", "")
            if "gift.png" in src:
                data["has_gift"] = 1
            elif "collabEF.png" in src:
                data["has_collab"] = 1
            elif "bloomEF.png" in src:
                data["has_bloom_effect"] = 1

    elif card_type == "サポート":
        data["support_subtype"] = parts[1] if len(parts) > 1 else None
        data["is_limited"] = 1 if "LIMITED" in parts else 0

    elif card_type == "エール":
        color_img = soup.select_one("img[src*='texticon/type_']")
        if color_img:
            m = re.search(r"type_(\w+)\.png", color_img.get("src", ""))
            data["color"] = m.group(1) if m else None

    return data


def fetch_card_detail(official_id: int):
    url = f"{BASE}/cardlist/?id={official_id}"
    res = requests.get(url, headers=HEADERS)
    if res.status_code != 200:
        return None
    soup = BeautifulSoup(res.text, "html.parser")
    return parse_card_detail(soup, official_id)


def save_card_master(conn, data: dict):
    conn.execute("""
        INSERT INTO card_master (
            card_id, official_id, name_jp, card_type, rarity, image_url,
            color, bloom_stage, hp_or_life, has_gift, has_collab, has_bloom_effect,
            support_subtype, is_limited, description_jp, first_seen_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, datetime('now'))
        ON CONFLICT(card_id) DO UPDATE SET
            official_id=excluded.official_id,
            name_jp=excluded.name_jp,
            card_type=excluded.card_type,
            rarity=excluded.rarity,
            image_url=excluded.image_url,
            color=excluded.color,
            bloom_stage=excluded.bloom_stage,
            hp_or_life=excluded.hp_or_life,
            has_gift=excluded.has_gift,
            has_collab=excluded.has_collab,
            has_bloom_effect=excluded.has_bloom_effect,
            support_subtype=excluded.support_subtype,
            is_limited=excluded.is_limited,
            description_jp=excluded.description_jp
    """, (
        data["card_id"], data["official_id"], data["name_jp"], data["card_type"],
        data["rarity"], data["image_url"], data["color"], data["bloom_stage"],
        data["hp_or_life"], data["has_gift"], data["has_collab"], data["has_bloom_effect"],
        data["support_subtype"], data["is_limited"], data["description_jp"],
    ))


def get_connection():
    return libsql.connect(
        database=os.environ["TURSO_URL"],
        auth_token=os.environ["TURSO_TOKEN"],
    )


def scan_new_cards(conn):
    needed = get_needed_card_ids(conn)
    if not needed:
        print("신규 카드 없음 (card_master가 cards와 이미 동기화됨)")
        return

    print(f"신규 카드 {len(needed)}개 탐색 시작: {sorted(needed)}")

    current_id = get_scan_start_id(conn)
    consecutive_misses = 0
    found_count = 0

    while needed and consecutive_misses < MAX_CONSECUTIVE_MISSES:
        data = fetch_card_detail(current_id)
        if data is None:
            consecutive_misses += 1
        else:
            consecutive_misses = 0
            if data["card_id"] in needed:
                saved = False
                for attempt in range(3):
                    try:
                        save_card_master(conn, data)
                        conn.commit()
                        saved = True
                        break
                    except Exception as e:
                        print(f"  DB 오류 (재시도 {attempt + 1}/3): {e}")
                        time.sleep(2)
                        conn = get_connection()  # 재연결
                if saved:
                    needed.remove(data["card_id"])
                    found_count += 1
                    print(f"  저장됨: {data['card_id']} (official_id={current_id}, type={data['card_type']})")
                else:
                    print(f"  저장 실패(3회 재시도 후 포기): {data['card_id']} - 다음 실행 때 다시 시도됨")
        current_id += 1
        time.sleep(REQUEST_DELAY_SEC)

    print(f"완료: {found_count}개 저장, 못 찾은 카드 {len(needed)}개")
    if needed:
        print(f"  못 찾음: {sorted(needed)}")


if __name__ == "__main__":
    conn = libsql.connect(
        database=os.environ["TURSO_URL"],
        auth_token=os.environ["TURSO_TOKEN"],
    )
    scan_new_cards(conn)