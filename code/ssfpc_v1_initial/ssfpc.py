# -*- coding: utf-8 -*-
"""
ssfpc.py — SSFPC (Wang et al. 2022, IEEE TFS) 主循环, 复刻+落地到电力画像约束

输入:
  data/output/features_std.npy            # X: 6,031×5 标准化负荷行为特征 (Luo 2019 Table I)
  code/dispose/output/constraints_gower.parquet  # 约束表 (idx_p, idx_q, s_pq≥0, 上三角)
  code/dispose/output/customer_ids.npy    # 行号 -> customer_ID

输出: code/main/output/
  ├── U.npy            # 隶属度矩阵 6,031×k
  ├── centers.npy      # 簇中心 k×5 (标准化空间)
  ├── labels.npy       # argmax 硬标签
  ├── objective.csv    # 每轮目标函数值 (式5, 验证单调不增)
  └── run_meta.json

算法 (α=0, 论文式5/6/13/14/15-16, Algorithm 1+2):
  E步: c_j = Σ u_ij² x_i / Σ u_ij²                     (式13)
  M步: 无约束样本 -> 闭式 (式14); 有约束样本 -> 逐连通块凸 QP (式15-16)
  QP 构造 (仅 s≥0, D 恒正定, 无需 DBCD):
    min Σ_iΣ_j d_ij u_ij² + (β/2)Σ_(p,q) s_pq ||u_p-u_q||²
    =>  ½ uᵀHu, H = bdiag_j( diag(d_·j) + β·L ),  L=块内加权图拉普拉斯
    s.t. A u = 1 (每样本行和=1), u ≥ 0

GPU: torch(CUDA) 负责距离/中心/闭式更新; QP 用 OSQP (CPU, 稀疏)。
运行 (项目根目录, yolo 环境; Git Bash 下先 export POLARS_SKIP_CPU_CHECK=1):
  python code/main/ssfpc.py
"""
from __future__ import annotations

import json
import time
from pathlib import Path

import numpy as np
import polars as pl
import scipy.sparse as sp
import torch
import osqp

# ============================== CONFIG ==============================
ROOT = Path(__file__).resolve().parents[2]
FEATURES = ROOT / "data/output/features_std.npy"
CONSTRAINTS = ROOT / "code/dispose/output/constraints_gower.parquet"
IDS = ROOT / "code/dispose/output/customer_ids.npy"
OUTPUT_DIR = Path(__file__).resolve().parent / "output"

K_CLUSTERS = 5          # 簇数 (后续做 k 扫描)
BETA = 0.1              # 约束权重, 论文网格 {0,0.02,...,0.3}; 0 = 纯 FCM
MAX_ITER = 200
TOL = 1e-6              # ||U_new - U_old||_F 收敛阈值
SEED = 0
DEVICE = "cuda" if torch.cuda.is_available() else "cpu"
DTYPE = torch.float64
OSQP_EPS = 1e-6
# =====================================================================


