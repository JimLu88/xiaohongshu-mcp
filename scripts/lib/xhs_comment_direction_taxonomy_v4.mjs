export const POLICY_VERSION = "xhs-comment-intent.v4";

export const TOPICS = {
  purchase_service: {
    label: "购买渠道与售后",
    keywords: ["哪里买", "怎么买", "链接", "店铺", "官网", "型号", "品牌", "售后", "保修"],
  },
  budget_value: {
    label: "价格预算与替代",
    keywords: ["价格", "多少钱", "预算", "价位", "贵", "便宜", "替代", "先不买", "省钱"],
  },
  material_craft: {
    label: "材料结构与工艺",
    keywords: ["木种", "实木", "贴皮", "板材", "涂装", "结构", "连接", "五金", "榫", "工艺", "检测报告"],
  },
  dimensions_fit: {
    label: "尺寸净空与放置",
    keywords: ["尺寸", "多宽", "多高", "多深", "净宽", "墙宽", "柜深", "开间", "进深", "放得下"],
  },
  layout_circulation: {
    label: "户型布局与动线",
    keywords: ["户型", "动线", "通道", "过道", "门洞", "开门", "转身", "客厅", "餐区", "玄关"],
  },
  storage_function: {
    label: "收纳容量与使用方式",
    keywords: ["收纳", "容量", "抽屉", "层板", "柜门", "餐边柜", "置物", "随手放", "拿取"],
  },
  comfort_ergonomics: {
    label: "舒适度与人体工学",
    keywords: ["舒服", "舒适", "坐高", "座深", "靠背", "扶手", "腿部", "人体工学", "久坐"],
  },
  maintenance_lifetime: {
    label: "清洁维护与耐久",
    keywords: ["清洁", "打理", "耐用", "划痕", "开裂", "变形", "维修", "寿命", "长期", "耐久"],
  },
  installation_logistics: {
    label: "安装运输与进场",
    keywords: ["安装", "运输", "物流", "入户", "电梯", "楼梯", "组装", "拆装", "搬家", "到货"],
  },
  color_light_atmosphere: {
    label: "配色采光与空间氛围",
    keywords: ["颜色", "木色", "白墙", "采光", "光线", "灯光", "朝向", "软装", "搭配", "氛围"],
  },
  household_constraints: {
    label: "家庭成员与居住限制",
    keywords: ["小户型", "租房", "孩子", "儿童", "宠物", "老人", "独居", "家庭", "日常", "空间小"],
  },
  global_localization: {
    label: "国外案例与本地适配",
    keywords: ["国外", "海外", "北欧", "日本", "欧洲", "经典家具", "本地适配", "气候", "湿度", "标准"],
  },
  creator_process_ai: {
    label: "设计建模与AI过程",
    keywords: ["建模", "渲染", "效果图", "实物", "AI", "生成", "设计过程", "打样", "版本"],
  },
  entrepreneurship_brand: {
    label: "创业成长与品牌过程",
    keywords: ["创业", "主理人", "品牌", "团队", "工厂", "研发", "失败", "复盘", "成长", "产品开发"],
  },
};

const QUESTION = {
  speech_act: "question",
  logic_shape: "承接原帖一个具体点 -> 只问一个尚未回答的问题",
  tone: "好奇、平等、口语化，不在问句里夹带结论",
  character_range: { minimum: 18, maximum: 55 },
  sentence_range: { minimum: 1, maximum: 2 },
  requires: ["question_unanswered", "source_context_complete"],
};

