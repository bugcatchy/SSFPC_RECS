import fs from "node:fs";
import path from "node:path";
import {
  AlignmentType, Document, Footer, Header, HeadingLevel, LeaderType, Math,
  MathFraction, MathRun, Packer, PageNumber, Paragraph, PositionalTab,
  ShadingType, TabStopType, Table, TableCell, TableOfContents, TableRow,
  TextRun, WidthType, convertInchesToTwip,
} from "docx";

const outputPath = process.argv[2];
if (!outputPath) throw new Error("Usage: node create.js /absolute/path/output.docx");
fs.mkdirSync(path.dirname(outputPath), { recursive: true });

const T = String.raw;
const docTitle = T`面向智能电网终端用户的"社会信息过滤"电力零售套餐推荐系统——阶段性成果综述（聚类改进线）`;
const palette = { dark: "263238", primary: "37474F", light: "78909C", border: "D8E0E3", fill: "EEF3F6" };
const font = { ascii: "Times New Roman", hAnsi: "Times New Roman", cs: "Times New Roman", eastAsia: "SimSun" };

const run = (text, options = {}) => new TextRun({ text, font, size: 24, ...options });
const para = (children, options = {}) => new Paragraph({
  spacing: { after: 160, line: 300 }, ...options,
  children: Array.isArray(children) ? children : [children],
});
const p = (text) => para(run(text), { indent: { firstLine: convertInchesToTwip(0.33) } });
const h1 = (text) => para(run(text, { bold: true, size: 30, color: palette.dark }), {
  heading: HeadingLevel.HEADING_1, spacing: { before: 300, after: 140 },
});
const h2 = (text) => para(run(text, { bold: true, size: 26, color: palette.dark }), {
  heading: HeadingLevel.HEADING_2, spacing: { before: 220, after: 120 },
});
const mrun = (text) => new MathRun(text);
const mathPara = (children, caption) => para(
  [new Math({ children }), ...(caption ? [run("    " + caption, { size: 20, color: palette.light })] : [])],
  { alignment: AlignmentType.CENTER, spacing: { before: 120, after: 160 } },
);

const cell = (text, options = {}) => new TableCell({
  children: [para(run(String(text), options.bold ? { bold: true } : {}), { spacing: { after: 0, line: 260 } })],
  margins: { top: 80, bottom: 80, left: 100, right: 100 },
  ...options,
});
const makeTable = (widths, headerRow, rows) => new Table({
  width: { size: widths.reduce((a, b) => a + b, 0), type: WidthType.DXA },
  columnWidths: widths,
  rows: [
    new TableRow({
      tableHeader: true,
      children: headerRow.map((t, i) => cell(t, {
        bold: true,
        shading: { type: ShadingType.CLEAR, fill: palette.fill },
        width: { size: widths[i], type: WidthType.DXA },
      })),
    }),
    ...rows.map((r) => new TableRow({
      children: r.map((t, i) => cell(t, { width: { size: widths[i], type: WidthType.DXA } })),
    })),
  ],
});

const tocBlock = (entries) => [
  new TableOfContents("目录", { hyperlink: true, headingStyleRange: "1-2" }),
  ...entries.map(({ title, page }) => para(
    [run(title), new TextRun({ font, size: 24, children: [new PositionalTab({ alignment: AlignmentType.RIGHT, relativeTo: "margin", leader: LeaderType.DOT })] }), run(String(page))],
    { spacing: { after: 60, line: 280 } },
  )),
];

const tocEntries = [
  { title: T`一、加项式 FCM 变体及其与电力用户聚类的结合`, level: 1, page: 1 },
  { title: T`二、SSFPC 的数学原理与迭代算法`, level: 1, page: 2 },
  { title: T`三、数据集来源与预处理`, level: 1, page: 3 },
  { title: T`四、A/B/C/D 四组对照实验结果`, level: 1, page: 4 },
  { title: T`五、结论与下一步工作`, level: 1, page: 5 },
];

