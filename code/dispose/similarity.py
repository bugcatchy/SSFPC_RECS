# -*- coding: utf-8 -*-
"""
similarity.py — 由 demographic 社会画像生成 SSFPC 模糊成对约束 s_pq

输入:  data/index files/demographic_lookup_3_groups.parquet  (6,031 户 × 68 列)
输出:  code/dispose/output/
       ├── constraints_gower.parquet    # Gower 主线约束 (COO 稀疏表: idx_p, idx_q, s_pq, 只存上三角)
       ├── constraints_cosine.parquet   # 余弦+one-hot 对照组约束 (仅 15 个基础字段, 与 v1 口径一致)
       ├── customer_ids.npy             # 行序号 -> customer_ID 映射 (与负荷矩阵列对齐)
       └── run_meta.json                # 字段/参数/统计报告 (约束数、连通块分布、S 分布分位数)

v2 变更 (2026-09-11, 解决"大家都像"问题):
  v1 仅用 15 个低基数字段 (房型/气候区仅 2 档), Gower 输出被压在少数离散值上,
  满分平局严重。v2 扩充至 30+ 字段:
  - 地理分层: 同 suburb=1.0 / 同 LGA=0.67 / 同 region=0.33 / 其他=0 (单个复合字段)
  - CENSUS_GROUP_CODE (606 值): 名义字段
  - 计量配置计数: GENERAL_SUPPLY_CNT / CONTROLLED_LOAD_CNT / GROSS_SOLAR_CNT /
    OTHER_LOAD_CNT (有序, 按极差归一)
  - HAS_INTERNET_ACCESS (二值)
  - 问卷字段 (约 23% 用户作答, Gower δ 机制天然处理缺失: 任一方缺失则该字段
    不计入分子分母): NUM_OCCUPANTS / NUM_CHILDREN_0_10 / NUM_CHILDREN_11_17 /
    NUM_OCCUPANTS_70PLUS / NUM_REFRIGERATORS / NUM_ROOMS_HEATED (数值有序),
    DWELLING_TYPE_CD(4档) / AIRCON_TYPE_CD / HAS_CHILDREN (名义),
    HHOLD_INCOME_GROUP_CD / DRYER_USAGE_CD / REDUCING_CONSUMPTION_CD (有序,
    DeclinedToAnswer 按缺失处理)
  排除 (同 v1): 负荷衍生字段 (ASSRTD_ELECTRICITY_USE_GRP_CD/eDaily/peakTime/
  cluster_*)、试验字段 (TRIAL_CUSTOMER_TYPE/CONTROL_GROUP_FLAG)、
  日期/产品码/退订字段、HAS_AGREED_TO_SMS (噪音)。

方法:
  1) Gower 主线: 逐字段算相似度再加权平均 (式: S = Σ δ·s / Σ δ)
     - 有序字段:  s = 1 - |档差| / 极差
     - 名义字段:  相同=1, 不同=0
     - 二值字段:  相同=1, 不同=0;
       ASYMMETRIC_BINARY=True 时 "同为0" 的对子按闫泓序(2021)式(3)剔除 (δ=0)
     - 缺失: 任一方缺失 δ=0
  2) 余弦对照: 仅 15 个基础字段 one-hot (与 v1 相同口径, 供消融对照)
  3) 映射: s_pq = 2·S - 1 ∈ [-1, 1];  阈值 s >= S_THRESHOLD 保留; 对称 Top-K 稀疏化

运行 (项目根目录, yolo 环境):
  python code/dispose/similarity.py
  # Git Bash 下 polars 需先: export POLARS_SKIP_CPU_CHECK=1
"""
from __future__ import annotations

import json
import time
from pathlib import Path

import numpy as np
import polars as pl

# ============================== CONFIG ==============================
PROJECT_ROOT = Path(__file__).resolve().parents[2]
INPUT_PARQUET = PROJECT_ROOT / "data/index files/demographic_lookup_3_groups.parquet"
OUTPUT_DIR = Path(__file__).resolve().parent / "output"

