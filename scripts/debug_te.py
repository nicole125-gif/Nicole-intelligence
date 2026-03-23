#!/usr/bin/env python3
import urllib.request, re

url = "https://tradingeconomics.com/china/indicators"
req = urllib.request.Request(url, headers={
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36",
    "Accept-Language": "en-US,en;q=0.9",
})
with urllib.request.urlopen(req, timeout=20) as r:
    page = r.read().decode("utf-8", errors="ignore")

print(f"页面总长度: {len(page)}")

# 搜索PPI相关所有关键词
for keyword in ["Producer Prices Change", "PPI", "producer-prices-change", "producer-prices"]:
    idx = page.find(keyword)
    if idx >= 0:
        print(f"\n=== '{keyword}' @{idx} ===")
        print(page[idx-50:idx+300])
    else:
        print(f"\n=== '{keyword}': 未找到 ===")
