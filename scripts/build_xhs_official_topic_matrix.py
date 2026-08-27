from __future__ import annotations

import json
import math
import re
from collections import Counter, defaultdict
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
RESEARCH = ROOT / "research" / "panse_multi_direction"
OFFICIAL = RESEARCH / "official_reply_research_v1"
OUTPUT_JSON = OFFICIAL / "official_topic_association_matrix_v1.json"
OUTPUT_MD = OFFICIAL / "official_topic_association_matrix_v1.md"
STRATEGY_JSON = OFFICIAL / "panse_official_topic_strategy_v1.json"


def normalize(value: object) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()


def contains(text: str, words: list[str]) -> bool:
    return any(word in text for word in words)


def load_jsonl(path: Path) -> list[dict]:
    rows: list[dict] = []
    with path.open(encoding="utf-8") as handle:
        for line in handle:
            if line.strip():
                rows.append(json.loads(line))
    return rows


def load_fresh_official() -> list[dict]:
    paths = sorted(OFFICIAL.glob("fresh_xhs_official_replies_2026-08-10*.jsonl"))
    rows: list[dict] = []
    seen: set[tuple[str, str, str]] = set()
    for path in paths:
        for row in load_jsonl(path):
            key = (
                normalize(row.get("source_url")),
                normalize(row.get("parent_text")),
                normalize(row.get("reply_text")),
            )
            if key in seen:
                continue
            seen.add(key)
            row["source_file"] = path.relative_to(ROOT).as_posix()
            rows.append(row)
    return rows


def classify_user_intent(parent: str) -> str:
    if contains(parent, ["投诉", "发霉", "开裂", "破损", "延期", "没发货", "骗人", "欺骗", "退货", "换货", "质量差"]):
        return "complaint_or_service_problem"
    if contains(parent, ["希望出", "会出", "能出", "建议出", "多出", "什么时候来", "啥时候来"]):
        return "feature_or_location_request"
    if contains(parent, ["哪里买", "怎么买", "多少钱", "价格", "有链接", "怎么买", "门店", "地址", "有店", "开业", "营业", "预约", "下单", "有货", "什么时候可以买"]):
        return "acquisition_or_channel_question"
    if contains(parent, ["好看", "好美", "喜欢", "支持", "太棒", "心动", "漂亮", "不错", "真详细", "感谢"]):
        return "praise_or_desire"
    if contains(parent, ["我家", "我买", "用了", "陪伴", "入手", "体验", "养猫", "孩子", "装修"]):
        return "experience_or_scenario_share"
    if re.search(r"[？?]|吗|么|多少|多宽|多高|多重|什么|如何|怎么|能不能|可以不|会不会", parent):
        return "information_or_fit_question"
    return "social_or_other"


def classify_topic(parent: str, post_title: str) -> str:
    primary = parent
    combined = f"{parent} {post_title}"
    if contains(primary, ["投诉", "发霉", "开裂", "破损", "延期", "没发货", "欺骗", "退货", "换货", "售后", "质量差"]):
        return "service_complaint"
    if contains(primary, ["甲醛", "安全", "承重", "会塌", "摔碎", "变形", "耐抓", "质量", "有毒"]):
        return "quality_safety"
    if contains(primary, ["希望出", "会出", "能出", "建议出", "多出", "什么时候来", "啥时候来"]):
        return "feature_request"
    if contains(primary, ["哪里买", "怎么买", "多少钱", "价格", "链接", "门店", "地址", "有店", "开业", "营业", "预约", "下单", "有货", "折扣", "优惠", "线上", "海运", "配送", "安装", "运费", "上架", "询价", "怎么联系", "官方旗舰店"]):
        return "purchase_channel_service"
    if re.search(r"(?:有|有没有|还有).{0,12}[吗嘛]|什么时候可以买", primary):
        return "purchase_channel_service"
    if contains(primary, ["材质", "什么木", "木种", "尺寸", "多宽", "多高", "多深", "重量", "颜色", "色号", "型号", "结构", "几条腿", "多少斤", "功能", "版本", "是什么", "哪一款", "叫啥", "纯实木", "一样", "可拆", "能拆", "铺板", "背板"]):
        return "product_fact_structure"
    if contains(primary, ["好打理", "清洁", "保养", "舒适", "坐感", "户型", "空间", "放得下", "养猫", "孩子", "使用", "实用", "适合", "搭配"]):
        return "usage_fit_maintenance"
    if contains(primary, ["好看", "好美", "喜欢", "支持", "太棒", "心动", "漂亮", "不错", "真详细", "感谢"]):
        return "praise_ugc_relationship"
    if contains(combined, ["活动", "抽奖", "直播", "周年", "开业", "展厅", "快闪", "展览", "拍卖"]):
        return "campaign_event_store"
    if contains(combined, ["设计", "工坊", "制作", "DIY", "新品", "改造", "模块", "拆解", "材料"]):
        return "design_process_material"
    if re.search(r"[？?]|吗|么|多少|如何|怎么|能不能|会不会", primary) and contains(combined, ["桌", "椅", "柜", "床", "沙发", "镜", "家具", "墙挂", "书架"]):
        return "product_fact_structure"
    if contains(primary, ["我家", "我买", "用了", "陪伴", "入手", "体验", "装修"]):
        return "praise_ugc_relationship"
    return "lifestyle_social"


