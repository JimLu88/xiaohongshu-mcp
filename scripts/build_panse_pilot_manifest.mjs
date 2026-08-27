import fs from "node:fs";
import path from "node:path";

const researchDir = path.resolve("research", "panse_pilot_5");

const sampleDefinitions = [
  {
    sample_no: 1,
    note_file: "sample_01_苏安生home_宅家过夏天.json",
    profile_file: "profile_01_苏安生home.json",
    role: "合作博主｜真实居住者",
    direction: "家居日常 + 季节情绪 + 实用养护",
    selection_reason: "观察合作博主近期由装修干货向居住日常延展的镜头语言。",
    visual_pattern:
      "固定在自家窗边、台面和边几附近，用近景动作、物件特写和短字幕推进。",
    panse_fit:
      "适合转成“家具进入四季日常”的生活片，但畔色产品结构与朝向必须保持原样。",
  },
  {
    sample_no: 2,
    note_file: "sample_02_蓝山Orz_小户型多功能房.json",
    profile_file: "profile_02_蓝山Orz.json",
    role: "合作博主｜真实居住者",
    direction: "小户型痛点 + 空间方案 + 家具植入",
    selection_reason: "验证功能型长文、真实空间和商品植入如何组合。",
    visual_pattern:
      "同一书房内反复使用房间全景、家具正面、柜内收纳和人物使用四类固定机位。",
    panse_fit:
      "很适合畔色做“一个家具解决一个生活问题”，要用真实尺寸和功能证据支撑。",
  },
  {
    sample_no: 3,
    note_file: "sample_03_乙舟官方_餐边柜评审.json",
    profile_file: "profile_03_乙舟.json",
    role: "竞品官方｜主理人/品牌账号",
    direction: "新品过程公开 + 用户共创评审",
    selection_reason: "观察竞品官方如何把未定稿产品变成评论区参与话题。",
    visual_pattern:
      "产品正面全貌作为主镜头，辅以开合、抽屉、轨道、腿部等手部功能特写。",
    panse_fit:
      "适合畔色的新品评审、颜色投票、功能取舍和命名征集，比单纯上新更有参与感。",
  },
  {
    sample_no: 4,
    note_file: "sample_04_乙舟素人_电视支架收货.json",
    profile_file: "profile_04_melody.json",
    role: "竞品相关素人｜真实 UGC",
    direction: "收货问题 + 售后过程 + 安装证明 + 最终效果",
    selection_reason: "观察小体量账号如何靠完整问题链条获得高收藏和评论。",
    visual_pattern:
      "纪录片式顺序：尺寸/运输证据、入户、拆装、结构细节、使用场景和最终效果。",
    panse_fit:
      "适合作为售后透明度与安装教程的参考；当前样本不能证明是品牌付费或协同投放。",
  },
  {
    sample_no: 5,
    note_file: "sample_05_NOKITSCH_瑞典设计师自宅.json",
    profile_file: "profile_05_NOKITSCH.json",
    role: "设计内容作者｜建筑背景",
    direction: "国外设计档案 + 空间解读 + 家具史",
    selection_reason: "验证高收藏、低评论的审美资料型内容。",
    visual_pattern:
      "以建筑摄影为主，按工作区、客厅、家具组合、动线和材料细节组成图组。",
    panse_fit:
      "适合建立畔色的设计知识栏目，但必须做原创研究与解读，不能把海外图片当作产品图。",
  },
];

function readJson(filename) {
  return JSON.parse(fs.readFileSync(path.join(researchDir, filename), "utf8"));
}

