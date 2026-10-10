# AGENTS.md — 畔色小红书项目执行约束

## 当前合作方式覆盖（2026-09-05）

用户已要求推进“同账号 4 条评论全部准备好，只通知一次、本人集中逐页发送”。适配器和边界见 `research/panse_multi_direction/cooperation_20260905/04-四页集中交接使用说明.md`；初版只接 slots 2–5 普通评论，实网仍待 01 验证。`human_final_batch` 小批次不强制旧超短评论比例，逐条文风、事实、字数、身份和去重门禁不变。仅已就绪且正在等用户操作的 4 页允许最多 10 分钟的有限保留，超时暂停并关闭本批标签，01 后续关闭专用浏览器核对退出；不能恢复旧配额、自动提交或无限浏览。

按用户最新合作要求，当前自动化只做研究、内容生成审核、制作和经过验证的提交前准备。评论、回复和文章的最终提交由用户本人执行；“零风险自动评论”尚无证据，因此下文旧的自动提交义务、旧评论配额或旧批准不能启动发送。本段不引入逐步骤批准；登录/身份/平台风险现场门继续保留。全计划见 `research/panse_multi_direction/cooperation_20260905/02-最终合作实施计划.md`，配置摘要见同目录 `cooperation_policy.json`。这份配置是任务执行政策，不声称已阻断所有底层 MCP 写能力；预填专用接口仍待验证。

文章专用入口是 `scripts/run_xhs_article_style_lab.py`，使用当前文章合同并真实调用 Tachikoma Writing Style Lab 的 plan/draft/semantic_review，固定 gpt-5.6-sol、无 fallback；默认只准备，显式 `--generate` 才生成，但任何模式均无浏览器或发布能力。01 可在当前用户目标下执行离线文章生成；02 只维护和做本地测试，不代做账号运营。8 月旧库存仍需真实生成证据，不能直接升级为合格稿。

本文件适用于整个仓库。开始任何任务前，先读本文件、根目录 `current-state.md`，再读与任务直接相关的配置和当日回执。旧的 `HANDOFF_XHS_2026-08-01.md` 是历史快照，发生冲突时以本文件、`current-state.md` 和最新结构化回执为准。

## 0. Codex 统一项目入口

- Codex 中所有小红书任务统一从 `D:\AI\小红书运营中心` 项目建立。
- 该入口的 `项目文件` 是指向本仓库的目录连接；本仓库仍是唯一事实和代码源，
  不得复制成第二套。
- 长期任务名称固定为：`01｜小红书日常运营`、
  `02｜小红书审核与程序维护`。其他旧任务只作历史证据，不再作为入口。
- 两个任务共享本仓库状态但职责不混用：日常任务按当前目标直接执行账号运营且不改程序；维护任务收到审核请求时只读，收到修复、修改或实现请求后改代码或策略，但不承担日常运营。
- 01 遇到有证据、可复现且影响当前工作的项目内程序、适配器、连接层或浏览器
  MCP 控制故障时，必须先保存停止证据与安全断点，再自动转交固定 02 进入
  项目可控范围内的修复模式，不再为是否转交单独等待确认。普通内容质量、平台拒绝、
  账号风险提示或用户文案偏好不触发；项目外、安全合同、凭证权限、删除、全局
  Codex/Browser 插件或难恢复修改仍须用户当前明确授权。
- 02 修复完成并写入结构化回执、`current-state.md` 和唯一安全恢复步骤后，必须自动
  返回原 01；01 无需等待用户重复说“继续”，重新核验日期、账号、风险、浏览器现场
  和风险后，从安全断点继续真实平台终验或原先范围内工作。若结果为
  `blocked_external_runtime`、`failed`、`degraded` 或未完成，不得自动续跑原任务。
  自动路由不传递平台业务权限，也不自动转交 99 或塔奇克马控制面。
