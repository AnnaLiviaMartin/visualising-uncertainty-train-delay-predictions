# app.py
import math
import re
from dataclasses import dataclass
from typing import Dict, Optional, Tuple, List, Set

import numpy as np
import pandas as pd
import streamlit as st


def normalize_text(x: object) -> str:
    if x is None or (isinstance(x, float) and np.isnan(x)):
        return ""
    s = str(x).strip()
    s = re.sub(r"\s+", " ", s)
    return s.lower()


def detect_delimiter(sample_bytes: bytes) -> str:
    text = sample_bytes.decode("utf-8", errors="ignore")
    lines = "\n".join(text.splitlines()[:30])
    counts = {",": lines.count(","), ";": lines.count(";"), "\t": lines.count("\t")}
    return max(counts, key=counts.get)


def read_csv(uploaded_file) -> pd.DataFrame:
    raw = uploaded_file.getvalue()
    sep = detect_delimiter(raw[:50_000])

    for enc in ("utf-8-sig", "utf-8", "cp1252"):
        try:
            return pd.read_csv(
                pd.io.common.BytesIO(raw),
                sep=sep,
                dtype=str,
                encoding=enc,
            )
        except Exception:
            continue

    return pd.read_csv(pd.io.common.BytesIO(raw), sep=sep, dtype=str)


def parse_question_col(col: str) -> Tuple[Optional[int], str]:
    if not isinstance(col, str):
        return None, str(col)
    m = re.match(r"^\s*Frage\s+(\d+)\s*-\s*(.*)\s*$", col, flags=re.IGNORECASE)
    if not m:
        return None, col.strip()
    return int(m.group(1)), m.group(2).strip()


def load_include_numbers(df_include: pd.DataFrame) -> Set[int]:
    nums: Set[int] = set()
    for col in df_include.columns:
        s = df_include[col].astype(str).fillna("")
        for v in s.tolist():
            v = v.strip()
            if not v:
                continue
            m = re.search(r"(\d+)", v)
            if m:
                nums.add(int(m.group(1)))
    return nums


def load_mapping(df_map: pd.DataFrame, value_col: str, code_col: str) -> Dict[str, float]:
    m: Dict[str, float] = {}
    for _, row in df_map.iterrows():
        v = normalize_text(row.get(value_col, ""))
        c_raw = row.get(code_col, "")

        if not v:
            continue
        if c_raw is None or str(c_raw).strip() == "":
            continue

        s = str(c_raw).strip().replace(",", ".")
        try:
            c = float(s)
        except Exception:
            continue

        m[v] = c
    return m


def apply_mapping(df_raw: pd.DataFrame, mapping: Dict[str, float]) -> pd.DataFrame:
    coded = pd.DataFrame(index=df_raw.index)
    for col in df_raw.columns:
        out = []
        for val in df_raw[col].tolist():
            if val is None or (isinstance(val, float) and np.isnan(val)) or str(val).strip() == "":
                out.append(np.nan)
                continue

            s = str(val).strip()
            try:
                out.append(float(s.replace(",", ".")))
                continue
            except Exception:
                pass

            key = normalize_text(val)
            out.append(mapping.get(key, np.nan))

        coded[col] = pd.to_numeric(pd.Series(out), errors="coerce")
    return coded


def binom_cdf(k: int, n: int, p: float) -> float:
    s = 0.0
    for i in range(0, k + 1):
        s += math.comb(n, i) * (p ** i) * ((1 - p) ** (n - i))
    return s


def sign_test_two_sided(k_above: int, k_below: int) -> Optional[float]:
    m = k_above + k_below
    if m == 0:
        return None
    k = min(k_above, k_below)
    p = 2.0 * binom_cdf(k, m, 0.5)
    return min(1.0, p)


@dataclass
class LikertMeta:
    scale_max: int
    midpoint: int