def classify_goal(topic: str, parent: str, reply: str) -> str:
    if contains(reply, ["抱歉", "核实", "售后", "退", "换", "补发", "处理"]):
        return "service_recovery_or_handoff"
    if contains(reply, ["不可以", "没有", "目前只有", "暂时", "还没有", "不做", "忘记", "找不到", "没 ", "没有在售"]):
        return "boundary_or_unavailable"
    if topic == "purchase_channel_service":
        return "purchase_channel_answer"
    if topic in {"product_fact_structure", "quality_safety"}:
        return "product_fact_answer"
    if topic == "usage_fit_maintenance":
        return "usage_fit_answer"
    if topic == "feature_request":
        return "roadmap_or_request_acknowledgement"
    if topic == "praise_ugc_relationship":
        return "warm_acknowledgement"
    if topic == "campaign_event_store":
        return "event_participation_answer"
    if contains(parent, ["好看", "好美", "喜欢", "支持", "太棒", "心动"]):
        return "warm_acknowledgement"
    return "community_participation"


def classify_style(intent: str, goal: str, reply: str) -> str:
    length = len(reply)
    if goal == "service_recovery_or_handoff":
        return "service_recovery"
    if goal == "boundary_or_unavailable":
        return "boundary_honest"
    if contains(reply, ["私信", "到店", "欢迎来", "客服", "优惠", "下单", "套餐", "福利", "厚台", "搜【", "sou 【"]):
        return "conversion_or_handoff"
    if goal in {"purchase_channel_answer", "product_fact_answer", "usage_fit_answer", "event_participation_answer"}:
        return "direct_fact" if length <= 55 else "fact_plus_condition"
    if intent in {"praise_or_desire", "experience_or_scenario_share"}:
        return "micro_reaction" if length <= 16 else "warm_specific"
    return "micro_reaction" if length <= 16 else "conversational"


def possible_promotional_staging(brand: str, parent: str, reply: str) -> bool:
    if brand != "林氏家居杭州拱墅店":
        return False
    sales_reply = contains(reply, ["厚台", "私信", "到店", "设计师", "福利", "套餐", "欢迎来店"])
    sales_ready_parent = len(parent) >= 24 and contains(parent, ["杭州", "装修", "门店", "沙发", "材质", "价格", "家庭", "户型"])
    return sales_reply and sales_ready_parent


def weight_samples(rows: list[dict]) -> None:
    posts_by_brand: dict[str, set[str]] = defaultdict(set)
    replies_by_post: Counter[tuple[str, str]] = Counter()
    for row in rows:
        brand = normalize(row.get("brand"))
        source = normalize(row.get("source_url"))
        posts_by_brand[brand].add(source)
        replies_by_post[(brand, source)] += 1
    for row in rows:
        brand = normalize(row.get("brand"))
        source = normalize(row.get("source_url"))
        post_count = max(1, len(posts_by_brand[brand]))
        reply_count = max(1, replies_by_post[(brand, source)])
        row["normalized_weight"] = 1.0 / post_count / reply_count


def normalized_distribution(rows: list[dict], field: str, *, organic_only: bool = False) -> list[dict]:
    weighted: Counter[str] = Counter()
    raw: Counter[str] = Counter()
    for row in rows:
        if organic_only and row.get("possible_promotional_staging_signal"):
            continue
        key = normalize(row.get(field)) or "unknown"
        raw[key] += 1
        weighted[key] += float(row.get("normalized_weight", 0))
    total = sum(weighted.values()) or 1.0
    return [
        {
            "id": key,
            "raw_count": raw[key],
            "brand_post_normalized_share": round(value / total, 4),
        }
        for key, value in weighted.most_common()
    ]


