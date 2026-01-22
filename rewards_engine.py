import sqlite3
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

import numpy as np
import pandas as pd


# -----------------------------
# CONFIG (à adapter à tes paliers exacts)
# -----------------------------
CREATORS_MIN_DAYS = 12
CREATORS_MIN_HOURS = 25
CREATORS_ROUND_STEP = 100  # arrondi à la centaine inférieure
THRESHOLD_150K = 150_000

# Exemple de paliers (à remplacer par TES paliers validés)
# percent_reward est déjà "palier +0,5 point" (ex: 2.0% -> 2.5%)
CREATORS_TIERS = [
    {"name": "T1", "min": 0,      "max": 49_999,  "percent": 0.025, "bonus": 0},
    {"name": "T2", "min": 50_000, "max": 149_999, "percent": 0.035, "bonus": 0},
    {"name": "T3", "min": 150_000,"max": None,    "percent": 0.045, "bonus": 0},
]

BANNED_STATUSES = {"banni", "ban", "banned", "depart", "départ", "inactive"}


# -----------------------------
# DB (historique 150k)
# -----------------------------
def db_connect(db_path: str) -> sqlite3.Connection:
    conn = sqlite3.connect(db_path)
    conn.execute("""
    CREATE TABLE IF NOT EXISTS creator_thresholds(
        creator_id TEXT PRIMARY KEY,
        first_reached_150k_date TEXT
    )
    """)
    conn.commit()
    return conn

def get_first_150k_date(conn: sqlite3.Connection, creator_id: str) -> Optional[str]:
    cur = conn.cursor()
    cur.execute("SELECT first_reached_150k_date FROM creator_thresholds WHERE creator_id = ?", (creator_id,))
    row = cur.fetchone()
    return row[0] if row else None

def set_first_150k_date(conn: sqlite3.Connection, creator_id: str, date_str: str) -> None:
    # n'écrit que si absent
    cur = conn.cursor()
    cur.execute("SELECT creator_id FROM creator_thresholds WHERE creator_id = ?", (creator_id,))
    if cur.fetchone() is None:
        cur.execute(
            "INSERT INTO creator_thresholds(creator_id, first_reached_150k_date) VALUES (?, ?)",
            (creator_id, date_str),
        )
        conn.commit()


# -----------------------------
# Helpers
# -----------------------------
def floor_to_step(x: float, step: int) -> int:
    if step <= 1:
        return int(np.floor(x))
    return int(np.floor(x / step) * step)

def pick_tier(diamonds: float, tiers: List[Dict]) -> Dict:
    for t in tiers:
        mn, mx = t["min"], t["max"]
        if mx is None and diamonds >= mn:
            return t
        if mx is not None and diamonds >= mn and diamonds <= mx:
            return t
    return tiers[-1]


@dataclass
class ComputeResult:
    df: pd.DataFrame
    warnings: List[str]


# -----------------------------
# MAIN: compute creators
# -----------------------------
def compute_creators(
    df: pd.DataFrame,
    mapping: Dict[str, str],
    conn: sqlite3.Connection,
    as_of_date: str,
) -> ComputeResult:
    warnings: List[str] = []

    # colonnes requises via mapping
    need = ["creator_id", "diamonds_month", "live_days_valid", "live_hours_valid", "status"]
    for k in need:
        if k not in mapping or mapping[k] not in df.columns:
            warnings.append(f"Colonne manquante ou non mappée: {k}")

    # si mapping incomplet, on s'arrête proprement
    if any("Colonne manquante" in w for w in warnings):
        out = df.copy()
        return ComputeResult(df=out, warnings=warnings)

    id_col = mapping["creator_id"]
    d_col = mapping["diamonds_month"]
    days_col = mapping["live_days_valid"]
    hours_col = mapping["live_hours_valid"]
    status_col = mapping["status"]

    out = df.copy()

    # normalisation
    out[d_col] = pd.to_numeric(out[d_col], errors="coerce").fillna(0)
    out[days_col] = pd.to_numeric(out[days_col], errors="coerce").fillna(0)
    out[hours_col] = pd.to_numeric(out[hours_col], errors="coerce").fillna(0)
    out[status_col] = out[status_col].astype(str).str.lower().str.strip()

    tiers = []
    percents = []
    bonuses = []
    rewards = []
    eligibles = []
    reasons = []
    reached_flags = []
    first_dates = []

    for _, r in out.iterrows():
        creator_id = str(r[id_col])
        diamonds = float(r[d_col])
        days = float(r[days_col])
        hours = float(r[hours_col])
        status = str(r[status_col])

        eligible = True
        rs = []

        if status in BANNED_STATUSES:
            eligible = False
            rs.append(f"statut={status}")

        if days < CREATORS_MIN_DAYS:
            eligible = False
            rs.append(f"jours<{CREATORS_MIN_DAYS}")

        if hours < CREATORS_MIN_HOURS:
            eligible = False
            rs.append(f"heures<{CREATORS_MIN_HOURS}")

        tier = pick_tier(diamonds, CREATORS_TIERS)
        percent = float(tier["percent"])
        bonus = float(tier.get("bonus", 0))

        reward = 0
        if eligible:
            reward_calc = diamonds * percent + bonus
            reward = floor_to_step(reward_calc, CREATORS_ROUND_STEP)

        # Historique 150k basé sur diamonds_month
        first = get_first_150k_date(conn, creator_id)
        if first is None and diamonds >= THRESHOLD_150K:
            set_first_150k_date(conn, creator_id, as_of_date)
            first = as_of_date

        tiers.append(tier["name"])
        percents.append(percent)
        bonuses.append(bonus)
        rewards.append(reward)
        eligibles.append("OK" if eligible else "NON")
        reasons.append(";".join(rs))
        reached_flags.append("Oui" if first is not None else "Non")
        first_dates.append(first or "")

    out["Tier"] = tiers
    out["%"] = percents
    out["Bonus"] = bonuses
    out["Récompense (diamants)"] = rewards
    out["Eligible"] = eligibles
    out["Raison inéligibilité"] = reasons
    out["Déjà atteint 150k (Oui/Non)"] = reached_flags
    out["Date 1er atteinte 150k"] = first_dates

    return ComputeResult(df=out, warnings=warnings)