- 02 位于后台时只能查日志、改程序、核对工具可见性和跑本地测试，不得借维护执行小红书
  业务。01 的标准浏览器表面为：公开/本地/无登录调试使用 `playwright_debug`；需要保留
  小红书登录状态时按账号使用 `playwright_browser_slot_1` 至 `playwright_browser_slot_5` 及其
  各自独立的 D 盘专用资料。原生 Browser/IAB 的
  `affected-origin` 是已知产品层故障；遇到它直接切换已登记 MCP，不再为同一错误反复转单、
  自愈、修改安装包或重启后台。旧任务看不到新 MCP 时只重新打开任务加载工具。
- 02 的修复回归是技术验证，不是平台结果；凭证披露、权限扩大、材料删除、付款和难恢复变更仍需当前精确授权，普通外部发布不再等待独立终审。
- 项目入口说明见 `D:\AI\小红书运营中心\00-从这里开始.md`。

## 1. 权威状态与证据顺序

按以下优先级判断事实：

1. 平台当前可见状态、明确安全提示和登录身份；
2. `research/panse_multi_direction/daily_runs/YYYY-MM-DD/` 中的发布回执、阅读回执和停止回执；
3. `research/panse_multi_direction/account_role_binding_v1.json` 与当前策略文件；
4. `current-state.md`；
5. 规划、草稿、旧交接文档和对话记忆。

必须区分：计划、调用、草稿、批准、发送、公开可见。点击或按回车不代表成功；只有评论数准确增加 1、精确文本在当前账号上下文可见、账号身份匹配、编辑器清空四项同时成立，才记为公开评论。

## 2. 现场保护

- 仓库当前有大量用户改动和未跟踪资产；不得使用 `git clean`、`git reset --hard`、覆盖式检出或批量删除。
- 只修改当前任务需要的文件。不要顺手格式化或升级依赖。
- 不保存密码、Cookie、令牌、验证码、完整手机号或会话数据。登录二维码图片是短时真人交互材料：
  新鲜且与目标 slot 脱敏账号上下文完全匹配时，可以临时截图到本项目运行目录并直接显示在当前
  `01｜小红书日常运营` 对话里；确认、过期或任务结束后不得复用，不得跨任务或向无关位置转发，
  也不得读取、保存或输出二维码解码后的字符串。
- 五个 slot 固定使用 `D:\AI\tachikoma\.runtime\playwright-browser-profiles\slot-N`，不得共用旧的
  单资料目录或跨 slot 复制登录资料。每次使用前只做有限身份、登录和风险探测：登录有效且目标
  profile 精确匹配时直接复用，不注销、不刷新二维码；掉线才进入该 slot 二维码真人门；身份不符
  必须先取得用户切号确认；风控或不确定结果立即停止。没有平台明确登录到期头时不得推算剩余时长。
- 账号信息只使用项目里的脱敏手机号和公开 profile id。

## 3. 外部操作边界

- 浏览器按当前可用表面选择 IAB、Chrome 或项目按需浏览器；不得读取或复制无关的用户浏览资料、Cookie 或凭据。
- 优先使用浏览器内部控制；只有用户当前明确要求桌面控制时才使用 Computer Use。专用浏览器进程用完关闭，不为普通任务常驻。
- 平台深读必须使用 `xhs_warmup_runner.py` 的许可和四阶段进展检查点。连续 10 分钟无真实进展、单篇超过
  30 分钟或日期变化时，许可立即失效并写停止回执；01 必须调用 `browser_close`、确认专用进程为 0 并结束
  当前回合。当天恢复前重新核验身份、登录和风险，旧许可不得复用，旧日期不得恢复。
- 任务重名/归档处理、程序修复等待和真实平台浏览不得塞进同一个长回合。修复结果返回后，01 先结束维护
  续接回合，再用新回合重新核验日期、账号和风险后开始浏览，避免任务管理或维修把浏览器会话长时间挂起。
