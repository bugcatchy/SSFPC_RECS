# 面向智能电网终端用户的"社会信息过滤"电力零售套餐推荐系统

> 项目方案文档 —— 复刻并改进 Luo et al. (2019) 的电力零售套餐推荐系统，
> 核心创新点：改进 FCM 聚类环节 + 混合相似度设计 + 场景化下游验证。
>
> **更新记录**：2026-08-27 —— ① 数据集已下载并核验（见 `data/README.md`）；
> ② 原论文 FCM 用法已核实（仅引用 Bezdek 1984，无任何实现细节）；
> ③ 第二层改进方案按文献溯源修正（源自地下水水质 FCM 论文的"领域标量项"思路，
> 原"类间分离项"公式降级为备选）；④ 本地标准 FCM 实现已与经典文献核对一致。
>
> **更新记录（二）**：2026-08-27 —— ⑤ 第二层理论方案收敛：Relangi 式 (14) 完成数学解剖
> （确认为不可计算、与迭代脱节的装饰项，仅存思路价值）；改进定位收敛至"正则化/
> 半监督 FCM 家族"；修正版目标函数（写法 B：标量中心联合更新）确定为算法主线，
> 写法 A（两两项）作为等价性说明；⑥ "电力版 WQI"确立四条选择硬约束与候选标量清单；
> ⑦ FCM 家族谱系补全根节点与关键分支（见 3.2 末尾）。
>
> **更新记录（三）**：2026-08-27 —— ⑧ SSFPC（Wang 2022）与 EWSS-FCM（Liu 2019）
> 精读完成（两篇 TXT 提取件已生成至 `literature/international/core_references/TXT/`）：
> SSFPC 确证为**加项式两两模板**（式 5/6，写法 A 近亲成立），但约束对象是隶属度
> 向量对（u 空间成对约束，非特征空间标量），隶属度更新无闭式解需 DBCD 解 IQPP——
> 恰反衬写法 B 保持标准闭式更新的工程优势；EWSS-FCM **定位修正：非加项式**
> （J 不变、熵权重调制中心更新 + 标签隶属度钉死，属机制①的权重自动化变体），
> 仅作"加权式 vs 加项式"对照；FCM_S（Ahmed 2002）据此升格为写法 B 在
> "特征空间加项 + 完整重推"层面的最近血亲（待精读）；⑨ 本文第六节文献路径
> 表述按 `literature/README.md` 结构修正。
>
> **更新记录（四）**：2026-08-27 —— ⑩ 第二层主创新方向定稿：由"写法 B（特征
> 空间连续标量加项，源自 Relangi 2022 水刊意图）"转向 **SSFPC 式 u 空间成对
> 约束**（Wang 2022, IEEE TFS 为方法学基础，其目标函数式 5/6、MEM+DBCD 求解
> 框架）；写法 B 降级为**消融对照**（同一 demographic 信息来源的标量注入形态）；
> 约束 s_pq 由 demographic 社会画像自动生成（SSFPC 原文为监督者人工标注——
> 差异点①），监督信息从行为结果空间迁移至社会属性空间（差异点②，呼应
> "社会信息过滤"标题）；demographic 素材已核验（ASSRTD_*/HAS_* 全量 6,031
> 户无缺失，见 data/README.md）。
>
> **更新记录（五）**：2026-09-11 —— ⑪ SSFPC 实现落地并与官方代码核对完成：
> 官方 MATLAB 码（github.com/gamer1882/FDC，本地 `code/reference/FDC-main`）
> 逐行对照，确认我们的拉普拉斯构造与论文式 (15)(18)(19) 在 s≥0 时数学等价
> （平方项↔度矩阵、交叉项↔非对角 −W）；发现**论文与官方代码不一致**——
> 代码私加 m/|S| 归一化因子（论文无），不采用；⑫ **路线决策：走"正约束
> 特例"**——约束由 Gower 相似度自动生成、天然非负，故简化式 (6) 删去负约束
> 分支，重新推导后 Algorithm 2 塌缩为单次凸 QP（恒严格正定，有定理与每块
> λ_min 数值验证双保险），DBCD 与负约束降级为 future work；⑬ 修复 v1 的
> 因子 2 缺陷（v1 标称 β 实为论文口径 2 倍）；⑭ 代码重整为
> `ssfpc_v1_initial`（冻结基线）+ `ssfpc_v2_positive_constraints`（当前版本，含
> SSFPC构造说明.md 完整推导链）；⑮ Gower 约束生成管线（15 字段、
> Top-K(10)、54,473 对）与 Luo Table I 五特征提取管线均已跑通并对齐
> （见第五节目录地图）；⑯ 待办：k/β 网格扫描（β 需按约束密度重定标）、
> 多 seed 重启、余弦消融、推荐层（套餐评分数据来源未定，最大未知数）。

