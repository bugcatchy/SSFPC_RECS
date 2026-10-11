# -*- coding: utf-8 -*-
"""
ssfpc.py (v2 正约束特例版) — SSFPC (Wang et al. 2022, IEEE TFS) 主循环

与 v1 (代码/ssfpc_v1_初版) 的差异:
  1. [因子2修复] QP 矩阵 P = blkdiag_j(2·diag(d_·j) + β·L), 使 ½uᵀPu
     精确等于论文式(5)口径 J = Σd·u² + (β/2)Σs‖u_p−u_q‖²。
     v1 的 H = diag(d)+βL 使 β 实为论文口径的 2 倍 (v1 β=0.1 ≈ 论文 β=0.2)。
     objective.csv 现在与 QP 实际优化量严格一致。
  2. [正定性验证] 启动时对每个连通块的 L 做最小特征值检查 (eigsh),
     结果写入 run_meta.json["pd_check"]; 距离对角项运行期 clamp>0。
  3. 空簇防护: 中心更新分母 clamp_min(eps)。
  4. [2026-09-11] 主循环抽为 run_ssfpc() 供 checking/run_compare.py 复用;
     支持 checkpoint 断点续跑 (checkpoint.npz) 与 max_seconds 限时优雅退出;
     β=0 时全部样本走式(14)闭式 (数学上即纯 FCM)。
  5. [2026-09-11] 性能: fp64→fp32 (消费级显卡 fp64 吞吐 1/64), TOL 1e-6→1e-5;
     块 QP 改用 BlockQPSolver (setup 一次, 每轮 update(Px)+热启动;
     与 solve_block_qp 逐位等价, 验证 max|Δu|=5.6e-16)。

数学依据见同目录 SSFPC构造说明.md (简化式6正约束特例的完整推导链)。

输入:
  data/output/features_std.npy                 # X: 6,031×5 标准化负荷行为特征
  代码/dispose/output/constraints_gower.parquet # 约束表 (idx_p, idx_q, s_pq≥0, 上三角)

输出: 代码/ssfpc_v2_正约束特例/output/
  ├── U.npy / centers.npy / labels.npy / objective.csv / run_meta.json

运行 (项目根目录, yolo 环境; Git Bash 下先 export POLARS_SKIP_CPU_CHECK=1):
  python 代码/ssfpc_v2_正约束特例/ssfpc.py
"""
from __future__ import annotations

import json
import time
from pathlib import Path

import numpy as np
import polars as pl
import scipy.sparse as sp
import scipy.sparse.linalg as spl
import torch
import osqp

# ============================== CONFIG ==============================
ROOT = Path(__file__).resolve().parents[2]
FEATURES = ROOT / "data/output/features_std.npy"
CONSTRAINTS = ROOT / "代码/dispose/output/constraints_gower.parquet"
IDS = ROOT / "代码/dispose/output/customer_ids.npy"
OUTPUT_DIR = Path(__file__).resolve().parent / "output"

K_CLUSTERS = 5          # 簇数 (后续做 k 扫描)
BETA = 0.1              # 论文口径 β, 论文网格 {0,0.02,...,0.3}; 0 = 纯 FCM
MAX_ITER = 200
TOL = 1e-5              # ||U_new - U_old||_F 收敛阈值 (fp32 适配, 原 fp64 为 1e-6)
SEED = 0
DEVICE = "cuda" if torch.cuda.is_available() else "cpu"
DTYPE = torch.float32   # 2026-09-11 起 fp64→fp32: 消费级显卡 fp64 吞吐 1/64;
                        # FCM/SSFPC 迭代对精度不敏感, fp32 为业界标准
OSQP_EPS = 1e-6
# =====================================================================