# ---- 全量无缺失字段 (与 v1 一致 + v2 新增) ----
ORDINAL_FIELDS = {  # 有序字段 -> 档次数值映射
    "ASSRTD_HHOLD_INCOME_GROUP_CD": {"LOW": 1, "MED": 2, "HI": 3},
    "ASSRTD_GAS_USAGE_GROUP_CD": {"LOW": 1, "MED": 2, "HI": 3},
}
NOMINAL_FIELDS = ["ASSRTD_DWELLING_TYPE_CD", "ASSRTD_CLIMATE_ZONE_CD"]
BINARY_FIELDS = [
    "HAS_AIRCON", "HAS_POOLPUMP", "HAS_SOLAR", "HAS_GAS",
    "HAS_GAS_HEATING", "HAS_GAS_HOT_WATER", "HAS_GAS_COOKING",
    "HAS_GAS_OTHER_APPLIANCE", "HAS_GENERATION",
    "IS_RENTING", "IS_HOME_DURING_DAYTIME",
    "HAS_INTERNET_ACCESS",  # v2 新增
]
# v2 新增: 计量配置计数 (全量无缺失, 按极差归一的有序字段)
COUNT_FIELDS = [
    "GENERAL_SUPPLY_CNT", "CONTROLLED_LOAD_CNT",
    "GROSS_SOLAR_CNT", "OTHER_LOAD_CNT",
]
# v2 新增: 地理分层复合字段 (同 suburb=1 / 同 LGA=0.67 / 同 region=0.33 / 否则 0)
GEO_FIELDS = ("SUBURB_NAME", "LOCAL_GOV_AREA_NAME", "TRIAL_REGION_NAME")
GEO_SCORES = (1.0, 0.67, 0.33)
# v2 新增: 人口普查小区 (名义, 606 值)
CENSUS_FIELD = "CENSUS_GROUP_CODE"

# ---- v2 新增: 问卷字段 (~23% 作答, 缺失经 δ=0 剔除) ----
SURVEY_ORDINAL_FIELDS = {  # 有序问卷字段 -> 档次数值映射
    "HHOLD_INCOME_GROUP_CD": {"LOW": 1, "MED": 2, "HI": 3},  # DeclinedToAnswer -> 缺失
    "DRYER_USAGE_CD": {"NONE": 0, "LOW": 1, "MED": 2, "HI": 3},
    "REDUCING_CONSUMPTION_CD": {"NONE": 0, "LOW": 1, "MED": 2, "HI": 3},
}
SURVEY_NUMERIC_FIELDS = [  # 数值问卷字段 (字符串存储, 需转 float)
    "NUM_OCCUPANTS", "NUM_CHILDREN_0_10", "NUM_CHILDREN_11_17",
    "NUM_OCCUPANTS_70PLUS", "NUM_REFRIGERATORS", "NUM_ROOMS_HEATED",
]
SURVEY_NOMINAL_FIELDS = ["DWELLING_TYPE_CD", "AIRCON_TYPE_CD", "HAS_CHILDREN"]

ASYMMETRIC_BINARY = False  # True: 二值字段"同为0"的对子剔除(闫泓序式3); False: 对称计分
S_THRESHOLD = 0.0          # 只保留 s_pq >= 阈值 (0 = 只要非负约束, 保证 QP 凸性)
TOP_K = 10                 # 每行保留的最大约束数 (对称取并集)
CHUNK = 1024               # 分块行数, 控制内存 (每块 ~1024×6031 float32 ≈ 25 MB/字段)

# ---- 负约束 (cannot-link) 输出开关: 走 Wang 2022 完整版式(6)用 ----
EMIT_NEGATIVE = True       # True: 额外输出负相似度约束到 NEG_OUTPUT_DIR
NEG_OUTPUT_DIR = Path(__file__).resolve().parent / "output_negative"
NEG_THRESHOLD = 0.0        # 只保留 s_pq < NEG_THRESHOLD 的对子 (严格小于, 0 本身不算负约束)
BOTTOM_M = 10              # 每行保留的最大负约束数 (取 s 最小的 M 个, 对称取并集)
                           # ⚠️ 与 TOP_K 同取 10 仅为控制变量; 负边会把正约束的连通块
                           # 耦合成更大的块, 块规模会明显上涨
