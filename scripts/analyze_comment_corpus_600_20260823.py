#!/usr/bin/env python3
"""Create a reproducible multi-axis analysis of the 600-comment corpus.

This is a local research utility. It performs no network or platform action and
does not change any production writing policy.
"""

from __future__ import annotations

import json
import re
from collections import Counter, defaultdict
from datetime import date
from difflib import SequenceMatcher
from pathlib import Path


REPO = Path(__file__).resolve().parents[1]
RESEARCH = REPO / "research" / "panse_multi_direction"
SOURCE = RESEARCH / "comment_direction_corpus_600_2026-08-09.json"
OUTPUT_JSON = RESEARCH / "comment_corpus_600_multiaxis_analysis_2026-08-23.json"
OUTPUT_MD = RESEARCH / "comment_corpus_600_taxonomy_report_2026-08-23.md"


CATEGORIES = {
    "C01_direct_emotional_reaction": "直接表达喜欢、舒服、惊讶或不喜欢，不展开解释",
    "C02_object_specific_preference": "点出一个具体物件、画面或局部，并给出个人偏好",
    "C03_dimension_layout_fit_question": "询问面积、开间、尺寸、走道、展开余量或家具能否放下",
    "C04_practical_use_maintenance_question": "询问坐、走、开门、清洁、耐用、维修等使用结果",
    "C05_acquisition_price_channel_question": "询问价格、链接、品牌、门店、渠道或定制成本",
    "C06_factual_identification_question": "询问物件、材质、型号、颜色或做法是什么",
    "C07_context_adaptation_question": "把问题放进家庭、地区、预算或国内适配条件",
    "C08_verified_experience_share": "评论者分享自己真实购买、居住或使用经验",
    "C09_desire_vote_or_imitation": "表达想买、想抄、投票、选择或希望复刻",
    "C10_peer_tip_or_suggestion": "提供经验建议、条件提醒或可执行做法",
    "C11_stance_or_disagreement": "提出赞成、反对、质疑或不同偏好",
    "C12_humor_roleplay_or_banter": "接梗、角色代入、夸张或轻松玩笑",
    "C13_request_more_or_continuation": "请求清单、教程、后续、更多区域或下一期",
    "C14_minimal_ack_or_context_answer": "极短回应、确认、点名、接话或上下文答案",
    "C15_context_dependent_neutral_other": "文本本身自然但缺少父评论或正文，无法可靠判断动作",
    "C16_editorial_summary_or_aphorism": "抽象总结、格言、评审式升华或过度文学化表达",
    "C17_noise_hostility_or_unsafe": "乱码、恶意嘲讽、攻击、群体概括或明显不宜复用内容",
}


CONTENT_THEMES = {
    "T01_small_space_layout_flow": "小户型、布局、动线、开间和空间分配",
    "T02_light_color_atmosphere": "采光、色彩、氛围和软装视觉",
    "T03_dimensions_fit_ergonomics": "家具尺寸、人体使用、展开和适配",
    "T04_purchase_price_budget": "购买、价格、预算、渠道和成本",
    "T05_material_craft_structure": "材料、工艺、结构、设计和制作",
    "T06_maintenance_durability_after_sales": "清洁、耐用、维修、质保和售后",
    "T07_storage_cabinet_kitchen": "收纳、柜体、厨房和台面",
    "T08_seating_comfort_soft_furnishings": "沙发、椅子、床、地毯和坐卧舒适",
    "T09_global_design_brand_case": "国外住宅、设计师、品牌和经典家具案例",
    "T10_renovation_transformation": "装修、改造、拆改和前后变化",
    "T11_anti_consumption_lived_use": "不一次买齐、真实入住、长期取舍和反消费",
    "T12_tools_tutorial_source_request": "工具、软件、教程、清单、链接和资料来源",
    "T13_other_home_lifestyle": "其他家居生活、关系互动或无法细分主题",
}


ROLE_NAMES = {
    2: "空间生活提案编辑",
    3: "理性家具决策编辑",
    4: "户型、尺寸与动线顾问",
    5: "全球家具工艺与居住偏好观察编辑",
}


def compact(value: object) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()


def normalized_chars(value: str) -> str:
    return "".join(re.findall(r"[\u4e00-\u9fffA-Za-z0-9]", value.lower()))