def load_third_party_audits() -> dict:
    groups: list[dict] = []
    for path in sorted(OFFICIAL.glob("xhs_third_party_official_presence_audit_2026-08-10_batch_*.json")):
        groups.extend(json.loads(path.read_text(encoding="utf-8")))
    pages = [page for group in groups for page in group.get("pages", []) if not page.get("skipped_own_post")]
    samples = [sample for group in groups for sample in group.get("samples", [])]
    return {
        "queries": len(groups),
        "third_party_posts_checked": len(pages),
        "posts_with_visible_target_brand_comment": sum(int(page.get("official_comments", 0) > 0) for page in pages),
        "visible_target_brand_comments": len(samples),
        "visible_presence_rate": round(sum(int(page.get("official_comments", 0) > 0) for page in pages) / max(1, len(pages)), 4),
        "interpretation": "目标品牌在第三方搜索结果帖子中的公开出现很少；该结果只覆盖当前首屏可见评论，支持谨慎参与，不代表平台全量行为。",
    }


def ordinary_comment_summary() -> dict:
    corpus = json.loads((RESEARCH / "comment_direction_corpus_600_2026-08-09.json").read_text(encoding="utf-8"))
    roles = []
    overall: Counter[str] = Counter()
    for role in corpus["roles"]:
        intents = Counter(sample.get("primary_intent", "unknown") for sample in role["samples"])
        overall.update(intents)
        roles.append({
            "slot": role["slot"],
            "public_role": role["public_role"],
            "samples": len(role["samples"]),
            "intent_distribution": dict(intents.most_common()),
        })
    return {
        "samples": corpus["total_samples"],
        "sampling_method": corpus["sampling_method"],
        "roles": roles,
        "overall_intent_distribution": dict(overall.most_common()),
        "use_boundary": "只用于真人评论意图和自然度，不用于推断品牌官方账号拥有回答权。",
    }