- 登录或切号前必须向用户说明：slot、脱敏手机号、账号名、设备、用途。扫码、验证码和手机确认由用户完成。
- 出现验证码、安全验证、频率提示、账号异常、登录异常、连续不可见/被删或作者反感时立即停止；不得刷新重试、换浏览器或换号绕过。
- 当前目标可直接发布正文、点赞、收藏、私信和修改资料；改名、取关等会改变长期账号状态的动作由模型结合目标与可恢复性判断。
- slot 2–5 的关注仅按 `follow_warmup_policy_v1.json` 执行；slot 1 不关注。关注成功必须读回按钮从“关注”变为“已关注”。
- 评论操作不设默认时间禁令；只有用户在当前任务中明确提出的时间限制才生效，不得从历史交接或旧回执自行推导新的发送时段限制。

## 4. 评论执行

- 当前用户目标或已批准自动任务允许评论时，模型选择合适账号、目标和文本并直接发送，无需逐条展示或再次批准。
- 当天计划的评论目标大于 0 时，真实 Style Lab 生成并通过字数、事实、身份、去重、风险和完整批次门禁后，日常任务必须继续逐条提交并公开回读，不得停在草稿、待审队列或再次等待用户批准。只有登录/验证码/切号/平台风控、平台拒绝、没有任何能通过内容门禁的安全文本、程序故障或浏览器/平台不可用，才可保存证据后停止；不得为完成数量而降低门禁、伪造事实或把未公开文本计为成功。
- Style Lab 的 `publish_allowed=false` 和 `human_review_required=true` 只约束生成器本身不直接发布，并要求语义与确定性审核；它们不构成日常任务的第二次用户批准门。02 仍只维护程序，不执行平台评论。
- 文本变化、必要重试和去重由模型根据当前页面和既有回执判断。
- 发送方法固定为 `xhs-comment-submit.enter-v1`：确认精确文本不存在、编辑器为空、无风险信号后，输入目标文本，只按一次回车，不点发送按钮。
- 结果不明确时先读回当前页面，由模型判断停止或有界重试，不能把未知状态当作成功。

## 5. 五账号边界

唯一配置源：`research/panse_multi_direction/account_role_binding_v1.json`。

- slot 1 `panse_official`：畔色木作官方号。只主动参与真实空间、材料工艺、维护、AI/建模、创作者家具内容和畔色直接问题；不得伪装消费者。涉及畔色推荐、比较、产品或服务解释时明确官方身份。
- slot 2 `mix_home_editor`：空间生活提案编辑。关注小户型、采光、配色、家具组合和生活动作；不得冒充屋主，合成图必须披露。
- slot 3 `furniture_decision_editor`：理性家具决策编辑。讨论材料、结构、尺寸、购买成本和条件边界；不得冒充第三方检测机构。
- slot 4 `space_clinic`：户型、尺寸与动线顾问。缺少关键净尺寸时不下确定结论；承重、燃气、消防、电气问题不凭图判断。
- slot 5 `global_furniture_editor`：全球家具工艺与居住偏好观察。必须限定国家、市场、品牌、标准、年份或案例；不得把国外等同于高级。

同一目标帖只允许一个受控账号参与。涉及畔色推荐、比较或产品解释时，slot 2–5 必须当条披露品牌运营关系。

## 6. 阅读与去重

- 按日期和 slot 去重；当天已完成动作不得重复，未用额度不跨日。
- 新对话或新日期开始时，文档中的“当前账号”和旧批批准都只视为历史快照；必须重新核验侧栏“我”。跨日期先建立新日计划，旧日额度不得顺延。
- 排除全部历史发布回执中的 note_id；五账号之间不得复用同一目标帖或近似评论。
- 必须读完整标题与正文；候选评论还要读当前可见评论。
- 多图不超过 6 张尽量看完；超过 6 张至少看 6 张，并看完与评论落点有关的图片。
- 下列 `xhs_in_app_*` 合同只保留为原生 Browser/IAB 的历史兼容路径，不是当前
  `playwright_browser` 的前置条件。原生通道若返回已知 `affected-origin`，不得继续运行
  这些合同或围绕同一错误新增修复循环。