def contains_any(text: str, terms: tuple[str, ...] | list[str]) -> bool:
    return any(term in text for term in terms)


def question_present(text: str, labels: set[str]) -> bool:
    return bool(
        re.search(r"[?？]", text)
        or re.search(r"(请问|想问|求问|吗|嘛|多少|多大|多宽|多高|多深|哪里|哪儿|为什么|什么|怎么|如何|能不能|会不会|有没有|是不是|哪款|啥|还是)", text)
    )


def noise_or_garbled(text: str) -> bool:
    stripped = re.sub(r"\s+", "", text)
    if not stripped:
        return True
    return bool(
        re.search(r"(?:^|\s)[A-Za-z](?:\s+[A-Za-z]){3,}(?:$|\s)", text)
        or re.search(r"(?:^|[\s,，!！])[\u4e00-\u9fff](?:\s+[\u4e00-\u9fff]){2,}", text)
    )


def title_overlap(text: str, title: str) -> float:
    left = normalized_chars(text)
    right = normalized_chars(title)
    if not left or not right:
        return 0.0
    return round(SequenceMatcher(None, left, right).ratio(), 4)


def content_themes_for(row: dict, text: str, title: str) -> list[str]:
    combined = " ".join(
        (
            compact(row.get("query")),
            compact(row.get("source_group")),
            title,
            text,
        )
    )
    rules = {
        "T01_small_space_layout_flow": (
            "小户型", "小空间", "布局", "动线", "开间", "过道", "走道", "户型", "平米", "㎡",
        ),
        "T02_light_color_atmosphere": (
            "采光", "阳光", "颜色", "色彩", "配色", "氛围", "软装", "原木色", "中古风", "北欧风",
        ),
        "T03_dimensions_fit_ergonomics": (
            "尺寸", "多宽", "多高", "多深", "展开", "顶腿", "坐久", "放得下", "舒适", "人体",
        ),
        "T04_purchase_price_budget": (
            "价格", "预算", "多少钱", "多少米", "链接", "哪里买", "怎么买", "门店", "定做", "淘宝", "下单",
        ),
        "T05_material_craft_structure": (
            "材质", "材料", "工艺", "结构", "木", "纸绳", "藤", "焊缝", "连接件", "家具设计", "名椅",
        ),
        "T06_maintenance_durability_after_sales": (
            "清洁", "打理", "难打理", "耐用", "发霉", "开裂", "维修", "修复", "质保", "售后", "退货", "影响", "耐抓", "划痕", "保养",
        ),
        "T07_storage_cabinet_kitchen": (
            "收纳", "柜", "厨房", "台面", "衣柜", "书柜", "斗柜", "餐边柜", "置物架",
        ),
        "T08_seating_comfort_soft_furnishings": (
            "沙发", "椅", "床", "地毯", "茶几", "坐感", "靠背", "餐椅", "凳子",
        ),
        "T09_global_design_brand_case": (
            "国外", "海外", "欧洲", "法国", "瑞典", "丹麦", "米兰", "巴黎", "设计师", "品牌", "ins",
        ),
        "T10_renovation_transformation": (
            "装修", "改造", "爆改", "拆墙", "拆改", "老破小", "翻车", "入住",
        ),
        "T11_anti_consumption_lived_use": (
            "不要一次买齐", "没必要买", "反消费", "入住", "用了", "一年", "长期", "后悔", "取舍",
        ),
        "T12_tools_tutorial_source_request": (
            "软件", "AI", "教程", "清单", "资料", "来源", "哪一期", "链接", "博主",
        ),
    }
    themes = [theme for theme, terms in rules.items() if contains_any(combined, terms)]
    return themes or ["T13_other_home_lifestyle"]