def infer_likert_meta(series: pd.Series) -> Optional[LikertMeta]:
    s = pd.to_numeric(series, errors="coerce").dropna()
    if s.empty:
        return None
    s_int = s.round().astype(int)
    uniq = set(s_int.unique().tolist())

    if uniq.issubset({1, 2, 3, 4, 5}):
        return LikertMeta(scale_max=5, midpoint=3)
    if uniq.issubset({1, 2, 3}):
        return LikertMeta(scale_max=3, midpoint=2)
    return None


def compute_descriptives(df_coded: pd.DataFrame, cols: List[str]) -> pd.DataFrame:
    rows = []
    for col in cols:
        s = pd.to_numeric(df_coded[col], errors="coerce").dropna()
        if s.empty:
            continue
        rows.append(
            {
                "frage_nr": parse_question_col(col)[0],
                "column": col,
                "n": int(s.shape[0]),
                "mean": float(s.mean()),
                "median": float(s.median()),
                "std": float(s.std(ddof=1)) if s.shape[0] > 1 else np.nan,
                "min": float(s.min()),
                "max": float(s.max()),
            }
        )
    df = pd.DataFrame(rows)
    if not df.empty:
        df = df.sort_values(["frage_nr", "column"], na_position="last")
    return df


def compute_likert_stats(df_coded: pd.DataFrame, cols: List[str], alpha: float) -> pd.DataFrame:
    rows = []
    for col in cols:
        meta = infer_likert_meta(df_coded[col])
        if not meta:
            continue

        s = pd.to_numeric(df_coded[col], errors="coerce").dropna()
        if s.empty:
            continue

        s_int = s.round().astype(int)
        counts = {i: int((s_int == i).sum()) for i in range(1, meta.scale_max + 1)}

        if meta.scale_max == 5:
            k_above = counts.get(4, 0) + counts.get(5, 0)
            k_below = counts.get(1, 0) + counts.get(2, 0)
            ties = counts.get(3, 0)
        else:
            k_above = counts.get(3, 0)
            k_below = counts.get(1, 0)
            ties = counts.get(2, 0)

        p_val = sign_test_two_sided(k_above=k_above, k_below=k_below)

        rows.append(
            {
                "frage_nr": parse_question_col(col)[0],
                "column": col,
                "scale_max": meta.scale_max,
                "midpoint_tested": meta.midpoint,
                "n": int(s.shape[0]),
                "mean": float(s.mean()),
                "median": float(s.median()),
                "std": float(s.std(ddof=1)) if s.shape[0] > 1 else np.nan,
                "c1": counts.get(1, 0),
                "c2": counts.get(2, 0),
                "c3": counts.get(3, 0),
                "c4": counts.get(4, 0) if meta.scale_max == 5 else np.nan,
                "c5": counts.get(5, 0) if meta.scale_max == 5 else np.nan,
                "k_above": k_above,
                "k_below": k_below,
                "ties": ties,
                "m_no_ties": k_above + k_below,
                "p_value": p_val,
                "significant": (p_val is not None) and (p_val < alpha),
            }
        )

    df = pd.DataFrame(rows)
    if not df.empty:
        df = df.sort_values(["frage_nr", "p_value", "column"], na_position="last")
    return df

def compute_construct_stats(
    df_coded: pd.DataFrame,
    df_mapping: pd.DataFrame,
    alpha: float
) -> pd.DataFrame:

    rows = []

    for visualisation in df_mapping["visualisation"].unique():
        df_vis = df_mapping[
            df_mapping["visualisation"] == visualisation
        ]

        for construct in df_vis["construct"].unique():
            questions = (
                df_vis[df_vis["construct"] == construct]["question_number"]
                .astype(int)
                .tolist()
            )
            cols = []

            for col in df_coded.columns:
                nr, _ = parse_question_col(col)

                if nr in questions:
                    cols.append(col)

            if not cols:
                continue

            # Mittelwert pro Teilnehmer über die Items
            items = df_coded[cols]
            scores = items.mean(axis=1).dropna()

            if scores.empty:
                continue

            rows.append(
                {
                    "visualisation": visualisation,
                    "construct": construct,
                    "items": len(cols),
                    "n": len(scores),
                    "mean": float(scores.mean()),
                    "std": float(scores.std(ddof=1)),
                    "median": float(scores.median()),
                    "min": float(scores.min()),
                    "max": float(scores.max())
                }
            )

    return pd.DataFrame(rows)