# =====================================================================


def load_profiles():
    """读 parquet, 返回 (customer_ids, 字段结构 dict, 字段名列表)

    字段结构:
      cols["full"]  : list[(kind, values_float, ranges)]  全量字段, 无缺失
                      kind ∈ {"ord","nom","bin","cnt"}
      cols["geo"]   : (suburb_codes, lga_codes, region_codes, valid_mask)
      cols["survey"]: list[(kind, values_float_with_nan, range_or_none)]
    """
    df = pl.read_parquet(INPUT_PARQUET)
    ids = df["customer_ID"].to_numpy().astype(np.int64)
    used: list[str] = []

    full: list[tuple[str, np.ndarray, float]] = []
    for name, mapping in ORDINAL_FIELDS.items():
        v = df[name].replace(mapping).cast(pl.Int8).to_numpy().astype(np.float32)
        full.append(("ord", v, float(max(mapping.values()) - min(mapping.values()))))
        used.append(name)
    for name in NOMINAL_FIELDS:
        v = np.unique(df[name].to_numpy(), return_inverse=True)[1].astype(np.float32)
        full.append(("nom", v, 0.0))
        used.append(name)
    for name in BINARY_FIELDS:
        v = (df[name] == "Y").cast(pl.Int8).to_numpy().astype(np.float32)
        full.append(("bin", v, 0.0))
        used.append(name)
    for name in COUNT_FIELDS:
        v = df[name].cast(pl.Float32).to_numpy()
        full.append(("cnt", v, float(v.max() - v.min())))
        used.append(name)
    # CENSUS_GROUP_CODE 名义字段
    v = np.unique(df[CENSUS_FIELD].to_numpy(), return_inverse=True)[1].astype(np.float32)
    full.append(("nom", v, 0.0))
    used.append(CENSUS_FIELD)

    # 地理分层
    geo_cols = []
    for name in GEO_FIELDS:
        s = df[name].cast(pl.Utf8)
        geo_cols.append(s.to_numpy())
    geo_valid = np.ones(len(ids), dtype=bool)
    geo_codes = []
    for arr in geo_cols:
        miss = np.array([a is None for a in arr])
        geo_valid &= ~miss
        filled = np.where(miss, "\x00MISSING", arr)
        geo_codes.append(np.unique(filled, return_inverse=True)[1].astype(np.int64))
    used.extend(GEO_FIELDS)

    # 问卷字段 (缺失 -> NaN)
    survey: list[tuple[str, np.ndarray, float]] = []
    for name, mapping in SURVEY_ORDINAL_FIELDS.items():
        raw = df[name].cast(pl.Utf8).to_numpy()
        v = np.full(len(ids), np.nan, dtype=np.float32)
        for val, code in mapping.items():
            v[raw == val] = float(code)
        survey.append(("ord", v, float(max(mapping.values()) - min(mapping.values()))))
        used.append(name)
    for name in SURVEY_NUMERIC_FIELDS:
        raw = df[name].cast(pl.Utf8).to_numpy()
        v = np.full(len(ids), np.nan, dtype=np.float32)
        mask = np.array([a is not None for a in raw])
        v[mask] = np.array([float(a) for a in raw[mask]], dtype=np.float32)
        rng = float(np.nanmax(v) - np.nanmin(v))
        survey.append(("ord", v, rng))
        used.append(name)
    for name in SURVEY_NOMINAL_FIELDS:
        raw = df[name].cast(pl.Utf8).to_numpy()
        v = np.full(len(ids), np.nan, dtype=np.float32)
        mask = np.array([a is not None for a in raw])
        codes = np.unique(raw[mask], return_inverse=True)[1].astype(np.float32)
        v[mask] = codes
        survey.append(("nom", v, 0.0))
        used.append(name)

    return ids, {"full": full, "geo": (geo_codes, geo_valid), "survey": survey}, used


