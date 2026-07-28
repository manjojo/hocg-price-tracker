"""
yuyu-tei 스크래핑 결과를 DB에 저장하는 통합 스크립트
 
사전 준비:
- 같은 폴더에 scrape.py (yuyu-tei 스크래퍼) 있어야 함
- pip install libsql requests beautifulsoup4
- 환경변수 TURSO_URL, TURSO_TOKEN 설정
"""
 
import os
import datetime
import libsql
 
from yuyutei_Scraping import scrape_all  # 기존 yuyu-tei 스크래퍼 재사용
 
 
def upsert_sets(conn, sets: list[dict], scraped_at: str):
    for s in sets:
        conn.execute("""
            INSERT INTO sets (set_code, set_name, first_seen_at)
            VALUES (?, ?, ?)
            ON CONFLICT(set_code) DO UPDATE SET set_name=excluded.set_name
        """, (s["set_code"], s["set_name"], scraped_at))
 
 
def upsert_cards(conn, cards: list[dict], scraped_at: str) -> dict:
    """(product_id, set_code) 조합 기준으로 upsert.
    product_id는 세트 내에서만 유일해서 이 조합이 진짜 유니크 키.
    반환값: {(product_id, set_code): 내부 id} 매핑 (price_history insert에 사용)
    """
    row_id_map = {}
    for c in cards:
        if c["product_id"] is None or c["card_id"] is None:
            continue  # 파싱 실패한 항목은 건너뜀
        conn.execute("""
            INSERT INTO cards (product_id, set_code, card_id, name, rarity, first_seen_at)
            VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(product_id, set_code) DO UPDATE SET
                card_id=excluded.card_id,
                name=excluded.name,
                rarity=excluded.rarity
        """, (c["product_id"], c["set_code"], c["card_id"], c["name"], c["rarity"], scraped_at))
 
        row = conn.execute(
            "SELECT id FROM cards WHERE product_id = ? AND set_code = ?",
            (c["product_id"], c["set_code"])
        ).fetchone()
        row_id_map[(c["product_id"], c["set_code"])] = row[0]
 
    return row_id_map
 
 
def insert_price_history(conn, cards: list[dict], scraped_at: str, row_id_map: dict):
    for c in cards:
        if c["product_id"] is None:
            continue
        card_row_id = row_id_map.get((c["product_id"], c["set_code"]))
        if card_row_id is None:
            continue
        conn.execute("""
            INSERT INTO price_history (card_row_id, scraped_at, sell_price, sell_price_prev)
            VALUES (?, ?, ?, ?)
        """, (card_row_id, scraped_at, c["sell_price"], c["sell_price_prev"]))
 
 
def save_scrape_result(conn, data: dict):
    scraped_at = datetime.datetime.now(datetime.timezone.utc).isoformat()
 
    upsert_sets(conn, data["sets"], scraped_at)
    row_id_map = upsert_cards(conn, data["cards"], scraped_at)
    insert_price_history(conn, data["cards"], scraped_at, row_id_map)
 
    conn.commit()
    print(f"저장 완료: 세트 {len(data['sets'])}개, 카드 {len(data['cards'])}건 (scraped_at={scraped_at})")
 
 
if __name__ == "__main__":
    conn = libsql.connect(
        database=os.environ["TURSO_URL"],
        auth_token=os.environ["TURSO_TOKEN"],
    )
 
    print("yuyu-tei 스크래핑 시작...")
    data = scrape_all()
    print(f"스크래핑 완료: 세트 {len(data['sets'])}개, 카드 {len(data['cards'])}건")
 
    print("DB 저장 시작...")
    save_scrape_result(conn, data)
 