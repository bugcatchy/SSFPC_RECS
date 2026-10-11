# literature/ 文献库说明

> 本目录存放项目的全部参考文献，按"来源 × 用途"分层。
> 文档更新于 2026-08-27（配合当日的文件夹结构重整；同日精读 SSFPC 与 EWSS-FCM
> 并生成其 TXT 提取件，见下表"已精读 2026-08-27"行）。

## 目录结构

```
literature/
├── international/
│   ├── core_references/
│   │   ├── PDF/        # 核心英文论文原件
│   │   └── TXT/        # 对应的全文提取件（便于全文检索；公式可能缺失，
│   │                   #   正式引用与公式核对一律以 PDF 原貌为准）
│   └── non_core/           # 低质量期刊文献，仅存思路/反面教材价值
└── cnki/
    ├── *.txt           # 中文论文全文提取件（由 CAJ 转换，公式可能缺失）
    └── CAJ/            # 中文论文原始 .caj 文件（知网私有格式，需 CAJViewer）
```

另：Connected Papers 导出的 .bib 文献条目在**项目根目录**的 `相关论文索引/`，
不在本目录。

## international/core_references/PDF

| 文件 | 文献 | 角色 | 状态 |
|---|---|---|---|
| Social Information Filtering-Based Electricity.pdf | Luo et al. 2019, IEEE TSG | **复刻基准**（FCM 仅一句带过、无任何参数细节，已核实 2026-08-27） | 已精读 |
| Household power usage pattern filtering-based ... .pdf | Zhao 2022 学位论文（含 Yang 2021 期刊版扩写） | 同团队迭代，相关工作定位（未改进聚类） | 已精读 |
| 1996prssfcmimages.pdf | Bensaid et al. 1996, Pattern Recognition（ssFCM） | 方法血统：约束式注入辅助信息 | 已精读（式 8–14e 核对原貌） |
| Semisupervised_Fuzzy_Clustering_With_Fuzzy_Pairwise_Constraints.pdf | Wang et al. 2022, IEEE TFS（SSFPC） | **第二层方法学基础（主线，2026-08-27 定）**：模糊成对约束（式 5/6，u 空间 s_pq∈[−1,1]）+ MEM/DBCD 求解。**已精读 2026-08-27**：中心更新式 (13) 不受加项影响，隶属度更新无闭式解、需 DBCD 解 IQPP。与本文差异（新颖性）：约束 s_pq 由 demographic 画像相似度**自动生成**（原文为人工标注）、监督空间从行为结果迁移到社会属性、下游用推荐 MAE 验证 | 已精读 2026-08-27 |
| Clustering data with partial background information.pdf | Liu et al. 2019, IJMLC（EWSS-FCM） | ⚠️ **非加项式**（2026-08-27 修正）：J 保持标准 FCM 形式，创新在熵权重 w_i 调制中心更新（式 6）+ 标签样本隶属度钉死（式 7），是 ssFCM"变量固定/约束式"机制的权重自动化变体；原文中仅作 Constrained-NMF 的初始化组件。仅作"加权式 vs 加项式"对照，非推导模板 | 已精读 2026-08-27 |

## international/non_core

| 文件 | 文献 | 角色 |
|---|---|---|
| 地下水改进 FCM.pdf / .txt | Relangi et al. 2022, MMEP（IIETA） | 第二层思路溯源 + 反面教材：式 (14) 已解剖，不可计算、与迭代脱节；**只写"受其启发"，不可写"基于其方法"** |

## 知网参考

TXT 区（已转换，可直接检索）：

| 文件 | 角色 |
|---|---|
| 融合FCM和TFNs的协同过滤推荐算法_徐新卫 | GA-FCM+CF 先例（措辞红线：不可声称"首次智能优化 FCM 用于 CF"） |
| 基于麻雀搜索优化模糊C均值聚类的推荐算法研究_王丽 | 三层消融实验设计模板 |
| 基于改进FCM的协同过滤推荐系统设计与实现_李朋起 | 第三层混合相似度出处（式 4.6/5.7 已核实） |
| 基于FCM-PSO算法的大工业用电价格峰谷调节策略_马静 | 电力领域 PSO-FCM 先例（措辞红线：不可声称"首次 PSO-FCM 用于电力聚类"） |

CAJ 区（原件，需 CAJViewer；已转换者同上 4 篇，其余待转换）：
王晓云（QPSO）、余洁茹（直觉模糊）、苏庆、字云飞（特征加权）、
蒋宗礼（差分隐私，备选）、潘鹏程（低优先级）、穆禹锟（低优先级）。

## 使用规则

1. **读文献优先看 TXT**（全文检索快），**核公式必须回 PDF**——TXT 提取件
   可能丢公式，个别 PDF 文本层损坏（如 1996prssfcmimages 第 4–5 页），
   损坏处按 PDF 页面图片阅读；
2. 新增文献放入对应分区后在**项目根 README 的"六、参考文献清单"**登记，
   保持两边一致；
3. 精读完一篇，在本表"状态"列和根 README 文献条目标注日期与结论。