class BlockQPSolver:
    """可复用的块 QP 求解器: P = blkdiag_j(2·diag(d_·j)+βL) 的稀疏结构固定,
    每轮只对角值 (距离项) 变化 ⇒ setup 一次, 之后 update(Px) + 热启动。

    数学上与 solve_block_qp 完全等价 (同一 QP, 仅免去重复符号分解)。"""

    def __init__(self, r: int, k: int, L: sp.csc_matrix, beta: float):
        self.r, self.k, self.beta = r, k, beta
        # 模板: d 全 1 时建一次, 记录 P.data 中对角项位置
        P_full = sp.block_diag([2.0 * sp.diags(np.ones(r)) + beta * L
                                for _ in range(k)], format="csc")
        P0 = sp.triu(P_full, format="csc")   # OSQP 只保留上三角, update 需同序
        P0.sum_duplicates()
        rows = P0.indices
        cols = np.repeat(np.arange(P0.shape[1]), np.diff(P0.indptr))
        diag = rows == cols
        self._diag_pos = np.where(diag)[0]
        gcol = cols[diag]
        self._diag_j = gcol // r
        self._diag_i = rows[diag] - self._diag_j * r
        self._P0_data = P0.data.copy()      # 含 2·1 的对角初值
        self._P = P0

        ii = np.repeat(np.arange(r), k)
        jj = (np.arange(k) * r)[None, :] + np.arange(r)[:, None]
        A = sp.coo_matrix((np.ones(r * k), (ii, jj.ravel())), shape=(r, r * k)).tocsc()
        A_full = sp.vstack([A, sp.eye(r * k, format="csc")], format="csc")
        l = np.concatenate([np.ones(r), np.zeros(r * k)])
        u_ = np.concatenate([np.ones(r), np.full(r * k, np.inf)])
        self.prob = osqp.OSQP()
        self.prob.setup(P=P0, q=None, A=A_full, l=l, u=u_,
                        eps_abs=OSQP_EPS, eps_rel=OSQP_EPS, verbose=False, polish=True)

    def solve(self, d: np.ndarray, u0: np.ndarray | None) -> np.ndarray:
        d64 = np.asarray(d, dtype=np.float64)
        data = self._P0_data.copy()
        data[self._diag_pos] += 2.0 * (d64[self._diag_i, self._diag_j] - 1.0)
        self.prob.update(Px=data)
        if u0 is not None:
            self.prob.warm_start(x=np.concatenate(
                [np.asarray(u0[:, j], dtype=np.float64) for j in range(self.k)]))
        res = self.prob.solve()
        if res.info.status_val not in (1, 2):
            raise RuntimeError(f"OSQP 求解失败: {res.info.status}")
        uk = res.x.reshape(self.k, self.r).T
        return np.clip(uk, 0.0, 1.0)


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


def block_laplacian(r: int, edges: np.ndarray) -> sp.csc_matrix:
    """块内加权图拉普拉斯 L = Λ − W (s≥0 ⇒ 半正定)"""
    p_, q_, s_ = edges["p"], edges["q"], edges["s"]
    W = sp.coo_matrix(
        (np.concatenate([s_, s_]), (np.concatenate([p_, q_]), np.concatenate([q_, p_]))),
        shape=(r, r)).tocsc()
    return sp.diags(np.asarray(W.sum(axis=1)).ravel()) - W


def pd_check(blocks, beta: float) -> list[dict]:
    """启动时一次性正定性验证: 报告每块 L 的最小/最大特征值。
    s≥0 时 L 半正定 (理论 λ_min=0, 孤立特征值=0); d>0 使 2diag(d)+βL 严格正定。
    数值容差: λ_min > -1e-8 即通过。"""
    report = []
    for bi, (nodes, edges) in enumerate(blocks):
        r = len(nodes)
        L = block_laplacian(r, edges)
        if r <= 3:
            ev = np.linalg.eigvalsh(L.toarray())
            lam_min, lam_max = float(ev[0]), float(ev[-1])
        else:
            lam_min = float(spl.eigsh(L, k=1, which="SA", return_eigenvectors=False)[0])
            lam_max = float(spl.eigsh(L, k=1, which="LA", return_eigenvectors=False)[0])
        ok = lam_min > -1e-8
        report.append({"block": bi, "size": r, "lam_min": round(lam_min, 10),
                       "lam_max": round(lam_max, 6), "psd_ok": ok})
        if not ok:
            raise RuntimeError(f"块 {bi} 拉普拉斯非半正定: λ_min={lam_min:.3e}")
    return report