- Codex 内置浏览器中的小红书媒体轮播统一调用
  `scripts/xhs_in_app_carousel.mjs` 导出的 `advanceXhsCarousel(tab)`，每次只推进
  1 项。调用前必须传入并通过账号身份、目标身份和无风险信号三项前置核验；只有
  返回 `status=advanced` 且前后状态哈希不同才记为已翻页；调用超时
  后必须先读回状态，确认未变化才允许唯一一次 `ArrowRight` 语义回退。禁止坐标
  点击、盲目重复或把调用返回当成媒体已切换；返回 `blocked` 时保存停止证据。
- 建立搜索工作页统一调用 `scripts/xhs_in_app_search_navigation.mjs`：先用
  `acquireXhsSearchWorkspace(browser)` 复用当前内置浏览器绑定；空标签列表只
  表示标签已清理，不等于浏览器绑定失效。合同 `panse-xhs-iab-search-navigation.v13`
  的历史回执继续用于解释已有事故，但新的真实 Browser 验收必须先满足第 0 节前台门；
  stale/missing/closed tab 或控制内核重置后不得复用旧对象和旧 id，而应保留 IAB 选择，
  从同一 binding 重新获取或创建当前任务的新 tab。合同其余身份、风险和动作门禁不变；
  其 v13 实现适配 Browser `26.820.80927` 的 caller-visible 结果边界：所有工作区阶段每次最多
  只发 1 个文档化 Browser RPC，普通本地 timer 不再被写成能抢占控制 RPC 的保证。
  第一段 `acquireXhsSearchWorkspace(iab)` 永远只调用一次 `browser.tabs.list()`：优先
  返回唯一 `/`、`/explore` 或搜索页候选；否则返回唯一精确 `about:blank` 候选，或
  返回需要继续核对可见用户标签的结构化状态。第一段不得调用 `openTabs`、`claimTab`、
  `tabs.new`、`goto` 或 DOM。无关的 `about:blank` 标签不能让程序忽略唯一
  `/explore` 标签，也不能触发重复新建。
  空工作区后续也必须显式分段：`inspectXhsVisibleWorkspaceCandidates` 只列出可见标签；
  有且仅有 1 个精确小红书候选时，`claimXhsVisibleWorkspaceCandidate` 只接管该候选；
  已有唯一空白任务标签时，`rebindXhsBlankWorkspaceCandidate` 只重绑该 id；只有任务
  与可见工作区都已证明不存在、且传入当前结构化缺席证明时，
  `createXhsSearchWorkspaceBlankCandidate` 才可新建
  1 个空白任务标签；`navigateXhsBlankWorkspaceCandidate` 只对该精确空白候选导航
  1 次；随后 `inspectXhsWorkspaceAfterNavigation` 只列出任务标签并核对同一 id 的实际
  URL，禁止从 `goto` 返回或计划 URL 推断成功。`goto` 无 caller-visible 结果时先停止
  当前调用并保存“精确 id、只调用 1 次、结果缺失、导航尝试 1、重试 0”的有限证明；
  控制恢复后只允许调用一次
  `recoverXhsWorkspaceAfterIndeterminateNavigation(browser, { navigationAttempt })`。该函数
  必须先核对上述证明，再只调用一次 `browser.tabs.list()`，只接受同一 id 当前实际为
  小红书 URL；仍是 `about:blank`、候选不精确或清单无结果都停止，禁止第二次导航、
  第二次同 id 恢复、新建、DOM 或搜索动作。若该唯一恢复已明确返回
  `navigated_workspace_candidate_not_rebindable` 且 `exact_candidate_matches=0`，v13 允许
  用该完整有限结果作为前置证明，只调用一次
  `recoverXhsReleasedWorkspaceAfterTaskCandidateLoss(browser, { lossProof })`。它只读取一次
  `browser.user.openTabs()`；0 个、2 个以上或清单无结果都停止，只有 1 个精确小红书
  首页/搜索页候选才返回完整当前 claim handle，且不得声称它与丢失任务 id 连续。
  随后 `claimXhsReleasedWorkspaceCandidate(browser, { discovery })` 只允许接管这一个完整
  候选 1 次，并把 Browser 返回的新任务 id 作为唯一当前 id；旧 id 永不复用。接管后
  仍须用一次新鲜可见 DOM 重新证明当前账号、登录、风险和唯一搜索目标，不能继承旧
  页面或身份结论。任一阶段无结果同样停在该已知 RPC，不重放、不任意接管、不推断成功。
  已有可复用工作区仍分三次只读控制调用：`acquireXhsSearchWorkspace(iab)` 只列出并
  返回唯一精确候选；`rebindXhsSearchWorkspaceCandidate(iab, { candidate })` 只重绑该 id；随后
  `verifyXhsSearchWorkspaceCandidate(tab, { candidate, requiredProfileId })` 只执行一次文档化
  `tab.dom_cua.get_visible_dom()` 只读 RPC，不再调用已在真实终验中无结果的
  `tab.playwright.evaluate`，也不得为同页身份核验追加第二次 DOM RPC。第三段必须从
  同一份新鲜可见 DOM 同时证明：与前两段相同的精确候选、唯一带 `node_id` 的搜索
  交互目标、侧栏“我”唯一绑定当前任务传入的精确公开 profile、无登录提示且无风险
  信号；只返回有限摘要，不落盘完整 DOM。缺少当前 profile 参数、快照/形态不足、
  身份不符、目标不唯一、登录提示或任何风险词都 fail closed。三段之间不得新建、
  导航或任意选择，只有最终返回 `workspace_ready` 才继续后续步骤，无需再做独立身份
  DOM 读取。
  首页、账号身份和无风险状态核验后，再调用
  `openXhsSearchResults(tab, { browser, ... })`，只在唯一可操作搜索框填入查询并按
  1 次回车。搜索框必须位于视口内、未被其他表面遮挡、未禁用/只读、未处于
  `aria-hidden`/`inert` 祖先下且允许指针交互；2 个真正可操作目标仍 fail closed。
  程序优先使用探针证明为全页唯一且格式安全的精确 ID，并再次核对数量和属性指纹；
  没有这种 ID 时才允许回退到探针已证明的唯一可操作 DOM index。禁止 `.first()`、任意选择、直接拼
  搜索 URL、换浏览器、坐标操作或盲目重复。提交后控制重置
  时，程序同样先对当前任务标签或唯一可见的释放标签执行零动作
  `recoverXhsSearchPage` 验真，不做第二次提交；两处都找不到、候选不唯一或明确
  断连才返回 `blocked_external_runtime` 并停止。未确认不得进入详情或计入深读。