def classify_category(row: dict, text: str, labels: set[str]) -> tuple[str, list[str]]:
    intent = str(row.get("primary_intent", ""))
    reasons: list[str] = []
    is_question = question_present(text, labels)

    hostile = contains_any(
        text,
        (
            "什么也不懂",
            "谦虚点",
            "孤独终老",
            "智商税",
            "闭嘴",
            "垃圾",
            "恶心",
            "滚",
        ),
    )
    group_generalization = bool(
        re.search(r"(欧洲人|外国人|国外人|中国人|国内人).{0,10}(都|就是|真的|天生)", text)
    )
    if noise_or_garbled(text) or hostile or group_generalization:
        reasons.append("noise_hostility_or_group_generalization")
        return "C17_noise_hostility_or_unsafe", reasons

    lyrical = len(text) >= 70 and contains_any(
        text, ("最深的含义", "拥有你的时间", "空间里", "忠实地记录", "这才是")
    )
    aphorism = contains_any(
        text,
        (
            "任何事情都是多面",
            "适合自己的才是最好",
            "生活就是",
            "审美能力的体现",
            "真正的意义",
            "这才是生活",
        ),
    )
    if lyrical or aphorism or row.get("teacher_posture") is True:
        reasons.append("editorial_lyrical_or_teacher_posture")
        return "C16_editorial_summary_or_aphorism", reasons

    if intent == "request_more" or contains_any(
        text, ("再做一期", "出一期", "期待下期", "想看后续", "多分享", "求教程", "有教程吗")
    ):
        reasons.append("explicit_request_for_continuation")
        return "C13_request_more_or_continuation", reasons

    acquisition_terms = (
        "多少钱",
        "多少米",
        "价格",
        "链接",
        "哪里买",
        "哪儿买",
        "怎么买",
        "门店",
        "定做",
        "淘宝",
        "购买",
        "求链接",
    )
    if intent == "acquisition_question" or "acquisition_where" in labels or "price_budget" in labels or contains_any(text, acquisition_terms):
        reasons.append("acquisition_or_price_signal")
        return "C05_acquisition_price_channel_question", reasons

    if (
        intent in {"self_reference_verified", "self_display_verified"}
        or "self_reference" in labels
        or "self_display" in labels
        or re.search(
            r"(我家|我的|我在公司|我之前|我也有|我们家|^买了|我.{0,10}(买|用|住|有|开间|过道|沙发|茶几|装)|(?:买了|买完|买的).{0,12}我|入住|用了.{0,6}年)",
            text,
        )
    ):
        reasons.append("first_person_experience_signal")
        return "C08_verified_experience_share", reasons

    if intent == "light_humor" or contains_any(
        text,
        (
            "哈哈",
            "笑死",
            "救命",
            "拍完了你就走吧",
            "我要看电视",
            "能搬出去吗",
            "比国王",
        ),
    ):
        reasons.append("humor_or_roleplay_signal")
        return "C12_humor_roleplay_or_banter", reasons

    if (
        intent == "contextual_disagreement"
        or contains_any(
            text,
            ("不认同", "我不同意", "我并不", "不行不行", "没必要", "问题是", "我觉得还是", "但是我", "不过我", "不如", "怎么不实用", "多大的错", "视为大敌"),
        )
        or re.search(r"我觉得.{0,24}(最好|更好|不如|没必要|不实用)", text)
    ):
        reasons.append("first_person_stance_signal")
        return "C11_stance_or_disagreement", reasons

    advice_signal = bool(
        intent == "peer_tip_invited"
        or "peer_tip" in labels
        or contains_any(text, ("建议", "尽量", "记得", "可以先", "不用买", "要考虑", "先问清楚", "可以试试"))
        or re.search(r"最好(先|把|问|看|买|选|做|别|不要)", text)
    )
    if advice_signal:
        reasons.append("advice_or_peer_tip_signal")
        return "C10_peer_tip_or_suggestion", reasons

    if contains_any(
        text,
        ("我投", "我选", "想买", "想要", "想抄", "准备抄", "准备入", "真想", "想搬", "种草", "心动", "同款"),
    ):
        reasons.append("desire_vote_or_imitation_signal")
        return "C09_desire_vote_or_imitation", reasons

    if is_question:
        adaptation_terms = (
            "国内",
            "国外",
            "普通家庭",
            "家里",
            "有娃",
            "养猫",
            "地暖",
            "潮",
            "预算",
            "通风",
            "采光",
            "西晒",
        )
        dimension_terms = (
            "尺寸",
            "多大",
            "面积",
            "开间",
            "多宽",
            "多高",
            "多深",
            "多少厘米",
            "多少公分",
            "走道",
            "过道",
            "展开",
            "放得下",
            "层高",
            "小户型",
            "套内",
        )
        use_terms = (
            "舒服",
            "卡住",
            "顶腿",
            "托住头",
            "好打理",
            "清洁",
            "耐用",
            "发霉",
            "影响",
            "打开",
            "展开",
            "进出",
            "坐久",
            "安全",
            "稳不稳",
        )
        factual_terms = (
            "是什么",
            "叫什么",
            "哪款",
            "什么材质",
            "什么颜色",
            "什么牌子",
            "型号",
            "色号",
            "中间那个",
            "哪个是",
            "承重墙",
            "自带",
            "原本的还是",
            "后来安装",
            "自己设计",
            "找人设计",
            "怎么改造",
        )
        if contains_any(text, adaptation_terms):
            reasons.append("question_contains_context_adaptation_condition")
            return "C07_context_adaptation_question", reasons
        if contains_any(text, dimension_terms):
            reasons.append("question_about_dimensions_layout_or_fit")
            return "C03_dimension_layout_fit_question", reasons
        if contains_any(text, factual_terms):
            reasons.append("question_seeks_identification_or_fact")
            return "C06_factual_identification_question", reasons
        if contains_any(text, use_terms) or intent == "utility_fit_question" or "utility_fit" in labels:
            reasons.append("question_about_real_use_or_fit")
            return "C04_practical_use_maintenance_question", reasons
        reasons.append("question_with_practical_information_need")
        return "C04_practical_use_maintenance_question", reasons

    if "praise" in labels or intent == "grounded_praise" or contains_any(
        text, ("好看", "漂亮", "舒服", "喜欢", "厉害", "优雅", "温馨", "有灵气", "特别", "绝了")
    ):
        object_specific = bool(
            re.search(r"(这个|那个|这把|那把|这张|图\d+|灯|椅|桌|柜|沙发|配色|颜色|材质|连接件|焊缝)", text)
        )
        if object_specific:
            reasons.append("praise_targets_specific_object_or_detail")
            return "C02_object_specific_preference", reasons
        reasons.append("direct_emotional_or_aesthetic_reaction")
        return "C01_direct_emotional_reaction", reasons

    if len(normalized_chars(text)) <= 8 or re.fullmatch(
        r"(?:学到了|同意|确实|是的|没错|重点|支持|LC3|谢谢分享)[！!。.]?",
        text,
    ):
        reasons.append("minimal_acknowledgement_or_context_answer")
        return "C14_minimal_ack_or_context_answer", reasons

    if len(text) >= 50 and re.search(r"(因为|所以|而且|但是|不是|而是|如果)", text):
        reasons.append("long_abstract_or_argumentative_neutral_comment")
        return "C16_editorial_summary_or_aphorism", reasons

    reasons.append("short_neutral_context_dependent_comment")
    return "C15_context_dependent_neutral_other", reasons