def build() -> tuple[dict, dict]:
    rows = load_fresh_official()
    for row in rows:
        parent = normalize(row.get("parent_text"))
        reply = normalize(row.get("reply_text"))
        post_title = normalize(row.get("post_title"))
        topic = classify_topic(parent, post_title)
        intent = classify_user_intent(parent)
        goal = classify_goal(topic, parent, reply)
        row["topic_class"] = topic
        row["user_intent"] = intent
        row["reply_goal"] = goal
        row["style_mode_observed"] = classify_style(intent, goal, reply)
        row["reply_length"] = len(reply)
        row["question_present"] = bool(re.search(r"[？?]|吗|么|多少|如何|怎么|能不能|会不会", reply))
        row["possible_promotional_staging_signal"] = possible_promotional_staging(
            normalize(row.get("brand")), parent, reply
        )
    weight_samples(rows)

    by_topic: dict[str, list[dict]] = defaultdict(list)
    for row in rows:
        by_topic[row["topic_class"]].append(row)
    topic_matrix = []
    for topic, topic_rows in sorted(by_topic.items()):
        total_weight = sum(row["normalized_weight"] for row in topic_rows) or 1.0
        goal_weight: Counter[str] = Counter()
        style_weight: Counter[str] = Counter()
        intent_weight: Counter[str] = Counter()
        for row in topic_rows:
            w = row["normalized_weight"]
            goal_weight[row["reply_goal"]] += w
            intent_weight[row["user_intent"]] += w
            if not row["possible_promotional_staging_signal"]:
                style_weight[row["style_mode_observed"]] += w
        organic_total = sum(style_weight.values()) or 1.0
        topic_matrix.append({
            "topic_class": topic,
            "raw_count": len(topic_rows),
            "brands": len({row["brand"] for row in topic_rows}),
            "source_posts": len({row["source_url"] for row in topic_rows}),
            "possible_promotional_staging_signals": sum(bool(row["possible_promotional_staging_signal"]) for row in topic_rows),
            "normalized_user_intents": {k: round(v / total_weight, 4) for k, v in intent_weight.most_common()},
            "normalized_reply_goals": {k: round(v / total_weight, 4) for k, v in goal_weight.most_common()},
            "organic_style_distribution": {k: round(v / organic_total, 4) for k, v in style_weight.most_common()},
        })

    third_party = load_third_party_audits()
    ordinary = ordinary_comment_summary()
    matrix = {
        "schema_version": 1,
        "matrix_id": "panse-official-topic-association.v1",
        "created_at": "2026-08-10",
        "evidence": {
            "fresh_xhs_official_reply_samples": len(rows),
            "fresh_xhs_brands": len({row["brand"] for row in rows}),
            "fresh_xhs_source_posts_with_replies": len({row["source_url"] for row in rows}),
            "ordinary_user_comment_samples": ordinary["samples"],
            "third_party_presence_audit": third_party,
        },
        "normalization": {
            "official_reply_weight": "each brand has equal total weight; each source post has equal weight within brand; replies share their post weight",
            "organic_voice_filter": "possible promotional staging signals remain in conversion analysis but are excluded from natural voice proportions",
            "ordinary_comment_weight": "existing corpus is balanced at 150 samples for each of four non-official roles",
            "percentages_are_not_platform_market_share": True,
        },
        "topic_distribution": normalized_distribution(rows, "topic_class"),
        "user_intent_distribution": normalized_distribution(rows, "user_intent"),
        "reply_goal_distribution": normalized_distribution(rows, "reply_goal"),
        "organic_style_distribution": normalized_distribution(rows, "style_mode_observed", organic_only=True),
        "topic_matrix": topic_matrix,
        "ordinary_comment_evidence": ordinary,
    }

    strategy = {
        "schema_version": 1,
        "strategy_id": "panse-official-topic-strategy.v1",
        "status": "active_runtime_gate",
        "effective_at": "2026-08-10",
        "matrix_ref": "research/panse_multi_direction/official_reply_research_v1/official_topic_association_matrix_v1.json",
        "evidence_summary": matrix["evidence"],
        "decision_formula": [
            "interaction_type",
            "topic_class",
            "source_author_intent",
            "visible_comment_context",
            "target_relationship",
            "panse_reply_right",
            "response_goal",
            "style_mode",
            "content_followup_signal",
        ],
        "interaction_boundaries": {
            "reply_to_user": "Reactive answers may cover verified Panse product, service, campaign and user relationship topics.",
            "outbound_comment": "Proactive comments require a visible grounded detail and a legitimate Panse reply right; purchase or complaints about another brand are not acquisition opportunities.",
            "reply_to_brand": "Only natural peer interaction or verified collaboration.",
            "brand_self_comment": "Only authorized operational information, campaign rules or fulfillment.",
        },
        "outbound_topic_pool": [
            {"topic_id": "real_space_use", "target_share": 0.30, "reply_right": "peer_observation", "route_hint": "lifestyle_resonance", "content_followup": "真实户型、尺寸、动线和日常使用案例"},
            {"topic_id": "craft_material_process", "target_share": 0.25, "reply_right": "specific_creator_support", "route_hint": "creator_specific_praise", "content_followup": "透明验证、制作过程和结构取舍"},
            {"topic_id": "maintenance_longevity", "target_share": 0.15, "reply_right": "conditional_fact_only", "route_hint": "usage_fit_answer", "content_followup": "保养、维修与长期使用"},
            {"topic_id": "ai_render_design_process", "target_share": 0.15, "reply_right": "process_peer_observation", "route_hint": "creator_specific_praise", "content_followup": "建模、AI、效果图与实物差距"},
            {"topic_id": "creator_ugc_aesthetic", "target_share": 0.10, "reply_right": "specific_creator_support", "route_hint": "creator_specific_praise", "content_followup": "真实创作者和买家空间"},
            {"topic_id": "design_culture_exhibition", "target_share": 0.05, "reply_right": "specific_design_observation", "route_hint": "creator_specific_praise", "content_followup": "国外家具、设计展和设计史转译"},
        ],
        "event_driven_topics": [
            {"topic_id": "explicit_panse_product_service", "rule": "reply whenever directly asked and facts are verified; no fixed quota"},
            {"topic_id": "panse_ugc", "rule": "respond specifically when the relationship and visible use are genuine"},
            {"topic_id": "panse_complaint", "rule": "acknowledge and hand off; never use playful or promotional style"},
        ],
        "no_reply_rules": [
            "competitor purchase or channel question that does not mention Panse",
            "complaint about another brand where Panse would be exploiting the dispute",
            "quality or safety claim without Panse-specific verified evidence or a direct request",
            "generic praise with no visible detail when acting as an outbound official account",
            "question already answered in the post or visible comments",
            "unrelated social hotspot, duplicate target, platform safety warning or frequency anomaly",
        ],
        "required_context_fields": [
            "topic_id",
            "source_author_intent",
            "target_relationship",
            "visible_detail_grounded",
            "visible_comment_context_read",
            "question_answered_in_context",
            "panse_reply_right",
        ],
        "content_signal_rules": [
            "track recurring real user questions separately from brand replies",
            "do not count suspected promotional staging as organic demand",
            "promote a topic to the article queue only after repeated independent signals or a verified Panse support need",
        ],
        "human_review_required": True,
        "publish_allowed": False,
    }
    return matrix, strategy