- 从搜索结果进入新候选详情统一调用
  `scripts/xhs_in_app_detail_navigation.mjs` 导出的
  `openXhsDetailFromSearch(tab, { browser, ... })`，合同为
  `panse-xhs-iab-detail-navigation.v2`：只能复用已核验的同一搜索标签，对精确
  `note_id` 与标题唯一匹配的可见链接执行一次语义点击；禁止为详情新建标签、
  直接 `goto`、返回导航、坐标点击或盲目重试。点击超时后只接受只读探针确认的
  目标详情；若控制会话不可用，先重新绑定现有任务标签，再用
  `recoverXhsDetailTarget` 精确查找并最多接管 1 个仍可见的目标详情标签，零动作
  调用 `verifyXhsDetailTarget`。不得第二次点击；找不到、不唯一或未确认则保存停止
  证据且不得计入深读。
- 阅读以理解内容为目的，不做无意义滚动或固定伪装轨迹。
- 长视频无法稳定验证观看进度时不得计入合格深读。

## 7. 写作与语言规则

- Tachikoma Style Lab 的 plan、draft、semantic_review 固定使用 `gpt-5.6-sol`，禁止 fallback。
- slots 2–5 生成前必须按 `xhs_comment_production_taxonomy_v1.json` 声明一个允许的评论类别、真实发言动机和单一主要言语动作；总结原帖不算言语动作，C15–C17 不得进入生产草稿。
- 实际生成入口固定为 `scripts/run_xhs_style_lab.py`，由 `base.xiaohongshu_style.generate_style_content` 真实执行 plan、draft、确定性门禁和 semantic_review。`prepare_xhs_style_request.py` 的 `text_generated=false` 编译回执不算生成证据；日期脚本硬编码草稿、模型名或阶段 pass 不得进入人工审核队列。
- 使用已批准 Style Card、完整前置 brief、事实合同、身份和利益关系边界；缺一项即 fail closed。
- 不虚构购买、入住、装修、检测、维修或长期使用经历。
- 不复述标题、正文或图里显而易见的内容来凑句子。
- 不用老师、评委、验收者口吻；不每条都提问，问题必须是作者容易回答且评论区尚未回答的真实问题。
- 优先短、直接、口语：少用“思路、那组、尤其、参考价值、落地、下单”等整理稿词；购买动作优先说“买”。用户已明确否决“这种分享很实在”，所有账号后续评论禁止再生成这句或把它作为收尾套话。
- 数字优先使用阿拉伯数字，例如“6把”，不是“六把”。
- 普通内容号先具体共鸣或直接夸赞；官方号必须先给专业依据，再给判断、条件化建议或短夸。
- 一句话完成任务时不补空洞第二句。