def gower_similarity(cols: dict, n: int) -> np.ndarray:
    """分块计算 Gower 相似度矩阵 (n×n, float32, 对称, 对角=1), 支持缺失 (δ=0)"""
    S = np.zeros((n, n), dtype=np.float32)      # 分子: Σ δ·s
    W = np.zeros((n, n), dtype=np.float32)      # 分母: Σ δ
    full = cols["full"]
    geo_codes, geo_valid = cols["geo"]
    survey = cols["survey"]

    for i0 in range(0, n, CHUNK):
        i1 = min(i0 + CHUNK, n)
        num = np.zeros((i1 - i0, n), dtype=np.float32)
        den = np.zeros((i1 - i0, n), dtype=np.float32)
        # ---- 全量字段 (无缺失) ----
        for kind, v, rng in full:
            vi = v[i0:i1]
            if kind in ("ord", "cnt"):
                diff = np.abs(vi[:, None] - v[None, :])
                num += 1.0 - diff / max(rng, 1e-9)
            else:  # nom / bin
                num += (vi[:, None] == v[None, :]).astype(np.float32)
            den += 1.0
        # ---- 地理分层复合字段 ----
        gv_i = geo_valid[i0:i1]
        delta = (gv_i[:, None] & geo_valid[None, :]).astype(np.float32)
        same_sub = geo_codes[0][i0:i1, None] == geo_codes[0][None, :]
        same_lga = geo_codes[1][i0:i1, None] == geo_codes[1][None, :]
        same_reg = geo_codes[2][i0:i1, None] == geo_codes[2][None, :]
        geo_score = np.where(same_sub, GEO_SCORES[0],
                    np.where(same_lga, GEO_SCORES[1],
                    np.where(same_reg, GEO_SCORES[2], 0.0))).astype(np.float32)
        num += geo_score * delta
        den += delta
        # ---- 问卷字段 (缺失 δ=0) ----
        for kind, v, rng in survey:
            vi = v[i0:i1]
            delta = (~np.isnan(vi))[:, None] & (~np.isnan(v))[None, :]
            if kind == "ord":
                diff = np.abs(vi[:, None] - v[None, :])
                sc = 1.0 - diff / max(rng, 1e-9)
            else:
                sc = (vi[:, None] == v[None, :]).astype(np.float32)
            num += np.where(delta, sc, 0.0)
            den += delta.astype(np.float32)
        S[i0:i1] = num
        W[i0:i1] = den
    with np.errstate(invalid="ignore", divide="ignore"):
        G = np.where(W > 0, S / np.maximum(W, 1e-9), 0.0).astype(np.float32)
    np.fill_diagonal(G, 1.0)
    return G


def cosine_similarity(cols: dict, n: int) -> np.ndarray:
    """one-hot 展开后分块算余弦相似度 (对照组; 仅 v1 的 15 个基础字段, 口径不变)"""
    parts = []
    full = cols["full"]
    # 前 2 有序 + 2 名义 + 11 基础二值 = v1 的 15 字段
    n_base = len(ORDINAL_FIELDS) + len(NOMINAL_FIELDS) + 11
    base = full[:n_base]
    base_names = ([n for n in ORDINAL_FIELDS] + NOMINAL_FIELDS + BINARY_FIELDS[:11])
    for (kind, v, rng), name in zip(base, base_names):
        if kind == "ord":
            k = int(v.max())
            parts.append(np.eye(k, dtype=np.float32)[v.astype(int) - 1])
        elif kind == "nom":
            parts.append(np.eye(int(v.max()) + 1, dtype=np.float32)[v.astype(int)])
        else:  # bin: [N, Y] 两列
            parts.append(np.eye(2, dtype=np.float32)[v.astype(int)])
    A = np.concatenate(parts, axis=1)                 # n × d one-hot
    norms = np.linalg.norm(A, axis=1).astype(np.float32)
    C = np.zeros((n, n), dtype=np.float32)
    for i0 in range(0, n, CHUNK):
        i1 = min(i0 + CHUNK, n)
        C[i0:i1] = (A[i0:i1] @ A.T) / np.maximum(
            norms[i0:i1, None] * norms[None, :], 1e-9)
    np.fill_diagonal(C, 1.0)
    return C


