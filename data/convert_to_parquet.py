# -*- coding: utf-8 -*-
"""
将宽表 CSV（6,031 用户 × 17,520 时刻）流式转换为单个宽表 parquet。

用法（在项目根目录运行，需要 Python 3 + polars）：
    python data/convert_to_parquet.py [--src <csv路径>] [--dst <parquet路径>] [--force]

默认输入：data/interval load data/data_3_groups.csv
默认输出：data/interval load data/data_3_groups.parquet

要点：
- 使用 polars 惰性扫描（scan_csv）+ 流式写出（sink_parquet），
  990 MB CSV 转换时内存占用很小（数十 MB 量级），不要求整表装入内存。
- 用户列显式统一为 Float64（用电量，含缺失值 null）；
  timestamp 解析为 Datetime("us")。
- 压缩默认 zstd（polars 默认），体积通常可缩小到原 CSV 的 1/3 左右。
"""
from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

import polars as pl

TIMESTAMP_FORMAT = "%Y-%m-%d %H:%M:%S"

DEFAULT_SRC = Path("data/interval load data/data_3_groups.csv")
DEFAULT_DST = Path("data/interval load data/data_3_groups.parquet")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="宽表 CSV → 宽表 parquet（流式，低内存）"
    )
    parser.add_argument("--src", type=Path, default=DEFAULT_SRC, help="输入 CSV 路径")
    parser.add_argument("--dst", type=Path, default=DEFAULT_DST, help="输出 parquet 路径")
    parser.add_argument(
        "--force",
        action="store_true",
        help="目标文件已存在时覆盖（默认拒绝，避免误覆盖）",
    )
    return parser.parse_args()


def build_schema(csv_path: Path) -> dict[str, pl.DataType]:
    """只读表头，构造全列 schema：timestamp 为字符串，其余用户列为 Float64。"""
    meta = pl.read_csv(csv_path, n_rows=0)
    cols = meta.columns
    if not cols or cols[0] != "timestamp":
        raise ValueError(f"表头异常，首列应为 timestamp，实际为: {cols[:3]}")
    schema = {"timestamp": pl.Utf8}
    schema.update({c: pl.Float64 for c in cols[1:]})
    return schema


def convert(csv_path: Path, dst_path: Path, force: bool = False) -> None:
    if dst_path.exists() and not force:
        print(f"[跳过] 目标已存在: {dst_path}（加 --force 覆盖）")
        return

    print(f"[1/3] 读取表头，构造 schema（{csv_path}）…")
    schema = build_schema(csv_path)
    print(f"      列数: {len(schema)}（1 个 timestamp + {len(schema) - 1} 个用户列）")

    print("[2/3] 流式解析 CSV 并写出 parquet…")
    lazy = pl.scan_csv(
        csv_path,
        schema=schema,
        try_parse_dates=False,   # timestamp 稍后按明确格式解析
        low_memory=True,
    )
    lazy = lazy.with_columns(
        pl.col("timestamp").str.to_datetime(TIMESTAMP_FORMAT, strict=False)
    )
    lazy.sink_parquet(dst_path, compression="zstd", compression_level=6)

    print(f"[3/3] 完成: {dst_path}")
    print(f"      大小: {dst_path.stat().st_size / 1e6:.1f} MB")


def main() -> None:
    a = parse_args()
    if not a.src.exists():
        print(f"[错误] 输入文件不存在: {a.src}", file=sys.stderr)
        sys.exit(1)
    t0 = time.perf_counter()
    convert(a.src, a.dst, force=a.force)
    print(f"      耗时: {time.perf_counter() - t0:.1f} s")


if __name__ == "__main__":
    main()
