import os
import re
import sqlite3
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

# -----------------------------
# CONFIG "recompense la agency live"
# -----------------------------
CREATORS_MIN_DAYS = 12
CREATORS_MIN_HOURS = 25
CREATORS_ROUND_STEP = 100
THRESHOLD_150K = 150_000

BOOST_DAYS, BOOST_HOURS = 20, 80

BEGINNER_MAX_DAYS_SINCE_JOIN = 90
BEGINNER_MIN_DAYS, BEGINNER_MIN_HOURS = 7, 15  # uniquement palier 75k-500k et jamais 150k

# Barème final (déjà +0,5 point intégré)
CREATORS_TIERS = [
    {"name": "<75 000",              "min": 0,         "max": 75_000,     "base": 0.000, "boost": 0.000, "bonus": 0},
    {"name": "75 000-500 000",       "min": 75_000,    "max": 500_000,    "base": 0.015, "boost": 0.020, "bonus": 0},
    {"name": "500 000-1 000 000",    "min": 500_000,   "max": 1_000_000,  "base": 0.020, "boost": 0.025, "bonus": 0},
    {"name": "1 000 000-2 000 000",  "min": 1_000_000, "max": 2_000_000,  "base": 0.025, "boost": 0.030, "bonus": 0},
    {"name": "2 000 000-∞",          "min": 2_000_000, "max": None,       "base": 0.030, "boost": 0.035, "bonus": 0},
]

# -----------------------------
# DB historique 150k (SQLite)
# -----------------------------
def ensure_dir(path: str) -> None:
    d = os.path.dirname(path)
    if d and not os.path.exists(d):
        os.makedirs(d, exist_ok=True)

def db_connect(db_path: str) -> sqlite3.Connection:
    ensure_dir(db_path)
    conn = sqlite3.connect(db_path, check_same_thread=False)
    conn.execute("""
    CREATE TABLE IF NOT EXISTS creator_thresholds(
        creator_id TEXT PRIMARY KEY,
        first_reached_150k_month TEXT
    )
    """)
    conn.commit()
    return conn

def get_first_150k_month(conn: sqlite3.Connection, creator_id: str) -> Optional[str]:
    cur = conn.cursor()
    cur.execute("SELECT first_reached_150k_month FROM creator_thresholds WHERE creator_id = ?", (creator_id,))
    row = cur.fetchone()
    return row[0] if row else None