> **更新记录（六）**：2026-09-11 —— ⑰ 相似度字段扩充 v1→v2（15→36 字段：
> 地理分层 suburb/LGA/region 复合计分、CENSUS_GROUP_CODE、计量配置计数、
> HAS_INTERNET_ACCESS + 12 个问卷字段 δ 缺失处理），解决"大家都像"——
> s 唯一值 79,196、满分平局 3.1%→0.21%、20.7% 对子自然为负（按阈值 0 截断
> 为 unknown，负约束完整版列为 future work）；旧版留档
> `code/dispose/output_v1_gower15_fields/`；⑱ 评估体系落地（`code/checking/`）：
> evaluate.py 四层指标（PC/PE/XB/silhouette/CH/DB + 约束 lift/残差 +
> Roberts 标签外部参照 + seed 间 ARI），run_compare.py 三组对照 ×3 seeds
> 全部收敛且 seed 间 ARI=1.0——**结论：约束有用**（lift 1.32→1.48，
> 残差 0.62→0.27），**字段扩充全面更优**（C 组七项指标全胜 B 组）；
> 与 Roberts 预聚类标签 ARI≈0.016（仅背景参照，不可作准确性证据）；
> ⑲ 性能优化：fp64→fp32（消费卡 fp64 吞吐 1/64，TOL 放宽 1e-5）、
> 块 QP 求解器复用 BlockQPSolver（与逐轮新建逐位等价，max|Δu|=5.6e-16）、
> checkpoint 断点续跑机制。
>
> **更新记录（七）**：2026-09-12 —— ⑳ **负约束（完整版式 6）落地**：
> similarity.py 加 `EMIT_NEGATIVE` 开关，负约束（s<0，Bottom-10 选边）
> 输出至 `code/dispose/output_negative/`（59,760 对，s∈[−0.871,0)；
> 每户负值对中位数 828 个，材料充足；正+负边合并后全图 1 个连通块，
> v2 块切分失效）；㉑ "对角平移投影+OSQP"快速验证版试跑后**否决**
> （λ_min(βM)=−5.21 ⇒ 投影 τ=5.21 岭项压垮距离项，隶属度退化均匀，
> PC 0.507→0.260）——恰好印证论文用 DBCD 的必要性；㉒ **串行 DBCD
> 正式版**（`code/ssfpc_v3_negative_constraints/`）严格对齐官方 QPP_IDsolver/Solver_x0：
> 逐样本 Gauss-Seidel + 每样本恒凸 5 维子问题精确水填充解，不采用官方
> 私加的 m/|S| 因子（既定立场），顶点遍历分支不移植（官方仅用于
> ≤3 样本微块）；凸情形（POSITIVE_ONLY）与 v2 OSQP 解对照验证通过
> （mean|ΔU|=5.7e-8）；㉓ **D 组三 seed 全量运行完成**（
> `code/checking/output/D_gower36neg/`）：负对同簇率 30.5%→16.5%
> （随机基线 26.9%）、负对隶属度内积减半、正约束 lift 1.475→1.541、
> 内部指标仅轻微下降（silhouette −0.04），三 seed ARI=1.0/0.9565/0.9565，
> objective_ascents 全 0——**Q3 结论：负约束有效且代价小，C↔D 消融即
> 论文"负约束有用"的直接证据**（详见 checking/README「D 组实验结果」）。

---

## 文档导航（本项目全部 README 一览）

| 路径 | 用途 |
|---|---|
| `README.md`（本文） | 项目总纲：研究背景、创新点论证、技术方案、对照设计、代码地图、文献清单、写作要点、协作约定 |
| `data/README.md` | 数据集说明：SGSC 数据来源与引用、文件清单、parquet 转换、负荷五特征提取（load_features.py）口径、demographic 字段用途与排除纪律、相似度约束输出位置指引 |
| `code/dispose/README.md` | 约束生成：社会画像 → s_pq 的字段口径（v2 36 字段）、v1/v2 输出对照统计、负约束 future work、运行方法 |
| `code/checking/README.md` | 评估与对照实验：output/ 目录结构、四层指标口径、四组对照（A 纯 FCM / B 旧约束 / C 新约束 / D 新约束+负约束）的实验结果与结论 |
| `code/ssfpc_v3_negative_constraints/README.md` | 完整版式 6（含负约束）串行 DBCD 版：求解方法、与官方偏差、运行方法、凸情形验证记录、投影版否决记录 |
| `code/ssfpc_v2_positive_constraints/README.md` | 当前聚类版本说明：运行方法、与 v1 差异、验证记录、fp32/求解器复用等工程变更；完整数学推导见同目录 `SSFPC构造说明.md` |
| `code/ssfpc_v1_initial/README.md` | 冻结基线说明：首版 SSFPC 实现记录，含因子 2 缺陷的存档说明（勿再用） |
| `literature/README.md` | 文献库结构与检索记录：core_references/non_core/知网/constraint_generation各子库的组织与精读状态 |
| `code/reference/FDC-main/README.md` | SSFPC 官方 MATLAB 码（github.com/gamer1882/FDC）自带的原始说明，非本项目撰写 |
| `code/docx_build/README.md` | Word 综述文档生成脚本与 docx-js 环境说明，含 TOC 手写 XML 解析 bug 排错记录与 docx-js 组件陷阱 |

---

## 一、研究背景与目标

复刻 **Luo, F., Ranzi, G., Wang, X., Dong, Z.Y., "Social Information Filtering-Based
Electricity Retail Plan Recommender System for Smart Grid End Users",
IEEE Transactions on Smart Grid, 2019**（被引 68），并在此基础上改进。

原论文技术链：

```
智能电表数据(AMI) → 5维用电特征提取 → FCM聚类 → 簇内余弦相似度
→ 评分推断(5/3/2/1/0规则) → 相似度加权聚合 → Top-N 套餐推荐
```

## 二、创新空间论证（文献排查结论）

调研过程：Connected Papers 文献网络 + Google Scholar 实时被引（2022 以来 56 条）
+ 知网高级检索（3 组检索式）+ 关键风险文献全文精读。

| 排查对象 | 结论 |
|----------|------|
| 原作者团队后续（Zhao 2022 学位论文 / Yang 2021 Applied Energy） | 转向特征工程路线，未改进聚类（全文 FCM 出现 0 次） |
| 同团队最新（Guo et al. 2024, KBS） | 转向多任务学习 + 节能电器推荐，仍未动聚类 |
| 徐新卫 2023（GA-FCM + TFN 协同过滤，电影推荐） | "智能优化 FCM + CF" 通用组合已被做 → 创新点须落在电力场景 |
| 马静 2025（FCM-PSO 大工业电价调节） | 只用了聚类零件，无推荐系统 → 无实质冲突 |
| 王丽 2022 / 李朋起 2020 等 9 篇中文学位论文 | 均为通用场景（电影/阅读/物流），无电力套餐推荐 |

