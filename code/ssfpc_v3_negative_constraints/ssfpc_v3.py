# -*- coding: utf-8 -*-
"""
ssfpc_v3.py (v3 负约束·串行 DBCD 正式版) — SSFPC (Wang et al. 2022) 完整版式(6)

求解严格对齐官方 MATLAB 码 (code/reference/FDC-main):
  QPP_IDsolver.m / Solver_x0 的块坐标下降 (BCD/DBCD) —— 逐样本串行
  (Gauss-Seidel: 解完第 i 个样本立即写回, 第 i+1 个立刻用新值),
  每样本一个 k 维凸子问题, 大块用热启动 (与官方 else 分支一致;
  官方的顶点遍历分支仅用于 ≤3 样本微块, 不移植)。

每样本子问题 (论文式5/6 口径, 推导见 README):
  min  Σ_j [d_ij + (β/2)·deg⁺_i]·u_ij² + f_iᵀu_i   s.t. 行和=1, u≥0
  其中  deg⁺_i = Σ_{正邻居q} s_iq   (仅正边贡献二次项)
        f_i   = −β·Σ_{所有邻居q} s_iq·u_q   (正边→负系数, 负边→正系数; 统一式)
  二次系数恒正 ⇒ 子问题严格凸 ⇒ 精确水填充解 (active-set, 解析公式,
  不调 OSQP: 6031 次/扫描 × 求解器启动开销不可接受; 数学上同为全局最优)。

与官方的两处既定偏差 (2026-09-10/11 已决策, 见根 README 更新记录五):
  ① 不采用官方私加的 m/|S| 归一化因子 (论文式18/19 无此项);
  ② 顶点遍历分支不移植 (官方自身也仅用于 ≤3 样本块)。

模式开关:
  POSITIVE_ONLY = True  → 只用正约束 (凸问题), 用于与 v2 OSQP 结果逐位对照验证
  POSITIVE_ONLY = False → 正+负约束 (完整版式6, 不定问题, BCD 收敛到驻点)

进度显示: 手写进度条 (无 tqdm 依赖), 外层迭代/内层扫描/样本进度/已用时/ETA。

输入:
  data/output/features_std.npy                          # X: 6,031×5
  code/dispose/output/constraints_gower.parquet          # 正约束 (s≥0, Top-10)
  code/dispose/output_negative/constraints_gower_negative.parquet  # 负约束 (s<0, Bottom-10)

输出: code/ssfpc_v3_negative_constraints/output/  (U/centers/labels/objective/run_meta)

运行 (项目根目录, conda yolo 环境):
  Git Bash:  export POLARS_SKIP_CPU_CHECK=1
             /c/Users/BugCat/miniconda3/envs/yolo/python.exe code/ssfpc_v3_negative_constraints/ssfpc_v3.py
  CMD:       set POLARS_SKIP_CPU_CHECK=1
             C:\\Users\\BugCat\\miniconda3\\envs\\yolo\\python.exe code\\ssfpc_v3_negative_constraints\\ssfpc_v3.py
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

import numpy as np
import polars as pl
import torch

# ============================== CONFIG ==============================
ROOT = Path(__file__).resolve().parents[2]
FEATURES = ROOT / "data/output/features_std.npy"
CONS_POS = ROOT / "code/dispose/output/constraints_gower.parquet"
CONS_NEG = ROOT / "code/dispose/output_negative/constraints_gower_negative.parquet"
OUTPUT_DIR = Path(__file__).resolve().parent / "output"

K_CLUSTERS = 5
BETA = 0.1              # 论文口径; 与 C 组 (checking/output/C_gower36) 控制变量
MAX_ITER = 200          # 外层迭代上限
TOL = 1e-5              # 外层收敛: ‖ΔU‖_F
SEED = 0
POSITIVE_ONLY = False   # True = 只用正约束 (凸, 对照 v2 验证); False = 完整版式6
INNER_TOL = 1e-8        # 内层 BCD 收敛: 一轮扫描的 ‖ΔU‖_2 (对齐官方 Solver_x0 的 1e-8)
INNER_MAX_SWEEPS = 200  # 内层扫描上限 (官方为 100, 我们块更大放宽到 200)
DTYPE = torch.float32
# =====================================================================


# ---------------- 单样本 k 维凸子问题: 精确水填充 ----------------

def solve_simplex_qp(a: np.ndarray, f: np.ndarray) -> np.ndarray:
    """min Σ_j a_j·u_j² + f_j·u_j   s.t. Σu=1, u≥0  (a_j>0, 严格凸)

    KKT: u_j = max(λ−f_j, 0)/(2a_j), 活跃集 = {j: f_j < λ} ⇒ 按 f 排序后
    活跃集必为前缀, 枚举前缀长度 t 求 λ 并检验边界条件, 精确 O(k log k)。
    兜底: 二分法 (理论上不会走到)。"""
    k = len(a)
    order = np.argsort(f, kind="stable")
    fs, as_ = f[order], a[order]
    s_fa, s_ia = 0.0, 0.0
    for t in range(1, k + 1):
        s_fa += fs[t - 1] / (2.0 * as_[t - 1])
        s_ia += 1.0 / (2.0 * as_[t - 1])
        lam = (1.0 + s_fa) / s_ia
        if lam > fs[t - 1] - 1e-12 and (t == k or lam <= fs[t] + 1e-12):
            u = np.zeros(k)
            act = order[:t]
            u[act] = np.maximum((lam - f[act]) / (2.0 * a[act]), 0.0)
            return u
    # ---- 兜底: 二分 λ 使 Σ max(λ−f,0)/(2a) = 1 ----
    lo, hi = float(f.min()), float(f.max()) + 1.0
    while (np.maximum(hi - f, 0) / (2 * a)).sum() < 1.0:
        hi = hi * 2 - lo
    for _ in range(60):
        mid = 0.5 * (lo + hi)
        if (np.maximum(mid - f, 0) / (2 * a)).sum() >= 1.0:
            hi = mid
        else:
            lo = mid
    return np.maximum(hi - f, 0) / (2 * a)


# ---------------- 进度条 (手写, 无依赖) ----------------

class Progress:
    def __init__(self, max_iter: int):
        self.max_iter = max_iter
        self.t0 = time.perf_counter()
        self.outer_times: list[float] = []
        self._outer_start = self.t0
        self._last_print = 0.0

    @staticmethod
    def _fmt(sec: float) -> str:
        m, s = divmod(int(sec), 60)
        return f"{m:02d}:{s:02d}" if m < 60 else f"{m // 60}h{m % 60:02d}m"

    def outer_begin(self, it: int):
        self.it = it
        self._outer_start = time.perf_counter()

    def tick(self, sweep: int, i: int, r: int, obj: float | None):
        now = time.perf_counter()
        if now - self._last_print < 0.25 and i < r - 1:
            return
        self._last_print = now
        elapsed = now - self.t0
        frac_outer = (i + 1) / r
        if self.outer_times:
            avg = np.mean(self.outer_times[-5:])
            remain = avg * (1 - frac_outer) + avg * (self.max_iter - self.it - 1)
            eta = f"~{self._fmt(remain)}"
        else:
            eta = "估算中"
        obj_s = f"{obj:.4f}" if obj is not None else "—"
        line = (f"\r外层 {self.it + 1}/{self.max_iter} │ 内层扫描 {sweep + 1} │ "
                f"样本 {i + 1}/{r} ({100 * frac_outer:4.1f}%) │ "
                f"已用 {self._fmt(elapsed)} │ 剩余 {eta} │ obj={obj_s}   ")
        sys.stdout.write(line)
        sys.stdout.flush()

    def outer_end(self, it: int, obj: float, du: float, sweeps: int):
        self.outer_times.append(time.perf_counter() - self._outer_start)
        sys.stdout.write("\r" + " " * 100 + "\r")
        print(f"  iter {it:3d}: obj={obj:.4f}, ‖ΔU‖={du:.2e}, "
              f"内层扫描 {sweeps} 轮, 本轮 {self.outer_times[-1]:.1f}s")
        sys.stdout.flush()


# ---------------- 图结构 ----------------

def build_blocks(p, q, s, n):
    """并查分块 (正+负边一起参与连通性)"""
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
    return out, ~constrained


def block_neighbors(r: int, edges: np.ndarray):
    """块内邻接表: nbr_idx[i], nbr_s[i] (含双向), deg_pos[i] = Σ_{正邻居} s"""
    nbr_idx: list[list[int]] = [[] for _ in range(r)]
    nbr_s: list[list[float]] = [[] for _ in range(r)]
    for p_, q_, s_ in edges:
        nbr_idx[p_].append(q_); nbr_s[p_].append(s_)
        nbr_idx[q_].append(p_); nbr_s[q_].append(s_)
    deg_pos = np.zeros(r)
    out_idx, out_s = [], []
    for i in range(r):
        idx = np.array(nbr_idx[i], dtype=np.int64)
        sv = np.array(nbr_s[i], dtype=np.float64)
        out_idx.append(idx)
        out_s.append(sv)
        deg_pos[i] = sv[sv > 0].sum()
    return out_idx, out_s, deg_pos


# ---------------- 内层: 串行 BCD (Gauss-Seidel, 对齐官方 Solver_x0) ----------------

def bcd_block(d: np.ndarray, nbr_idx, nbr_s, deg_pos, beta: float,
              u0: np.ndarray, prog: Progress | None, it: int,
              obj: float | None) -> tuple[np.ndarray, int]:
    """串行块坐标下降: 逐样本精确求解凸子问题, 立即写回。
    每次样本更新都是坐标准确最小化 ⇒ 块目标单调不增。"""
    r, k = d.shape
    U = u0.copy()
    a_const = 0.5 * beta * deg_pos                    # 二次系数的常数部分
    sweep = 0
    for sweep in range(INNER_MAX_SWEEPS):
        change = 0.0
        for i in range(r):
            if len(nbr_idx[i]):
                f = -beta * (nbr_s[i] @ U[nbr_idx[i]])
            else:
                f = np.zeros(k)
            a = d[i] + a_const[i]
            u_new = solve_simplex_qp(a, f)
            diff = u_new - U[i]
            change += float(diff @ diff)
            U[i] = u_new
            if prog is not None and (i % 256 == 0 or i == r - 1):
                prog.tick(sweep, i, r, obj)
        if change ** 0.5 < INNER_TOL:
            break
    return U, sweep + 1


# ---------------- 主循环 ----------------

def run_ssfpc_v3(X_np, p, q, s, k, beta, seed,
                 max_iter=MAX_ITER, tol=TOL, out_dir=None,
                 max_seconds=None, checkpoint_every=20,
                 device=None) -> dict:
    t0 = time.perf_counter()
    device = device or ("cuda" if torch.cuda.is_available() else "cpu")
    n = X_np.shape[0]
    if out_dir is not None:
        out_dir.mkdir(parents=True, exist_ok=True)
    ckpt_path = (out_dir / "checkpoint.npz") if out_dir is not None else None

    X = torch.tensor(X_np, dtype=DTYPE, device=device)
    s64 = s.astype(np.float64)
    pos_mask = s64 >= 0

    if beta > 0:
        blocks, free_mask = build_blocks(p, q, s64, n)
    else:
        blocks, free_mask = [], np.ones(n, dtype=bool)
    free_idx = np.where(free_mask)[0]
    # 每块预处理邻接表
    block_data = [(nodes, *block_neighbors(len(nodes), edges))
                  for nodes, edges in blocks]

    obj_hist: list[float] = []
    it_start = 0
    if ckpt_path is not None and ckpt_path.exists():
        with np.load(ckpt_path) as z:
            U_np = z["U"].copy()
            obj_hist = z["obj_hist"].tolist()
            it_start = int(z["it"]) + 1
        print(f"  [续跑] 从 iter {it_start} 恢复 (obj={obj_hist[-1]:.4f})")
    else:
        rng = np.random.default_rng(seed)
        U_np = rng.uniform(0, 1, size=(n, k))
        U_np /= U_np.sum(axis=1, keepdims=True)
    U_t = torch.tensor(U_np, dtype=DTYPE, device=device)

    prog = Progress(max_iter)
    ascents = 0
    converged = False
    it = it_start
    for it in range(it_start, max_iter):
        prog.outer_begin(it)
        U_old = U_t.clone()
        # E步: 式(13)
        w = U_t ** 2
        C = (w.T @ X) / w.sum(dim=0, keepdim=True).T.clamp_min(1e-12)
        D2 = torch.cdist(X, C) ** 2
        # M步A: 无约束样本闭式 (式14)
        if len(free_idx):
            dfree = D2[free_idx].clamp_min(1e-12)
            U_t[free_idx] = (1.0 / dfree) / (1.0 / dfree).sum(dim=1, keepdim=True)
        # M步B: 逐块串行 BCD (热启动: 用上一轮 U)
        D2_np = D2.detach().cpu().numpy().astype(np.float64)
        U_cur = U_t.cpu().numpy().astype(np.float64)
        total_sweeps = 0
        for nodes, nbr_idx, nbr_s, deg_pos in block_data:
            u_new, sweeps = bcd_block(D2_np[nodes], nbr_idx, nbr_s, deg_pos,
                                      beta, U_cur[nodes], prog, it,
                                      obj_hist[-1] if obj_hist else None)
            total_sweeps += sweeps
            U_cur[nodes] = u_new
        U_t = torch.tensor(U_cur, dtype=DTYPE, device=device)
        # 论文真实目标 (式5+式6)
        w_new = U_t ** 2
        obj = float((w_new * D2).sum())
        if beta > 0:
            Up = U_t[p].cpu().numpy()
            Uq = U_t[q].cpu().numpy()
            obj += float(beta / 2 * (s64[pos_mask] *
                         ((Up[pos_mask] - Uq[pos_mask]) ** 2).sum(axis=1)).sum())
            if (~pos_mask).any():
                obj += float(beta * ((-s64[~pos_mask]) *
                             (Up[~pos_mask] * Uq[~pos_mask]).sum(axis=1)).sum())
        if obj_hist and obj > obj_hist[-1] + 1e-6 * max(1.0, abs(obj_hist[-1])):
            ascents += 1  # 相对阈值 1e-6: fp32 噪音 (~3e-7 相对) 不计入
        obj_hist.append(obj)
        du = float(torch.linalg.norm(U_t - U_old))
        prog.outer_end(it, obj, du, total_sweeps)
        if du < tol:
            converged = True
            break
        if ckpt_path is not None and (it % checkpoint_every == 0):
            np.savez(ckpt_path, U=U_t.cpu().numpy(),
                     obj_hist=np.array(obj_hist), it=np.int64(it))
        if max_seconds is not None and (time.perf_counter() - t0) > max_seconds:
            if ckpt_path is not None:
                np.savez(ckpt_path, U=U_t.cpu().numpy(),
                         obj_hist=np.array(obj_hist), it=np.int64(it))
            print(f"  [限时] {max_seconds}s 到达, 已存 checkpoint, 再次运行自动续跑")
            break

    U_np = U_t.cpu().numpy()
    meta = {
        "version": "v3 负约束·串行DBCD正式版 (对齐官方 QPP_IDsolver/Solver_x0)",
        "k": k, "beta": beta, "beta_convention": "论文式(5)(6)口径, 无 m/|S| 因子",
        "alpha": 0.0, "seed": seed, "device": device,
        "positive_only": POSITIVE_ONLY,
        "n_samples": n,
        "n_pairs_pos": int(pos_mask.sum()), "n_pairs_neg": int((~pos_mask).sum()),
        "n_blocks": len(blocks),
        "max_block_size": int(max((len(b[0]) for b in blocks), default=0)),
        "n_free_samples": int(len(free_idx)),
        "inner_tol": INNER_TOL, "inner_max_sweeps": INNER_MAX_SWEEPS,
        "objective_ascents": ascents,
        "objective_note": "BCD 坐标准确最小化 ⇒ 目标应单调不增; ascents>0 需排查",
        "iters": int(it + 1), "final_obj": obj_hist[-1] if obj_hist else None,
        "converged": converged,
        "cluster_sizes": np.bincount(U_np.argmax(axis=1), minlength=k).tolist(),
        "elapsed_sec": round(time.perf_counter() - t0, 1),
    }
    if out_dir is not None:
        out_dir.mkdir(parents=True, exist_ok=True)
        np.save(out_dir / "U.npy", U_np)
        np.save(out_dir / "centers.npy", C.cpu().numpy())
        np.save(out_dir / "labels.npy", U_np.argmax(axis=1))
        np.savetxt(out_dir / "objective.csv", np.array(obj_hist), delimiter=",")
        (out_dir / "run_meta.json").write_text(
            json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")
        if converged and ckpt_path is not None and ckpt_path.exists():
            ckpt_path.unlink()
    return meta


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    X = np.load(FEATURES)
    cons = pl.read_parquet(CONS_POS)
    p = cons["idx_p"].to_numpy(); q = cons["idx_q"].to_numpy()
    s = cons["s_pq"].to_numpy()
    n_pos = len(s)
    if not POSITIVE_ONLY:
        neg = pl.read_parquet(CONS_NEG)
        p = np.concatenate([p, neg["idx_p"].to_numpy()])
        q = np.concatenate([q, neg["idx_q"].to_numpy()])
        s = np.concatenate([s, neg["s_pq"].to_numpy()])
    mode = "仅正约束 (凸, 对照v2验证)" if POSITIVE_ONLY else "正+负约束 (完整版式6)"
    print(f"[run] X {X.shape}, 正约束 {n_pos} 对 + 负约束 {len(s) - n_pos} 对, "
          f"β={BETA}, k={K_CLUSTERS}, seed={SEED}, 模式: {mode}")
    meta = run_ssfpc_v3(X, p, q, s, K_CLUSTERS, BETA, SEED,
                        max_iter=MAX_ITER, tol=TOL, out_dir=OUTPUT_DIR)
    print(json.dumps(meta, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