class UnionFind:
    def __init__(self, n: int):
        self.parent = list(range(n))

    def find(self, x: int) -> int:
        while self.parent[x] != x:
            self.parent[x] = self.parent[self.parent[x]]
            x = self.parent[x]
        return x

    def union(self, a: int, b: int) -> None:
        ra, rb = self.find(a), self.find(b)
        if ra != rb:
            self.parent[ra] = rb


def s_distribution(S: np.ndarray) -> dict:
    """全矩阵 s=2S-1 的分布统计 (排除对角), 用于评估区分度"""
    n = S.shape[0]
    s = 2.0 * S - 1.0
    iu = np.triu_indices(n, k=1)
    vals = s[iu]
    pct = np.percentile(vals, [0, 1, 5, 25, 50, 75, 95, 99, 100])
    return {
        "percentiles": {f"p{p}": round(float(v), 4) for p, v in
                        zip([0, 1, 5, 25, 50, 75, 95, 99, 100], pct)},
        "frac_negative": round(float((vals < 0).mean()), 4),
        "frac_tie_1.0": round(float((vals >= 1.0 - 1e-6).mean()), 4),
        "n_unique_s": int(len(np.unique(vals))),
    }


def to_constraints(S: np.ndarray, top_k: int, threshold: float) -> tuple[np.ndarray, np.ndarray, np.ndarray, dict]:
    """S∈[0,1] -> s=2S-1 -> 阈值 -> 对称Top-K -> 上三角 COO + 统计"""
    n = S.shape[0]
    s = 2.0 * S - 1.0
    np.fill_diagonal(s, -np.inf)                     # 排除自身
    keep = s >= threshold
    k = min(top_k, n - 1)
    # 对称 Top-K: 每行取 top-k, 再取并集保证对称
    idx = np.argpartition(-s, k, axis=1)[:, :k]
    top_mask = np.zeros_like(keep)
    rows = np.repeat(np.arange(n), k)
    top_mask[rows, idx.ravel()] = True
    keep = keep & (top_mask | top_mask.T)

    uf = UnionFind(n)
    p_idx, q_idx = np.nonzero(np.triu(keep, k=1))
    for a, b in zip(p_idx.tolist(), q_idx.tolist()):
        uf.union(a, b)
    vals = s[p_idx, q_idx].astype(np.float32)

    # 连通块统计
    roots = np.array([uf.find(i) for i in range(n)])
    uniq, counts = np.unique(roots, return_counts=True)
    constrained = counts > 1
    block_sizes = counts[constrained]
    n_constrained_samples = int(counts[constrained].sum())
    stats = {
        "n_samples": n,
        "n_pairs": int(len(vals)),
        "s_min": float(vals.min()) if len(vals) else None,
        "s_max": float(vals.max()) if len(vals) else None,
        "s_mean": float(vals.mean()) if len(vals) else None,
        "n_components_total": int(len(uniq)),
        "n_nontrivial_blocks": int(constrained.sum()),
        "block_size_max": int(block_sizes.max()) if len(block_sizes) else 0,
        "block_size_median": float(np.median(block_sizes)) if len(block_sizes) else 0,
        "n_constrained_samples": n_constrained_samples,
        "frac_constrained": round(n_constrained_samples / n, 4),
        "n_isolated": int((counts == 1).sum()),
    }
    return p_idx.astype(np.int32), q_idx.astype(np.int32), vals, stats


