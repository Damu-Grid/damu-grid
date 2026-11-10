"""DG-01: read every official CSV from data/raw/ and validate it against the data dictionary.

Validation fails loudly (SchemaError) on missing or unexpected columns, unparseable values,
duplicate or empty keys, unknown categorical values and facility ids that are not in
facilities.csv. Row-count differences from docs/DATA.md are reported, not hidden.
data/raw/ is only ever read.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import pandas as pd

from pipeline.schema import ENUMS, EXPECTED_ROWS, FACILITY_KEYS, PRIMARY_KEYS, TABLES

RAW_DIR = Path(__file__).resolve().parent.parent / "data" / "raw"


class SchemaError(ValueError):
    """The CSV does not match the official data dictionary."""


@dataclass
class ValidationReport:
    row_counts: dict[str, int] = field(default_factory=dict)
    row_count_discrepancies: dict[str, tuple[int, int]] = field(default_factory=dict)

    @property
    def ok(self) -> bool:
        return not self.row_count_discrepancies

    def lines(self) -> list[str]:
        out = []
        for name, n in self.row_counts.items():
            exp = EXPECTED_ROWS.get(name)
            mark = "ok" if exp == n else f"EXPECTED {exp}"
            out.append(f"{name:18s} {n:>8,d} rows  {mark}")
        return out


def _parse(series: pd.Series, kind: str, where: str) -> pd.Series:
    filled = series.notna()
    if kind == "str":
        return series.astype("string")
    if kind == "bool":
        mapped = series.map({"True": True, "False": False}).astype("boolean")
    elif kind == "int":
        num = pd.to_numeric(series, errors="coerce")
        bad_int = num.notna() & (num != num.round())
        if bad_int.any():
            raise SchemaError(f"{where}: {int(bad_int.sum())} non-integer values")
        mapped = num.astype("Int64")
    elif kind == "float":
        mapped = pd.to_numeric(series, errors="coerce").astype("Float64")
    elif kind == "date":
        mapped = pd.to_datetime(series, format="%Y-%m-%d", errors="coerce")
    elif kind == "datetime":
        mapped = pd.to_datetime(series, format="%Y-%m-%d %H:%M:%S", errors="coerce")
    else:  # pragma: no cover - schema typo
        raise ValueError(f"unknown kind {kind}")
    bad = filled & mapped.isna()
    if bad.any():
        sample = series[bad].head(3).tolist()
        raise SchemaError(f"{where}: {int(bad.sum())} values are not {kind}, e.g. {sample}")
    return mapped


def read_table(name: str, raw_dir: Path = RAW_DIR) -> pd.DataFrame:
    """Read one official CSV with its declared types. Raises SchemaError on any mismatch."""
    spec = TABLES[name]
    path = Path(raw_dir) / f"{name}.csv"
    if not path.exists():
        raise SchemaError(f"{path} is missing")
    raw = pd.read_csv(path, dtype=str, keep_default_na=False, na_values=[""])
    cols = list(raw.columns)
    missing = [c for c in spec if c not in cols]
    unexpected = [c for c in cols if c not in spec]
    if missing or unexpected:
        raise SchemaError(f"{name}.csv: missing columns {missing}, unexpected columns {unexpected}")
    df = pd.DataFrame({c: _parse(raw[c], kind, f"{name}.{c}") for c, kind in spec.items()})

    for col_key, allowed in ENUMS.items():
        if col_key[0] != name:
            continue
        col = col_key[1]
        bad = df[col].notna() & ~df[col].isin(allowed)
        if bad.any():
            raise SchemaError(f"{name}.{col}: unknown values {sorted(df.loc[bad, col].unique())[:5]}")

    keys = PRIMARY_KEYS.get(name)
    if keys:
        if df[keys].isna().any().any():
            raise SchemaError(f"{name}: empty primary key {keys}")
        dup = df.duplicated(keys)
        if dup.any():
            raise SchemaError(f"{name}: {int(dup.sum())} duplicate keys on {keys}")
    return df


def check_facility_keys(tables: dict[str, pd.DataFrame]) -> None:
    """Every facility reference must exist in facilities.facility_id (joins use facility_id only)."""
    known = set(tables["facilities"]["facility_id"])
    for name, cols in FACILITY_KEYS.items():
        if name not in tables:
            continue
        for col in cols:
            vals = tables[name][col].dropna()
            unknown = sorted(set(vals) - known)
            if unknown:
                raise SchemaError(f"{name}.{col}: facility ids not in facilities.csv: {unknown[:5]}")


def load_all(raw_dir: Path = RAW_DIR, names: list[str] | None = None) -> tuple[dict[str, pd.DataFrame],
                                                                              ValidationReport]:
    """Load and validate the official tables. Returns the typed frames and a row-count report."""
    names = names or list(TABLES)
    tables = {n: read_table(n, raw_dir) for n in names}
    if "facilities" in tables:
        check_facility_keys(tables)
    report = ValidationReport()
    for n, df in tables.items():
        report.row_counts[n] = len(df)
        if EXPECTED_ROWS.get(n) != len(df):
            report.row_count_discrepancies[n] = (EXPECTED_ROWS.get(n, -1), len(df))
    return tables, report
