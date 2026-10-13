"""Development / evaluation split (benchmarks/split.json, documented in benchmarks/SPLIT.md)."""
from __future__ import annotations

import json
import re
from functools import lru_cache

from circuitevolve.blocks import REPO

SPLIT_PATH = REPO / "benchmarks" / "split.json"


@lru_cache(None)
def load_split() -> dict:
    return json.loads(SPLIT_PATH.read_text())


def fast() -> list:
    return list(load_split()["fast"])


def dev() -> list:
    return list(load_split()["dev"])


def is_eval(name: str) -> bool:
    s = load_split()
    stem = name.split("/")[-1].removesuffix(".qasm")
    return bool(re.match(s["eval_pattern"], stem)) or stem in s["eval"] or stem in s["eval_transfer"]


def check_dev(name: str) -> str:
    """Refuse anything that is not in the development set (evaluation circuits are never touched here)."""
    if is_eval(name):
        raise PermissionError(f"{name} is an evaluation circuit; not allowed in development")
    if name not in load_split()["dev"]:
        raise PermissionError(f"{name} is not in the development split ({SPLIT_PATH.name})")
    return name