**结论**：「在面向居民的电力零售套餐协同过滤推荐系统中改进 FCM 聚类环节，
并用推荐精度做下游验证」这一组合无人做过。

**注意措辞**：不可声称"首次将智能优化 FCM 用于协同过滤"（徐新卫 2023 已做）、
不可声称"首次将 PSO-FCM 用于电力用户聚类"（马静 2025 已做）。

## 三、技术方案

### 3.1 复现基线（原论文）

**已核实的关键事实（2026-08-27）**：原论文对 FCM 仅一句话带过——"the fuzzy
C-means (FCM) clustering method [31] is used... More details about FCM can be found
in [31]"，**没有给出目标函数、模糊指数 m、聚类数等任何参数细节**，把 FCM 当黑箱用。
因此：

- 复现基线 = 教科书标准 FCM（Bezdek et al. 1984，即原论文参考文献 [31]，
  本地 `code\FCM - The Fuzzy c-Means Clustering Algorithm.pdf`）；
- 本地 `code\main.py` 已实现标准 FCM，经核对与该文献式 (11a) 中心更新、
  式 (11b) 隶属度更新、式 (12a/12b) PC/PE 有效性指标一致，可直接作为基线；
- m 与聚类数 c 原论文未交代，复现时需自行设定并说明依据
  （建议用 XB / Silhouette 指标扫描自动选择，并做敏感性分析）；
- 原论文数据为 SGSC 项目 1,000 户（2013-01 至 2014-01，其参考文献 [30]），
  本项目使用同一项目的清洗版 6,031 户（见第四节）。

基线流程：

1. 特征提取：5 维用电特征（月均用电量、用电时间偏差、非工作时段占比、
   季节偏差等，见原论文 Table I）
2. FCM 聚类（本地实现或 scikit-fuzzy 交叉验证）
3. 簇内余弦相似度（原论文式 4）
4. 评分推断：当前套餐=5，近两个历史套餐=3/2，更早=1，未用过=0，续用累加
5. 加权聚合预测评分（原论文式 5），Top-N 输出

### 3.2 改进设计（创新点，2026-08-27 修正版）

