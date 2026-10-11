# ssfpc_v2_正约束特例（当前工作版本）

SSFPC（Wang et al. 2022, IEEE TFS）的正约束特例实现。
完整推导链、与论文/官方代码的偏差声明、正定性定理见
**[SSFPC构造说明.md](SSFPC构造说明.md)**。

## 运行

```bash
# 项目根目录，yolo 环境；Git Bash 下必须先：
export POLARS_SKIP_CPU_CHECK=1
python 代码/ssfpc_v2_正约束特例/ssfpc.py
```

输入：`data/output/features_std.npy` + `代码/dispose/output/constraints_gower.parquet`。
输出：`output/`（U.npy / centers.npy / labels.npy / objective.csv / run_meta.json）。

## 与 v1（代码/ssfpc_v1_初版，冻结）的差异

1. **因子 2 修复**：QP 矩阵 P = blkdiag_j(2·diag(d_·j) + β·L)，
   ½uᵀPu 与论文式 (5) 严格同口径；v1 标称 β 实为论文口径 2 倍；
2. 启动时逐块拉普拉斯 λ_min 正定性验证（写入 run_meta.json["pd_check"]）；
3. 空簇防护、L 矩阵缓存。

## 与已有工作的关系（先例梳理，写作定位用）

"只保留正约束"并非我们的新构造，而是已有成熟路线的一个实例：

- 正约束特例目标 Σd·u² + (β/2)Σs‖u_p−u_q‖² 的第二项即约束图
  拉普拉斯正则 uᵀ(βL)u，等价于 **拉普拉斯正则化的 FCM**，该路线早有先例：
  - Grira et al. 2005：must-link 对修正隶属度的半监督模糊聚类（早期代表）；
  - MMRFCM（Information Sciences, 2023）：must-link 对要求隶属度
    "位于同一流形且彼此接近"，即 s‖u_p−u_q‖² 项的几何表述；
  - 约束分类学综述（Springer AIR, 2024）将 fuzzy must-link
    （带置信度的正约束，即本实现的 s∈(0,1]）列为标准设置，
    最早见 Díaz-Valenzuela et al. 2015。
- **Wang 2022 的真正创新点恰是被本特例删除的部分**：负模糊约束
  （s<0，用内积而非 L2）及为其服务的整套机制（CQPP、BᵀDB 检查、
  DBCD 迭代）。正约束分支在原文中是"简单情形"。

**对论文写作的定位**：

- ✅ 优势：凸性、唯一全局解、单调收敛有现成理论背书；
  "为何不用完整版"的标准答案——约束由画像相似度自动生成、
  天然非负，负分支机制不适用。
- ⚠️ 代价：聚类算法本身不能作为创新点宣称；创新点必须落在
  ① 约束的自动生成（demographic 画像 → Gower → s_pq 权重图，
  即"社会信息过滤"）与 ② 电力零售推荐场景的端到端落地。
- 📌 相关工作一节应引出上述先例线，说明本实现 =
  SSFPC 正约束特例 ≈ 拉普拉斯正则 FCM。

## 验证记录（β=0.1, k=5, seed=0）

168 轮收敛，141s；目标函数 6027.73→3352.01，168 步 0 次上升；
22 块 λ_min 全部 ≥ 0；隶属度行和偏差 7.8e−16；
簇规模 [1939, 110, 599, 2140, 1243]。（fp64 时代记录）

## 2026-09-11 性能与接口变更

- **fp64 → fp32**（消费级显卡 fp64 吞吐 1/64），TOL 1e-6 → 1e-5；
  数值轨迹与 fp64 留档有末位差异，簇结构不变；
- **BlockQPSolver**：块 QP setup 一次，之后 update(Px 对角值)+热启动，
  与逐轮新建逐位等价（验证 max|Δu|=5.6e-16）；
- **run_ssfpc() 可复用接口**：供 `代码/checking/run_compare.py` 调用；
  支持 checkpoint 断点续跑（checkpoint.npz）与 max_seconds 限时优雅退出；
  β=0 时全部样本走式 (14) 闭式（数学上即纯 FCM，用作对照组 A）；
- 聚类效果评估统一走 **`代码/checking/`**（evaluate.py），
  三组对照结果见 `代码/checking/README.md` 与 `output/summary.csv`。