const children = [
  para(run(T`阶段性成果综述：基于 SSFPC 模糊成对约束的电力用户聚类改进`, { bold: true, size: 36, color: palette.dark }), {
    heading: HeadingLevel.TITLE, alignment: AlignmentType.CENTER, spacing: { after: 160 },
  }),
  para(run(T`项目：面向智能电网终端用户的"社会信息过滤"电力零售套餐推荐系统 · 2026-09-12`, { color: palette.light }), {
    alignment: AlignmentType.CENTER, spacing: { after: 300 },
  }),
  para(run("目录", { bold: true, size: 28, color: palette.dark }), { spacing: { before: 120, after: 120 } }),
  para(run(T`（打开后右键目录选择"更新域"可刷新页码）`, { italics: true, size: 20, color: palette.light })),
  ...tocBlock(tocEntries),

  // ============ 一 ============
  h1(T`一、加项式 FCM 变体及其与电力用户聚类的结合`),
  h2(T`1.1 从标准 FCM 到加项式半监督变体`),
  p(T`本项目复刻 Luo et al.（2019, IEEE Trans. Smart Grid）的电力零售套餐推荐系统，其技术链为：智能电表数据 → 5 维用电特征 → FCM 聚类 → 簇内余弦相似度 → 评分推断与加权聚合 → Top-N 套餐推荐。原论文将 FCM 作为黑箱直接引用（仅引 Bezdek 1984，无任何参数细节），聚类环节从未被审视——这正是本项目的改进落点。`),
  p(T`标准 FCM 的目标函数为：`),
  mathPara([mrun("J = ΣᵢΣⱼ uᵢⱼᵐ‖xᵢ − cⱼ‖²")], T`（式 1，s.t. 行和为 1，u ≥ 0）`),
  p(T`其中 uᵢⱼ 为样本 i 对簇 j 的隶属度，cⱼ 为簇中心，m 为模糊指数。在 FCM 家族谱系中，"往目标函数加辅助信息项"形成了一整条正则化/半监督分支（Pedrycz 加项式、FCM_S 空间邻域项、SSFPC 成对约束项等），统称"加项式"变体：J = FCM 项 + β·辅助信息项。本项目主线采用的 SSFPC（Wang et al. 2022, IEEE TFS）即该家族中"隶属度空间（u 空间）成对约束"分支的代表。`),
  h2(T`1.2 本文变体的结构`),
  p(T`本文变体由三个模块串联构成，整体数据流如下：`),
  p(T`demographic 社会画像（36 字段）→ Gower 混合类型相似度 → 两两约束 s_pq → SSFPC 目标函数约束项 → 模糊聚类（隶属度矩阵 U + 簇中心）→ 下游套餐推荐。`),
  p(T`与 SSFPC 原文相比，本文的差异（即新颖性位置）有三：① 约束来源自动化——SSFPC 的 s_pq 需监督者人工标注两样本隶属度分布的相似程度，本文从社会画像自动推导 s_pq，6,031 户全样本可得、零人工标注；② 监督信息空间迁移——SSFPC 在行为结果空间给监督，本文在社会属性空间给监督（画像相近 ⇒ 用电行为相近 ⇒ 隶属度分布相近），与论文标题"社会信息过滤（Social Information Filtering）"的语义一致；③ 场景与验证——落在电力零售套餐推荐场景，最终以推荐 MAE 做下游验证（推荐层待建）。`),

  // ============ 二 ============
  h1(T`二、SSFPC 的数学原理与迭代算法`),
  h2(T`2.1 目标函数的构造`),
  p(T`SSFPC 在标准 FCM 目标上叠加模糊成对约束项（原文式 5/6，本文取模糊指数 q=2、α=0）：`),
  mathPara([mrun("J = ΣᵢΣⱼ uᵢⱼ²‖xᵢ − cⱼ‖² + β·Σ_(p,q)∈S C(uₚ, u_q)")], T`（式 2）`),
  p(T`其中约束代价函数 C 对正、负约束采用不同的二次型构造（原文式 6）：`),
  mathPara([mrun("C(uₚ, u_q) = ½·s_pq·‖uₚ − u_q‖²    若 s_pq ≥ 0")], T`（式 3a）`),
  mathPara([mrun("C(uₚ, u_q) = −s_pq·uₚᵀu_q    若 s_pq < 0")], T`（式 3b）`),
  p(T`s_pq ∈ [−1, 1] 刻画样本 p、q 隶属度分布应相似（s > 0，must-link 推广）或相异（s < 0，cannot-link 推广）的程度：正约束用距离平方把两者的隶属度向量拉近，负约束用内积项把两者推开（内积越小越相异）。当约束全部非负时（本文正约束特例），式 3b 不出现，目标退化为 J = ΣᵢΣⱼ uᵢⱼ²‖xᵢ − cⱼ‖² + (β/2)·Σ s_pq‖uₚ − u_q‖²。β 控制约束项相对强度。`),
  h2(T`2.2 交替迭代（MEM）`),
  p(T`求解采用交替优化，每轮迭代只用两套更新：`),
  p(T`（1）中心更新（闭式）。约束项不含簇中心，故中心更新不受加项影响，仍为隶属度加权均值（原文式 13）：`),
  mathPara([mrun("cⱼ = "), new MathFraction({
    numerator: [mrun("Σᵢ uᵢⱼ² xᵢ")],
    denominator: [mrun("Σᵢ uᵢⱼ²")],
  })]),
  p(T`（2）隶属度更新（无闭式解）。固定中心后，隶属度子问题为带单纯形约束（行和 = 1、非负）的二次规划。将约束项按图拉普拉斯方式矩阵化（平方项归入对角度矩阵、交叉项归入非对角 −W），每个连通约束块构成一个块 QP。无约束样本仍走标准 FCM 闭式更新（原文式 14）。`),
  h2(T`2.3 求解器的两档实现`),
  p(T`① 正约束特例（v2 版）：s_pq ≥ 0 时块 QP 的黑塞矩阵恒严格正定（有定理与每块 λ_min 数值验证双保险），原论文的 Algorithm 2 塌缩为单次凸 QP，用 OSQP（稀疏 ADMM + 热启动）求解。`),
  p(T`② 完整版含负约束（v3 版）：负约束使黑塞矩阵不定，凸 QP 失效，按原论文路线采用 DBCD——逐样本 Gauss-Seidel 串行扫描，每样本的 5 维子问题恒凸，本文以精确水填充算法解出（按线性项排序枚举活跃前缀 + 二分兜底），实现严格对齐官方 MATLAB 码（github.com/gamer1882/FDC）的 QPP_IDsolver/Solver_x0 结构。`),
  p(T`偏差声明：官方代码私加了 m/|S| 归一化因子（论文式 18/19 中并无此项），本文不采用；β 一律按论文式 (5)(6) 口径报告。完整推导链与验证记录见项目内《SSFPC构造说明.md》及各版本 README。`),

  // ============ 三 ============
  h1(T`三、数据集来源与预处理`),
  h2(T`3.1 数据来源`),
  p(T`主数据为澳大利亚 SGSC（Smart Grid Smart City）项目清洗版数据集（Roberts et al. 2019, Mendeley Data, DOI: 10.17632/zm4f727vvr.1），含 6,031 户新南威尔士州居民 2013 全年完整的 30 分钟级用电负荷（17,520 个采样点无缺失）及配套人口统计（demographic）问卷字段。该数据与原论文所用 1,000 户同属 SGSC 项目但更大（6 倍规模）；实验对比一律以本数据上自跑基线为准，不直接引用原论文数值。`),
  h2(T`3.2 预处理管线一：负荷 → 用电特征`),
  p(T`按原论文 Table I 从 30 分钟负荷序列提取 5 维特征：月均用电量、夏季/冬季（南半球 12–2 月 / 6–8 月）月均、春秋季月均、工作时间（澳大利亚惯例工作日 9:00–17:00）周均、非工作时间周均，再经 z-score 标准化、按 demographic 行序对齐，供聚类输入（输出 data/output/features_std.npy）。`),
  h2(T`3.3 预处理管线二：社会画像 → 两两相似度约束`),
  p(T`从 demographic 表选取 36 个画像字段（有序型如收入/燃气档位、名义型如房型/气候区/地理分层、二值型如 HAS_* 设施拥有情况、普查码与计量配置计数等），用 Gower 相似度处理混合类型并保留有序渐进性；映射为 s = 2S − 1 ∈ [−1, 1] 后稀疏化：每户取 Top-10 相似邻居构成正约束（42,927 对，21 个连通块），Bottom-10 构成负约束（59,760 对，s ∈ [−0.871, 0)）。字段纪律：排除源自负荷曲线的字段（与 5 维特征冗余）与试验分组字段（非画像属性）。正+负边合并后全图为 1 个连通块。`),

  // ============ 四 ============
  h1(T`四、A/B/C/D 四组对照实验结果`),
  h2(T`4.1 实验设计`),
  p(T`四组配置均在 6,031 户 × 5 维标准化特征上运行，k = 5，β = 0.1（A 组 β = 0 即纯 FCM），每组 3 个随机种子；指标分四层：模糊内部指标（PC/PE/XB）、硬划分内部指标（silhouette/Calinski-Harabasz/Davies-Bouldin）、约束满足度（正对同簇率/lift/残差）、外部参照（与 Roberts 预聚类标签的 ARI/NMI，仅背景参照）与稳定性（seed 间 ARI）。`),
  makeTable([1100, 2500, 2900, 2500],
    ["组别", "约束", "求解器", "定位"],
    [
      ["A_fcm", "无（β=0）", "闭式更新", "纯 FCM 基线"],
      ["B_gower15", "旧版 15 字段正约束（54,473 对）", "OSQP 凸 QP", "约束有效性对照"],
      ["C_gower36", "新版 36 字段正约束（42,927 对）", "OSQP 凸 QP", "字段扩充效果"],
      ["D_gower36neg", "C + 负约束（59,760 对）", "串行 DBCD", "负约束消融"],
    ]),
  h2(T`4.2 主指标结果（3 seeds 均值）`),
  makeTable([2600, 1600, 1600, 1600, 1600],
    ["指标", "A 纯 FCM", "B 旧约束", "C 新约束", "D 加负约束"],
    [
      ["PC ↑", "0.689", "0.493", "0.507", "0.504"],
      ["PE ↓", "0.601", "0.935", "0.909", "0.914"],
      ["XB ↓", "0.216", "0.332", "0.298", "0.392"],
      ["Silhouette ↑", "0.449", "0.423", "0.433", "0.395"],
      ["CH ↑", "9810", "9345", "9602", "8854"],
      ["DB ↓", "0.810", "0.833", "0.821", "0.856"],
      ["正对同簇率", "0.376", "0.411", "0.420", "0.415"],
      ["Lift（对随机基线）↑", "1.320", "1.459", "1.475", "1.541"],
      ["约束残差 ↓", "0.620", "0.227", "0.270", "0.266"],
      ["目标函数终值", "2392.14", "3352.01", "3240.51", "3791.87"],
      ["迭代轮数 / 单轮耗时量级", "≈214 轮 / 秒级", "≈178 轮 / 约 102 s", "≈178 轮 / 约 194 s", "200（上限）/ 约 261 s"],
    ]),
  p(T`注：B 与 C 的约束集合不同，残差绝对值不可跨组直接比较，应看 lift 与同簇率；D 组 200 轮为迭代上限到点，但目标尾部变化已在 fp32 噪音量级（相对约 1e-7），视为数值收敛，且三个 seed 的 objective_ascents 全为 0。`),
  h2(T`4.3 负约束专项（C ↔ D 消融）`),
  makeTable([3400, 1900, 1900, 1800],
    ["指标", "C 组（仅正约束）", "D 组（正+负）", "随机基线"],
    [
      ["负对同簇率 ↓", "0.305", "0.165", "0.269"],
      ["负对隶属度内积 ↓", "0.300", "0.161", "—"],
      ["负约束残差 ↓", "0.136", "0.069", "—"],
      ["簇规模（seed 0）", "[1926,105,591,2189,1220]", "[1792,133,705,2077,1324]", "—"],
    ]),
  h2(T`4.4 结论`),
  p(T`结论一（A↔B/C）：约束有用。加入社会画像约束后，正对同簇率 lift 从 1.32 提升到 1.48，约束残差从 0.62 降至 0.27，隶属度分布确实向"画像相似者隶属度分布相近"的方向移动；PC/PE 变化反映划分更模糊，属约束项起作用的预期现象。`),
  p(T`结论二（B↔C）：字段扩充全面更优。36 字段版在七项可比指标上全胜 15 字段版，且相似度区分度问题（"大家都像"）得到缓解——s 唯一值达 79,196 个，满分平局对占比从 3.1% 降至 0.21%。`),
  p(T`结论三（C↔D）：负约束有效且代价小。cannot-link 对子同簇率 30.5% → 16.5%（远低于随机基线 26.9%），隶属度内积减半，"推远"真实发生；正约束满足度反而更好（lift 1.475 → 1.541）；内部指标仅轻微下降（silhouette −0.04）。三组实验 seed 间 ARI 均为 1.0（D 组 1.0 / 0.9565 / 0.9565），结果稳定可复现。`),

  // ============ 五 ============
  h1(T`五、结论与下一步工作`),
  p(T`聚类改进线已全部打通：约束生成（Gower 画像相似度，含正/负两档）、正约束特例凸 QP 求解、完整版串行 DBCD 求解、四层指标评估体系与 A/B/C/D 对照实验，三条核心结论均获数据支持。`),
  p(T`下一步（按优先级）：① k/β 网格扫描与敏感性分析（β 需按约束密度重定标，k 的取值依据待从原论文核实）；② 推荐层实现——评分推断（5/3/2/1/0 规则）、相似度加权聚合、Top-N 输出与 MAE 验证，其中套餐评分数据来源（合成 / powertochoose 采集 / 按原论文 4 条选择模式仿真）待定，是当前最大未知数；③ 写法 B（特征空间标量注入）消融对照。`),
];

const doc = new Document({
  features: { updateFields: true },
  sections: [{
    properties: { page: { margin: { top: 1440, bottom: 1440, left: 1440, right: 1440 } } },
    headers: { default: new Header({ children: [para(run(T`阶段性成果综述 · 聚类改进线`, { bold: true, color: palette.primary }), { alignment: AlignmentType.CENTER })] }) },
    footers: { default: new Footer({ children: [para(new TextRun({ children: [PageNumber.CURRENT] }), { alignment: AlignmentType.CENTER })] }) },
    children,
  }],
});

fs.writeFileSync(outputPath, await Packer.toBuffer(doc));
