"""
竞品产品页抓取与分析
目标：Bürkert / Gemü（盖米）/ ESG
输出：data/products_raw.json
"""

import json
import time
import hashlib
import requests
from bs4 import BeautifulSoup
from datetime import datetime
from pathlib import Path

Path("data").mkdir(exist_ok=True)

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                  "AppleWebKit/537.36 (KHTML, like Gecko) "
                  "Chrome/120.0.0.0 Safari/537.36",
    "Accept":          "text/html,application/xhtml+xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9,de;q=0.8",
    "Accept-Encoding": "gzip, deflate, br",
}

def safe_get(url, timeout=20):
    try:
        r = requests.get(url, headers=HEADERS, timeout=timeout,
                         allow_redirects=True)
        r.encoding = r.apparent_encoding
        print(f"  GET {url[:70]} → {r.status_code}")
        return r if r.status_code == 200 else None
    except Exception as e:
        print(f"  FAIL {url[:60]} → {e}")
        return None

def make_id(text):
    return hashlib.md5(text.encode()).hexdigest()[:8]

# ─────────────────────────────────────────────
# Bürkert 产品抓取
# 产品体系：Type编号（Type 2000 / 2030 等）
# ─────────────────────────────────────────────
def scrape_burkert():
    print("\n→ Bürkert 产品抓取...")
    products = []

    # 产品总览页
    r = safe_get("https://www.burkert.com/en/type/Products")
    if not r:
        return products

    soup = BeautifulSoup(r.text, "lxml")

    # Bürkert 产品用 Type 编号组织，找所有 Type 链接
    type_links = []
    for a in soup.find_all("a", href=True):
        href = a["href"]
        text = a.get_text(strip=True)
        # 匹配 /en/type/Type-XXXX 或含 "Type" 的链接
        if "/type/Type" in href or "/product/" in href.lower():
            type_links.append((text, href if href.startswith("http")
                               else "https://www.burkert.com" + href))

    print(f"  找到 {len(type_links)} 个产品链接")

    # 取前30个详情页
    for name, url in type_links[:30]:
        r2 = safe_get(url)
        if not r2:
            continue
        soup2 = BeautifulSoup(r2.text, "lxml")

        # 提取产品描述
        desc_el = (soup2.find("div", class_=lambda c: c and "description" in c.lower())
                   or soup2.find("div", class_=lambda c: c and "intro" in c.lower())
                   or soup2.find("p"))
        desc = desc_el.get_text(strip=True)[:300] if desc_el else ""

        # 提取应用行业标签
        tags = []
        for span in soup2.find_all(["span", "li", "a"],
                                    class_=lambda c: c and "tag" in str(c).lower()):
            t = span.get_text(strip=True)
            if t and len(t) < 40:
                tags.append(t)

        products.append({
            "id":       make_id(name + url),
            "company":  "Bürkert",
            "name":     name,
            "url":      url,
            "desc":     desc,
            "tags":     tags[:8],
            "scraped":  datetime.now().strftime("%Y-%m-%d"),
        })
        time.sleep(0.8)

    print(f"  Bürkert: {len(products)} 个产品")
    return products