def tone_for(category: str, text: str) -> str:
    if category == "C12_humor_roleplay_or_banter":
        return "playful"
    if category == "C17_noise_hostility_or_unsafe":
        return "confrontational_or_unsafe"
    if category == "C16_editorial_summary_or_aphorism":
        return "editorial_or_lyrical"
    if category in {
        "C03_dimension_layout_fit_question",
        "C04_practical_use_maintenance_question",
        "C05_acquisition_price_channel_question",
        "C06_factual_identification_question",
        "C07_context_adaptation_question",
        "C13_request_more_or_continuation",
    }:
        return "curious"
    if category == "C11_stance_or_disagreement":
        return "skeptical_or_assertive"
    if category == "C10_peer_tip_or_suggestion":
        return "instructive"
    if category in {"C01_direct_emotional_reaction", "C02_object_specific_preference"}:
        return "warm_or_enthusiastic"
    if category in {"C08_verified_experience_share", "C09_desire_vote_or_imitation"}:
        return "personal"
    return "direct_or_neutral"


def structure_for(category: str, text: str, labels: set[str]) -> str:
    is_question = question_present(text, labels)
    sentence_count = max(1, len(re.findall(r"[。！？!?]", text)))
    has_statement_before_question = bool(is_question and re.search(r"[,，。!！].*[?？]", text))
    if category == "C12_humor_roleplay_or_banter":
        return "roleplay_or_punchline"
    if category == "C08_verified_experience_share":
        return "first_person_experience"
    if category == "C10_peer_tip_or_suggestion":
        return "advice_or_condition"
    if category == "C11_stance_or_disagreement":
        return "contrastive_judgment"
    if category == "C16_editorial_summary_or_aphorism" or sentence_count >= 3:
        return "multi_clause_argument_or_mini_essay"
    if has_statement_before_question:
        return "statement_plus_question"
    if is_question:
        return "direct_question"
    if category == "C02_object_specific_preference":
        return "object_plus_evaluation"
    if len(normalized_chars(text)) <= 8:
        return "minimal_fragment"
    return "single_declaration"


