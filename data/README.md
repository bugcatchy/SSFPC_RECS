# data/ 目录说明

> 本目录存放项目使用的智能电表数据集及其索引文件。
> 文档更新于 2026-09-11，基于对实际文件的检查结果。

## 一、数据来源

- **数据集**：Clustered residential electricity load profiles from Smart Grid Smart City dataset
- **发布平台**：Mendeley Data，DOI: 10.17632/zm4f727vvr.1
- **发布者**：Mike Roberts, Navid Haghdadi, Anna Bruce, Iain MacGill（UNSW）
- **发布时间**：2019-01-31（Version 1）
- **原始数据**：澳大利亚 AusGrid Smart Grid Smart City（SGSC）项目客户试验数据（2014 年于 data.gov.au 公开）

**与本项目复刻对象（Luo et al. 2019, IEEE TSG）的关系**：原论文使用 SGSC 项目
的 1,000 户居民数据（2013-01 至 2014-01，其参考文献 [30] 为 SGSC 官网）。本数据集
是同一项目数据的**清洗版**：剔除了全年数据完整率不足 90% 的用户、排除了受 SGSC
需求响应试验显著影响的用户、填补了缺失值。因此本数据集与原论文**同源但不完全等同**，
实验对比应以本数据集上自跑的复现基线为准，不能直接引用原论文报告的数值。

引用格式：

```
Roberts, Mike; Haghdadi, Navid; Bruce, Anna; MacGill, Iain (2019),
"Clustered residential electricity load profiles from Smart Grid Smart City dataset",
Mendeley Data, V1, doi: 10.17632/zm4f727vvr.1
```

## 二、文件清单

```
data/
├── README.md                     # 本说明
├── zm4f727vvr-1.zip              # 原始下载压缩包（217 MB，解压后可删除）
├── convert_to_parquet.py         # CSV → parquet 转换脚本（见「转换脚本与依赖」）
├── load_features.py              # 负荷特征提取脚本（见「预处理产物」小节）
├── interval load data/
│   ├── data_3_groups.csv         # 主数据：负荷数据（990 MB，原始 CSV）
│   └── data_3_groups.parquet     # 主数据：转换产物（211 MB，推荐日常使用）
├── index files/
│   ├── cluster_index.csv                 # 用户聚类标签索引（原始 CSV，含 #N/A 缺失）
│   ├── cluster_index.parquet             # 聚类标签索引（转换产物，20 KB）
│   ├── demographic_lookup_3_groups.csv   # 用户人口统计信息表（原始 CSV）
│   ├── demographic_lookup_3_groups.parquet  # 用户人口统计信息表（转换产物，165 KB）
│   ├── Column Mappings.csv               # 人口统计表的字段数据字典（原始 CSV）
│   └── Column Mappings.parquet           # 字段数据字典（转换产物，26 KB）
└── output/                       # 负荷特征预处理产物（load_features.py 生成）
    ├── load_features.parquet     # 每户一行：customer_ID + 5 个原始特征
    ├── features_std.npy          # z-score 标准化特征矩阵 6,031×5（SSFPC 的 X）
    ├── customer_ids.npy          # 行序号 → customer_ID（与画像约束行序一致）
    └── load_meta.json            # 口径与统计留痕
```

> **用户相似度约束（s_pq）的输出不在本目录**：由 `代码/dispose/similarity.py`
> 生成，暂存于代码侧 **`代码/dispose/output/`**（正约束：constraints_gower.parquet、
> constraints_cosine.parquet、customer_ids.npy、run_meta.json；旧 15 字段版
> 留档于 `代码/dispose/output_v1_gower15字段/`）；**负约束（s<0，Bottom-10
> 选边，59,760 对，2026-09-12 起）输出至 `代码/dispose/output_negative/`**。
> 字段口径与统计见本文第四节 demographic 表的「用途参考」。

### 转换产物：data_3_groups.parquet