export const DIRECTIONS = {
  acquisition_channel_question: {
    label: "问购买渠道/型号",
    parent_intent: "acquisition_question",
    topic_ids: ["purchase_service"],
    interaction_mode: "curiosity_question",
    ...QUESTION,
  },
  price_budget_question: {
    label: "问价格/预算",
    parent_intent: "acquisition_question",
    topic_ids: ["budget_value", "purchase_service"],
    interaction_mode: "curiosity_question",
    ...QUESTION,
  },
  product_identity_material_question: {
    label: "问木种/材料/结构",
    parent_intent: "utility_fit_question",
    topic_ids: ["material_craft"],
    interaction_mode: "curiosity_question",
    ...QUESTION,
  },
  size_clearance_question: {
    label: "问尺寸/净空",
    parent_intent: "utility_fit_question",
    topic_ids: ["dimensions_fit"],
    interaction_mode: "curiosity_question",
    ...QUESTION,
  },
  layout_circulation_question: {
    label: "问布局/动线",
    parent_intent: "utility_fit_question",
    topic_ids: ["layout_circulation", "dimensions_fit"],
    interaction_mode: "curiosity_question",
    ...QUESTION,
  },
  storage_usage_question: {
    label: "问收纳/使用方式",
    parent_intent: "utility_fit_question",
    topic_ids: ["storage_function"],
    interaction_mode: "curiosity_question",
    ...QUESTION,
  },
  comfort_ergonomics_question: {
    label: "问舒适度/人体工学",
    parent_intent: "utility_fit_question",
    topic_ids: ["comfort_ergonomics"],
    interaction_mode: "curiosity_question",
    ...QUESTION,
  },
  maintenance_durability_question: {
    label: "问清洁/耐久/维修",
    parent_intent: "utility_fit_question",
    topic_ids: ["maintenance_lifetime", "material_craft"],
    interaction_mode: "curiosity_question",
    ...QUESTION,
  },
  installation_delivery_question: {
    label: "问安装/运输/进场",
    parent_intent: "utility_fit_question",
    topic_ids: ["installation_logistics", "dimensions_fit"],
    interaction_mode: "curiosity_question",
    ...QUESTION,
  },
  color_light_fit_question: {
    label: "问配色/采光适配",
    parent_intent: "utility_fit_question",
    topic_ids: ["color_light_atmosphere"],
    interaction_mode: "curiosity_question",
    ...QUESTION,
  },
  household_constraint_question: {
    label: "问孩子/宠物/租房等限制",
    parent_intent: "utility_fit_question",
    topic_ids: ["household_constraints"],
    interaction_mode: "curiosity_question",
    ...QUESTION,
  },
  global_localization_question: {
    label: "问国外案例的本地适配",
    parent_intent: "utility_fit_question",
    topic_ids: ["global_localization"],
    interaction_mode: "curiosity_question",
    ...QUESTION,
  },
  request_more_evidence: {
    label: "求尺寸图/清单/后续/过程",
    parent_intent: "request_more",
    topic_ids: ["*"],
    interaction_mode: "curiosity_question",
    ...QUESTION,
  },
  detail_grounded_praise: {
    label: "夸一个具体细节",
    parent_intent: "grounded_praise",
    topic_ids: ["*"],
    interaction_mode: "support_only",
    speech_act: "praise",
    logic_shape: "指出一个可见细节 -> 说个人感受 -> 停住",
    tone: "真诚、具体、短，不追加建议",
    character_range: { minimum: 12, maximum: 38 },
    sentence_range: { minimum: 1, maximum: 2 },
    requires: ["visible_detail_grounded"],
  },
  atmosphere_grounded_praise: {
    label: "夸整体氛围/生活感",
    parent_intent: "grounded_praise",
    topic_ids: ["color_light_atmosphere", "layout_circulation", "household_constraints"],
    interaction_mode: "support_only",
    speech_act: "praise",
    logic_shape: "承接光线/配色/生活动作 -> 说主观感受 -> 停住",
    tone: "温暖、日常，避免高级感等编辑腔",
    character_range: { minimum: 12, maximum: 38 },
    sentence_range: { minimum: 1, maximum: 2 },
    requires: ["visible_detail_grounded"],
  },
  verified_same_situation: {
    label: "真实同场景自述",
    parent_intent: "self_reference_verified",
    topic_ids: ["*"],
    interaction_mode: "soft_observation",
    speech_act: "self_reference",
    logic_shape: "真实的自身条件 -> 与原帖一个点对照 -> 不外推",
    tone: "聊天式、有限经验，不装专家",
    character_range: { minimum: 25, maximum: 70 },
    sentence_range: { minimum: 1, maximum: 2 },
    requires: ["firsthand_verified"],
  },
  verified_self_display: {
    label: "真实晒自己的选择",
    parent_intent: "self_display_verified",
    topic_ids: ["*"],
    interaction_mode: "soft_observation",
    speech_act: "self_display",
    logic_shape: "真实拥有/做过的事实 -> 一个轻比较 -> 不贬低作者",
    tone: "轻微得意但友好，不抢楼、不踩一捧一",
    character_range: { minimum: 25, maximum: 70 },
    sentence_range: { minimum: 1, maximum: 2 },
    requires: ["firsthand_verified"],
  },
  invited_peer_tip: {
    label: "被邀请后给一个经验建议",
    parent_intent: "peer_tip_invited",
    topic_ids: ["*"],
    interaction_mode: "soft_observation",
    speech_act: "advice",
    logic_shape: "先承接作者条件 -> 只给一个可执行建议 -> 保留条件",
    tone: "同伴式、商量式，不使用命令和裁判口吻",
    character_range: { minimum: 25, maximum: 70 },
    sentence_range: { minimum: 1, maximum: 2 },
    requires: ["advice_invited"],
  },
  contextual_difference: {
    label: "提出有依据的条件差异",
    parent_intent: "contextual_disagreement",
    topic_ids: ["*"],
    interaction_mode: "soft_observation",
    speech_act: "qualified_difference",
    logic_shape: "先承认可见优点 -> 补一个不同家庭条件 -> 说明可能结果",
    tone: "克制、条件化，不反驳、不下总判决",
    character_range: { minimum: 25, maximum: 70 },
    sentence_range: { minimum: 1, maximum: 2 },
    requires: ["difference_basis_verified"],
  },
  light_social_response: {
    label: "轻松接话/中性互动",
    parent_intent: "neutral_social",
    topic_ids: ["*"],
    interaction_mode: "light_humor_or_neutral",
    speech_act: "social_response",
    logic_shape: "顺着原帖一个点自然接一句 -> 停住",
    tone: "轻松但不硬玩梗，不强夸、不强问",
    character_range: { minimum: 8, maximum: 32 },
    sentence_range: { minimum: 1, maximum: 2 },
    requires: ["source_context_complete"],
  },
};

