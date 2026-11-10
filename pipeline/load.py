"""DG-01: read every official CSV from data/raw/ and validate it against the data dictionary.

Validation fails loudly (SchemaError) on missing or unexpected columns, unparseable values,
duplicate or empty keys, unknown categorical values and facility ids that are not in
facilities.csv. Every problem in every table is collected and reported together, so one run
shows the whole picture. Row-count differences from docs/DATA.md are reported, not hidden.
data/raw/ is only ever read.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

import pandas as pd

from pipeline.schema import ENUMS, EXPECTED_ROWS, FACILITY_KEYS, PRIMARY_KEYS, TABLES

RAW_DIR = Path(__file__).resolve().parent.parent / "data" / "raw"


class SchemaError(ValueError):
    """The CSVs do not match the official data dictionary. `problems` lists every issue found."""

    def __init__(self, problems: list[str]):
        self.problems = list(problems)
        super().__init__("; ".join(self.problems))


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


def _parse(series: pd.Series, kind: str, where: str, problems: list[str]) -> pd.Series:
    filled = series.notna()
    if kind == "str":
        return series.astype("string")
    if kind == "bool":
        mapped = series.map({"True": True, "False": False}).astype("boolean")
    elif kind == "int":
        num = pd.to_numeric(series, errors="coerce")
        frac = num.notna() & (num != num.round())
        if frac.any():
            problems.append(f"{where}: {int(frac.sum())} non-integer values")
        mapped = num.where(~frac).astype("Int64")
    elif kind == "float":
        mapped = pd.to_numeric(series, errors="coerce").astype("Float64")
    elif kind == "date":
        mapped = pd.to_datetime(series, format="%Y-%m-%d", errors="coerce")
    elif kind == "datetime":
        mapped = pd.to_datetime(series, format="%Y-%m-%d %H:%M:%S", errors="coerce")
    else:  # pragma: no cover - schema typo
        raise ValueError(f"unknown kind {kind}")
    bad = filled & mapped.isna()
    if kind == "int":
        bad &= ~(pd.to_numeric(series, errors="coerce").notna())
    if bad.any():
        sample = series[bad].head(3).tolist()
        problems.append(f"{where}: {int(bad.sum())} values are not {kind}, e.g. {sample}")
    return mapped


def _read(name: str, raw_dir: Path, problems: list[str]) -> pd.DataFrame | None:
    spec = TABLES[name]
    path = Path(raw_dir) / f"{name}.csv"
    if not path.exists():
        problems.append(f"{path} is missing")
        return None
    raw = pd.read_csv(path, dtype=str, keep_default_na=False, na_values=[""])
    cols = list(raw.columns)
    missing = [c for c in spec if c not in cols]
    unexpected = [c for c in cols if c not in spec]
    if missing or unexpected:
        problems.append(f"{name}.csv: missing columns {missing}, unexpected columns {unexpected}")
        return None
    df = pd.DataFrame({c: _parse(raw[c], kind, f"{name}.{c}", problems) for c, kind in spec.items()})

    for (table, col), allowed in ENUMS.items():
        if table != name:
            continue
        bad = df[col].notna() & ~df[col].isin(allowed)
        if bad.any():
            problems.append(f"{name}.{col}: unknown values {sorted(df.loc[bad, col].unique())[:5]}")

    keys = PRIMARY_KEYS.get(name)
    if keys:
        if df[keys].isna().any().any():
            problems.append(f"{name}: empty primary key {keys}")
        dup = df.duplicated(keys)
        if dup.any():
            problems.append(f"{name}: {int(dup.sum())} duplicate keys on {keys}")
    return df


def read_table(name: str, raw_dir: Path = RAW_DIR) -> pd.DataFrame:
    """Read one official CSV with its declared types. Raises SchemaError listing every problem."""
    problems: list[str] = []
    df = _read(name, raw_dir, problems)
    if problems:
        raise SchemaError(problems)
    return df


def facility_key_problems(tables: dict[str, pd.DataFrame]) -> list[str]:
    """Every facility reference must exist in facilities.facility_id (joins use facility_id only)."""
    if "facilities" not in tables:
        return []
    known = set(tables["facilities"]["facility_id"])
    problems = []
    for name, cols in FACILITY_KEYS.items():
        if name not in tables:
            continue
        for col in cols:
            unknown = sorted(set(tables[name][col].dropna()) - known)
            if unknown:
                problems.append(f"{name}.{col}: facility ids not in facilities.csv: {unknown[:5]}")
    return problems


def check_facility_keys(tables: dict[str, pd.DataFrame]) -> None:
    problems = facility_key_problems(tables)
    if problems:
        raise SchemaError(problems)


def load_all(raw_dir: Path = RAW_DIR, names: list[str] | None = None) -> tuple[dict[str, pd.DataFrame],
                                                                              ValidationReport]:
    """Load and validate the official tables. Returns the typed frames and a row-count report.
    Raises one SchemaError that lists every problem in every table."""
    names = names or list(TABLES)
    problems: list[str] = []
    tables = {}
    for n in names:
        df = _read(n, raw_dir, problems)
        if df is not None:
            tables[n] = df
    problems += facility_key_problems(tables)
    if problems:
        raise SchemaError(problems)
    report = ValidationReport()
    for n, df in tables.items():
        report.row_counts[n] = len(df)
        if EXPECTED_ROWS.get(n) != len(df):
            report.row_count_discrepancies[n] = (EXPECTED_ROWS.get(n, -1), len(df))
    return tables, report


def dictionary_columns(path: Path = RAW_DIR / "DATA_DICTIONARY.md") -> dict[str, list[str]]:
    """Column names per table as written in the official data dictionary, to check schema.py."""
    out: dict[str, list[str]] = {}
    table = None
    for line in Path(path).read_text(encoding="utf-8").splitlines():
        head = re.match(r"^## (\w+)\.csv", line)
        if head:
            table = head.group(1)
            out[table] = []
            continue
        cell = re.match(r"^\| ([a-z0-9_, ]+) \|", line)
        if table and cell and cell.group(1).strip() != "column":
            out[table] += [c.strip() for c in cell.group(1).split(",")]
    return out