def negative_pair_stats(S: np.ndarray) -> dict:
    """每户负相似对 (s<0) 的数量分布 + 不同 BOTTOM_M 下的覆盖率"""
    n = S.shape[0]
    s = 2.0 * S - 1.0
    np.fill_diagonal(s, 1.0)                         # 排除自身
    cnt = (s < 0).sum(axis=1).astype(np.int64)       # 每户负值对数
    pct = np.percentile(cnt, [0, 25, 50, 75, 100])
    return {
        "per_user_neg_count_percentiles": {
            f"p{p}": round(float(v), 1) for p, v in
            zip([0, 25, 50, 75, 100], pct)},
        "per_user_neg_count_mean": round(float(cnt.mean()), 1),
        "frac_users_with_any_negative": round(float((cnt > 0).mean()), 4),
        "frac_users_ge_5_negatives": round(float((cnt >= 5).mean()), 4),
        "frac_users_ge_10_negatives": round(float((cnt >= 10).mean()), 4),
        "frac_users_ge_20_negatives": round(float((cnt >= 20).mean()), 4),
        "s_of_most_negative_partner_percentiles": {
            f"p{p}": round(float(v), 4) for p, v in
            zip([0, 25, 50, 75, 100],
                np.percentile(s.min(axis=1), [0, 25, 50, 75, 100]))},
    }


def to_negative_constraints(S: np.ndarray, bottom_m: int, neg_threshold: float) -> tuple[np.ndarray, np.ndarray, np.ndarray, dict]:
    """S∈[0,1] -> s=2S-1 -> 保留 s<neg_threshold -> 每行取 s 最小的 bottom_m 个
    -> 对称并集 -> 上三角 COO + 统计 (负约束/cannot-link 边)"""
    n = S.shape[0]
    s = 2.0 * S - 1.0
    np.fill_diagonal(s, np.inf)                      # 排除自身
    keep = s < neg_threshold
    m = min(bottom_m, n - 1)
    idx = np.argpartition(s, m, axis=1)[:, :m]       # 每行 s 最小的 m 个
    bot_mask = np.zeros_like(keep)
    rows = np.repeat(np.arange(n), m)
    bot_mask[rows, idx.ravel()] = True
    keep = keep & (bot_mask | bot_mask.T)

    p_idx, q_idx = np.nonzero(np.triu(keep, k=1))
    vals = s[p_idx, q_idx].astype(np.float32)
    stats = {
        "n_samples": n,
        "n_pairs": int(len(vals)),
        "s_min": float(vals.min()) if len(vals) else None,
        "s_max": float(vals.max()) if len(vals) else None,
        "s_mean": float(vals.mean()) if len(vals) else None,
        "bottom_m": bottom_m,
        "neg_threshold": neg_threshold,
    }
    return p_idx.astype(np.int32), q_idx.astype(np.int32), vals, stats