def build_blocks(p: np.ndarray, q: np.ndarray, s: np.ndarray, n: int):
    """并查分块 (论文式15: 'associated directly or indirectly')"""
    parent = list(range(n))

    def find(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    for a, b in zip(p.tolist(), q.tolist()):
        ra, rb = find(a), find(b)
        if ra != rb:
            parent[ra] = rb
    root = np.array([find(i) for i in range(n)])
    blocks: dict[int, dict] = {}
    for a, b, v in zip(p, q, s):
        blocks.setdefault(root[a], {"nodes": set(), "edges": []})
        blocks[root[a]]["nodes"].update((a, b))
        blocks[root[a]]["edges"].append((a, b, v))
    out = []
    for blk in blocks.values():
        nodes = np.array(sorted(blk["nodes"]), dtype=np.int64)
        loc = {g: i for i, g in enumerate(nodes)}
        edges = np.array([(loc[a], loc[b], v) for a, b, v in blk["edges"]],
                         dtype=[("p", np.int64), ("q", np.int64), ("s", np.float64)])
        out.append((nodes, edges))
    constrained = np.zeros(n, dtype=bool)
    for nodes, _ in out:
        constrained[nodes] = True
    return out, ~constrained  # (块列表, 无约束样本掩码)


def solve_block_qp(d: np.ndarray, edges: np.ndarray, beta: float,
                   u0: np.ndarray | None) -> np.ndarray:
    """单块凸 QP: d∈R^{r×k} 距离平方, 返回 u∈R^{r×k}"""
    r, k = d.shape
    p_, q_, s_ = edges["p"], edges["q"], edges["s"]
    L = sp.coo_matrix(
        (np.concatenate([s_, s_]), (np.concatenate([p_, q_]), np.concatenate([q_, p_]))),
        shape=(r, r)).tocsc()
    L = sp.diags(np.asarray(L.sum(axis=1)).ravel()) - L  # 加权图拉普拉斯

    blocks, A_rows = [], []
    for j in range(k):
        blocks.append(sp.diags(d[:, j]) + beta * L)
    H = sp.block_diag(blocks, format="csc") * 1.0        # r k × r k

    # u 按簇分块排布: u = [u_·1; u_·2; ...; u_·k], 等式行 i 在 i, i+r, ..., i+(k-1)r 处为 1
    ii = np.repeat(np.arange(r), k)
    jj = (np.arange(k) * r)[None, :] + np.arange(r)[:, None]
    A = sp.coo_matrix((np.ones(r * k), (ii, jj.ravel())), shape=(r, r * k)).tocsc()
    A_full = sp.vstack([A, sp.eye(r * k, format="csc")], format="csc")
    l = np.concatenate([np.ones(r), np.zeros(r * k)])
    u_ = np.concatenate([np.ones(r), np.full(r * k, np.inf)])

    prob = osqp.OSQP()
    prob.setup(P=H, q=None, A=A_full, l=l, u=u_,
               eps_abs=OSQP_EPS, eps_rel=OSQP_EPS, verbose=False, polish=True)
    if u0 is not None:  # 热启动: 按簇分块排布
        prob.warm_start(x=np.concatenate([u0[:, j] for j in range(k)]))
    res = prob.solve()
    if res.info.status_val not in (1, 2):
        raise RuntimeError(f"OSQP 求解失败: {res.info.status}")
    uk = res.x.reshape(k, r).T  # 还原为 r×k (按样本)
    return np.clip(uk, 0.0, 1.0)


def main() -> None:
    t0 = time.perf_counter()
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    torch.manual_seed(SEED)
    rng = np.random.default_rng(SEED)

    X = torch.tensor(np.load(FEATURES), dtype=DTYPE, device=DEVICE)   # n×5
    ids = np.load(IDS)
    cons = pl.read_parquet(CONSTRAINTS)
    p = cons["idx_p"].to_numpy(); q = cons["idx_q"].to_numpy(); s = cons["s_pq"].to_numpy()
    n = X.shape[0]; k = K_CLUSTERS
    print(f"[1/4] X {tuple(X.shape)} ({DEVICE}), 约束 {len(s)} 对, β={BETA}, k={k}")

    blocks, free_mask = build_blocks(p, q, s.astype(np.float64), n)
    free_idx = np.where(free_mask)[0]
    print(f"[2/4] 连通块 {len(blocks)} 个 (最大 {max(len(b[0]) for b in blocks)}), "
          f"无约束样本 {len(free_idx)}")

    U = rng.uniform(0, 1, size=(n, k))
    U /= U.sum(axis=1, keepdims=True)
    U_t = torch.tensor(U, dtype=DTYPE, device=DEVICE)
    obj_hist, U_prev_blocks = [], {}

    print("[3/4] MEM 主循环 ...")
    for it in range(MAX_ITER):
        U_old = U_t.clone()
        # ---- E步: 式(13) ----
        w = U_t ** 2                                    # α=0 => 指数2
        C = (w.T @ X) / w.sum(dim=0, keepdim=True).T    # k×5
        # ---- 全量距离 ----
        D2 = torch.cdist(X, C) ** 2                     # n×k
        # ---- M步A: 无约束样本闭式 (式14) ----
        if len(free_idx):
            dfree = D2[free_idx].clamp_min(1e-12)
            U_t[free_idx] = (1.0 / dfree) / (1.0 / dfree).sum(dim=1, keepdim=True)
        # ---- M步B: 逐块 QP (式15-16) ----
        D2_np = D2.detach().cpu().numpy()
        for bi, (nodes, edges) in enumerate(blocks):
            u0 = U_prev_blocks.get(bi)
            uk = solve_block_qp(D2_np[nodes], edges, BETA, u0)
            U_prev_blocks[bi] = uk
            U_t[nodes] = torch.tensor(uk, dtype=DTYPE, device=DEVICE)
        # ---- 目标函数 (式5) 与收敛 ----
        obj = float((w * D2).sum())
        if BETA > 0:
            Up = U_t[p].cpu().numpy(); Uq = U_t[q].cpu().numpy()
            obj += float(BETA / 2 * (s * ((Up - Uq) ** 2).sum(axis=1)).sum())
        obj_hist.append(obj)
        du = float(torch.linalg.norm(U_t - U_old))
        if it % 10 == 0 or du < TOL:
            print(f"  iter {it:3d}: obj={obj:.4f}, ‖ΔU‖={du:.2e}")
        if du < TOL:
            break

    print(f"[4/4] 收敛于 iter {it}, 写出结果 -> {OUTPUT_DIR}")
    U_np = U_t.cpu().numpy()
    np.save(OUTPUT_DIR / "U.npy", U_np)
    np.save(OUTPUT_DIR / "centers.npy", C.cpu().numpy())
    np.save(OUTPUT_DIR / "labels.npy", U_np.argmax(axis=1))
    np.savetxt(OUTPUT_DIR / "objective.csv", np.array(obj_hist), delimiter=",")
    meta = {
        "k": k, "beta": BETA, "alpha": 0.0, "seed": SEED, "device": DEVICE,
        "n_samples": n, "n_pairs": int(len(s)), "n_blocks": len(blocks),
        "max_block_size": int(max(len(b[0]) for b in blocks)),
        "n_free_samples": int(len(free_idx)),
        "iters": int(it + 1), "final_obj": obj_hist[-1],
        "cluster_sizes": np.bincount(U_np.argmax(axis=1), minlength=k).tolist(),
        "elapsed_sec": round(time.perf_counter() - t0, 1),
    }
    (OUTPUT_DIR / "run_meta.json").write_text(
        json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(meta, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