```
第一层（初始化改进，辅助/对照定位）：PSO / SSA 确定 FCM 初始聚类中心
    —— ⚠️ 该方向先例众多（徐新卫 GA-FCM、王丽 SSA-FCM、马静 PSO-FCM），
       创新性低，定位为对照组与实用组件，不作主创新点
第二层（目标函数改进，主创新点，2026-08-27 定稿）：SSFPC 式模糊成对约束 + 自动约束生成
    —— 家族定位：正则化/半监督 FCM 的机制②加项式（J = FCM 项 + λ·辅助信息项），
       但走 **u 空间成对约束分支**（与写法 B 的特征空间标量分支相对）。
       方法学基础：SSFPC（Wang et al. 2022, IEEE TFS，已精读 2026-08-27，
       📁 `literature\international\core_references\PDF\Semisupervised_Fuzzy_Clustering_With_Fuzzy_Pairwise_Constraints.pdf`）。
       其目标函数（原文式 5/6）：
       J = ΣΣ (u_ir^q − α)·‖x_r−v_i‖² + β·Σ_{(p,q)∈NS} C(u_p,u_q)
       C(u_p,u_q) = ½·s_pq·‖u_p−u_q‖²（s_pq ≥ 0 相似）或 −s_pq·u_pᵀ·u_q（s_pq < 0 不相似）
       求解：MEM 交替——E 步中心更新不受约束项影响（原文式 13，仍为加权均值）；
       M 步解带成对约束的隶属度 u，原文分解为不定二次规划（IQPP）用 DBCD 求解，
       无闭式解
    —— 与 SSFPC 的差异（=新颖性位置，写作必须逐条写清）：
       ① 约束来源自动化：SSFPC 的 s_pq ∈ [−1,1] 需监督者**人工标注**
       （人脸表情场景下判断"两样本隶属度分布的相似程度"）；本文从 demographic
       社会画像**自动推导** s_pq = f(a_p, a_q)，全样本 6,031 户可得、零人工标注；
       ② 监督信息空间迁移：SSFPC 在行为结果空间（隶属度分布）给监督，本文在
       **社会属性空间**给监督（画像相近 ⇒ 用电行为相近 ⇒ 隶属度分布相近），
       与论文标题"社会信息过滤（Social Information Filtering）"语义一致；
       ③ 场景与验证：电力零售套餐推荐 + 下游推荐 MAE（SSFPC 为通用聚类 +
       ARI/NMI）
    —— 约束生成（✅ 已实现 2026-09-09，`code/dispose/similarity.py`）：
       画像字段 15 个——有序（收入、燃气 LOW-MED-HI，按 1−|档差|/2）、
       名义（房型、气候区）、二值（11 个 HAS_*/IS_*）；
       **Gower 相似度为主线**（处理混合类型 + 有序渐进，避免 one-hot 余弦的
       互斥性/稀疏性缺陷），one-hot 余弦留作消融对照（开关切换）；
       s = 2S−1 ∈ [0,1]，阈值 ≥0 + 对称 Top-K(10) 稀疏化；
       输出 54,473 对约束（22 个连通块，最大 1,820 户，100% 样本受约束）。
       已知问题：s=1.0 满分对占 3.1%（平局泛滥），备选"等价类内限边"未实现。
       电力领域先例：闫泓序 2021 工业用户画像（Gower+RST+PAM，
       `literature/constraint_generation/`），定位差异已辨析（Gower 在彼处是聚类距离、
       在此是约束生成器；硬聚类 vs 模糊；工业价值评级 vs 居民推荐）。
       字段纪律：排除 ASSRTD_ELECTRICITY_USE_GRP_CD / eDaily / peakTime
       （源自负荷曲线，与 5 维特征冗余）与 TRIAL_CUSTOMER_TYPE /
       CONTROL_GROUP_FLAG（试验分组，非画像属性）、cluster_*（信息泄漏）。
       素材：`data/index files/demographic_lookup_3_groups.parquet`
    —— 求解实现（✅ 已实现并验证 2026-09-11，`code/ssfpc_v2_positive_constraints/`）：
       走**正约束特例**路线（2026-09-11 定稿，见更新记录五）——简化式 (6)
       删去负约束分支，块子问题恒严格正定（有定理证明 + 每块 λ_min 数值
       验证），Algorithm 2 塌缩为单次凸 QP（OSQP 稀疏 ADMM + 热启动）。
       ~~DBCD 与负约束列为 future work~~ → **已完成（2026-09-12，见更新
       记录七）**：负约束 Bottom-10 选边 + 完整版式 (6) 串行 DBCD 求解器
       （`code/ssfpc_v3_negative_constraints/`，对齐官方 QPP_IDsolver），D 组对照证实
       负约束有效（负对同簇率 30.5%→16.5%）。完整推导链与偏差声明见
       `code/ssfpc_v2_positive_constraints/SSFPC构造说明.md`；
       已与官方 MATLAB 码（`code/reference/FDC-main`）逐行核对，
       不采用其私加的 m/|S| 因子（论文式 18/19 无此项）；
       β=0.1（论文口径）、k=5 验证运行：168 轮收敛，目标函数 168 步
       0 次上升，簇规模 [1939, 110, 599, 2140, 1243]
    —— 写法 B（原主线，2026-08-27 降级为**消融对照**）：特征空间连续标量加项
       λ·ΣΣ u_ir^q·(s_r−s_i)²（s_i = Σ_r u_ir^q·s_r/Σ_r u_ir^q 标量模糊中心），
       三组更新式已完整重推且数学自洽（三步交替均为单块全局最小、目标单调收敛）。
       消融设计：同一 demographic 信息来源构造两种注入形态——单样本标量 s_r
       （如收入档数值化或画像综合指数）走写法 B，vs 成对约束 s_pq 走 SSFPC 式，
       对比验证"成对约束 > 单样本标量"（成对携带两两关系信息）。
       ⚠️ 思路溯源 Relangi et al. 2022 水刊（式 14 已解剖为不可计算、与迭代
       脱节），写法 B 只作消融/对照，不作主线、不引为方法来源（措辞纪律：
       只写"受其启发"，不写"基于其方法"）
    —— 回应质疑的固定说法："为何不用单样本标量（写法 B）？"——成对约束携带
       两两关系信息，且 SSFPC 有 IEEE TFS 审稿验证的求解框架；"SSFPC 需要
       人工标注？"——本文约束由 demographic 自动生成；"为何不用 RL/深度
       方法？"——见第七节
    —— FCM 家族谱系补记（related work 用）：根节点为标准 FCM
       （Dunn 1974 / Bezdek 1981，本文基线）；"往目标函数加项"有两条
       经典路线——内部正则（Entropy-FCM，Karayiannis，加 Σu·ln u 熵项）
       vs 外部信息正则（FCM_S/ssFCM/SSFPC/本文），本文落后者且走 SSFPC 的
       u 空间成对约束分支；FCM_S 一族的后代 FLICM 挂名即可；PFCM（PCM
       修复版）在抗离群讨论中挂名；Fuzzy k-shape 用于回应"为何不直接聚
       负荷曲线形状"（答：沿用原论文特征空间技术链，形状级聚类列为未来工作）
第三层（相似度改进）：用电特征相似度 ⊕ 套餐评分相似度加权融合
    —— 结构源自李朋起 2020（已核实其摘要与式 4.6/5.7）：
       Sim(u,v) = w·Sim_特征(u,v) + (1−w)·Sim_评分(u,v)，评分侧用
       Pearson；w 为超参数，消融设"只特征/只评分/融合"三档
    —— 支线（更有新意，可探索）：隶属度向量参与相似度——两用户的
       c 维隶属度分布越像越相似；并可作"跨簇近邻"补充原论文簇内
       相似度的近邻池
    —— 与第二层的分工叙事（须写清，防"为什么不在一处改两次"的质疑）：
       第二层改**簇的构成**（粗粒度、聚类阶段），第三层改**簇内近邻
       的选择**（细粒度、推荐阶段）
场景层：电力套餐推荐 + 欺诈套餐过滤验证（独有贡献）
```

### 3.3 对照实验

- 聚类对照：K-means / GMM / DBSCAN
- 初始化对照：随机初始化 FCM / PSO-FCM / GA-FCM / (改进)SSA-FCM
- 原论文自带对照：Base case 1（随机推荐）、Base case 2（不聚类、全用户算相似度，
  用于验证"聚类降低计算量"的动机）——复现时保留
- 消融：三层改进逐一开启/关闭

### 3.4 评估体系

- 聚类内部指标：Silhouette、Davies-Bouldin、Calinski-Harabasz、
  Xie-Beni、划分系数 PC / 划分熵 PE
- 下游任务指标：推荐评分预测 MAE（核心）、RMSE
- 稳定性：每算法跑 20 次，报均值 ± 标准差
- 效率：运行时间对比（验证"聚类降低推荐计算量"的动机）
- 交叉验证：80/20 划分 + 3 折交叉验证（沿用原论文设置）

## 四、数据（已下载，2026-08-27 核验）

主数据集已下载并解压至 `data/`，**详细说明见 `data/README.md`**。

