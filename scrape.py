"""
yuyu-tei.jp hOCG 판매가(sell) 스크래퍼

- 세트 목록은 매번 top 페이지에서 다시 읽어옴 (신규 부스터팩 자동 대응)
- 각 세트 페이지(/sell/hocg/s/{set_code})의 카드 목록을 파싱
- 카드 고유키는 product_id (yuyu-tei 내부 상품 번호, URL 끝 숫자) 사용
"""

import re
import time
import requests
from bs4 import BeautifulSoup

BASE = "https://yuyu-tei.jp"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Accept-Language": "ja,en-US;q=0.9,en;q=0.8",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
}
REQUEST_DELAY_SEC = 1.5  # 서버 부하 방지용 딜레이


def get_all_set_codes() -> list[dict]:
    """top 페이지의 '収録弾' 검색 필터 체크박스(name='vers[]')에서
    전체 세트 목록을 뽑아온다. value 속성이 세트 코드, 연결된 label이 세트 이름.
    (사이드바 아코디언 버튼은 JS 렌더링 후에만 존재해서 순수 HTML엔 없음 -> 사용 불가)
    """
    res = requests.get(f"{BASE}/top/hocg", headers=HEADERS)
    res.raise_for_status()
    soup = BeautifulSoup(res.text, "html.parser")

    sets = {}
    for inp in soup.select("input[name='vers[]']"):
        code = inp.get("value")
        if not code:
            continue
        label = soup.find("label", {"for": inp.get("id")})
        name = label.get_text(strip=True) if label else code
        sets[code] = name  # 모바일/PC 등 중복 체크박스가 있어도 dict라 자동으로 중복 제거됨

    if not sets:
        # 세트를 하나도 못 찾으면 사이트 구조가 바뀌었을 가능성 -> 명시적으로 실패시키기
        raise RuntimeError("세트 목록을 하나도 찾지 못했습니다. 페이지 구조가 바뀌었을 수 있어요.")

    return [{"set_code": code, "set_name": name} for code, name in sets.items()]


def parse_price(text: str) -> int | None:
    """'1,400 円' 같은 문자열에서 숫자만 추출."""
    if not text:
        return None
    digits = re.sub(r"[^\d]", "", text)
    return int(digits) if digits else None


def fetch_set_cards(set_code: str) -> list[dict]:
    """세트 하나의 카드 목록 + 판매가를 파싱."""
    url = f"{BASE}/sell/hocg/s/{set_code}"
    res = requests.get(url, headers=HEADERS)
    res.raise_for_status()
    soup = BeautifulSoup(res.text, "html.parser")

    cards = []
    for item in soup.select("div.card-product"):
        # 상품ID / 세트코드는 hidden input에서
        cid_input = item.select_one("input.cart_cid")
        ver_input = item.select_one("input.cart_ver")
        if not cid_input or not ver_input:
            continue
        product_id = int(cid_input["value"])
        listed_set_code = ver_input["value"]

        # 카드ID + 레어도 + 이름은 이미지 alt 속성에서: "hBP08-003 SEC FUWAMOCO(...)"
        img = item.select_one("div.product-img img")
        alt = img.get("alt", "") if img else ""
        parts = alt.split(" ", 2)
        card_id = parts[0] if len(parts) > 0 else None
        rarity = parts[1] if len(parts) > 1 else None
        name_from_alt = parts[2] if len(parts) > 2 else None

        # 이름은 h4에서도 다시 확인 (alt가 비어있는 예외 대비)
        h4 = item.select_one("h4.text-primary.fw-bold")
        name = h4.get_text(strip=True) if h4 else name_from_alt

        # 현재 가격
        price_el = item.select_one("strong.d-block.text-end")
        sell_price = parse_price(price_el.get_text(strip=True)) if price_el else None

        # 할인 전 가격 (있을 때만, <del> 안에 위치)
        prev_el = item.select_one("small.fs-9 del")
        sell_price_prev = parse_price(prev_el.get_text(strip=True)) if prev_el else None

        # 재고: 숫자("2 点") 또는 기호("◯") 형태
        stock_el = item.select_one("label.cart_sell_zaiko")
        stock_raw = stock_el.get_text(strip=True).replace("在庫", "").replace(":", "").strip() if stock_el else None

        cards.append({
            "product_id": product_id,
            "card_id": card_id,
            "rarity": rarity,
            "name": name,
            "set_code": listed_set_code,
            "sell_price": sell_price,
            "sell_price_prev": sell_price_prev,
            "stock_raw": stock_raw,
        })

    return cards


def scrape_all() -> dict:
    sets = get_all_set_codes()
    result = {"sets": [], "cards": []}

    for s in sets:
        try:
            cards = fetch_set_cards(s["set_code"])
        except Exception as e:
            print(f"[WARN] {s['set_code']} 파싱 실패: {e}")
            cards = []
        result["sets"].append(s)
        result["cards"].extend(cards)
        time.sleep(REQUEST_DELAY_SEC)

    return result


if __name__ == "__main__":
    data = scrape_all()
    print(f"세트 {len(data['sets'])}개, 카드 {len(data['cards'])}건 수집")
    # 샘플 출력
    for c in data["cards"][:5]:
        print(c)