- **格式**：Apache Parquet（列式），压缩 zstd，单文件 211 MB（约原 CSV 的 1/5）。
- **结构与 CSV 完全一致**：17,520 行 × 6,032 列；`timestamp` 为
  `Datetime(us)`（2013-01-01 00:00 至 2013-12-31 23:30，无缺失），
  6,031 个用户列均为 `Float64`；全表无缺失值（该数据集为清洗版）。
- **生成方式**：运行转换脚本 `data/convert_to_parquet.py`（依赖与命令见下方
  「转换脚本与依赖」小节），全程约 5 秒，可用 `--force` 覆盖重建。
- **读取示例**：

  ```python
  import polars as pl
  df = pl.read_parquet("data/interval load data/data_3_groups.parquet")

  import pandas as pd
  df = pd.read_parquet("data/interval load data/data_3_groups.parquet")
  ```

  用户列为数值型 customer_ID（如 `10006630`），读取时注意避免 pandas
  将其与行索引混淆。

### 转换脚本与依赖：data/convert_to_parquet.py

- **位置**：`data/convert_to_parquet.py`（与主数据同目录）。
- **依赖**：仅需 Python 3 + `polars` 一个第三方包（不需要 pandas/pyarrow）。
  本机已验证环境：miniconda3 的 `yolo` 环境（Python 3.10 + polars 1.41.2）。
- **如何运行**（在项目根目录执行）：

  ```bash
  python data/convert_to_parquet.py                 # 默认：CSV → parquet
  python data/convert_to_parquet.py --force         # 目标已存在时覆盖重建
  python data/convert_to_parquet.py --src <csv路径> --dst <parquet路径>
  ```

- **行为说明**：polars 流式转换（`scan_csv` + `sink_parquet`），990 MB CSV
  转换全程内存占用低、约 5 秒；`timestamp` 解析为 `Datetime(us)`，6,031 个
  用户列统一为 `Float64`，压缩用 zstd（level 6）。

### 预处理产物：data/output/（load_features.py）

- **作用**：从 30 分钟原始负荷提取 Luo et al. (2019, IEEE TSG) Table I 的
  5 维用电行为特征（月均用电量、夏+冬季月均、春+秋季月均、工作时间周均、
  非工作时间周均；季节按南半球划定，工作时间取澳大利亚标准工时
  周一至周五 9:00–17:00），z-score 标准化后作为 SSFPC 聚类的输入矩阵 X。
- **如何运行**（项目根目录，yolo 环境；Git Bash 下先
  `export POLARS_SKIP_CPU_CHECK=1`）：

  ```bash
  python data/load_features.py
  ```

- **输出**：`load_features.parquet`（每户 5 个原始特征）、
  `features_std.npy`（6,031×5 标准化矩阵）、`customer_ids.npy`、
  `load_meta.json`（口径与统计留痕）。

## 三、主数据：interval load data/data_3_groups.csv

| 属性 | 值 |
|---|---|
| 规模 | 17,520 行 × 6,032 列 |
| 行含义 | 每行一个 30 分钟时间点，2013-01-01 00:00 至 2013-12-31 23:30（365 天 × 48 点，完整无缺） |
| 列含义 | 第 1 列 `timestamp`；其余 6,031 列各为一个用户，列名为 `customer_ID` |
| 数值含义 | 该用户在该 30 分钟间隔的用电量 |
| 时间分辨率 | 30 分钟 |

**使用注意**：原始 CSV 是 990 MB 宽表，pandas 全量读取约需十几秒并占用数 GB 内存。
**日常使用请直接读取已转换的 `data_3_groups.parquet`**（见上节：读取秒级、内存低、
体积 211 MB）。如需重建 parquet，运行转换脚本（见上文「转换脚本与依赖」小节）。
CSV 仅在重新转换时读取，实验代码一律以 parquet 为输入。

## 四、索引文件