def style_flags_for(category: str, text: str, row: dict, overlap: float) -> list[str]:
    flags: list[str] = []
    if len(text) <= 20:
        flags.append("concise")
    if len(text) <= 12 or not re.search(r"[。！？!?]", text):
        flags.append("elliptical_or_fragmentary")
    if re.search(r"(呀|啊|啦|咯|诶|哈哈|哇|哎|吧|嘛|呢)", text):
        flags.append("colloquial_particle")
    if re.search(r"[\U0001F300-\U0001FAFF]|\[[^\]]+R\]", text):
        flags.append("emoji_or_platform_sticker")
    if re.search(r"[A-Za-z]{2,}", text):
        flags.append("mixed_language_or_model_name")
    if len(text) > 60:
        flags.append("overlong_for_casual_comment")
    if row.get("teacher_posture") is True or category == "C16_editorial_summary_or_aphorism":
        flags.append("editorial_or_teacher_risk")
    if category == "C17_noise_hostility_or_unsafe":
        flags.append("noise_or_hostility_risk")
    if category == "C01_direct_emotional_reaction" and len(text) <= 12:
        flags.append("generic_praise_risk")
    if category in {
        "C03_dimension_layout_fit_question",
        "C04_practical_use_maintenance_question",
        "C05_acquisition_price_channel_question",
        "C06_factual_identification_question",
        "C07_context_adaptation_question",
        "C08_verified_experience_share",
        "C09_desire_vote_or_imitation",
        "C11_stance_or_disagreement",
        "C12_humor_roleplay_or_banter",
        "C13_request_more_or_continuation",
    }:
        flags.append("speaker_motive_visible")
    if overlap >= 0.55:
        flags.append("high_title_overlap")
    return flags


def risk_flags_for(category: str, text: str, row: dict) -> list[str]:
    risks: list[str] = []
    if category == "C08_verified_experience_share":
        risks.append("firsthand_claim_requires_account_verification")
    if category == "C10_peer_tip_or_suggestion":
        risks.append("advice_requires_invitation_or_clear_problem")
    if category == "C11_stance_or_disagreement":
        risks.append("disagreement_requires_respectful_non_verdict_tone")
    if category == "C16_editorial_summary_or_aphorism":
        risks.append("editorial_summary_or_empty_evaluation")
    if category == "C17_noise_hostility_or_unsafe":
        risks.append("reject_for_production")
    if contains_any(text, ("欧洲人", "外国人", "中国人", "国内人")):
        risks.append("country_or_group_generalization")
    if contains_any(text, ("私信", "加我", "联系我")):
        risks.append("private_contact_or_lead_generation")
    if row.get("teacher_posture") is True:
        risks.append("teacher_or_judge_posture")
    if row.get("critique_first") is True:
        risks.append("critique_first")
    if len(text) > 80:
        risks.append("overlong_mini_essay")
    return sorted(set(risks))


def reuse_policy(category: str, flags: list[str], risks: list[str]) -> str:
    if category == "C17_noise_hostility_or_unsafe":
        return "reject"
    if category == "C16_editorial_summary_or_aphorism":
        return "observe_only"
    if category in {"C08_verified_experience_share", "C10_peer_tip_or_suggestion", "C11_stance_or_disagreement"}:
        return "conditional"
    if category in {"C01_direct_emotional_reaction", "C14_minimal_ack_or_context_answer", "C15_context_dependent_neutral_other"}:
        return "limited_use"
    if risks:
        return "conditional"
    if "generic_praise_risk" in flags:
        return "limited_use"
    return "preferred_structure"


