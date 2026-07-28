"""
hOCG 가격 사이트 - DB 테이블 생성 스크립트
 
실행 전 준비:
- pip install libsql
- 환경변수 TURSO_URL, TURSO_TOKEN 설정 (또는 아래 값 직접 입력)
 
이미 존재하는 테이블은 건드리지 않음 (CREATE TABLE IF NOT EXISTS)
"""
 
import os
import libsql
 
TURSO_URL = os.environ.get("TURSO_URL", "libsql://yuyu-tei-friedfish.aws-ap-northeast-1.turso.io")
TURSO_TOKEN = os.environ.get("TURSO_TOKEN", "eyJhbGciOiJFZERTQSIsInR5cCI6IkpXVCJ9.eyJhIjoicnciLCJpYXQiOjE3ODQ1OTk4MDQsImlkIjoiMDE5ZjgyNmQtZDMwMS03NTJhLWE2ODUtNTEwYzA1NjQzZDc5Iiwia2lkIjoidW9EQXduZktyYXZ3VTJYemdhbzkxWGFfN1V1UVEwQ2tocGhGdTFxdzl3TSIsInJpZCI6IjM5ZjcxMjE3LTFmYjItNGQ4NS04ZWVlLTY0ODI5MjVkN2ZmMyJ9.439p8Nrz_wUoUkavJUYM5CM0ETyOBIL3U1DGfLVwQbJCU86TnYXVssTLs7R9svZs_NiuLwARoYzfN7gtlR_eCQ")
 
conn = libsql.connect(database=TURSO_URL, auth_token=TURSO_TOKEN)
 
SCHEMA = """
-- 세트(부스터팩/스타트덱 등) 목록
CREATE TABLE IF NOT EXISTS sets (
  set_code TEXT PRIMARY KEY,      -- 예: hbp08, hsd19
  set_name TEXT,                  -- 예: バウンサーバウンド
  first_seen_at TEXT
);
 
-- yuyu-tei 상품(카드) 메타데이터 — 재수록판마다 별도 row (product_id 기준)
CREATE TABLE IF NOT EXISTS cards (
  product_id INTEGER PRIMARY KEY, -- yuyu-tei 내부 상품 고유 ID
  card_id TEXT NOT NULL,          -- 카드 표기 번호 (예: hBP08-003), 재수록판끼리 동일할 수 있음
  name TEXT NOT NULL,
  rarity TEXT NOT NULL,
  set_code TEXT NOT NULL REFERENCES sets(set_code),
  first_seen_at TEXT
);
 
-- 가격 이력 — 스크래핑마다 새 row로 append (덮어쓰지 않음)
CREATE TABLE IF NOT EXISTS price_history (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  product_id INTEGER NOT NULL REFERENCES cards(product_id),
  scraped_at TEXT NOT NULL,
  sell_price INTEGER,             -- 현재 판매가
  sell_price_prev INTEGER         -- 할인/변동 전 가격 (있을 때만)
);
 
-- 공식 사이트 기반 카드 마스터 정보 — card_id 기준 (재수록되어도 속성은 동일)
CREATE TABLE IF NOT EXISTS card_master (
  card_id TEXT PRIMARY KEY,
  official_id INTEGER,            -- 공식 사이트 내부 id
  name_jp TEXT,
  name_kr TEXT,                   -- 나중에 채움 (지금은 NULL 가능)
  card_type TEXT NOT NULL,        -- ホロメン / Buzzホロメン / 推しホロメン / サポート / エール
  rarity TEXT,
  image_url TEXT,
 
  -- 홀로멤・오시・옐 공통
  color TEXT,
 
  -- 홀로멤 전용 (오시 포함)
  bloom_stage TEXT,               -- Debut/1st/Buzz/2nd/Spot
  hp_or_life INTEGER,             -- 홀로멘=HP, 오시=LIFE
  has_gift INTEGER DEFAULT 0,     -- 기프트 효과 보유(0/1)
  has_collab INTEGER DEFAULT 0,   -- 콜라보 효과 보유(0/1)
  has_bloom_effect INTEGER DEFAULT 0, -- 블룸 효과 보유(0/1)
 
  -- 서포트 전용
  support_subtype TEXT,           -- スタッフ/アイテム/イベント/ツール/マスコット/ファン
  is_limited INTEGER DEFAULT 0,   -- LIMITED 여부(0/1)
 
  description_jp TEXT,            -- 능력 텍스트 원문
  description_kr TEXT,            -- 한글 번역 (나중에 채움)
  first_seen_at TEXT
);
 
CREATE INDEX IF NOT EXISTS idx_price_product_date ON price_history(product_id, scraped_at);
CREATE INDEX IF NOT EXISTS idx_cards_card_id ON cards(card_id);
CREATE INDEX IF NOT EXISTS idx_cards_set_code ON cards(set_code);
CREATE INDEX IF NOT EXISTS idx_card_master_type ON card_master(card_type);
"""
 
if __name__ == "__main__":
    for statement in SCHEMA.strip().split(";"):
        stmt = statement.strip()
        if stmt:
            conn.execute(stmt)
    conn.commit()
    print("테이블/인덱스 생성 완료")
 
    # 확인
    tables = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"
    ).fetchall()
    print("현재 테이블 목록:", [t[0] for t in tables])