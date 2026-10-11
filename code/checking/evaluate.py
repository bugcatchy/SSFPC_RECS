# -*- coding: utf-8 -*-
"""
evaluate.py — SSFPC 聚类效果评估模块 (无 sklearn 依赖, 全部手实现)

指标分四层 (详见 checking/README.md):
  ① 模糊内部指标: PC (划分系数↑), PE (划分熵↓), XB (Xie-Beni↓)
  ② 硬划分内部指标 (defuzzify 后): silhouette↑, CH (Calinski-Harabasz↑), DB (Davies-Bouldin↓)
  ③ 约束效果: 受约束对同簇率 / 随机基线 = lift↑; 约束残差 mean s‖Δu‖²↓
  ④ 外部参照 (非真值): 与 Roberts cluster_index 6 个标签列的 ARI / NMI

用法 (项目根目录, yolo 环境; Git Bash 先 export POLARS_SKIP_CPU_CHECK=1):
  python code/checking/evaluate.py <run_dir> [--constraints <parquet>]
  # run_dir 内需有 U.npy; 输出 metrics.json 到同目录并打印
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import polars as pl

ROOT = Path(__file__).resolve().parents[2]
FEATURES = ROOT / "data/output/features_std.npy"
DEFAULT_CONSTRAINTS = ROOT / "code/dispose/output/constraints_gower.parquet"
CLUSTER_INDEX = ROOT / "data/index files/cluster_index.parquet"
CUSTOMER_IDS = ROOT / "code/dispose/output/customer_ids.npy"
LABEL_COLS = ["3a", "3h", "3u", "ca", "ch", "cu"]


# ---------------- 基础指标 ----------------

def fuzzy_internal(U: np.ndarray, X: np.ndarray, C: np.ndarray) -> dict:
    """PC / PE / XB (U: n×k, X: n×d, C: k×d)"""
    n, k = U.shape
    u2 = U ** 2
    pc = float(u2.sum() / n)                              # ↑ [1/k, 1]
    with np.errstate(divide="ignore", invalid="ignore"):
        pe = float(-(U * np.log(np.maximum(U, 1e-12))).sum() / n)  # ↓ [0, log k]
    d2 = ((X[:, None, :] - C[None, :, :]) ** 2).sum(axis=2)  # n×k
    numer = float((u2 * d2).sum())
    cd = ((C[:, None, :] - C[None, :, :]) ** 2).sum(axis=2)
    np.fill_diagonal(cd, np.inf)
    xb = numer / (n * float(cd.min()))                    # ↓
    return {"PC": pc, "PE": pe, "XB": xb}


def hard_internal(X: np.ndarray, labels: np.ndarray) -> dict:
    """silhouette / CH / DB (defuzzified 硬标签, numpy 实现)"""
    n = len(labels)
    k = len(np.unique(labels))
    if k < 2:
        return {"silhouette": None, "CH": None, "DB": None}
    # 成对距离 (Gram 展开避免 n×n×d 中间量; 6031² float32 ≈ 145 MB)
    X32 = X.astype(np.float32)
    g = X32 @ X32.T
    sq = np.diag(g).copy()
    D = np.sqrt(np.maximum(sq[:, None] + sq[None, :] - 2.0 * g, 0.0))
    del g
    sizes = np.bincount(labels, minlength=k).astype(np.float64)
    # silhouette: a(i)=簇内均距, b(i)=最近他簇均距
    intra = np.zeros(n, dtype=np.float64)
    inter = np.full((n, k), np.inf, dtype=np.float64)
    for j in range(k):
        m = labels == j
        din = D[:, m].sum(axis=1)
        intra[m] = din[m] / max(sizes[j] - 1, 1)
        inter[:, j] = din / max(sizes[j], 1)
    inter[np.arange(n), labels] = np.inf                  # 排除本簇
    b = inter.min(axis=1)
    sil = float(np.mean((b - intra) / np.maximum(np.maximum(intra, b), 1e-12)))
    # CH / DB
    mu = X.mean(axis=0)
    centers = np.stack([X[labels == j].mean(axis=0) for j in range(k)])
    bg = ((centers - mu) ** 2).sum(axis=1)
    # CH = [组间平方和/(k-1)] / [组内平方和/(n-k)]
    sse = float(sum(((X[labels == j] - centers[j]) ** 2).sum() for j in range(k)))
    ch = float(((sizes * bg).sum() / (k - 1)) / max(sse / (n - k), 1e-12))
    scat = np.sqrt(np.array([((X[labels == j] - centers[j]) ** 2).sum() / max(sizes[j], 1)
                             for j in range(k)]))
    cd = np.sqrt(((centers[:, None, :] - centers[None, :, :]) ** 2).sum(axis=2))
    np.fill_diagonal(cd, np.inf)
    R = (scat[:, None] + scat[None, :]) / cd
    np.fill_diagonal(R, -np.inf)
    db = float(R.max(axis=1).mean())
    return {"silhouette": sil, "CH": ch, "DB": db}


def contingency_ari_nmi(a: np.ndarray, b: np.ndarray) -> tuple[float, float]:
    """ARI / NMI (numpy 手实现, a/b 为等长硬标签)"""
    _, ai = np.unique(a, return_inverse=True)
    _, bi = np.unique(b, return_inverse=True)
    na, nb = ai.max() + 1, bi.max() + 1
    n = len(a)
    tab = np.zeros((na, nb), dtype=np.float64)
    np.add.at(tab, (ai, bi), 1)
    comb = lambda x: x * (x - 1) / 2.0
    sum_ij = comb(tab).sum()
    sum_a = comb(tab.sum(axis=1)).sum()
    sum_b = comb(tab.sum(axis=0)).sum()
    total = comb(n)
    expected = sum_a * sum_b / total if total else 0.0
    maxidx = (sum_a + sum_b) / 2.0
    ari = (sum_ij - expected) / (maxidx - expected) if maxidx != expected else 1.0
    # NMI (算术平均归一化)
    pa = tab.sum(axis=1) / n
    pb = tab.sum(axis=0) / n
    with np.errstate(divide="ignore", invalid="ignore"):
        ha = -(pa[pa > 0] * np.log(pa[pa > 0])).sum()
        hb = -(pb[pb > 0] * np.log(pb[pb > 0])).sum()
        pij = tab / n
        m = pij > 0
        mi = float((pij[m] * np.log(pij[m] / np.outer(pa, pb)[m])).sum())
    nmi = mi / ((ha + hb) / 2.0) if (ha + hb) > 0 else 1.0
    return float(ari), float(nmi)


def constraint_metrics(U: np.ndarray, p: np.ndarray, q: np.ndarray,
                       s: np.ndarray) -> dict:
    """约束同簇率 lift / 约束残差"""
    lab = U.argmax(axis=1)
    same = (lab[p] == lab[q]).mean()
    sizes = np.bincount(lab, minlength=U.shape[1]).astype(np.float64)
    baseline = float(((sizes / len(lab)) ** 2).sum())     # 随机对同簇期望率
    resid = float((s * ((U[p] - U[q]) ** 2).sum(axis=1)).mean())
    return {
        "constrained_same_cluster_rate": float(same),
        "random_baseline_rate": baseline,
        "same_cluster_lift": float(same / baseline) if baseline > 0 else None,
        "constraint_residual_mean_s_du2": resid,
    }


# ---------------- 主入口 ----------------

def evaluate_run(run_dir: Path, constraints_path: Path = DEFAULT_CONSTRAINTS,
                 verbose: bool = True) -> dict:
    U = np.load(run_dir / "U.npy")
    C = np.load(run_dir / "centers.npy") if (run_dir / "centers.npy").exists() else None
    X = np.load(FEATURES)
    labels = U.argmax(axis=1)

    out: dict = {"run_dir": str(run_dir)}
    meta_path = run_dir / "run_meta.json"
    if meta_path.exists():
        m = json.loads(meta_path.read_text(encoding="utf-8"))
        out.update({"k": m.get("k"), "beta": m.get("beta"), "seed": m.get("seed"),
                    "iters": m.get("iters"), "final_obj": m.get("final_obj"),
                    "cluster_sizes": m.get("cluster_sizes"),
                    "elapsed_sec": m.get("elapsed_sec")})
    if C is None:  # 从 U 重算中心 (式13)
        w = U ** 2
        C = (w.T @ X) / np.maximum(w.sum(axis=0, keepdims=True).T, 1e-12)
    out["fuzzy_internal"] = fuzzy_internal(U, X, C)
    out["hard_internal"] = hard_internal(X, labels)

    cons = pl.read_parquet(constraints_path)
    p = cons["idx_p"].to_numpy(); q = cons["idx_q"].to_numpy(); s = cons["s_pq"].to_numpy()
    out["constraint_metrics"] = constraint_metrics(U, p, q, s.astype(np.float64))

    # 外部参照: Roberts 预聚类标签 (非真值)
    if CLUSTER_INDEX.exists() and CUSTOMER_IDS.exists():
        ids = np.load(CUSTOMER_IDS)
        ref = pl.read_parquet(CLUSTER_INDEX)
        ref_map = {cid: i for i, cid in enumerate(ids)}
        ref = ref.filter(pl.col("customer_ID").is_in(ids.tolist()))
        order = [ref_map[c] for c in ref["customer_ID"].to_numpy()]
        ext = {}
        for col in LABEL_COLS:
            v = ref[col]
            mask = ~v.is_null()
            if mask.sum() < 100:
                continue
            sub_order = np.array(order)[mask.to_numpy()]
            ari, nmi = contingency_ari_nmi(labels[sub_order],
                                           v.filter(mask).to_numpy())
            ext[col] = {"ARI": round(ari, 4), "NMI": round(nmi, 4),
                        "n_labeled": int(mask.sum())}
        out["external_vs_roberts"] = ext

    if verbose:
        print(json.dumps(out, ensure_ascii=False, indent=2))
    (run_dir / "metrics.json").write_text(
        json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("run_dir", type=Path)
    ap.add_argument("--constraints", type=Path, default=DEFAULT_CONSTRAINTS)
    args = ap.parse_args()
    evaluate_run(args.run_dir, args.constraints)


if __name__ == "__main__":
    main()