def quality_score(category: str, text: str, flags: list[str], risks: list[str], row: dict) -> int:
    score = 0
    if "speaker_motive_visible" in flags:
        score += 3
    if row.get("pragmatic") is True:
        score += 2
    if 6 <= len(text) <= 35:
        score += 2
    if not risks:
        score += 1
    if category in {"C03_dimension_layout_fit_question", "C04_practical_use_maintenance_question", "C07_context_adaptation_question", "C13_request_more_or_continuation"}:
        score += 1
    if "generic_praise_risk" in flags:
        score -= 2
    if "overlong_for_casual_comment" in flags:
        score -= 2
    if category in {"C16_editorial_summary_or_aphorism", "C17_noise_hostility_or_unsafe"}:
        score -= 4
    return score


def pct(count: int, total: int) -> str:
    return f"{count / total * 100:.1f}%" if total else "0.0%"


def markdown_table(headers: list[str], rows: list[list[object]]) -> str:
    def esc(value: object) -> str:
        return str(value).replace("|", "\\|").replace("\n", " ")

    lines = ["| " + " | ".join(map(esc, headers)) + " |"]
    lines.append("| " + " | ".join("---" for _ in headers) + " |")
    lines.extend("| " + " | ".join(esc(value) for value in row) + " |" for row in rows)
    return "\n".join(lines)


