# checking/ — 聚类效果评估与对照实验

本目录回答三个问题：

- **Q1（A vs C）**：画像约束对聚类有没有用？（β=0 纯 FCM ↔ β=0.1 + 新约束）
- **Q2（B vs C）**：相似度字段扩充有没有用？（15 字段旧约束 ↔ 36 字段新约束）
- **Q3（C vs D）**：负约束（cannot-link, s<0）有没有用？（完整版式 6 ↔ 正约束特例）

## 文件

- `evaluate.py` — 指标模块（无 sklearn 依赖，numpy 手实现），可单独对任意
  run 目录使用：`python code/checking/evaluate.py <run_dir>`
- `run_compare.py` — 三组对照 × 3 seeds 的批量运行 + 汇总；
  支持 checkpoint 断点续跑（`--max-seconds` 限时到点自动存档，重复执行即续跑）

## output/ 内存放什么

```
output/
├── A_fcm/seed_{0,1,2}/       # 对照组A: β=0 纯 FCM (无约束)
├── B_gower15/seed_{0,1,2}/   # 对照组B: β=0.1 + 旧约束 (15 字段 Gower,
│                             #            code/dispose/output_v1_gower15_fields/)
├── C_gower36/seed_{0,1,2}/   # 实验组C: β=0.1 + 新约束 (36 字段 Gower,
│                             #            code/dispose/output/)
├── D_gower36neg/seed_{0,1,2}/ # 实验组D: β=0.1 + 新约束 + 负约束 (完整版式6,
│                             #   code/dispose/output_negative/, v3 串行DBCD求解,
│                             #   seed_0 系code/ssfpc_v3_negative_constraints/output/ 的归档副本)
│   每个 run 目录: U.npy / centers.npy / labels.npy / objective.csv
│                  / run_meta.json / metrics.json
├── summary.csv               # 每行一个 run 的全部指标 (横向对比用)
└── stability.json            # 同配置不同 seed 的两两标签 ARI (稳定性)
```

**对比读法**：A↔C 看约束贡献；B↔C 看字段扩充贡献；summary.csv 中
`lift`（受约束对同簇率/随机基线）和 `residual`（约束残差）是约束效果的
直接证据；`PC/PE/XB/silhouette/CH/DB` 是聚类质量；`ARI_ca/ARI_3a` 是与
Roberts 预聚类标签的外部参照（**非真值**，仅一致性参考）。

## 指标口径（evaluate.py）

| 层 | 指标 | 方向 | 说明 |
|---|---|---|---|
| 模糊内部 | PC 划分系数 | ↑ | ∈[1/k, 1]，越硬越高 |
| 模糊内部 | PE 划分熵 | ↓ | ∈[0, log k] |
| 模糊内部 | XB (Xie-Beni) | ↓ | 紧密度/簇间最小分离度 |
| 硬内部 | silhouette | ↑ | defuzzify 后计算 |
| 硬内部 | CH (Calinski-Harabasz) | ↑ | 组间/组内方差比 |
| 硬内部 | DB (Davies-Bouldin) | ↓ | 簇间相似度最大值均值 |
| 约束效果 | same_cluster_rate / lift | ↑ | 受约束对同簇率 ÷ 随机基线 Σ(n_j/n)² |
| 约束效果 | residual | ↓ | mean s_pq‖u_p−u_q‖²（目标第二项实际值） |
| 外部参照 | ARI / NMI × 6 标签列 | ↑ | vs Roberts cluster_index，非真值 |
| 稳定性 | seed 间两两 ARI | ↑ | run_compare 汇总 |

## 运行

```bash
export POLARS_SKIP_CPU_CHECK=1   # Git Bash 必需
python code/checking/run_compare.py                  # 全部三组 × 3 seeds
python code/checking/run_compare.py --only C_gower36 # 只跑一组
python code/checking/run_compare.py --max-seconds 270  # 限时 (默认 270s)
```

注意：v2 新约束的最大连通块 5,039 户（占 84%），求解器复用后单轮 QP 约 2.6s，
C 组单 seed 收敛约 3~4 分钟；受终端单次命令时长限制，
脚本会自动 checkpoint，重复执行命令即可断点续跑。

统一环境：miniconda `yolo`（Python 3.10），PyTorch CUDA（距离/中心），
OSQP CPU（块 QP）。

## 实验结果（2026-09-11，k=5，三 seed 完全一致：seed 间 ARI=1.0）