const SHARED_ALLOWED = [
  "request_more_evidence",
  "detail_grounded_praise",
  "verified_same_situation",
  "verified_self_display",
  "invited_peer_tip",
  "contextual_difference",
  "light_social_response",
];

export const ROLE_DIRECTIONS = {
  stylist: {
    account_id: "mix_home_editor",
    voice_style_id: "warm_home_companion",
    voice_contract: {
      stance: "像一起看房间的普通家居爱好者",
      preferred_words: ["好看", "显亮", "看着舒服", "放进去", "家里"],
      forbidden_posture: ["设计师审判", "审美定论", "替作者总结方法论"],
      default_logic: "先说可见感受，再问一个生活化问题；一条只完成一个动作",
    },
    allowed_direction_ids: [
      "acquisition_channel_question", "price_budget_question", "size_clearance_question",
      "layout_circulation_question", "storage_usage_question", "color_light_fit_question",
      "household_constraint_question", "atmosphere_grounded_praise", ...SHARED_ALLOWED,
    ],
    direction_sequence: [
      "color_light_fit_question", "color_light_fit_question", "color_light_fit_question",
      "layout_circulation_question", "layout_circulation_question",
      "household_constraint_question", "household_constraint_question",
      "storage_usage_question", "atmosphere_grounded_praise", "atmosphere_grounded_praise",
      "atmosphere_grounded_praise", "detail_grounded_praise", "detail_grounded_praise",
      "acquisition_channel_question", "request_more_evidence", "verified_same_situation",
      "verified_self_display", "invited_peer_tip", "contextual_difference", "light_social_response",
    ],
  },
  evaluation_judgment: {
    account_id: "furniture_decision_editor",
    voice_style_id: "practical_purchase_peer",
    voice_contract: {
      stance: "像认真做功课但不替别人做决定的购买同伴",
      preferred_words: ["多少钱", "哪一款", "用多久", "好不好打理", "这个条件"],
      forbidden_posture: ["测评机构口吻", "大师结论", "无证据的质量判断"],
      default_logic: "先问自己真正影响购买的一个条件，必要时再给有限边界",
    },
    allowed_direction_ids: [
      "acquisition_channel_question", "price_budget_question", "product_identity_material_question",
      "size_clearance_question", "storage_usage_question", "comfort_ergonomics_question",
      "maintenance_durability_question", "installation_delivery_question",
      "household_constraint_question", ...SHARED_ALLOWED,
    ],
    direction_sequence: [
      "price_budget_question", "price_budget_question", "price_budget_question",
      "product_identity_material_question", "product_identity_material_question", "product_identity_material_question",
      "maintenance_durability_question", "maintenance_durability_question",
      "acquisition_channel_question", "acquisition_channel_question", "installation_delivery_question",
      "size_clearance_question", "storage_usage_question", "household_constraint_question",
      "request_more_evidence", "detail_grounded_praise", "invited_peer_tip", "invited_peer_tip",
      "contextual_difference", "light_social_response",
    ],
  },
  space_advisor: {
    account_id: "space_clinic",
    voice_style_id: "everyday_space_questioner",
    voice_contract: {
      stance: "像正在替自己家核对尺寸的普通住户",
      preferred_words: ["放得下吗", "会不会挡", "开门卡不卡", "还剩多少", "家里"],
      forbidden_posture: ["未量尺寸就诊断", "命令作者改造", "堆叠专业术语"],
      default_logic: "先落到一个真实动作，再问一个净尺寸或通行问题",
    },
    allowed_direction_ids: [
      "size_clearance_question", "layout_circulation_question", "storage_usage_question",
      "comfort_ergonomics_question", "color_light_fit_question", "household_constraint_question",
      "atmosphere_grounded_praise", ...SHARED_ALLOWED,
    ],
    direction_sequence: [
      "size_clearance_question", "size_clearance_question", "size_clearance_question",
      "size_clearance_question", "size_clearance_question", "layout_circulation_question",
      "layout_circulation_question", "layout_circulation_question", "layout_circulation_question",
      "household_constraint_question", "household_constraint_question",
      "storage_usage_question", "storage_usage_question", "comfort_ergonomics_question",
      "color_light_fit_question", "request_more_evidence", "detail_grounded_praise",
      "verified_same_situation", "invited_peer_tip", "light_social_response",
    ],
  },
  global_design_observer: {
    account_id: "global_furniture_editor",
    voice_style_id: "curious_localization_observer",
    voice_contract: {
      stance: "像对国外案例好奇、同时会想到中国家庭条件的读者",
      preferred_words: ["这个做法", "放到国内", "当地条件", "运输安装", "想看后续"],
      forbidden_posture: ["国外天然更高级", "国家群体概括", "无来源的设计史判断"],
      default_logic: "先扣住帖子真正讨论的主题，再说一个具体感受或观点；只有真想知道、作者也能回答时才问",
    },
    allowed_direction_ids: [
      "acquisition_channel_question", "price_budget_question", "product_identity_material_question",
      "maintenance_durability_question", "installation_delivery_question", "color_light_fit_question",
      "household_constraint_question", "global_localization_question", "atmosphere_grounded_praise",
      ...SHARED_ALLOWED,
    ],
    direction_sequence: [
      "global_localization_question", "global_localization_question", "global_localization_question",
      "global_localization_question", "product_identity_material_question", "product_identity_material_question",
      "product_identity_material_question", "maintenance_durability_question", "maintenance_durability_question",
      "installation_delivery_question", "installation_delivery_question", "color_light_fit_question",
      "acquisition_channel_question", "detail_grounded_praise", "detail_grounded_praise",
      "atmosphere_grounded_praise", "request_more_evidence", "contextual_difference",
      "invited_peer_tip", "light_social_response",
    ],
  },
};

