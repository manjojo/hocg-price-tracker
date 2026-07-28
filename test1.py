import requests
from bs4 import BeautifulSoup
from HOCGofficial_Scraping import parse_card_detail
 
HEADERS = {"User-Agent": "Mozilla/5.0 (hocg-price-tracker; contact: you@example.com)"}
 
# 기프트 효과 있는 홀로멤 카드로 테스트
url = "https://hololive-official-cardgame.com/cardlist/?id=1785"
res = requests.get(url, headers=HEADERS)
soup = BeautifulSoup(res.text, "html.parser")
 
result = parse_card_detail(soup, 1785)
print(result)
 