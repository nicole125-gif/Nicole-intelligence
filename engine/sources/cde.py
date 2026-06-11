"""CDE 优先审评公示（pipeline 前兆，L1）。

CDE 站点在瑞数（Riversafe）动态 WAF 后——plain requests 拿不到（202 + 混淆 JS 挑战）。
做法：Playwright 无头浏览器加载优先审评页过墙，**截获页面自身发出的数据 API 响应**
（`/main/priority/getPriorityApprovalList`，URL 带瑞数动态 token，故不能自己发请求，只读响应）。
JSON records 含 acceptid / drgnamecn / company → owner 可解析。

依赖 playwright（惰性导入），未装则跳过——不阻塞其余源。
"""

from __future__ import annotations

from engine.sources.base import make_id, today_str

LIST_URL = "https://www.cde.org.cn/main/xxgk/listpage/2f78f372d351c6851af7431c7710a731"
API_MARK = "getPriorityApprovalList"
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")


def _pick(rec: dict, *keys: str, default: str = "") -> str:
    for k in keys:
        v = rec.get(k)
        if v:
            return str(v).strip()
    return default


# 受理号第 3 位编码药品类型（API 不单独返回）：H=化药 S=生物制品 Z=中药
_DRUG_TYPE = {"H": "化学药品", "S": "生物制品", "Z": "中药"}


def _drug_type(accept: str) -> str:
    return _DRUG_TYPE.get(accept[2:3].upper(), "药品") if len(accept) >= 3 else "药品"


def fetch(cfg: dict, limit: int = 25) -> list[dict]:
    try:
        from playwright.sync_api import sync_playwright
    except Exception:
        print("   CDE: 跳过（playwright 未安装）")
        return []

    print("→ 抓取 CDE 优先审评（Playwright 过瑞数 WAF）...")
    records: list[dict] = []
    try:
        with sync_playwright() as p:
            b = p.chromium.launch(
                headless=True,
                args=["--disable-blink-features=AutomationControlled", "--no-sandbox"],
            )
            ctx = b.new_context(user_agent=UA, viewport={"width": 1366, "height": 900},
                                locale="zh-CN")
            pg = ctx.new_page()
            pg.add_init_script(
                "Object.defineProperty(navigator,'webdriver',{get:()=>undefined})")

            captured: dict = {}

            def on_resp(r):
                if API_MARK in r.url and "json" in r.headers.get("content-type", ""):
                    try:
                        captured["json"] = r.json()
                    except Exception:
                        pass

            pg.on("response", on_resp)
            pg.goto(LIST_URL, wait_until="networkidle", timeout=30000)
            pg.wait_for_timeout(8000)  # 等瑞数挑战 + 数据 API 返回
            b.close()
            records = ((captured.get("json") or {}).get("data") or {}).get("records") or []
    except Exception as e:
        print(f"   CDE 异常: {e}")

    results = []
    seen: set[str] = set()
    for rec in records[:limit]:
        drug = _pick(rec, "drgnamecn", "drgname")
        if not drug:
            continue
        company = _pick(rec, "company", "applicant")
        accept = _pick(rec, "acceptid", "acceptno")
        dedup_key = f"{company}|{drug}"  # 同公司同药的多个受理号视为一条信号
        if dedup_key in seen:
            continue
        seen.add(dedup_key)
        dtype = _drug_type(accept)  # 受理号派生（化学药品/生物制品/中药）
        date = _pick(rec, "noticeDate", "createdate", "applyDate",
                     default=today_str())[:10]
        results.append({
            "id": make_id(accept or drug),
            "source": "CDE优先审评",
            "source_type": "pipeline",
            # 药品类型并入标题，确保工况分类命中制药
            "title": f"{drug}（{dtype}）优先审评公示",
            "company": company,
            "url": LIST_URL,
            "date": date,
            "signal_type": "expansion",
            "lead_time_months": "6-12",
            "industry_pull": "医药制造业",
        })

    print(f"   CDE: {len(results)} 条")
    return results
