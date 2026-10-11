# -*- coding: utf-8 -*-
"""
load_features.py — 从 30 分钟原始负荷数据提取 Luo et al. (2019) Table I 的 5 维用电行为特征

输入:  data/interval load data/data_3_groups.parquet  (17,520 时刻 × 6,031 用户, 2013 全年)
输出:  data/output/
       ├── load_features.parquet     # 每户一行: customer_ID + 5 个原始特征
       ├── features_std.npy          # z-score 标准化后的特征矩阵 (6,031×5, SSFPC 的 X)
       ├── customer_ids.npy          # 行序号 -> customer_ID (与画像约束的行序一致)
       └── load_meta.json            # 口径与统计留痕

特征定义 (Luo et al. 2019, IEEE TSG, Table I, 复刻口径):
  f1  avg_monthly          月均用电量            = 全年总电量 / 12
  f2  avg_monthly_sum_win  夏+冬季月均用电量     南半球季节: 夏=12-2月, 冬=6-8月
  f3  avg_monthly_spr_aut  春+秋季月均用电量     春=9-11月, 秋=3-5月
  f4  avg_weekly_work      工作时间周均用电量    工作日(周一至周五) 09:00-17:00
  f5  avg_weekly_nonwork   非工作时间周均用电量  其余时间(晚间+周末)

  季节按南半球划定; 工作时间取澳大利亚标准工时周一至周五 9:00-17:00
  (NES 标准全职 38 小时/周, 常见 spread 9am-5pm)。

运行 (项目根目录, yolo 环境; Git Bash 下先 export POLARS_SKIP_CPU_CHECK=1):
  python data/load_features.py
"""
from __future__ import annotations

import json
import time
from pathlib import Path

import numpy as np
import polars as pl

# ============================== CONFIG ==============================
DATA_DIR = Path(__file__).resolve().parent
INPUT_PARQUET = DATA_DIR / "interval load data" / "data_3_groups.parquet"
DEMO_PARQUET = DATA_DIR / "index files" / "demographic_lookup_3_groups.parquet"
OUTPUT_DIR = DATA_DIR / "output"

SUMMER_MONTHS = (12, 1, 2)   # 南半球夏
WINTER_MONTHS = (6, 7, 8)    # 南半球冬
WORK_START_HOUR = 9          # 工作时间 09:00(含) - 17:00(不含)
WORK_END_HOUR = 17
WEEKS_IN_YEAR = 365 / 7
# =====================================================================


def main() -> None:
    t0 = time.perf_counter()
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    print(f"[1/3] 读取负荷主表: {INPUT_PARQUET.name} ...")
    df = pl.read_parquet(INPUT_PARQUET)
    ts = df["timestamp"]
    ids = np.array([int(c) for c in df.columns[1:]], dtype=np.int64)
    X = df.drop("timestamp").to_numpy().astype(np.float64)  # 17,520 × 6,031
    n_ts, n_users = X.shape
    print(f"      {n_ts} 时刻 × {n_users} 用户")

    month = ts.dt.month().to_numpy()
    hour = ts.dt.hour().to_numpy()
    weekday = ts.dt.weekday().to_numpy()  # 0=周一 ... 6=周日

    is_summer = np.isin(month, SUMMER_MONTHS)
    is_winter = np.isin(month, WINTER_MONTHS)
    is_work = (weekday < 5) & (hour >= WORK_START_HOUR) & (hour < WORK_END_HOUR)

    total = X.sum(axis=0)                                # 全年总电量
    f1 = total / 12.0
    f2 = (X[is_summer | is_winter].sum(axis=0)
          / (len(SUMMER_MONTHS) + len(WINTER_MONTHS)))   # 夏冬 6 个月的月均
    f3 = (X[~(is_summer | is_winter)].sum(axis=0) / 6.0) # 春秋 6 个月的月均
    f4 = X[is_work].sum(axis=0) / WEEKS_IN_YEAR          # 工作时间总量按周均
    f5 = X[~is_work].sum(axis=0) / WEEKS_IN_YEAR         # 非工作时间总量按周均

    F = np.column_stack([f1, f2, f3, f4, f5])
    names = ["avg_monthly", "avg_monthly_sum_win", "avg_monthly_spr_aut",
             "avg_weekly_work", "avg_weekly_nonwork"]

    # 对齐到 demographic 表的用户顺序 (约束表 idx 以此为基准)
    demo_ids = pl.read_parquet(DEMO_PARQUET, columns=["customer_ID"])["customer_ID"].to_numpy()
    pos = {int(c): j for j, c in enumerate(ids)}
    order = np.array([pos[int(c)] for c in demo_ids])  # demo 顺序 -> 负荷列位置
    missing = set(int(c) for c in demo_ids) - set(pos)
    if missing:
        raise ValueError(f"{len(missing)} 户在负荷数据中不存在, 例: {list(missing)[:3]}")
    ids, F = ids[order], F[order]

    print("[2/3] 特征矩阵完成, 标准化并写出 ...")
    mu, sd = F.mean(axis=0), F.std(axis=0, ddof=1)
    Z = (F - mu) / sd

    out = pl.DataFrame({"customer_ID": ids} | {nm: F[:, j] for j, nm in enumerate(names)})
    out.write_parquet(OUTPUT_DIR / "load_features.parquet")
    np.save(OUTPUT_DIR / "features_std.npy", Z.astype(np.float32))
    np.save(OUTPUT_DIR / "customer_ids.npy", ids)

    meta = {
        "input": str(INPUT_PARQUET),
        "n_users": int(n_users), "n_timestamps": int(n_ts),
        "feature_names": names,
        "definitions": {
            "seasons": "南半球: 夏=12-2月, 秋=3-5月, 冬=6-8月, 春=9-11月",
            "work_time": "工作日(周一至周五) 09:00-17:00",
            "f2_f3_months": "f2=夏+冬6个月月均, f3=春+秋6个月月均",
            "f4_f5_weeks": WEEKS_IN_YEAR,
        },
        "feature_mean": mu.tolist(), "feature_std": sd.tolist(),
        "check_f4_plus_f5_vs_f1": "f4+f5 与 f1*(12/52.14) 应近似相等",
        "elapsed_sec": round(time.perf_counter() - t0, 1),
    }
    (OUTPUT_DIR / "load_meta.json").write_text(
        json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"[3/3] 完成 ({meta['elapsed_sec']}s) -> {OUTPUT_DIR}")
    print(out.describe())


if __name__ == "__main__":
    main()
