"""抓取基础设施。无状态零件，移植自 fetch_pharma.py L23-39（safe_get/make_id）。"""

from __future__ import annotations

import hashlib
import time
from datetime import datetime

HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; ESGEventBot/1.0)"}


def safe_get(url, params=None, timeout=15, retries=2):
    import requests  # 惰性导入：样例/离线模式无需网络依赖
    for i in range(retries):
        try:
            r = requests.get(url, params=params, headers=HEADERS, timeout=timeout)
            r.encoding = r.apparent_encoding
            return r
        except Exception as e:
            if i == retries - 1:
                print(f"  [FAIL] {url} → {e}")
            time.sleep(2)
    return None


def make_id(text: str) -> str:
    return hashlib.md5(text.encode()).hexdigest()[:8]


def today_str() -> str:
    return datetime.now().strftime("%Y-%m-%d")


def keyword_pool(cfg: dict) -> list[str]:
    """所有工况的 strong+mid 关键词并集，用于源侧粗过滤。"""
    pool: set[str] = set()
    for cond in cfg.get("conditions", []):
        kw = cond.get("keywords", {})
        pool.update(kw.get("strong", []))
        pool.update(kw.get("mid", []))
    return sorted(pool)


def valve_pool(cfg: dict) -> list[str]:
    """所有工况的阀型并集 + 通用阀门词，用于招标侧识别。"""
    pool: set[str] = {"阀门", "阀", "管件"}
    for cond in cfg.get("conditions", []):
        pool.update(cond.get("valve_types", []))
    return sorted(pool)