def main() -> None:
    t0 = time.perf_counter()
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    ids, cols, used = load_profiles()
    n = len(ids)
    print(f"[1/4] 读取画像: {n} 户, {len(used)} 个字段 "
          f"(全量{len(cols['full'])} + 地理分层1 + 问卷{len(cols['survey'])})")

    meta: dict = {
        "input": str(INPUT_PARQUET),
        "version": "v2_扩展字段",
        "n_samples": n,
        "fields": {
            "ordinal": list(ORDINAL_FIELDS), "nominal": NOMINAL_FIELDS,
            "binary": BINARY_FIELDS, "count": COUNT_FIELDS,
            "geo": list(GEO_FIELDS), "geo_scores": list(GEO_SCORES),
            "census": CENSUS_FIELD,
            "survey_ordinal": list(SURVEY_ORDINAL_FIELDS),
            "survey_numeric": SURVEY_NUMERIC_FIELDS,
            "survey_nominal": SURVEY_NOMINAL_FIELDS,
        },
        "asymmetric_binary": ASYMMETRIC_BINARY,
        "s_threshold": S_THRESHOLD,
        "top_k": TOP_K,
        "methods": {},
    }

    np.save(OUTPUT_DIR / "customer_ids.npy", ids)

    print("[2/4] Gower 主线 ...")
    G = gower_similarity(cols, n)
    dist = s_distribution(G)
    meta.setdefault("s_distribution", {})["gower"] = dist
    print(f"      S 分布: 中位数 s={dist['percentiles']['p50']:.3f}, "
          f"负值占比 {dist['frac_negative']:.1%}, 满分平局 {dist['frac_tie_1.0']:.2%}, "
          f"唯一值 {dist['n_unique_s']}")
    p, q, v, st = to_constraints(G, TOP_K, S_THRESHOLD)
    pl.DataFrame({"idx_p": p, "idx_q": q, "s_pq": v}).write_parquet(OUTPUT_DIR / "constraints_gower.parquet")
    meta["methods"]["gower"] = st

    if EMIT_NEGATIVE:
        print("[2b] 负约束 (cannot-link) 输出 ...")
        NEG_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        np.save(NEG_OUTPUT_DIR / "customer_ids.npy", ids)
        neg_stats = negative_pair_stats(G)
        print(f"      每户负值对数: 中位数 {neg_stats['per_user_neg_count_percentiles']['p50']:.0f}, "
              f"均值 {neg_stats['per_user_neg_count_mean']:.0f}, "
              f"≥10 个负值对的用户占 {neg_stats['frac_users_ge_10_negatives']:.1%}")
        pn, qn, vn, stn = to_negative_constraints(G, BOTTOM_M, NEG_THRESHOLD)
        pl.DataFrame({"idx_p": pn, "idx_q": qn, "s_pq": vn}).write_parquet(
            NEG_OUTPUT_DIR / "constraints_gower_negative.parquet")
        # 正+负边合并后的连通块 (负边耦合效应)
        uf = UnionFind(n)
        for a, b in zip(p.tolist(), q.tolist()):
            uf.union(int(a), int(b))
        for a, b in zip(pn.tolist(), qn.tolist()):
            uf.union(int(a), int(b))
        roots = np.array([uf.find(i) for i in range(n)])
        _, counts = np.unique(roots, return_counts=True)
        nontrivial = counts[counts > 1]
        stn["merged_with_positive"] = {
            "n_nontrivial_blocks": int(len(nontrivial)),
            "block_size_max": int(nontrivial.max()) if len(nontrivial) else 0,
            "n_constrained_samples": int(nontrivial.sum()),
        }
        neg_meta = {
            "input": str(INPUT_PARQUET),
            "note": "负约束 (cannot-link) 边, 供 Wang 2022 完整版式(6) 使用; "
                    "字段口径与正约束 v2 完全相同, 仅选边规则为 s<0 且每行 Bottom-M",
            "n_samples": n,
            "negative_pair_stats": neg_stats,
            "constraints": stn,
        }
        (NEG_OUTPUT_DIR / "run_meta.json").write_text(
            json.dumps(neg_meta, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"      负约束对 {stn['n_pairs']}, s∈[{stn['s_min']:.3f},{stn['s_max']:.3f}]; "
              f"与正约束合并后连通块 {stn['merged_with_positive']['n_nontrivial_blocks']} "
              f"(最大 {stn['merged_with_positive']['block_size_max']})")
    del G

    print("[3/4] 余弦+one-hot 对照 (仅 v1 的 15 基础字段) ...")
    C = cosine_similarity(cols, n)
    p, q, v, st = to_constraints(C, TOP_K, S_THRESHOLD)
    pl.DataFrame({"idx_p": p, "idx_q": q, "s_pq": v}).write_parquet(OUTPUT_DIR / "constraints_cosine.parquet")
    meta["methods"]["cosine"] = st
    del C

    meta["elapsed_sec"] = round(time.perf_counter() - t0, 1)
    (OUTPUT_DIR / "run_meta.json").write_text(
        json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"[4/4] 完成 ({meta['elapsed_sec']}s), 输出目录: {OUTPUT_DIR}")
    for m, st in meta["methods"].items():
        print(f"  [{m}] 约束对 {st['n_pairs']}, 连通块 {st['n_nontrivial_blocks']} "
              f"(最大 {st['block_size_max']}), 受约束样本 {st['n_constrained_samples']}/{n} "
              f"({st['frac_constrained']:.1%}), s∈[{st['s_min']:.3f},{st['s_max']:.3f}]")


if __name__ == "__main__":
    main()
