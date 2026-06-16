"""实体本体（O1 实体解析）。

把事件里散落的业主字符串解析到稳定的 Company/OEM/Competitor 对象：
- 命中 config/entities.yml 的战略实体 → 正规 id + resolved=True；
- 未命中 → 稳定 auto-id（同名同 id），resolved=False，待人工提升进 registry。

只做规范化 + 别名 registry 比对；短名↔全称模糊匹配/统一信用代码是后续 refine。
"""

from __future__ import annotations

import hashlib
import re
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_REGISTRY = ROOT / "config" / "entities.yml"

_SUFFIXES = ("股份有限公司", "有限责任公司", "有限公司", "集团", "公司")
_cache: dict | None = None


def _normalize(name: str) -> str:
    n = re.sub(r"\s+", "", name or "")
    changed = True
    while changed:
        changed = False
        for suf in _SUFFIXES:
            if n.endswith(suf):
                n = n[: -len(suf)]
                changed = True
                break
    return n


def load_registry(path: Path = DEFAULT_REGISTRY) -> dict:
    """加载 registry，建立 别名规范化→实体 索引 + id→实体 索引。"""
    raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    by_id: dict[str, dict] = {}
    alias_index: dict[str, dict] = {}
    for ent in raw.get("entities", []):
        by_id[ent["id"]] = ent
        for nm in [ent["name"], *ent.get("aliases", [])]:
            alias_index[_normalize(nm)] = ent
    return {"by_id": by_id, "alias_index": alias_index}


def _default() -> dict:
    global _cache
    if _cache is None:
        _cache = load_registry()
    return _cache


def resolve(raw_name: str, registry: dict | None = None) -> dict:
    """业主字符串 → 实体引用 {id, name, type, resolved}。

    命中 registry → 正规身份；未命中 → 稳定 auto-id（同名同 id），待提升。
    """
    registry = registry or _default()
    raw = (raw_name or "").strip()
    if not raw:
        return {"id": None, "name": None, "type": None, "resolved": False}
    ent = registry["alias_index"].get(_normalize(raw))
    if ent:
        return {
            "id": ent["id"],
            "name": ent["name"],
            "type": ent.get("type", "company"),
            "resolved": True,
        }
    auto_id = "auto:" + hashlib.md5(_normalize(raw).encode()).hexdigest()[:8]
    return {"id": auto_id, "name": raw, "type": "company", "resolved": False}


def get(entity_id: str, registry: dict | None = None) -> dict | None:
    """按 id 独立寻址一个实体（OEM/Competitor 等）。"""
    registry = registry or _default()
    return registry["by_id"].get(entity_id)
