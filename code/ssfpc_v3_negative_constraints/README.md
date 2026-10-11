# ssfpc_v3_负约束（Wang 2022 完整版式 6 · 串行 DBCD 正式版）

> 状态：**✅ 已完成三 seed 全量运行**（2026-09-12）。D 组对照结论：**负约束有效
> 且代价小**——cannot-link 对子同簇率 30.5%→16.5%（随机基线 26.9%），正约束
> lift 1.475→1.541，内部指标仅轻微下降；三 seed ARI = 1.0 / 0.9565 / 0.9565。
> 结果归档 `code/checking/output/D_gower36neg/seed_{0,1,2}/`，
> 完整对比表见 `code/checking/README.md`「D 组实验结果」。
> 本目录 `output/` 为 seed_0 原始运行副本，`output_positive_only_vs_v2/`
> 为凸情形验证运行留档。

## 与 v2 的关系

- `code/ssfpc_v2_positive_constraints/`：简化式 (6)，删去负约束分支，块子问题恒严格正定，
  Algorithm 2 塌缩为单次凸 QP（OSQP）。
- 本版本：恢复论文完整版式 (6)——
  - s_pq ≥ 0：C(u_p,u_q) = ½·s_pq·‖u_p−u_q‖²（拉近）
  - s_pq < 0：C(u_p,u_q) = −s_pq·u_pᵀ·u_q（推远）
  - 块子问题不定（实测 λ_min(βM) = −5.21），按论文 Algorithm 2 / 官方 MATLAB 码
    （`code/reference/FDC-main` 的 QPP_IDsolver.m / Solver_x0）用**串行块坐标下降
    （DBCD）**求解。

## 求解方法（严格对齐官方）

逐样本串行（Gauss-Seidel：解完第 i 个立即写回，第 i+1 个用新值），每样本解
k 维子问题（论文式 5/6 口径）：

```
min  Σ_j [d_ij + (β/2)·deg⁺_i]·u_ij² + f_iᵀu_i    s.t. 行和=1, u≥0
deg⁺_i = Σ_{正邻居q} s_iq          （仅正边贡献二次项）
f_i    = −β·Σ_{所有邻居q} s_iq·u_q  （正边→负系数，负边→正系数，统一式）
```

- 二次系数恒正 ⇒ 子问题严格凸 ⇒ **精确水填充解**（active-set 解析法 + 二分兜底，
  不调 OSQP）；不定性只存在于样本间耦合，被 BCD 拆成线性项——这是 DBCD 的数学根基；
- 每次样本更新都是坐标准确最小化 ⇒ 块目标**单调不增**（run_meta 里
  `objective_ascents` 应为 0，>0 说明实现有误）；
- 内层收敛：一轮扫描 ‖ΔU‖₂ < 1e-8（对齐官方），上限 200 轮扫描；
- 大块热启动（与官方 else 分支一致）；官方"顶点遍历"分支仅用于 ≤3 样本微块，
  不移植；
- **非凸问题 BCD 只保证收敛到驻点**，不保证全局最优（论文方法固有性质）。

## 与官方的两处既定偏差（2026-09-10/11 已决策）

1. 不采用官方私加的 **m/|S| 归一化因子**（论文式 18/19 无此项）；
2. 顶点遍历分支不移植（官方自身也仅用于 ≤3 样本块）。

## 数据

- 正约束：`code/dispose/output/constraints_gower.parquet`（Top-10，s≥0，42,927 对）
- 负约束：`code/dispose/output_negative/constraints_gower_negative.parquet`
  （Bottom-10，s<0，59,760 对；similarity.py 开关 `EMIT_NEGATIVE` 控制输出）
- ⚠️ 正+负边合并后全图 1 个连通块（6,031 户），v2 的块切分优化在 v3 失效；
  选边取 10 是为与 v2 控制变量，后续可考虑减小 BOTTOM_M。

## 运行（用户自跑，无超时截断）

```bash
# Git Bash（项目根目录）
export POLARS_SKIP_CPU_CHECK=1
/c/Users/BugCat/miniconda3/envs/yolo/python.exe code/ssfpc_v3_negative_constraints/ssfpc_v3.py

# CMD / PowerShell
set POLARS_SKIP_CPU_CHECK=1
C:\Users\BugCat\miniconda3\envs\yolo\python.exe code\ssfpc_v3_negative_constraints\ssfpc_v3.py
```

- 进度条实时显示：外层迭代 / 内层扫描 / 样本进度 / 已用时 / ETA / obj；
- 冒烟测试实测约 **4 秒/外层迭代**，全程（约 93~200 轮）预计 **6~15 分钟**；
- 输出 `output/`：U.npy / centers.npy / labels.npy / objective.csv / run_meta.json。

## 验证入口（✅ 已通过 2026-09-12）

选择原因：`POSITIVE_ONLY = True` 只用正约束（凸问题），BCD 与 v2 的 OSQP
必须殊途同归。实测（188 轮收敛，obj 3240.5061，留档
`output_positive_only_vs_v2/`）：
- **vs `code/checking/output/C_gower36/seed_0/U.npy`（同约束同参数）：
  mean|ΔU| = 5.7×10⁻⁸，标签一致率 100%** —— 实现正确性确认；
- ⚠️ 注意参照别拿错：`code/ssfpc_v2_positive_constraints/output/` 存的是旧 15 字段
  约束时代的运行（簇规模 [1939,110,599,2140,1243]），与新约束结果本来就不同；
- `objective_ascents` 早期版本报 52 次"上升"系 fp32 噪音（最大相对幅度
  2.7×10⁻⁷），判定阈值已改为相对口径 1e-6。

## 投影版否决记录（2026-09-12，留档）

曾试"对角平移投影 + OSQP"快速验证版：负边使 βM 强不定（λ_min=−5.21），
投影 τ=5.21 的岭项量级远超距离项 O(1)，隶属度被拉向均匀（PC 0.507→0.260，
silhouette 0.433→0.200，退化解）。结论：投影近似在本约束密度下不可用，
恰好印证论文采用 DBCD 的必要性。投影版代码已被本串行版覆盖。

## 实验设计（对照）

在 checking 三组对照（A 纯 FCM / B 旧约束 / C 新约束）基础上加：
- **D 组 = C 的约束 + 负约束**（同 β=0.1、同 k=5、同 seeds），评估负约束增量；
- 指标沿用 `code/checking/evaluate.py` 四层口径
  （`python code/checking/evaluate.py code/ssfpc_v3_negative_constraints/output`）。
