#!/usr/bin/env node
/**
 * 制药行业自动化监测系统
 * 玄机自动化脚本 - 每周一 9:00 自动执行
 */

const OBSIDIAN_PATH = "/Users/nicolewang/Documents/Obsidian Vault";

// 搜索关键词配置
const KEYWORDS = {
  核心企业: ["东富龙", "楚天科技", "迦南科技", "森松国际", "新华医疗", "上海远东", "瑞安华旭"],
  产品设备: ["冻干机", "生物反应器", "灌装线", "固体制剂", "纯化设备", "灭菌设备", "CGT设备", "一次性生物反应器", "SUS"],
  下游应用: ["抗体药物", "疫苗", "生物制药", "细胞治疗", "CAR-T", "血液制品", "生物合成"],
  政策: ["国产替代", "十五五规划", "GMP", "一致性评价", "集采"],
  CDMO: ["药明康德", "康龙化成", "凯莱英", "博腾股份", "金斯瑞"],
  创新药: ["恒瑞", "百济神州", "信达生物", "ADC", "GLP-1"],
  原料药: ["华海药业", "天宇股份", "普洛药业"],
  合成生物学: ["凯赛生物", "华恒生物", "梅花生物"]
};

// Bitable 配置
const BITABLE_CONFIG = {
  app_token: "O43db8UZxaL53wsXyKAcE5UInkh",
  table_id: "tbl55GZJe947qePE",
  fields: {
    title: "制药行业监测",    // 标题（默认主字段）
    date: "日期",             // 日期
    source: "来源",           // 来源
    summary: "摘要",          // 摘要
    category: "行业分类",     // 行业分类
    keywords: "关键词"        // 关键词
  },
  // 行业分类选项映射
  categoryOptions: {
    "核心企业": "制药装备",
    "产品设备": "制药装备",
    "下游应用": "制药装备",
    "政策": "其他",
    "CDMO": "CDMO",
    "创新药": "创新药",
    "原料药": "原料药",
    "合成生物学": "合成生物学"
  }
};

/**
 * 搜索制药行业新闻
 */
async function searchNews() {
  const results = [];
  
  for (const [category, keywords] of Object.entries(KEYWORDS)) {
    for (const keyword of keywords) {
      try {
        const searchResults = await web_search({
          query: `${keyword} 制药 2026`,
          count: 3,
          freshness: "pw",
          country: "CN",
          search_lang: "zh"
        });
        
        if (searchResults?.web_results) {
          for (const item of searchResults.web_results) {
            results.push({
              category,
              keyword,
              title: item.title,
              url: item.url,
              snippet: item.description
            });
          }
        }
      } catch (e) {
        console.error(`搜索 ${keyword} 失败:`, e.message);
      }
    }
  }
  
  return results;
}

/**
 * 保存到飞书 Bitable
 */
async function saveToBitable(newsItems) {
  if (!BITABLE_CONFIG.app_token || !BITABLE_CONFIG.table_id) {
    console.log("Bitable 未配置，跳过存储");
    return;
  }
  
  const { fields, categoryOptions } = BITABLE_CONFIG;
  
  for (const item of newsItems) {
    try {
      await feishu_bitable_create_record({
        app_token: BITABLE_CONFIG.app_token,
        table_id: BITABLE_CONFIG.table_id,
        fields: {
          [fields.date]: Date.now(),
          [fields.title]: item.title,
          [fields.source]: item.url,
          [fields.summary]: item.snippet?.substring(0, 500) || "",
          [fields.category]: categoryOptions[item.category] || "其他",
          [fields.keywords]: item.keyword
        }
      });
    } catch (e) {
      console.error("保存记录失败:", e.message);
    }
  }
}

/**
 * 生成 Obsidian 周报
 */
async function generateWeeklyReport(newsItems) {
  const now = new Date();
  const weekStart = new Date(now);
  weekStart.setDate(now.getDate() - now.getDay() + 1);
  
  const md = `# 制药行业周报 (${weekStart.toLocaleDateString("zh-CN")} - ${now.toLocaleDateString("zh-CN")})

> 自动生成于 ${now.toLocaleString("zh-CN")}

## 📊 数据概览

- 新闻总数: ${newsItems.length}
- 数据来源: 飞书 Bitable

## 📰 行业动态

${newsItems.map((item, i) => `${i + 1}. **${item.title}**  
   - 分类: ${item.category} | 关键词: ${item.keyword}  
   - 来源: ${item.url}`).join("\n\n")}

---

*本报告由玄机自动生成*
`;

  const filename = `${OBSIDIAN_PATH}/Pharma-Monitoring/周报-${now.toISOString().split("T")[0]}.md`;
  
  // 写入文件
  await write({ content: md, path: filename });
  console.log(`周报已生成: ${filename}`);
}

/**
 * 主函数
 */
async function main() {
  console.log("🔍 开始制药行业监测...");
  
  const news = await searchNews();
  console.log(`找到 ${news.length} 条新闻`);
  
  await saveToBitable(news);
  await generateWeeklyReport(news);
  
  console.log("✅ 监测完成");
}

main().catch(console.error);