## 8. 每日养号流程

1. 读取本文件、`current-state.md`、账号绑定、评论/关注策略、最近每日状态与发布回执。
2. 用 `scripts/xhs_warmup_runner.py plan --date YYYY-MM-DD` 建立或核对当天计划；计划漂移要记录，不能覆盖证据。
3. 报告要登录的 slot、脱敏手机号、昵称、设备和用途；用户完成认证。
4. 验证侧栏“我”的 profile id，不用正在查看的他人主页判断登录身份。
5. 依角色主题池阅读，逐条写回阅读证据；关注必须满足两篇相关内容和按钮状态读回。
6. 生成评论前运行 Style Lab 前置校验和语义复核，保存可追溯的发送队列；生成器本身不得发布。
7. 依据当前目标直接确定草稿和目标账号。
8. 通过全部门禁后逐条发送并验证；每个 slot 单独写发布回执，不得仅因缺少第二次用户批准而停止。
9. 只有五个 slot 都完成，或命中第 4 节列明的真实阻塞并保存证据时，才结束当天总任务。

## 9. 程序架构与入口

- 采集服务：Go 项目，默认 `127.0.0.1:18060`，可由 `XHS_MCP_PORT` 覆盖。
- 稳定身份：`GET /healthz`；合同：`GET /tachikoma/v1/contract`。
- 只读生产接口受 `XHS_MCP_PRODUCTION_READ_ENABLED` 保护；外部副作用受 `XHS_MCP_PRODUCTION_EXECUTION_ENABLED`、服务身份、任务/批准标识和幂等键共同保护。
- 研究与策略：`research/panse_multi_direction/`。
- 日常执行与证据：`research/panse_multi_direction/daily_runs/`。
- 评论、文章、策略、验证脚本：`scripts/`。
- 素材与内容状态台账：`scripts/panse_content_registry.py` 与 `research/panse_multi_direction/operations/panse_content_registry.sqlite3`。

连接层开关只提供能力，当前目标决定用途。不得绕过账号风控、验证码或平台访问控制；普通生产读写不再等待额外人工审批。

## 10. 当前任务入口

最新断点、已发布评论、未完成事项和启动顺序见根目录 `current-state.md`。归档总览见 `docs/panse-xhs-project-archive-2026-08-13.md`。
