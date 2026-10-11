# dispose/ — 社会画像 → 成对约束 s_pq 生成

SSFPC 第二层的"社会信息过滤"入口：由 demographic 画像自动生成模糊成对约束。

## 文件

- `similarity.py` — 约束生成脚本（**v2 扩展字段版**，2026-09-11；
  2026-09-12 加 `EMIT_NEGATIVE` 开关，见下「负约束输出」）
- `output/` — v2 当前正约束输出（SSFPC 聚类的实际输入）
- `output_negative/` — 负约束输出（2026-09-12，供 v3 完整版式 6）
- `output_v1_gower15字段/` — v1（15 字段）输出留档，供对照组 B 使用

## v2 字段口径（36 个字段）

- **全量字段 21 个**：有序（推断收入/燃气用量 LOW-MED-HI）、名义（房型、
  气候区、CENSUS_GROUP_CODE 606 值）、二值（12 个 HAS_*/IS_*，含
  HAS_INTERNET_ACCESS）、计量配置计数 4 个（按极差归一）；
- **地理分层复合字段**：同 suburb=1.0 / 同 LGA=0.67 / 同 region=0.33 / 否则 0；
- **问卷字段 12 个**（约 23% 用户作答，Gower δ 机制：任一方缺失则不计分）：
  数值 6（居住人数/儿童/70+老人/冰箱数/供暖房间数）、有序 3（自报收入/
  烘干机使用/节电意愿，DeclinedToAnswer 按缺失）、名义 3（4 档房型/空调类型/
  有无儿童）；
- **排除**（防约束与聚类特征同源）：负荷衍生字段
  （ASSRTD_ELECTRICITY_USE_GRP_CD/eDaily/peakTime/cluster_*）、试验分组字段、
  日期/产品码、HAS_AGREED_TO_SMS（噪音）。

## 输出与统计（run_meta.json 为准）

| 版本 | 约束对 | 连通块 | s 唯一值 | 满分平局 | 负值占比 |
|---|---|---|---|---|---|
| v1（15 字段） | 54,473 | 22（最大 1,820） | 少数离散档 | 3.1% | ~0% |
| **v2（36 字段）** | 42,927 | 21（最大 5,039） | 79,196 | 0.21% | 20.7%（截断为 unknown） |

- 映射 s_pq=2S−1∈[−1,1]，S_THRESHOLD=0（只留非负约束保 QP 凸性）+ 对称 Top-K(10)；
- 注意：Top-K 选边下负值本就不会入选（每户第 10 名 s≈0.52）。

## 负约束输出（`EMIT_NEGATIVE=True`，2026-09-12，已落地不再是 future work）

- 选边规则：s<0 且每行取 s 最小的 Bottom-M(10) 个，对称并集；
  字段口径与正约束 v2 完全相同（只改选边规则，控制变量）；
- 输出 `output_negative/`：`constraints_gower_negative.parquet`（59,760 对，
  s∈[−0.871, −0.000]）+ `customer_ids.npy` + `run_meta.json`；
- 每户负值对统计（全图）：中位数 828 / 均值 1,246 个，≥10 个负值对的用户
  占 99.6%——Bottom-10 对几乎所有用户成立；
- ⚠️ 耦合效应：正+负边合并后全图 1 个连通块（6,031 户），v2 的按块切分
  在 v3 失效；BOTTOM_M=10 与 TOP_K 同取 10 仅为控制变量，后续可调小。

## 运行（项目根目录，yolo 环境）

```bash
export POLARS_SKIP_CPU_CHECK=1   # Git Bash 必需
python 代码/dispose/similarity.py   # EMIT_NEGATIVE=True 时同时写 output/ 与 output_negative/
```

下游：`代码/ssfpc_v2_正约束特例/ssfpc.py` 读 `output/constraints_gower.parquet`；
`代码/ssfpc_v3_负约束/ssfpc_v3.py` 读正+负两份（完整版式 6）；
对照组 B 读 `output_v1_gower15字段/constraints_gower.parquet`。
字段级说明另见 `data/README.md` 第四节。
