# -*- coding: utf-8 -*-
"""
run_compare.py — 三组对照实验: β=0(纯FCM) / v1旧约束(15字段) / v2新约束(36字段)

回答两个问题:
  Q1 (① vs ③): 加画像约束对聚类有没有用?
  Q2 (② vs ③): 相似度字段扩充 (15→36) 有没有用?

配置 (k=5, 每组 3 个 seed):
  A_fcm       β=0,  无约束 (数学上 = 纯 FCM)
  B_gower15   β=0.1, 代码/dispose/output_v1_gower15字段/constraints_gower.parquet
  C_gower36   β=0.1, 代码/dispose/output/constraints_gower.parquet   ← 新相似度

每个收敛的 run: 写出到 output/<config>/seed_<i>/ 并立即评估 (metrics.json),
汇总行追加到 output/summary.csv; 同配置 seed 间两两 ARI 作稳定性指标。

限时/续跑: --max-seconds 控制单次进程时长, 未收敛自动存 checkpoint,
重复执行同一命令即可续跑直到全部收敛。

运行 (项目根目录, yolo 环境; Git Bash 先 export POLARS_SKIP_CPU_CHECK=1):
  python 代码/checking/run_compare.py                    # 全部配置
  python 代码/checking/run_compare.py --only C_gower36   # 只跑一组
"""
from __future__ import annotations

import argparse
import csv
import itertools
import json
import sys
import time
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "代码/ssfpc_v2_正约束特例"))
sys.path.insert(0, str(ROOT / "代码/checking"))

from ssfpc import run_ssfpc            # noqa: E402
from evaluate import evaluate_run, contingency_ari_nmi  # noqa: E402

FEATURES = ROOT / "data/output/features_std.npy"
OUTPUT_DIR = Path(__file__).resolve().parent / "output"
SUMMARY_CSV = OUTPUT_DIR / "summary.csv"

K = 5
BETA = 0.1
SEEDS = [0, 1, 2]
CONFIGS = {
    "A_fcm": {"beta": 0.0,
              "constraints": ROOT / "代码/dispose/output/constraints_gower.parquet"},
    "B_gower15": {"beta": BETA,
                  "constraints": ROOT / "代码/dispose/output_v1_gower15字段/constraints_gower.parquet"},
    "C_gower36": {"beta": BETA,
                  "constraints": ROOT / "代码/dispose/output/constraints_gower.parquet"},
}

SUMMARY_FIELDS = [
    "config", "seed", "k", "beta", "iters", "final_obj", "elapsed_sec",
    "cluster_sizes", "PC", "PE", "XB", "silhouette", "CH", "DB",
    "same_cluster_rate", "lift", "residual",
    "ARI_ca", "NMI_ca", "ARI_3a", "NMI_3a",
]


def load_constraints(path: Path):
    import polars as pl
    cons = pl.read_parquet(path)
    return (cons["idx_p"].to_numpy(), cons["idx_q"].to_numpy(),
            cons["s_pq"].to_numpy())


def flatten_metrics(m: dict) -> dict:
    ext = m.get("external_vs_roberts", {})
    return {
        "config": m.get("config"), "seed": m.get("seed"), "k": m.get("k"),
        "beta": m.get("beta"), "iters": m.get("iters"),
        "final_obj": m.get("final_obj"), "elapsed_sec": m.get("elapsed_sec"),
        "cluster_sizes": m.get("cluster_sizes"),
        "PC": m["fuzzy_internal"]["PC"], "PE": m["fuzzy_internal"]["PE"],
        "XB": m["fuzzy_internal"]["XB"],
        "silhouette": m["hard_internal"]["silhouette"],
        "CH": m["hard_internal"]["CH"], "DB": m["hard_internal"]["DB"],
        "same_cluster_rate": m["constraint_metrics"]["constrained_same_cluster_rate"],
        "lift": m["constraint_metrics"]["same_cluster_lift"],
        "residual": m["constraint_metrics"]["constraint_residual_mean_s_du2"],
        "ARI_ca": ext.get("ca", {}).get("ARI"), "NMI_ca": ext.get("ca", {}).get("NMI"),
        "ARI_3a": ext.get("3a", {}).get("ARI"), "NMI_3a": ext.get("3a", {}).get("NMI"),
    }


def append_summary(row: dict) -> None:
    exists = SUMMARY_CSV.exists()
    with SUMMARY_CSV.open("a", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=SUMMARY_FIELDS)
        if not exists:
            w.writeheader()
        w.writerow(row)


def stability_ari(output_dir: Path, config: str) -> dict | None:
    """同配置不同 seed 的两两标签 ARI (稳定性)"""
    Us = []
    for sd in SEEDS:
        f = output_dir / config / f"seed_{sd}" / "U.npy"
        if f.exists():
            Us.append(np.load(f).argmax(axis=1))
    if len(Us) < 2:
        return None
    aris = [contingency_ari_nmi(a, b)[0] for a, b in itertools.combinations(Us, 2)]
    return {"config": config, "seed_pair_ARI": [round(a, 4) for a in aris],
            "ARI_mean": round(float(np.mean(aris)), 4),
            "ARI_std": round(float(np.std(aris)), 4)}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", choices=list(CONFIGS), default=None)
    ap.add_argument("--max-seconds", type=float, default=270.0,
                    help="单个 run 的进程限时 (到点存 checkpoint 退出, 再执行本脚本即续跑)")
    args = ap.parse_args()

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    X = np.load(FEATURES)
    print(f"[setup] X {X.shape}, k={K}, seeds={SEEDS}")

    pending = []
    for name, cfg in CONFIGS.items():
        if args.only and name != args.only:
            continue
        p, q, s = load_constraints(cfg["constraints"])
        for seed in SEEDS:
            run_dir = OUTPUT_DIR / name / f"seed_{seed}"
            if (run_dir / "metrics.json").exists():
                print(f"[skip] {name}/seed_{seed} 已完成")
                continue
            t0 = time.perf_counter()
            print(f"[run] {name}/seed_{seed}  β={cfg['beta']} 约束={cfg['constraints'].parent.name}")
            meta = run_ssfpc(X, p, q, s, K, cfg["beta"], seed,
                             max_iter=500, out_dir=run_dir,
                             max_seconds=args.max_seconds)
            if not meta["converged"]:
                pending.append(f"{name}/seed_{seed}")
                print(f"  未收敛, 已存 checkpoint -> 再执行本脚本续跑")
                continue
            m = evaluate_run(run_dir, cfg["constraints"], verbose=False)
            m["config"] = name
            append_summary(flatten_metrics(m))
            print(f"  收敛 iter={meta['iters']}, obj={meta['final_obj']:.2f}, "
                  f"簇规模={meta['cluster_sizes']}, 耗时={time.perf_counter()-t0:.0f}s")

    # 稳定性: 同配置 seed 间 ARI
    stab = [r for name in CONFIGS if (r := stability_ari(OUTPUT_DIR, name))]
    (OUTPUT_DIR / "stability.json").write_text(
        json.dumps(stab, ensure_ascii=False, indent=2), encoding="utf-8")
    if stab:
        print("[stability]", json.dumps(stab, ensure_ascii=False))

    if pending:
        print(f"\n未完成的 run: {pending}\n重复执行本命令继续。")
    else:
        print(f"\n全部完成, 汇总: {SUMMARY_CSV}")


if __name__ == "__main__":
    main()