| 指标 | A：纯 FCM | B：旧约束(15字段) | C：新约束(36字段) | 方向 |
|---|---|---|---|---|
| PC | **0.689** | 0.493 | 0.507 | ↑ |
| PE | **0.601** | 0.935 | 0.909 | ↓ |
| XB | **0.216** | 0.332 | **0.298** | ↓ |
| silhouette | **0.449** | 0.423 | **0.433** | ↑ |
| CH | 9810 | 9345 | **9602** | ↑ |
| DB | **0.810** | 0.833 | **0.821** | ↓ |
| 约束同簇率 lift | 1.320 | 1.459 | **1.475** | ↑ |
| 约束残差 | 0.620 | **0.227** | 0.270 | ↓ |
| ARI vs Roberts(ca) | 0.015 | 0.016 | 0.016 | 参照 |

**结论**：

- **Q1（A↔C）约束有用**：lift 1.32→1.48、残差 0.62→0.27，相似用户显著更倾向
  同簇；代价是划分更模糊（PC↓PE↑），即"几何紧凑 vs 社会相似"的固有权衡，
  可作 β 敏感性分析的动机；
- **Q2（B↔C）字段扩充全面更优**：C 在 PC/PE/XB/silhouette/CH/DB/lift 七项全胜，
  仅残差略高（0.270 vs 0.227，新约束 s 分布更分散所致）；
- 簇结构宏观一致（C 组 [1926,105,591,2189,1220] 与 B 组排列后相同），
  字段扩充改善的是簇质量而非推翻簇结构；
- ⚠️ 与 Roberts 预聚类标签 ARI≈0.016，几乎不相关（其按原始负荷曲线聚类，
  目标不同）——只能作背景参照，**不可作准确性证据**；
- 工程记录：C 组最大连通块 5,039 户（84% 样本），单轮 QP ~2.6s（求解器复用后），
  单 seed 收敛约 3~4 分钟；全部 run 通过 checkpoint 断点续跑完成。

## D 组实验结果（2026-09-12，完整版式6 = C 的约束 + 负约束，串行 DBCD）

三 seed 稳定性：ARI = 1.0（seed0↔1）、0.9565（seed0↔2、seed1↔2）——高度稳定。
下表为 seed_0（其余 seed 指标见各 metrics.json，组内差异 <0.01）：

**负约束分离效果（核心证据，对 59,760 对 cannot-link 对子统计）**

| 指标 | C 组（仅正约束） | D 组（正+负） | 随机基线 |
|---|---|---|---|
| 负对同簇率 ↓ | 0.305 | **0.165** | 0.269 |
| 负对隶属度内积 ↓ | 0.300 | **0.161** | — |
| 负约束残差 ↓ | 0.136 | **0.069** | — |

**正约束与内部指标（代价评估）**

| 指标 | C 组 | D 组 | 方向 |
|---|---|---|---|
| 正约束 lift | 1.475 | **1.541** | ↑ |
| 正约束残差 | 0.270 | **0.266** | ↓ |
| PC / PE | 0.507 / 0.909 | 0.503 / 0.915 | 基本不变 |
| silhouette | **0.433** | 0.393 | ↑ |
| CH | **9602** | 8836 | ↑ |
| XB / DB | **0.298** / **0.821** | 0.397 / 0.857 | ↓ |
| 簇规模 | [1926,105,591,2189,1220] | [1792,133,705,2077,1324] | 结构微调 |

**Q3 结论（C↔D）负约束有效且代价小**：cannot-link 对子同簇率 30.5%→16.5%
（远低於随机基线 26.9%）、隶属度内积减半——"推远"真实发生；正约束满足度
反而更好（lift 1.475→1.541）；特征空间紧凑度仅轻微下降（silhouette −0.04）。
C vs D 这组消融即论文中"负约束有用"的直接证据。

工程记录：正+负边合并后全图 1 个连通块（6,031 户），v2 块切分失效；
串行 DBCD（`code/ssfpc_v3_negative_constraints/ssfpc_v3.py`）约 4s/外层迭代、200 轮上限
到达时目标函数尾部已在 fp32 噪音水平（相对变化 ~1e-7，视为收敛）；
三 seed 的 `objective_ascents` 均为 0（BCD 单调性成立）；
POSITIVE_ONLY 模式已与 v2 OSQP 解对照验证（mean|ΔU|=5.7e-8）。