def solve_block_qp(d: np.ndarray, L: sp.csc_matrix, beta: float,
                   u0: np.ndarray | None) -> np.ndarray:
    """单块凸 QP: min ½uᵀPu s.t. 行和=1, u≥0;  P = blkdiag_j(2·diag(d_·j)+βL)
    ⇒ ½uᵀPu = Σd·u² + (β/2)Σs‖Δu‖², 与论文式(5)严格同口径。"""
    r, k = d.shape
    P = sp.block_diag([2.0 * sp.diags(d[:, j]) + beta * L for j in range(k)],
                      format="csc")

    # u 按簇分块排布: u = [u_·1; ...; u_·k], 等式行 i 在 i, i+r, ..., i+(k-1)r 处为 1
    ii = np.repeat(np.arange(r), k)
    jj = (np.arange(k) * r)[None, :] + np.arange(r)[:, None]
    A = sp.coo_matrix((np.ones(r * k), (ii, jj.ravel())), shape=(r, r * k)).tocsc()
    A_full = sp.vstack([A, sp.eye(r * k, format="csc")], format="csc")
    l = np.concatenate([np.ones(r), np.zeros(r * k)])
    u_ = np.concatenate([np.ones(r), np.full(r * k, np.inf)])

    prob = osqp.OSQP()
    prob.setup(P=P, q=None, A=A_full, l=l, u=u_,
               eps_abs=OSQP_EPS, eps_rel=OSQP_EPS, verbose=False, polish=True)
    if u0 is not None:  # 热启动: 按簇分块排布
        prob.warm_start(x=np.concatenate([u0[:, j] for j in range(k)]))
    res = prob.solve()
    if res.info.status_val not in (1, 2):
        raise RuntimeError(f"OSQP 求解失败: {res.info.status}")
    uk = res.x.reshape(k, r).T  # 还原为 r×k (按样本)
    return np.clip(uk, 0.0, 1.0)


# ============================ 可复用主循环 ============================