st.set_page_config(page_title="Umfrage-Auswertung (Likert + Signifikanz)", layout="wide")
st.title("Umfrage-Auswertung: Likert-Statistiken + Signifikanz")

with st.sidebar:
    st.header("Dateien")
    raw_file = st.file_uploader("Rohdaten CSV", type=["csv"])
    map_file = st.file_uploader("Mapping CSV", type=["csv"])
    include_file = st.file_uploader("Include-Fragen CSV (nur Nummern)", type=["csv"])
    construct_file = st.file_uploader("Construct Mapping CSV", type=["csv"])

    st.header("Analyse")
    alpha = st.number_input("Alpha", min_value=0.001, max_value=0.2, value=0.05, step=0.005)

if not raw_file or not map_file or not include_file:
    st.info("Rohdaten-CSV, Mapping-CSV und Include-CSV hochladen.")
    st.stop()

df_raw = read_csv(raw_file)
df_map = read_csv(map_file)
df_include = read_csv(include_file)
df_construct = read_csv(construct_file)

df_raw.columns = [str(c).strip() for c in df_raw.columns]
df_map.columns = [str(c).strip() for c in df_map.columns]
df_include.columns = [str(c).strip() for c in df_include.columns]
df_construct.columns = (
    df_construct.columns
    .str.strip()
    .str.lower()
)

df_construct["question_number"] = (
    df_construct["question_number"]
    .astype(int)
)

include_numbers = load_include_numbers(df_include)
if not include_numbers:
    st.error("Include-CSV enthält keine Frage-Nummern.")
    st.stop()

# Filter raw columns by included question numbers
included_cols = []
for c in df_raw.columns:
    nr, _ = parse_question_col(c)
    if nr is not None and nr in include_numbers:
        included_cols.append(c)

if not included_cols:
    st.error("Keine Rohdaten-Spalten passen zur Include-Liste. Erwartet: 'Frage <nr> - ...'")
    st.stop()

df_raw_f = df_raw[included_cols].copy()

# hard coded
val_col = "Value"
code_col = "Code"
mapping = load_mapping(df_map, val_col, code_col)
df_coded = apply_mapping(df_raw_f, mapping)

# Sort columns by question number for output
sorted_cols = sorted(df_raw_f.columns, key=lambda c: (parse_question_col(c)[0] or 10**9, c))

# Compute tables once
df_desc = compute_descriptives(df_coded, sorted_cols)
df_likert = compute_likert_stats(df_coded, sorted_cols, alpha=alpha)
df_construct_stats = compute_construct_stats(df_coded, df_construct, alpha=alpha)

# Downloads
def to_csv_bytes(df: pd.DataFrame) -> bytes:
    return df.to_csv(index=False).encode("utf-8")


c1, c2, c3, c4 = st.columns(4)
with c1:
    st.download_button("CodedData CSV", data=to_csv_bytes(df_coded[sorted_cols]), file_name="codeddata_included.csv")
with c2:
    st.download_button("Deskriptive CSV", data=to_csv_bytes(df_desc), file_name="descriptives_included.csv")
with c3:
    st.download_button("Likert Stats CSV", data=to_csv_bytes(df_likert), file_name="likert_stats_included.csv")
with c4:
    st.download_button("Construct Stats CSV", data=to_csv_bytes(df_construct_stats), file_name="construct_statistics.csv")

# Main layout: tables
st.subheader("Deskriptive Kennwerte")
st.dataframe(df_desc, use_container_width=True, height=340)

st.subheader("Likert-Statistiken + Sign-Test")
st.dataframe(df_likert, use_container_width=True, height=420)

st.subheader("Aggregierte Konstrukte")
st.dataframe(df_construct_stats, use_container_width=True, height=340)