| 数据 | 状态 | 说明 |
|------|------|------|
| 智能电表数据 | ✅ 已下载（Mendeley, DOI: 10.17632/zm4f727vvr.1） | 6,031 户 NSW 居民，2013 全年完整（17,520 个 30 分钟点无缺行），SGSC 项目清洗版，与原论文同源。主文件 `data_3_groups.csv`（990 MB 宽表，用户为列），建议转 parquet 加速 |
| 附带索引 | ✅ 已下载 | `cluster_index.csv`（Roberts 团队预打聚类标签）；`demographic_lookup_3_groups.csv`（收入分组、房型、人数、空调/泳池等人口统计字段——可作第二层"领域标量"素材）；`Column Mappings.csv`（字段字典） |
| 备用 | 未下载 | data.gov.au SGSC Customer Trial / Low Carbon London |
| 零售套餐 | 待做 | powertochoose.org 采集或按原论文 Section III 模拟；原论文 46 个套餐为人工采集，无公开数据集 |
| 套餐选择标签 | 待做 | 按原论文 4 条选择模式假设生成（仿真）：季节偏差→固定费率；非工作时段用电→TOU；价格相近→高信誉/高可再生 |

**数据引用注意**：本数据集应引用 Roberts et al. (2019, Mendeley Data)。
因与原论文自处理的 1,000 户不完全等同，实验对比一律以本数据上自跑的
复现基线为准，不直接引用原论文报告的 MAE 数值。

## 五、代码地图（2026-09-11 现状，取代原规划）

```
project/
├── data/
│   ├── convert_to_parquet.py      # 990MB CSV → parquet（已完成）
│   ├── load_features.py           # 负荷主表 → Luo Table I 五特征（月均/夏冬/春秋/
│   │                              #   工作时间(工作日9-17)/非工作时间周均）+ z-score，
│   │                              #   按 demographic 行序对齐（输出 data/output/）
│   └── output/                    # load_features.parquet / features_std.npy / ...
├── code/
│   ├── dispose/
│   │   ├── similarity.py          # demographic 36 字段(v2, 2026-09-11 扩充: 地理分层/
│   │   │                          #   普查码/计量计数/问卷字段δ缺失处理) → Gower 两两相似度
│   │   │                          #   (主线) / one-hot 余弦 (对照) → s=2S−1,
│   │   │                          #   阈值≥0 + 对称Top-K(10) → 42,927 对约束 (21 块, 最大 5,039)
│   │   ├── output/                # constraints_gower.parquet / constraints_cosine.parquet /
│   │   │                          #   customer_ids.npy / run_meta.json (v2 新约束)
│   │   ├── output_negative/       # 负约束 (2026-09-12): constraints_gower_negative.parquet
│   │   │                          #   (s<0, Bottom-10, 59,760 对) + customer_ids.npy + run_meta.json
│   │   └── output_v1_gower15_fields/  # 旧 15 字段版留档 (54,473 对, 22 块)
│   ├── checking/                  # ★评估与对照实验 (2026-09-11 建)
│   │   ├── evaluate.py            #   四层指标: PC/PE/XB + silhouette/CH/DB +
│   │   │                          #   约束lift/残差 + Roberts标签ARI/NMI (无sklearn依赖)
│   │   ├── run_compare.py         #   三组对照×3 seeds 批量运行 (checkpoint 断点续跑)
│   │   ├── README.md              #   output/ 内容与指标口径说明
│   │   └── output/                #   A_fcm / B_gower15 / C_gower36 / D_gower36neg
│   │                              #   各 3 seeds + summary.csv + stability.json
│   ├── ssfpc_v1_initial/             # 冻结基线：首个可运行 SSFPC（有因子2缺陷，
│   │   ├── ssfpc.py               #   标称β实为论文口径2倍；详见其 README）
│   │   └── output/                # β=0.1 验证运行记录
│   ├── ssfpc_v2_positive_constraints/        # ★当前版本：正约束特例，因子2已修复，
│   │   ├── ssfpc.py               #   λ_min 正定性验证; run_ssfpc() 可复用接口;
│   │   │                          #   fp32 + BlockQPSolver 求解器复用 (2026-09-11)
│   │   ├── SSFPC构造说明.md        # 简化式(6)完整推导链+偏差声明（论文章节草稿）
│   │   └── output/                # β=0.1 k=5 验证运行记录
│   ├── ssfpc_v3_negative_constraints/            # ★完整版式6 (2026-09-12): 串行DBCD对齐官方
│   │   ├── ssfpc_v3.py            #   QPP_IDsolver; POSITIVE_ONLY 验证开关;
│   │   │                          #   进度条+ETA; checkpoint 续跑
│   │   ├── output/                #   seed_0 原始运行 (副本归档 checking D 组)
│   │   └── output_positive_only_vs_v2/  # 凸情形验证留档 (mean|ΔU|=5.7e-8)
│   ├── reference/FDC-main/          # SSFPC 官方 MATLAB 码（github.com/gamer1882/FDC，
│   │                              #   已逐行对照；PNNG.m 为 GBK 编码）
│   ├── docx_build/                # Word 综述生成脚本 create.js + docx-js 环境（2026-09-12）
│   └── fcm_legacy/                   # 标准 FCM 手写实现（复刻基线，已核对 Bezdek 1984）
└── literature/                      # 文献库（见 literature/README.md）
```

运行环境纪律：用 conda **yolo** 环境（`/c/Users/BugCat/miniconda3/envs/yolo/python.exe`，
polars/torch-CUDA/scipy/osqp 齐备）；Git Bash 下必须 `export POLARS_SKIP_CPU_CHECK=1`；
受管 Python 无 polars/pyarrow。

待建（实验阶段）：k/β 网格扫描（可直接复用 checking/evaluate.py + run_ssfpc 接口）、
推荐层 `recommend.py`（评分推断式 4/5、Top-N、MAE）——套餐数据来源未定。