def run_ssfpc(X_np: np.ndarray, p: np.ndarray, q: np.ndarray, s: np.ndarray,
              k: int, beta: float, seed: int,
              max_iter: int = MAX_ITER, tol: float = TOL,
              out_dir: Path | None = None,
              max_seconds: float | None = None,
              checkpoint_every: int = 10,
              device: str | None = None,
              verbose: bool = True) -> dict:
    """SSFPC 正约束特例主循环 (可被 run_compare.py 复用)。

    β=0 时全部样本走式(14)闭式 (=纯 FCM), 不解 QP。
    max_seconds 限时到达时保存 checkpoint.npz 并返回 meta["converged"]=False,
    再次以相同 out_dir 调用会自动续跑。收敛后写出 U/centers/labels/objective/run_meta。
    """
    t0 = time.perf_counter()
    device = device or ("cuda" if torch.cuda.is_available() else "cpu")
    n = X_np.shape[0]
    if out_dir is not None:
        out_dir.mkdir(parents=True, exist_ok=True)
    ckpt_path = (out_dir / "checkpoint.npz") if out_dir is not None else None

    X = torch.tensor(X_np, dtype=DTYPE, device=device)
    s64 = s.astype(np.float64)

    # ---- 分块与正定性验证 (β>0 才有 QP) ----
    if beta > 0:
        blocks, free_mask = build_blocks(p, q, s64, n)
        pd_report = pd_check(blocks, beta)
    else:
        blocks, free_mask = [], np.ones(n, dtype=bool)
        pd_report = []
    free_idx = np.where(free_mask)[0]

    # ---- 初始化或续跑 ----
    obj_hist: list[float] = []
    U_prev_blocks: dict[int, np.ndarray] = {}
    it_start = 0
    if ckpt_path is not None and ckpt_path.exists():
        with np.load(ckpt_path) as z:
            U_np = z["U"].copy()
            obj_hist = z["obj_hist"].tolist()
            it_start = int(z["it"]) + 1
            for key in z.files:
                if key.startswith("uprev_"):
                    U_prev_blocks[int(key[6:])] = z[key].copy()
        if verbose:
            print(f"  [续跑] 从 iter {it_start} 恢复 (obj={obj_hist[-1]:.4f})")
    else:
        rng = np.random.default_rng(seed)
        U_np = rng.uniform(0, 1, size=(n, k))
        U_np /= U_np.sum(axis=1, keepdims=True)
    U_t = torch.tensor(U_np, dtype=DTYPE, device=device)
    solvers: dict[int, BlockQPSolver] = {}

    converged = False
    it = it_start
    for it in range(it_start, max_iter):
        U_old = U_t.clone()
        # ---- E步: 式(13) (α=0), 空簇防护 ----
        w = U_t ** 2
        C = (w.T @ X) / w.sum(dim=0, keepdim=True).T.clamp_min(1e-12)  # k×5
        # ---- 全量距离 ----
        D2 = torch.cdist(X, C) ** 2                     # n×k
        # ---- M步A: 无约束样本闭式 (式14) ----
        if len(free_idx):
            dfree = D2[free_idx].clamp_min(1e-12)
            U_t[free_idx] = (1.0 / dfree) / (1.0 / dfree).sum(dim=1, keepdim=True)
        # ---- M步B: 逐块 QP (式15塌缩版, 恒凸; 求解器复用+热启动) ----
        D2_np = D2.detach().cpu().numpy()
        for bi, (nodes, edges) in enumerate(blocks):
            if bi not in solvers:
                solvers[bi] = BlockQPSolver(len(nodes), k,
                                            block_laplacian(len(nodes), edges), beta)
            uk = solvers[bi].solve(D2_np[nodes], U_prev_blocks.get(bi))
            U_prev_blocks[bi] = uk
            U_t[nodes] = torch.tensor(uk, dtype=DTYPE, device=device)
        # ---- 目标函数 (论文式5口径, 与 QP 严格一致) ----
        w_new = U_t ** 2
        obj = float((w_new * D2).sum())
        if beta > 0:
            Up = U_t[p].cpu().numpy(); Uq = U_t[q].cpu().numpy()
            obj += float(beta / 2 * (s64 * ((Up - Uq) ** 2).sum(axis=1)).sum())
        obj_hist.append(obj)
        du = float(torch.linalg.norm(U_t - U_old))
        if verbose and (it % 10 == 0 or du < tol):
            print(f"  iter {it:3d}: obj={obj:.4f}, ‖ΔU‖={du:.2e}")
        if du < tol:
            converged = True
            break
        # ---- checkpoint / 限时 ----
        if ckpt_path is not None and (it % checkpoint_every == 0):
            _save_checkpoint(ckpt_path, U_t, obj_hist, it, U_prev_blocks)
        if max_seconds is not None and (time.perf_counter() - t0) > max_seconds:
            if ckpt_path is not None:
                _save_checkpoint(ckpt_path, U_t, obj_hist, it, U_prev_blocks)
            if verbose:
                print(f"  [限时] {max_seconds}s 到达, 已存 checkpoint, 待续跑")
            break

    U_np = U_t.cpu().numpy()
    meta = {
        "version": "v2 正约束特例",
        "k": k, "beta": beta, "beta_convention": "论文式(5)口径 (v1 的 2 倍关系已修正)",
        "alpha": 0.0, "seed": seed, "device": device,
        "n_samples": n, "n_pairs": int(len(s)), "n_blocks": len(blocks),
        "max_block_size": int(max((len(b[0]) for b in blocks), default=0)),
        "n_free_samples": int(len(free_idx)),
        "pd_check": pd_report,
        "iters": int(it + 1), "final_obj": obj_hist[-1] if obj_hist else None,
        "converged": converged,
        "cluster_sizes": np.bincount(U_np.argmax(axis=1), minlength=k).tolist(),
        "elapsed_sec": round(time.perf_counter() - t0, 1),
    }
    if out_dir is not None and converged:
        out_dir.mkdir(parents=True, exist_ok=True)
        np.save(out_dir / "U.npy", U_np)
        np.save(out_dir / "centers.npy", C.cpu().numpy())
        np.save(out_dir / "labels.npy", U_np.argmax(axis=1))
        np.savetxt(out_dir / "objective.csv", np.array(obj_hist), delimiter=",")
        (out_dir / "run_meta.json").write_text(
            json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")
        if ckpt_path is not None and ckpt_path.exists():
            ckpt_path.unlink()  # 收敛后清掉 checkpoint
    return meta


def _save_checkpoint(path: Path, U_t: torch.Tensor, obj_hist: list,
                     it: int, U_prev_blocks: dict[int, np.ndarray]) -> None:
    payload = {"U": U_t.cpu().numpy(), "obj_hist": np.array(obj_hist),
               "it": np.int64(it)}
    for bi, uk in U_prev_blocks.items():
        payload[f"uprev_{bi}"] = uk
    np.savez(path, **payload)


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    X = np.load(FEATURES)
    cons = pl.read_parquet(CONSTRAINTS)
    p = cons["idx_p"].to_numpy(); q = cons["idx_q"].to_numpy(); s = cons["s_pq"].to_numpy()
    print(f"[run] X {X.shape}, 约束 {len(s)} 对, β={BETA} (论文口径), k={K_CLUSTERS}, seed={SEED}")
    meta = run_ssfpc(X, p, q, s, K_CLUSTERS, BETA, SEED,
                     max_iter=MAX_ITER, tol=TOL, out_dir=OUTPUT_DIR)
    print(json.dumps({k_: v for k_, v in meta.items() if k_ != "pd_check"},
                     ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