def set_first_150k_month(conn: sqlite3.Connection, creator_id: str, month_str: str) -> None:
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO creator_thresholds(creator_id, first_reached_150k_month)
        VALUES(?, ?)
        ON CONFLICT(creator_id) DO NOTHING
    """, (creator_id, month_str))
    conn.commit()

# -----------------------------
# Helpers
# -----------------------------
def floor_to_step(x: float, step: int) -> int:
    if step <= 1:
        return int(np.floor(x))
    return int(np.floor(x / step) * step)

def pick_tier(diamonds: float, tiers: List[dict]) -> dict:
    # bornes demi-ouvertes pour éviter chevauchements: [min, max)
    for t in tiers:
        mn, mx = t["min"], t["max"]
        if mx is None and diamonds >= mn:
            return t
        if mx is not None and (diamonds >= mn) and (diamonds < mx):
            return t
    return tiers[0]

def is_excluded(status_value) -> bool:
    """
    True uniquement si exclusion explicite.
    IMPORTANT: par défaut => False (sinon tu mets tout à 0).
    """
    if pd.isna(status_value):
        return False
    s = str(status_value).strip().lower()
    if s in ("non", "0", "false", ""):
        return False
    if s in ("oui", "1", "true"):
        return True
    return any(k in s for k in ("banni", "ban", "banned", "infraction", "départ", "depart", "inactive"))

def parse_duration_to_hours(val) -> float:
    """
    Convertit '96h 43min 48s' -> heures (float)
    Si déjà numérique, retourne float(val).
    """
    if pd.isna(val):
        return 0.0
    if isinstance(val, (int, float, np.integer, np.floating)):
        return float(val)
    s = str(val).strip().lower()
    mh = re.search(r"(\d+)\s*h", s)
    mm = re.search(r"(\d+)\s*min", s)
    ms = re.search(r"(\d+)\s*s", s)
    hours = 0.0
    if mh: hours += int(mh.group(1))
    if mm: hours += int(mm.group(1)) / 60.0
    if ms: hours += int(ms.group(1)) / 3600.0
    return hours

@dataclass
class ComputeResult:
    df: pd.DataFrame
    warnings: List[str]

def compute_creators(
    df: pd.DataFrame,
    mapping: Dict[str, str],
    conn: sqlite3.Connection,
    month_str: str,  # ex: "2025-12"
) -> ComputeResult:
    """
    mapping attendu (noms logiques -> colonnes df):
      - creator_id
      - diamonds_month
      - live_days_valid
      - live_hours_valid   (peut être 'Durée de LIVE' => on parse)
      - status_excluding
      - days_since_join    (pour la règle débutant <90j)
    """
    warnings: List[str] = []

    required_keys = [
        "creator_id",
        "diamonds_month",
        "live_days_valid",
        "live_hours_valid",
        "status_excluding",
        "days_since_join",
    ]
    for k in required_keys:
        col = mapping.get(k)
        if not col or col not in df.columns:
            warnings.append(f"Colonne manquante ou non mappée: {k} -> '{col}'")

    if warnings:
        return ComputeResult(df=df.copy(), warnings=warnings)

    id_col = mapping["creator_id"]
    d_col = mapping["diamonds_month"]
    days_col = mapping["live_days_valid"]
    hours_col = mapping["live_hours_valid"]
    status_col = mapping["status_excluding"]
    since_col = mapping["days_since_join"]

    out = df.copy()

    # Normalisation
    out[d_col] = pd.to_numeric(out[d_col], errors="coerce").fillna(0.0)
    out[days_col] = pd.to_numeric(out[days_col], errors="coerce").fillna(0).astype(int)

    # hours: support "Durée de LIVE" texte
    if out[hours_col].dtype == object:
        out[hours_col] = out[hours_col].apply(parse_duration_to_hours)
    else:
        out[hours_col] = pd.to_numeric(out[hours_col], errors="coerce").fillna(0.0)

    out[since_col] = pd.to_numeric(out[since_col], errors="coerce")

    # Calcul ligne à ligne (simple mais fiable)
    palier_list: List[str] = []
    taux_list: List[float] = []
    bonus_list: List[float] = []
    reward_list: List[int] = []
    eligible_list: List[str] = []
    reason_list: List[str] = []
    reached_flag_list: List[str] = []
    first_month_list: List[str] = []

    for _, r in out.iterrows():
        creator_id = str(r[id_col])
        diamonds = float(r[d_col])
        days = int(r[days_col])
        hours = float(r[hours_col])
        excluded = is_excluded(r[status_col])

        # historique 150k (avant calcul conditions débutant)
        first_150k = get_first_150k_month(conn, creator_id)
        already_150k = first_150k is not None

        # si pas encore dans l'historique et >=150k sur le mois => on écrit le 1er mois atteint
        if not already_150k and diamonds >= THRESHOLD_150K:
            set_first_150k_month(conn, creator_id, month_str)
            first_150k = month_str
            already_150k = True

        tier = pick_tier(diamonds, CREATORS_TIERS)
        palier = tier["name"]
        base_rate = float(tier["base"])
        boost_rate = float(tier["boost"])
        bonus = float(tier.get("bonus", 0.0))

        rs: List[str] = []
        reward = 0
        taux_applique = 0.0

        # exclusion statut => ligne gardée mais 0
        if excluded:
            rs.append("statut_excluant")
        else:
            # minimum requis par défaut
            min_days = CREATORS_MIN_DAYS
            min_hours = CREATORS_MIN_HOURS

            # exception débutant uniquement sur palier 75k-500k
            days_since = r[since_col]
            if (palier == "75 000-500 000") and (pd.notna(days_since)) and (days_since < BEGINNER_MAX_DAYS_SINCE_JOIN) and (not already_150k):
                min_days = BEGINNER_MIN_DAYS
                min_hours = BEGINNER_MIN_HOURS

            # vérif minima
            if days < min_days:
                rs.append(f"jours<{min_days}")
            if hours < min_hours:
                rs.append(f"heures<{min_hours}")

            # si palier <75k => taux 0
            if base_rate <= 0:
                rs.append("sous_seuil")

            if len(rs) == 0:
                # taux boost si 20j/80h atteints
                taux_applique = boost_rate if (days >= BOOST_DAYS and hours >= BOOST_HOURS) else base_rate
                reward_calc = diamonds * taux_applique + bonus
                reward = floor_to_step(reward_calc, CREATORS_ROUND_STEP)

        palier_list.append(palier)
        taux_list.append(taux_applique)
        bonus_list.append(bonus)
        reward_list.append(int(reward))
        eligible_list.append("OK" if reward > 0 else "NON")
        reason_list.append(";".join(rs))
        reached_flag_list.append("Oui" if first_150k is not None else "Non")
        first_month_list.append(first_150k or "")

    # Colonnes sorties
    out["Palier"] = palier_list
    out["Taux appliqué"] = taux_list
    out["Bonus"] = bonus_list
    out["Récompense (diamants)"] = reward_list
    out["Eligible"] = eligible_list
    out["Raison inéligibilité"] = reason_list
    out["Déjà atteint 150k (Oui/Non)"] = reached_flag_list
    out["Premier mois 150k"] = first_month_list

    return ComputeResult(df=out, warnings=warnings)