> 三个索引 CSV 均已转换为同名 `.parquet` 转换产物（zstd 压缩），日常读取请
> 直接用 parquet，列结构、行数与 CSV 完全一致；`cluster_index.csv` 中的
> `#N/A` 在 parquet 中已正确转为 null（读取 CSV 时需 `null_values=["#N/A"]`）。
> 重建命令示例：
> `python -c "import polars as pl; pl.read_csv('data/index files/cluster_index.csv', null_values=['#N/A']).write_parquet('data/index files/cluster_index.parquet')"`
> （`demographic_lookup_3_groups.csv` 与 `Column Mappings.csv` 去掉 `null_values` 参数即可）

### cluster_index.csv

- 列：`customer_ID` + 6 个聚类标签列（`3a`、`3h`、`3u`、`ca`、`ch`、`cu`），
  即 Roberts 团队按"3 组分类法"（公寓/住宅/单元等）预先做好的聚类编号，含 `#N/A` 缺失值。
- 用途参考：可作为外部对照标签，非本项目 FCM 聚类的输入。

### demographic_lookup_3_groups.csv

- 每户一行，数十个字段，包括：收入分组（`HHOLD_INCOME_GROUP_CD` /
  `ASSRTD_HHOLD_INCOME_GROUP_CD`）、房型（`DWELLING_TYPE_CD`）、居住人数
  （`NUM_OCCUPANTS`）、有无空调/泳池/太阳能/燃气、邮编、地方政府区域、
  日均用电量（`eDaily`）、用电峰值时刻（`peakTime`）等。
- 用途参考：可用于特征工程的补充、分层分析；**第二层主创新的辅助信息来源
  （2026-08-27 定，2026-09-11 已实现）**——已编码为"社会画像向量"并生成
  SSFPC 成对约束 s_pq，生成脚本为 `代码/dispose/similarity.py`（v2 扩展字段版），
  输出暂存于代码侧 `代码/dispose/output/`（constraints_gower.parquet 等；
  旧 15 字段版留档于 `代码/dispose/output_v1_gower15字段/`），
  后续可考虑迁回本目录，暂维持现状。
  - v2 使用 36 个字段：21 个全量字段（含地理分层 suburb/LGA/region 复合计分、
    CENSUS_GROUP_CODE、计量配置计数、HAS_INTERNET_ACCESS）+ 12 个问卷字段
    （约 23% 作答，Gower δ 机制处理缺失）；
  - 排除源自负荷曲线的字段（`ASSRTD_ELECTRICITY_USE_GRP_CD`、`eDaily`、
    `peakTime`、`cluster_*`）与试验分组字段（`TRIAL_CUSTOMER_TYPE`、
    `CONTROL_GROUP_FLAG`），防止约束与聚类特征同源重复计入；
  - 效果：s=2S−1 的唯一取值从少数离散档提升到 79,196 个，满分平局
    3.1%→0.21%，20.7% 对子为负值；
  - **负约束已启用（2026-09-12）**：`EMIT_NEGATIVE=True` 时另按
    Bottom-M(10) 选边输出 s<0 的 cannot-link 对子至
    `代码/dispose/output_negative/`（59,760 对），供完整版式 6 求解器
    `代码/ssfpc_v3_负约束/`（串行 DBCD）使用；每户负值对中位数 828 个。

### Column Mappings.csv

- SGSC 原始数据库的字段数据字典（字段名、含义、类型、来源表）。

## 五、已知事项与备忘

- 数据年份为 2013 年（SGSC 项目采集期）。居民用电公开数据集因隐私限制普遍较老
  （Irish CER 2009-2010、Low Carbon London 2011-2014 同理），方法类研究对此无影响；
  且复刻对比要求与原论文使用同源数据，故该数据集为正确选择。
- 用户列为数值型 customer_ID（如 `10006630`），读取时注意避免 pandas 将其与
  行索引混淆。
- 用电量数值的单位口径（kWh/间隔）以 Mendeley 页面描述为准，
  正式写入论文前建议再次核对原始页面说明。
