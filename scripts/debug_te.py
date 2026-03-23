#!/usr/bin/env python3
import urllib.request, re

# 直接抓PPI单独页面
url = "https://tradingeconomics.com/china/producer-prices-change"
req = urllib.request.Request(url, headers={
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36",
    "Accept-Language": "en-US,en;q=0.9",
})
with urllib.request.urlopen(req, timeout=20) as r:
    page = r.read().decode("utf-8", errors="ignore")

print(f"页面长度: {len(page)}")

# 找数值附近的HTML
for keyword in ["-0.9", "0.90", "decreased", "fell", "percent", "Producer Prices in China"]:
    idx = page.find(keyword)
    if idx >= 0:
        print(f"\n=== '{keyword}' @{idx} ===")
        print(page[idx-30:idx+150])
    else:
        print(f"=== '{keyword}': 未找到 ===")