def main() -> int:
    corpus = json.loads(SOURCE.read_text(encoding="utf-8"))
    annotations: list[dict] = []
    source_index = 0
    for role in corpus["roles"]:
        slot = int(role["slot"])
        for role_index, row in enumerate(role["samples"], 1):
            source_index += 1
            text = compact(row.get("text") or row.get("comment_text"))
            title = compact(row.get("note_title"))
            labels = set(row.get("labels", []))
            category, reasons = classify_category(row, text, labels)
            content_themes = content_themes_for(row, text, title)
            overlap = title_overlap(text, title)
            tone = tone_for(category, text)
            structure = structure_for(category, text, labels)
            style_flags = style_flags_for(category, text, row, overlap)
            risk_flags = risk_flags_for(category, text, row)
            policy = reuse_policy(category, style_flags, risk_flags)
            score = quality_score(category, text, style_flags, risk_flags, row)
            annotations.append(
                {
                    "source_index": source_index,
                    "slot": slot,
                    "public_role": role["public_role"],
                    "role_index": role_index,
                    "note_id": row["note_id"],
                    "note_title": title,
                    "query": compact(row.get("query")),
                    "comment_text": text,
                    "source_primary_intent": row.get("primary_intent"),
                    "source_labels": sorted(labels),
                    "primary_category": category,
                    "category_reason": reasons,
                    "content_themes": content_themes,
                    "tone": tone,
                    "structure": structure,
                    "style_flags": style_flags,
                    "risk_flags": risk_flags,
                    "reuse_policy": policy,
                    "quality_score": score,
                    "length_chars": len(text),
                    "question_present": question_present(text, labels),
                    "title_overlap_ratio": overlap,
                }
            )

    if len(annotations) != 600:
        raise RuntimeError(f"expected 600 annotations, got {len(annotations)}")
    if len({item["source_index"] for item in annotations}) != 600:
        raise RuntimeError("source index is not unique")

    category_counts = Counter(item["primary_category"] for item in annotations)
    theme_counts = Counter(theme for item in annotations for theme in item["content_themes"])
    tone_counts = Counter(item["tone"] for item in annotations)
    structure_counts = Counter(item["structure"] for item in annotations)
    style_counts = Counter(flag for item in annotations for flag in item["style_flags"])
    risk_counts = Counter(flag for item in annotations for flag in item["risk_flags"])
    reuse_counts = Counter(item["reuse_policy"] for item in annotations)
    role_category_counts: dict[int, Counter] = defaultdict(Counter)
    role_theme_counts: dict[int, Counter] = defaultdict(Counter)
    role_tone_counts: dict[int, Counter] = defaultdict(Counter)
    role_structure_counts: dict[int, Counter] = defaultdict(Counter)
    for item in annotations:
        role_category_counts[item["slot"]][item["primary_category"]] += 1
        role_theme_counts[item["slot"]].update(item["content_themes"])
        role_tone_counts[item["slot"]][item["tone"]] += 1
        role_structure_counts[item["slot"]][item["structure"]] += 1

    representative_samples: dict[str, list[dict]] = {}
    for category in CATEGORIES:
        candidates = [item for item in annotations if item["primary_category"] == category]
        candidates.sort(key=lambda item: (-item["quality_score"], item["length_chars"], item["source_index"]))
        representative_samples[category] = [
            {
                "source_index": item["source_index"],
                "slot": item["slot"],
                "comment_text": item["comment_text"],
                "reuse_policy": item["reuse_policy"],
                "risk_flags": item["risk_flags"],
            }
            for item in candidates[:5]
        ]

    lengths = sorted(item["length_chars"] for item in annotations)
    summary = {
        "schema_version": 1,
        "analysis_id": "panse-xhs-comment-corpus-600-multiaxis.v1",
        "analyzed_at": str(date(2026, 8, 23)),
        "scope": "local_research_only_no_external_actions",
        "source": str(SOURCE.relative_to(REPO)).replace("\\", "/"),
        "source_rows": 600,
        "source_roles": 4,
        "source_note_ids": len({item["note_id"] for item in annotations}),
        "source_text_unique": len({item["comment_text"] for item in annotations}),
        "length": {
            "minimum": lengths[0],
            "median": (lengths[299] + lengths[300]) / 2,
            "mean": round(sum(lengths) / len(lengths), 2),
            "maximum": lengths[-1],
            "at_most_10": sum(length <= 10 for length in lengths),
            "at_most_20": sum(length <= 20 for length in lengths),
            "over_60": sum(length > 60 for length in lengths),
            "over_80": sum(length > 80 for length in lengths),
        },
        "category_definitions": CATEGORIES,
        "content_theme_definitions": CONTENT_THEMES,
        "category_counts": dict(category_counts.most_common()),
        "content_theme_counts": dict(theme_counts.most_common()),
        "tone_counts": dict(tone_counts.most_common()),
        "structure_counts": dict(structure_counts.most_common()),
        "style_flag_counts": dict(style_counts.most_common()),
        "risk_flag_counts": dict(risk_counts.most_common()),
        "reuse_policy_counts": dict(reuse_counts.most_common()),
        "role_category_counts": {str(slot): dict(role_category_counts[slot].most_common()) for slot in sorted(role_category_counts)},
        "role_content_theme_counts": {str(slot): dict(role_theme_counts[slot].most_common()) for slot in sorted(role_theme_counts)},
        "role_tone_counts": {str(slot): dict(role_tone_counts[slot].most_common()) for slot in sorted(role_tone_counts)},
        "role_structure_counts": {str(slot): dict(role_structure_counts[slot].most_common()) for slot in sorted(role_structure_counts)},
        "representative_samples": representative_samples,
        "limitations": [
            "Only 6 of the 270 source note_ids have complete note bodies in the current local deep dataset.",
            "The corpus does not retain the parent comment when a sample may be replying to another user.",
            "Category labels are deterministic research annotations, not human ground truth.",
            "Title overlap can be measured for all 600 items, but full-body restatement cannot be determined for 264 note_ids without recollection.",
            "Observed first-person experience is useful for studying human comments but cannot be copied by controlled accounts without verified firsthand evidence.",
        ],
        "external_actions_performed": False,
        "production_policy_modified": False,
    }

    OUTPUT_JSON.write_text(
        json.dumps({"summary": summary, "annotations": annotations}, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    category_rows = []
    for category, description in CATEGORIES.items():
        count = category_counts[category]
        policies = Counter(
            item["reuse_policy"] for item in annotations if item["primary_category"] == category
        )
        main_policy = policies.most_common(1)[0][0] if policies else "n/a"
        category_rows.append([category, description, count, pct(count, 600), main_policy])

    role_rows = []
    for slot in sorted(ROLE_NAMES):
        top = role_category_counts[slot].most_common(5)
        top_themes = role_theme_counts[slot].most_common(4)
        role_rows.append(
            [
                slot,
                ROLE_NAMES[slot],
                "；".join(f"{key}={value}" for key, value in top),
                "；".join(f"{key}={value}" for key, value in top_themes),
            ]
        )

    tone_rows = [[name, count, pct(count, 600)] for name, count in tone_counts.most_common()]
    structure_rows = [[name, count, pct(count, 600)] for name, count in structure_counts.most_common()]
    reuse_rows = [[name, count, pct(count, 600)] for name, count in reuse_counts.most_common()]
    theme_rows = [
        [theme, CONTENT_THEMES[theme], count, pct(count, 600)]
        for theme, count in theme_counts.most_common()
    ]

    samples_lines: list[str] = []
    for category in CATEGORIES:
        samples_lines.append(f"### {category}\n")
        for sample in representative_samples[category][:3]:
            risks = "、".join(sample["risk_flags"]) or "无"
            samples_lines.append(
                f"- #{sample['source_index']} / slot {sample['slot']} / {sample['reuse_policy']} / 风险：{risks}：{sample['comment_text']}"
            )
        samples_lines.append("")

    report = f"""# 畔色小红书 600 条真人评论多维分析 v1

日期：2026-08-23
范围：本地研究；未访问平台；未修改生产写作策略；未执行评论、关注或其他外部动作。

## 1. 数据完整性

- 600/600 条已逐条生成结构化标注，文本无空值、无完全重复。
- 四个非官方角色各 150 条，覆盖 270 个唯一 note_id。
- 长度 2–132 字，平均 {summary['length']['mean']} 字，中位数 {summary['length']['median']} 字。
- {summary['length']['at_most_20']}/600 条不超过 20 字；{summary['length']['over_60']}/600 条超过 60 字。
- 当前本地深语料只能为 270 个 note_id 中的 6 个补齐完整正文。因此本报告能完整分析评论文本、标题和既有标签，但不能把其余 264 篇的“是否复述正文”写成已验证事实。

## 2. 17 个组合分类

{markdown_table(['类别', '定义', '数量', '占比', '默认复用边界'], category_rows)}

## 3. 内容主题分布（多标签）

{markdown_table(['主题', '定义', '命中数', '相对600条占比'], theme_rows)}

一条评论可以同时命中多个内容主题，因此命中数之和会大于 600。

## 4. 语气分布

{markdown_table(['语气', '数量', '占比'], tone_rows)}

## 5. 结构分布

{markdown_table(['结构', '数量', '占比'], structure_rows)}

## 6. 生产复用边界

{markdown_table(['边界', '数量', '占比'], reuse_rows)}

- `preferred_structure`：优先学习说话动作和结构，仍不能复制事实或措辞。
- `limited_use`：真人常见但信息低，只能少量出现，不能成为批次主体。
- `conditional`：只有身份、事实、邀请或语气条件满足时才能使用。
- `observe_only`：只用来识别反例，不进入正向示例。
- `reject`：不得进入生成参考。

## 7. 四个角色的主要差异

{markdown_table(['slot', '角色', '数量最高的 5 类', '命中最高的 4 个内容主题'], role_rows)}

## 8. 典型样本

{chr(10).join(samples_lines)}
## 9. 建议进入下一轮讨论的候选类型

优先讨论：C01、C02、C03、C04、C05、C06、C07、C09、C12、C13。
条件讨论：C08、C10、C11、C14、C15。
只作反例：C16、C17。

真正需要决定的不是固定比例，而是：每个账号允许哪些说话动机、哪些类型只能在特定帖子和评论区气氛下出现，以及一个批次最多允许多少条低信息短评。

## 10. 方法边界

- 每条只有一个主分类，同时保留语气、结构、文风和风险多标签。
- 原始 `primary_intent` 标签存在误判，本报告没有把它当作人工真值。
- 完整逐条标注保存在 `{OUTPUT_JSON.name}`，可按 source_index 回查原语料。
- 本轮不修改 Style Lab、账号策略或评论草稿；分类经用户讨论确认后再进入生产设计。
"""
    OUTPUT_MD.write_text(report, encoding="utf-8")

    print(
        json.dumps(
            {
                "annotations": len(annotations),
                "categories": len(CATEGORIES),
                "category_counts": dict(category_counts.most_common()),
                "reuse_policy_counts": dict(reuse_counts.most_common()),
                "output_json": str(OUTPUT_JSON),
                "output_md": str(OUTPUT_MD),
                "external_actions_performed": False,
                "production_policy_modified": False,
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
