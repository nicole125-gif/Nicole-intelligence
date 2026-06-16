"""事件数据契约：schema 版本与字段常量。

前端队列按 schema_version 读取本契约，避免老热力图 heat_score 结构污染。
单条事件字段定义见 README/计划文档；本模块只固化版本号与枚举，供各模块共享。
"""

SCHEMA_VERSION = "1.0"

# review_flag 枚举
FLAG_OK = "ok"
FLAG_UNRESOLVED = "unresolved"  # 抽不到业主/工况，不臆造
FLAG_NEEDS_REVIEW = "needs_review"
FLAG_STALE = "stale"

# signal_type 枚举
SIGNAL_COMPLIANCE = "compliance"
SIGNAL_EXPANSION = "expansion"
SIGNAL_IMMEDIATE = "immediate"

# lead_time level → 月份区间
LEAD_MONTHS = {"L0": "0-2", "L1": "3-9", "L2": "12-18"}