const OFFICIAL_SHARED = Object.keys(DIRECTIONS);
ROLE_DIRECTIONS.official_explanation = {
  account_id: "panse_official",
  voice_style_id: "concise_disclosed_brand_reply",
  voice_contract: {
    stance: "明确身份、直接回答、只说可核实事实",
    preferred_words: ["当前版本", "以页面标注为准", "这条补充一下"],
    forbidden_posture: ["伪装消费者", "暗中导流", "回避利益关系"],
    default_logic: "先披露必要关系，再回答一个问题，不扩成广告",
  },
  allowed_direction_ids: OFFICIAL_SHARED,
  direction_sequence: OFFICIAL_SHARED,
};
ROLE_DIRECTIONS.principal_sincere_signed = {
  ...ROLE_DIRECTIONS.official_explanation,
  voice_style_id: "verified_founder_reply",
  voice_contract: {
    stance: "仅在真实参与得到验证时，以负责人身份说明取舍",
    preferred_words: ["当时我们", "这个版本", "这次取舍"],
    forbidden_posture: ["虚构创业故事", "借负责人身份压人", "把个案说成普遍真理"],
    default_logic: "说明一个真实节点或取舍，再承认边界",
  },
};

export function publicPolicyShape() {
  return {
    topics: TOPICS,
    directions: DIRECTIONS,
    roles: ROLE_DIRECTIONS,
  };
}
