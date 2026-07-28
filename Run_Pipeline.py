"""
전체 파이프라인 실행 스크립트

1단계: yuyu-tei 스크래핑 -> sets/cards/price_history 저장
2단계: 신규 카드 감지 -> 공식 사이트에서 마스터정보 수집 -> card_master 저장

GitHub Actions 등 자동화 환경에서 이 파일 하나만 실행하면 됩니다.
"""

import os
import sys
import libsql

from yuyutei_Scraping import scrape_all
from Save_To_DB import save_scrape_result
from HOCGofficial_Scraping import scan_new_cards


def get_connection():
    return libsql.connect(
        database=os.environ["TURSO_URL"],
        auth_token=os.environ["TURSO_TOKEN"],
    )


if __name__ == "__main__":
    conn = get_connection()

    print("=== 1단계: yuyu-tei 스크래핑 ===")
    data = scrape_all()
    print(f"스크래핑 완료: 세트 {len(data['sets'])}개, 카드 {len(data['cards'])}건")
    save_scrape_result(conn, data)

    print("=== 2단계: 공식 사이트 신규 카드 마스터정보 수집 ===")
    scan_new_cards(conn)

    print("=== 파이프라인 전체 완료 ===")