# ─────────────────────────────────────────────
# Gemü（盖米）产品抓取
# 产品按系列编号（Series 500 / 600 等）组织
# ─────────────────────────────────────────────
def scrape_gemu():
    print("\n→ Gemü（盖米）产品抓取...")
    products = []

    r = safe_get("https://www.gemu-group.com/en/products/")
    if not r:
        return products

    soup = BeautifulSoup(r.text, "lxml")

    # 找产品系列链接
    series_links = []
    for a in soup.find_all("a", href=True):
        href = a["href"]
        text = a.get_text(strip=True)
        if "/products/" in href and href != "/en/products/" and text:
            full = href if href.startswith("http") \
                   else "https://www.gemu-group.com" + href
            series_links.append((text, full))

    # 去重
    seen = set()
    series_links = [(t, u) for t, u in series_links
                    if u not in seen and not seen.add(u)]
    print(f"  找到 {len(series_links)} 个产品系列链接")

    for name, url in series_links[:30]:
        r2 = safe_get(url)
        if not r2:
            continue
        soup2 = BeautifulSoup(r2.text, "lxml")

        # 提取描述
        desc_el = (soup2.find("div", class_=lambda c: c and "description" in str(c).lower())
                   or soup2.find("div", class_=lambda c: c and "text" in str(c).lower())
                   or soup2.find("p"))
        desc = desc_el.get_text(strip=True)[:300] if desc_el else ""

        # 应用领域
        apps = []
        for el in soup2.find_all(["li", "span"],
                                  class_=lambda c: c and "appli" in str(c).lower()):
            t = el.get_text(strip=True)
            if t and len(t) < 50:
                apps.append(t)

        products.append({
            "id":       make_id(name + url),
            "company":  "Gemü",
            "name":     name,
            "url":      url,
            "desc":     desc,
            "applications": apps[:6],
            "scraped":  datetime.now().strftime("%Y-%m-%d"),
        })
        time.sleep(0.8)

    print(f"  Gemü: {len(products)} 个产品")
    return products


# ─────────────────────────────────────────────
# ESG 产品抓取
# 专注食品饮料卫生级阀门
# ─────────────────────────────────────────────
def scrape_esg():
    print("\n→ ESG 产品抓取...")
    products = []

    # ESG 有中文站和德文站，先试英文
    for base in ["https://www.esg-ventile.de/en/products/",
                 "https://www.esg-group.com/en/products/"]:
        r = safe_get(base)
        if r:
            break
    if not r:
        print("  ESG 官网无法访问，跳过")
        return products

    soup = BeautifulSoup(r.text, "lxml")
    prod_links = []
    for a in soup.find_all("a", href=True):
        href = a["href"]
        text = a.get_text(strip=True)
        if "/product" in href.lower() and text and len(text) > 3:
            domain = base.split("/en/")[0]
            full = href if href.startswith("http") else domain + href
            prod_links.append((text, full))

    seen = set()
    prod_links = [(t, u) for t, u in prod_links
                  if u not in seen and not seen.add(u)]
    print(f"  找到 {len(prod_links)} 个产品链接")

    for name, url in prod_links[:20]:
        r2 = safe_get(url)
        if not r2:
            continue
        soup2 = BeautifulSoup(r2.text, "lxml")
        desc_el = soup2.find("p") or soup2.find("div", class_=lambda c: c and "desc" in str(c).lower())
        desc = desc_el.get_text(strip=True)[:300] if desc_el else ""

        products.append({
            "id":      make_id(name + url),
            "company": "ESG",
            "name":    name,
            "url":     url,
            "desc":    desc,
            "scraped": datetime.now().strftime("%Y-%m-%d"),
        })
        time.sleep(0.8)

    print(f"  ESG: {len(products)} 个产品")
    return products


# ─────────────────────────────────────────────
# 主函数
# ─────────────────────────────────────────────
def main():
    print(f"\n{'='*50}")
    print(f"竞品产品抓取  {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print(f"{'='*50}")

    all_products = []
    all_products += scrape_burkert()
    all_products += scrape_gemu()
    all_products += scrape_esg()

    # 写原始数据
    raw_file = Path("data/products_raw.json")
    with open(raw_file, "w", encoding="utf-8") as f:
        json.dump({
            "scraped_at": datetime.now().strftime("%Y-%m-%d %H:%M"),
            "total": len(all_products),
            "by_company": {
                "Bürkert": len([p for p in all_products if p["company"] == "Bürkert"]),
                "Gemü":    len([p for p in all_products if p["company"] == "Gemü"]),
                "ESG":     len([p for p in all_products if p["company"] == "ESG"]),
            },
            "products": all_products
        }, f, ensure_ascii=False, indent=2)

    print(f"\n→ 共抓取 {len(all_products)} 个产品")
    print(f"→ 原始数据: {raw_file}")

if __name__ == "__main__":
    main()