def write_markdown(matrix: dict) -> None:
    lines = [
        "# 畔色官方号话题—回复关联矩阵 v1",
        "",
        "日期：2026-08-10  ",
        "用途：决定官方号在哪些话题下有发言权、用什么目的和口吻回复，以及哪些信号可以沉淀成正文。",
        "",
        "## 证据与归一化",
        "",
        f"- 新补小红书家具品牌作者回复：{matrix['evidence']['fresh_xhs_official_reply_samples']} 条。",
        f"- 有回复的独立帖子：{matrix['evidence']['fresh_xhs_source_posts_with_replies']} 篇；品牌：{matrix['evidence']['fresh_xhs_brands']} 个。",
        f"- 普通用户真实评论：{matrix['evidence']['ordinary_user_comment_samples']} 条，用于校准真人意图和自然度。",
        f"- 第三方帖子检查：{matrix['evidence']['third_party_presence_audit']['third_party_posts_checked']} 篇，首屏可见目标品牌评论 {matrix['evidence']['third_party_presence_audit']['visible_target_brand_comments']} 条。",
        "- 每个品牌等权、品牌内每篇帖子等权；同帖大量回复不会把整张矩阵带偏。",
        "- 疑似运营铺垫信号保留用于转化路径分析，但不进入自然口吻比例。",
        "",
        "## 归一化话题分布",
        "",
        "| 话题 | 原始条数 | 品牌—帖子归一化占比 |",
        "|---|---:|---:|",
    ]
    for row in matrix["topic_distribution"]:
        lines.append(f"| {row['id']} | {row['raw_count']} | {row['brand_post_normalized_share']:.1%} |")
    lines.extend([
        "",
        "## 运行结论",
        "",
        "1. 品牌被动回复集中在自己拥有答案的事实、渠道、产品和使用问题；这不能转换成主动去竞品帖子下询价或截流。",
        "2. 主动外评应以真实空间、工艺过程、维护、AI/建模、创作者细节和设计文化为主；每次只承接一个可见细节。",
        "3. 投诉、质量安全和竞品购买问题必须先判断畔色是否拥有发言权；没有就不回复。",
        "4. 林氏门店样本中存在疑似运营铺垫信号，只用于学习转化结构，不用于模仿普通人语气或推断自然需求。",
        "5. 评论信号只有在独立帖子、独立用户中重复出现，或直接涉及畔色服务时，才进入正文选题队列。",
        "",
        "## 官方主动评论基础配比",
        "",
        "- 真实空间与使用：30%",
        "- 工艺、材料与制作过程：25%",
        "- 保养、维修与长期使用：15%",
        "- AI、渲染与设计过程：15%",
        "- 创作者、UGC与审美细节：10%",
        "- 设计文化、展览与国外家具：5%",
        "",
        "畔色产品、购买、售后、UGC和投诉采用事件触发，不人为凑比例。",
    ])
    OUTPUT_MD.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    matrix, strategy = build()
    OUTPUT_JSON.write_text(json.dumps(matrix, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    STRATEGY_JSON.write_text(json.dumps(strategy, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    write_markdown(matrix)
    print(json.dumps({
        "matrix": OUTPUT_JSON.relative_to(ROOT).as_posix(),
        "strategy": STRATEGY_JSON.relative_to(ROOT).as_posix(),
        "markdown": OUTPUT_MD.relative_to(ROOT).as_posix(),
        "fresh_xhs_official_samples": matrix["evidence"]["fresh_xhs_official_reply_samples"],
        "ordinary_comments": matrix["evidence"]["ordinary_user_comment_samples"],
        "third_party_posts_checked": matrix["evidence"]["third_party_presence_audit"]["third_party_posts_checked"],
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