## 六、参考文献清单

本地目录说明（相对本 README 所在目录）：
- `literature\` —— 文献库（2026-08-27 重整，详见 `literature\README.md`）：
  `international\core_references\PDF|TXT`（英文核心文献）、`international\non_core\`、
  `cnki\*.txt`（转换件，公式可能有缺失，正式引用以原 PDF 为准）、
  `cnki\CAJ\`（知网原始格式，需 CAJViewer 打开）
- `相关论文索引\` —— Connected Papers 导出的 .bib 文献条目
- 全文提取件位置按文献库结构（详见 `literature\README.md`）：
  `literature\international\core_references\TXT\`（核心英文文献，与 PDF 分目录存放）、
  `literature\international\non_core\*.txt`（与 PDF 同目录）、
  `literature\cnki\*.txt`（与 CAJ 分目录）。提取件便于全文检索，公式可能缺失，
  正式引用与公式核对一律以原 PDF 为准

### 复刻基准
- Luo F, Ranzi G, Wang X, Dong ZY. Social Information Filtering-Based Electricity
  Retail Plan Recommender System for Smart Grid End Users. IEEE Trans. Smart Grid,
  2019, 10(1): 95-104.（被引 68）
  📁 本地：`literature\international\core_references\PDF\Social Information Filtering-Based Electricity.pdf`
  ⚠️ 已核实：FCM 部分无任何实现细节，仅引用 Bezdek 1984 [31]

### 方法基础
- Bezdek JC, Ehrlich R, Full W. FCM: The fuzzy c-means clustering algorithm.
  Computers & Geosciences, 1984, 10(2-3): 191-203.（FCM 原始文献，原论文参考文献 [31]；
  该文只给更新公式不给推导，推导在 Bezdek 1981 专著中）
  📁 本地：`code\FCM - The Fuzzy c-Means Clustering Algorithm.pdf`
- Relangi NDSSK, Chaparala A, Sajja R. Identification of Potential Quality of
  Groundwater Using Improved Fuzzy C Means Clustering Method. Mathematical
  Modelling of Engineering Problems (IIETA), 2022, 9(5). DOI: 10.18280/mmep.090527.
  （第二层**消融对照（写法 B）**的思路来源：目标函数加领域标量项。⚠️ 已核实其
  式 14 加项后未重推更新公式、不可计算、与迭代脱节，仅存思路价值——写法 B 的
  规范形式为本文自推，措辞纪律：只写"受其启发"，不写"基于其方法"）
  📁 本地：`literature\international\non_core\地下水改进 FCM.pdf`

### 同团队迭代（相关工作定位用）
- Yang J, et al. Household power usage pattern filtering-based residential electricity
  plan recommender system. Applied Energy, 2021, 298: 117191.（⚠️ 期刊版未下载，
  内容包含于下条学位论文中）
- Zhao P. Household Energy Consumption Analysis-based Electricity Plan Recommender
  System. MPhil Thesis, UNSW, 2022.（含期刊版扩写，已精读：未改进聚类）
  📁 本地：`literature\international\core_references\PDF\Household power usage pattern filtering-based residential electricity plan recommender system.pdf`
- Guo X, Zhang Y, Luo F, Dong ZY. User-centric recommendations on energy-efficient
  appliances in smart grids: A Multi-task learning approach. Knowledge-Based Systems,
  2024.（⚠️ 未下载，ScienceDirect 获取）

### 方法参考（改进 FCM + CF 的通用场景先例）
- 徐新卫, 陶飞, 等. 融合FCM和TFNs的协同过滤推荐算法. 计算机技术与发展,
  2023, 33(3): 161-166.（GA-FCM + 梯形模糊数，参数齐全可复现）
  📁 本地：`literature\cnki\融合FCM和TFNs的协同过滤推荐算法_徐新卫.txt`；
  原始 CAJ：`literature\cnki\CAJ\融合FCM和TFNs的协同过滤推荐算法_徐新卫.caj`
- 王丽. 基于麻雀搜索优化模糊C均值聚类的推荐算法研究. 桂林理工大学硕士论文, 2022.
  （ISSA-FCM 三层消融实验设计模板）
  📁 本地：`literature\cnki\基于麻雀搜索优化模糊C均值聚类的推荐算法研究_王丽.txt`；
  原始 CAJ：`literature\cnki\CAJ\基于麻雀搜索优化模糊C均值聚类的推荐算法研究_王丽.caj`
- 李朋起. 基于改进FCM的协同过滤推荐系统设计与实现. 南京邮电大学硕士论文, 2020.
  （混合相似度 + 系统设计参考）
  📁 本地：`literature\cnki\基于改进FCM的协同过滤推荐系统设计与实现_李朋起.txt`；
  原始 CAJ：`literature\cnki\CAJ\基于改进FCM的协同过滤推荐系统设计与实现_李朋起.caj`
- 马静, 等. 基于FCM-PSO算法的大工业用电价格峰谷调节策略. 2025.
  （电力领域 PSO-FCM 先例，仅聚类无推荐）
  📁 本地：`literature\cnki\基于FCM-PSO算法的大工业用电价格峰谷调节策略_马静.txt`；
  原始 CAJ：`literature\cnki\CAJ\基于FCM-PSO算法的大工业用电价格峰谷调节策略_马静.caj`

### 其他已下载待读的中文文献（CAJ 原件，暂未转换）
位于 `literature\cnki\CAJ\`：
- 基于QPSO与FCM融合的协同过滤推荐算法_王晓云.caj（QPSO，PSO 的量子改进版）
- 基于直觉模糊C均值聚类和用户兴趣的协同过滤推荐算法_余洁茹.caj（直觉模糊路线）
- 改进模糊划分聚类的协同过滤推荐算法_苏庆.caj
- 基于模糊C-均值和特征加权法的协同过滤推荐算法_字云飞.caj
- 基于差分隐私保护的模糊C均值聚类推荐_蒋宗礼.caj（隐私方向，备选）
- 基于模糊C均值聚类的阅读推荐系统研究_潘鹏程.caj（低优先级）
- 一种基于模糊聚类的数据挖掘推荐算法_穆禹锟.caj（低优先级）

### 电力负荷聚类前沿（均未下载，检索线索）
- Wang L, et al. A particle swarm optimization-based deep clustering algorithm for
  power load curve analysis. Electric Power Systems Research, 2024.（深度聚类路线代表）
- Michalakopoulos V, et al. A machine learning-based framework for clustering
  residential electricity load profiles to enhance demand response programs.
  Applied Energy, 2024, 361: 122943.
- 马宗彪, 许素安, 等. 基于特征加权模糊聚类的电力负荷分类. 中国电力,
  2022, 55(6): 25-32.（VMD-FCM，公式齐全，知网可下）

### Connected Papers 文献条目（bib，可导入 Zotero）
位于 `相关论文索引\`（项目根目录下，已随 2026-08-27 文件夹重整迁出）：
- `ConnectedPapers-for-...bib` —— 相似论文图全部节点
- `Derivative-Works-for-...bib` —— 衍生工作（引用原论文者）
- `Prior-Works-for-...bib` —— 先验工作（共同引用的奠基文献）

### 正则化 FCM 家族与电力标量支撑（Bensaid/Wang/Liu 已精读 2026-08-27；其余为检索线索）
- Bensaid AM, Hall LO, Bezdek JC, Clarke LP. Partially supervised clustering for
  image segmentation. Pattern Recognition, 1996.（SFCM 开山作，Scholar 检索被引 400+；
  家族血统文献，related work 必引。**已精读 2026-08-27**：ssFCM 走"变量固定/约束式"
  注入——J 不变、标签样本隶属度钉死、中心由标签样本播种；Pedrycz 1985 才是
  加项式祖先）
  📁 本地：`literature\international\core_references\PDF\1996prssfcmimages.pdf`；全文提取件同名 .txt
  （中间段文本层损坏，公式以 PDF 第 3–5 页原貌为准）
- Wang Z, Wang SS, Bai L, Wang WS, Shao YH. Semisupervised fuzzy clustering with
  fuzzy pairwise constraints. IEEE Trans. Fuzzy Systems, 2022, 30(9).（SSFPC；
  把 must-link/cannot-link 推广为模糊成对约束。**已精读 2026-08-27，定为本文
  第二层方法学基础（主线）**：① 加项式（J = 原型聚合项 + β·ΣC(u_p,u_q)，其
  式 5/6），约束对象为**隶属度向量对**（u 空间，s_pq∈[−1,1]）；② 中心更新式
  (13) 不受加项影响（仍为加权均值）；③ 隶属度更新无闭式解、需 DBCD 解 IQPP。
  本文差异点（新颖性）：约束 s_pq 由 demographic 画像相似度自动生成（原文为
  监督者人工标注）、监督空间从行为结果迁移到社会属性、下游用推荐 MAE 验证）
  📁 本地：`literature\international\core_references\PDF\Semisupervised_Fuzzy_Clustering_With_Fuzzy_Pairwise_Constraints.pdf`；
  全文提取件：`literature\international\core_references\TXT\` 同名 .txt（2026-08-27 生成）
- Liu CL, Hsaio WH, Chang TH, Li HH. Clustering data with partial background
  information. Int. J. of Machine Learning & Cybernetics, 2019.（EWSS-FCM。
  **已精读 2026-08-27，⚠️ 定位修正：非加项式**——J 保持标准 FCM 形式（式 1），
  创新在熵权重 w_i 调制中心更新（式 6）+ 标签样本隶属度钉死（式 7 仅对无标签样本
  更新），是 Bensaid ssFCM"变量固定/约束式"机制（①）的权重自动化变体；在原文中
  仅作为 Constrained-NMF 的初始化组件。不属本文加项式血统线，仅作"加权式 vs
  加项式"两分法对照，其熵权重思想可在 λ 敏感性/权重设计讨论中挂名。真正的
  特征空间加项推导模板为 FCM_S（Ahmed 2002，建议升格精读））
  📁 本地：`literature\international\core_references\PDF\Clustering data with partial background information.pdf`；
  全文提取件：`literature\international\core_references\TXT\` 同名 .txt（2026-08-27 生成）
- Ahmed MN, Yamany SM, Mohamed N, Farag AA, Moriarty T. A modified fuzzy c-means
  algorithm for bias field estimation and segmentation of MRI data. IEEE Trans.
  Medical Imaging, 2002.（FCM_S，空间邻域一致性正则化。⚠️ 2026-08-27 定位修正：
  结合 SSFPC/EWSS-FCM 精读结论，FCM_S 是写法 B（**消融对照**）在"**特征空间加项 +
  完整重推中心更新式**"层面的最近血亲（J = FCM 项 + α·邻域项，v_k 更新式含
  邻域均值项、被完整重推），作消融组推导核对模板 + 家族血统引用）
- Karayiannis NB. Entropy-based FCM（加 Σu·ln u 熵项；用于"内部正则 vs 外部信息
  正则"两分叙事，related work 一句话提及）
- Krinidis S, Chatzis V. FLICM, IEEE Trans. Image Processing, 2010.（FCM_S 一族
  最主流后代，挂名即可）；Pal NR, et al. PFCM, IEEE Trans. Fuzzy Systems, 2005.
  （PCM 修复版，抗离群讨论挂名）
- Fuzzy k-shape（模糊化时序形状聚类；仅用于回应"为何不直接聚负荷曲线"）
- 王敬敏, 王超. 减碳配额约束下电力客户的模糊聚类分析. 中国电力, 2013.
  （电力客户价值指标体系 + 模糊聚类，"电力版 WQI"最对口先例；知网可下）
- 王利利, 张琳娟, 等. 能源互联网背景下园区用户画像及成熟度评价模型研究.
  中国电力, 2020.（电费敏感标签、需求响应潜力标签体系；知网可下）
- 张清叶, 孙一夫. 基于CVaR的电价敏感用户组合购电风险模型. 2023.
  （"电费占支出比例大 = 电价敏感用户"定义先例）

## 七、论文写作要点备忘

- 研究意义可写："自 2021 年以来该方向缺乏跟进（Connected Papers 衍生工作止于
  2021；Scholar 2022+ 引用均为综述或 RL/数字孪生路线），且现有工作均未对相似
  用户发现的聚类环节做算法改进"；
- 原论文把 FCM 当黑箱（无任何参数细节，仅引 [31]）——"聚类环节从未被审视"
  的叙事有原文证据（2026-08-27 核实）；
- 第二层改进的规范性增量：主线采用 SSFPC（Wang 2022, IEEE TFS）的模糊成对
  约束框架（目标函数与 MEM/DBCD 求解均经期刊审稿验证），本文的增量在约束
  来源自动化（demographic 画像相似度推导 s_pq，SSFPC 为人工标注）与电力推荐
  场景验证。写法 B（消融对照）的规范形式为本文自推（三步交替均单块全局最小、
  单调收敛），思路溯源 Relangi et al. (2022)——**措辞纪律：只能写"受其思路启发
  并发现其方法学缺陷"，不可写"基于 Relangi 的方法"**；
- 第二层的 related-work 三层结构：方法学基础（主线）→ SSFPC 2022（模糊成对
  约束 + MEM/DBCD，IEEE TFS）；家族血统 → Pedrycz 加项式 / Bensaid 约束式 /
  FCM_S 特征空间加项 / EWSS-FCM 加权式；本文位置 → 约束自动生成（demographic
  画像相似度）、社会属性空间监督、电力推荐场景 + 下游 MAE。消融对照 → 写法 B
  （Relangi 2022 思路，只写"受其启发"）。各层各引各的；
- 单样本标量（"电力版 WQI"，写法 B 消融用）需引电力领域文献支撑其定义，
  不可自定义而无依据；候选月度电费（张清叶 2023、王利利 2020 支撑）/综合指数
  （王敬敏 2013 支撑）；标量定稿前先核对 demographic 字段质量 + 标量与 5 维
  特征的相关性（尤其排除源自负荷曲线的字段：ASSRTD_ELECTRICITY_USE_GRP_CD、
  eDaily、peakTime）；
- 知网检索证据：「FCM × 推荐/套餐/电价」2019 年以来 106 条结果中无电力套餐
  推荐方向论文（检索截图已存）；
- 需回答的潜在质疑："为什么不用 RL/深度方法？"——答：输入特征仅 5 维、需要
  软隶属度支持相似度计算、行业要求可解释性、无需大量交互数据；"为什么不直接
  聚负荷曲线形状？"——答：沿用原论文特征空间技术链，Fuzzy k-shape 等形状级
  路线列为未来工作；"为什么不直接加一维特征？"（写法 B 消融语境）——答：
  λ 显式可控、可消融；"成对约束 vs 单样本标量？"——答：消融实验对比，成对
  约束携带两两关系信息；
- 数据集用 6,031 户（原论文 1,000 户的 6 倍）本身是加分项；引用 Roberts et al.
  (2019, Mendeley Data)，对比以自跑基线为准；
- 三层创新的角色定位：第二层是主创新点（方法贡献），第一层是对照/辅助，
  第三层与场景验证撑应用价值——写作时主线聚焦第二层，避免"每层都不深"。

---

## 协作约定（"记住"命令，2026-09-10 确立）

**复刻算法时遇到论文无法直接提供的关键细节（公式排版损坏、伪代码含糊、
超参数/实现细节缺失等）：**

1. **停下来先问用户**，把缺失点具体列出来；
2. 有官方源代码时，**请用户下载**（或经用户同意后拉取），以官方实现为准；
3. 在用户给出方向之前，**不自行推导、不猜测补齐**——推导只能作为
   "备选方案"提出供用户选择，不得直接当作最终实现写进代码。

背景：2026-09-10 SSFPC 的 QP 构造系自行推导（论文矩阵构造段落排版损坏），
虽通过 β=0 退化验证，但未经用户确认，事后按本约定应改为先问。

---

*文档生成于 2026-08-26，基于当日的文献调研结论；
2026-08-27 更新：数据集就位核验、原论文 FCM 用法核实、第二层方案按溯源修正；
2026-08-27（二）更新：第二层理论收敛（式 14 解剖、正则化/半监督 FCM 定位、
写法 B 目标函数、电力版 WQI 四约束与候选标量、FCM 家族谱系补记、第三层细化）；
2026-08-27（三）更新：第二层主线转向 SSFPC 式成对约束（Wang 2022）、写法 B
降级为消融对照、约束由 demographic 画像自动生成；
2026-09-10 更新：确立协作约定（复刻遇缺失细节先问用户，官方源码为准）；
2026-09-11 更新：SSFPC 落地并与官方 MATLAB 码核对（不采用 m/|S| 因子）、
正约束特例路线定稿（Algorithm 2 塌缩为凸 QP）、因子 2 修复、代码重整为
ssfpc_v1_initial（冻结）+ ssfpc_v2_positive_constraints（当前）、Gower 约束生成与
五特征提取管线跑通；2026-09-11（二）更新：相似度字段扩充 v2（36 字段）、
评估模块与三组对照实验落地（约束有效、字段扩充全面更优）、fp32 与
QP 求解器复用性能优化。*