function extractTopics(text = "") {
  return [...text.matchAll(/#([^#\n]+?)\[话题\]#/g)].map((match) =>
    match[1].trim(),
  );
}

function interactionMap(interactions = []) {
  return Object.fromEntries(
    interactions.map((item) => [item.type, Number(item.count || 0)]),
  );
}

function countAuthorReplies(comments, authorId) {
  const walk = (items = []) =>
    items.reduce((sum, item) => {
      const isAuthor =
        item?.userInfo?.userId === authorId ||
        (item?.showTags ?? []).includes("is_author");
      return sum + Number(isAuthor) + walk(item?.subComments ?? []);
    }, 0);
  return walk(comments?.list ?? []);
}

const samples = sampleDefinitions.map((definition) => {
  const notePayload = readJson(definition.note_file);
  const profilePayload = readJson(definition.profile_file);
  const detail = notePayload?.data?.data ?? {};
  const note = detail.note ?? {};
  const profile = profilePayload?.data?.data ?? {};
  const accountMetrics = interactionMap(profile.interactions);
  const publishAt = new Date(note.time).toISOString();

  return {
    ...definition,
    feed_id: note.noteId,
    xsec_token: note.xsecToken,
    source_url: `https://www.xiaohongshu.com/explore/${note.noteId}?xsec_token=${encodeURIComponent(note.xsecToken)}&xsec_source=pc_search`,
    collected_at: "2026-07-28T15:43:00+08:00",
    note: {
      title: note.title,
      text: note.desc,
      topics: extractTopics(note.desc),
      type: note.type,
      publish_at: publishAt,
      ip_location: note.ipLocation,
      metrics: {
        likes: Number(note.interactInfo?.likedCount || 0),
        comments: Number(note.interactInfo?.commentCount || 0),
        collects: Number(note.interactInfo?.collectedCount || 0),
      },
      media: {
        image_count: note.imageList?.length ?? 0,
        video_duration_seconds: Number(note.video?.capa?.duration || 0),
        local_dir: path
          .join(
            "media",
            definition.note_file.replace(/\.json$/i, ""),
          )
          .replaceAll("\\", "/"),
      },
      comments_loaded: detail.comments?.list?.length ?? 0,
      author_replies_loaded: countAuthorReplies(
        detail.comments,
        note.user?.userId,
      ),
    },
    author: {
      user_id: note.user?.userId,
      nickname: profile.userBasicInfo?.nickname ?? note.user?.nickname,
      red_id: profile.userBasicInfo?.redId,
      bio: profile.userBasicInfo?.desc,
      ip_location: profile.userBasicInfo?.ipLocation,
      following: accountMetrics.follows ?? 0,
      followers: accountMetrics.fans ?? 0,
      total_likes_and_collects: accountMetrics.interaction ?? 0,
      profile_feeds_loaded: profile.feeds?.length ?? 0,
    },
  };
});

const manifest = {
  schema_version: "0.1",
  generated_at: new Date().toISOString(),
  project: "畔色小红书账号方向研究",
  collector: {
    repository: "https://github.com/xpzouying/xiaohongshu-mcp",
    source_version: "v2.2.5",
    runtime_version: "dev",
    commit: "085da32eb93e28f7b981c075b2c306198c68ecf4",
    local_patch:
      "Windows build sets go-rod launcher Leakless(false) to avoid Defender error 225; no collection logic changed.",
    mode: "read-only",
    mutations_performed: [],
  },
  scope: {
    sample_count: samples.length,
    account_count: new Set(samples.map((sample) => sample.author.user_id)).size,
    caveats: [
      "首批 5 篇仅用于验证采集字段与方向差异，不能代表整个赛道。",
      "搜索排序与互动数据是 2026-07-28 的页面快照，后续会变化。",
      "未看到明确商业合作标识时，不把素人内容判定为付费或品牌协同。",
      "互动数据没有曝光量，不能直接计算或比较转化率。",
    ],
  },
  samples,
};

const outputPath = path.join(researchDir, "pilot_manifest.json");
fs.writeFileSync(outputPath, `${JSON.stringify(manifest, null, 2)}\n`, "utf8");
console.log(
  JSON.stringify(
    {
      output: outputPath,
      samples: samples.length,
      topics: samples.reduce(
        (sum, sample) => sum + sample.note.topics.length,
        0,
      ),
    },
    null,
    2,
  ),
);
