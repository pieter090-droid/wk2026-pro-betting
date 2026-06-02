"""
WK2026 Pro Betting — Gecombineerde ETL
Bronnen:
  1. StatsBomb open data  → event data + xG (toernooien)
  2. OpenFootball GitHub  → friendlies + kwalificatie + WK (scores, datum, stadion)
Geen API key nodig voor beide bronnen.
"""

import os
import time
import requests
from supabase import create_client

# ── Config ────────────────────────────────────────────────────────────────────
SUPABASE_URL   = os.environ["SUPABASE_URL"]
SUPABASE_KEY   = os.environ["SUPABASE_KEY"]
STATSBOMB_BASE = "https://raw.githubusercontent.com/statsbomb/open-data/master/data"
OF_BASE        = "https://raw.githubusercontent.com"
BATCH_SIZE     = 50
DELAY          = 0.3

# ── Competitieniveaus ─────────────────────────────────────────────────────────
COMPETITION_LEVEL = {
    "FIFA World Cup":            1,
    "World Cup":                 1,
    "UEFA Euro":                 2,
    "Euro":                      2,
    "Copa America":              2,
    "Africa Cup of Nations":     2,
    "Nations League":            3,
    "World Cup Qualification":   3,
    "Qualification":             3,
    "Friendly":                  4,
    "Friendlies":                4,
}

def get_level(name: str) -> int:
    for key, lvl in COMPETITION_LEVEL.items():
        if key.lower() in name.lower():
            return lvl
    return 3

# ── Alle 48 WK 2026 deelnemers ────────────────────────────────────────────────
WK2026_TEAMS = {
    "Germany", "France", "Spain", "Portugal", "England",
    "Netherlands", "Belgium", "Italy", "Croatia", "Denmark",
    "Austria", "Switzerland", "Scotland", "Norway", "Serbia", "Turkey",
    "Brazil", "Argentina", "Uruguay", "Colombia", "Ecuador",
    "Chile", "Paraguay", "Venezuela",
    "United States", "Mexico", "Canada", "Jamaica", "Honduras",
    "Costa Rica", "Panama", "Cuba", "Haiti", "Curaçao",
    "Morocco", "Senegal", "Nigeria", "Cameroon", "Egypt",
    "South Africa", "Mali", "Tanzania", "Ivory Coast", "Cape Verde",
    "Japan", "South Korea", "Australia", "Iran", "Saudi Arabia",
    "Qatar", "Uzbekistan", "Jordan", "Iraq", "New Zealand",
}

# OpenFootball bronnen — (url_path, competition_naam, level, match_type)
OF_SOURCES = [
    # WK
    ("openfootball/worldcup.json/master/2022/worldcup.json",
     "FIFA World Cup 2022", 1, "tournament"),
    ("openfootball/worldcup.json/master/2026/worldcup.json",
     "FIFA World Cup 2026", 1, "tournament"),
    # Euro
    ("openfootball/euro.json/master/2024/euro.json",
     "UEFA Euro 2024", 2, "tournament"),
    # Internationals (friendlies + kwalificatie via Mart Jürisoo dataset)
    ("openfootball/internationals/master/2022/intls.txt",
     "Internationals 2022", 4, "friendly"),
    ("openfootball/internationals/master/2023/intls.txt",
     "Internationals 2023", 4, "friendly"),
    ("openfootball/internationals/master/2024/intls.txt",
     "Internationals 2024", 4, "friendly"),
]

# StatsBomb internationale competitie IDs
SB_INTL_COMP_IDS = {43, 55, 223, 246, 72, 285}

# ── Setup ─────────────────────────────────────────────────────────────────────
sb      = create_client(SUPABASE_URL, SUPABASE_KEY)
session = requests.Session()


def fetch_json(url: str):
    resp = session.get(url, timeout=30)
    resp.raise_for_status()
    return resp.json()


def fetch_text(url: str):
    resp = session.get(url, timeout=30)
    resp.raise_for_status()
    return resp.text


def upsert(table: str, records, conflict: str):
    if not records:
        return 0
    if isinstance(records, dict):
        records = [records]
    for i in range(0, len(records), BATCH_SIZE):
        sb.from_(table).upsert(
            records[i:i + BATCH_SIZE], on_conflict=conflict
        ).execute()
    return len(records)


def has_wk_team(home: str, away: str) -> bool:
    return home in WK2026_TEAMS or away in WK2026_TEAMS


# ── StatsBomb ─────────────────────────────────────────────────────────────────

def sb_team_stats(events: list, match_id: str, match: dict) -> list:
    home = match.get("home_team", {}).get("home_team_name", "")
    away = match.get("away_team", {}).get("away_team_name", "")
    stats = {t: {"shots": 0, "shots_on_target": 0, "xg": 0.0,
                 "passes": 0, "pass_success": 0, "tackles": 0,
                 "interceptions": 0, "yellow_cards": 0, "red_cards": 0,
                 "corners": 0, "fouls": 0}
             for t in [home, away]}

    for e in events:
        team  = e.get("team", {}).get("name", "")
        etype = e.get("type", {}).get("name", "")
        if team not in stats:
            continue
        s = stats[team]
        if etype == "Shot":
            s["shots"] += 1
            out = e.get("shot", {}).get("outcome", {}).get("name", "")
            if out in ("Goal", "Saved", "Saved To Post"):
                s["shots_on_target"] += 1
            s["xg"] += e.get("shot", {}).get("statsbomb_xg", 0) or 0
        elif etype == "Pass":
            s["passes"] += 1
            if not e.get("pass", {}).get("outcome"):
                s["pass_success"] += 1
        elif etype == "Tackle":
            s["tackles"] += 1
        elif etype == "Interception":
            s["interceptions"] += 1
        elif etype == "Bad Behaviour":
            card = e.get("bad_behaviour", {}).get("card", {}).get("name", "")
            if "Yellow" in card:
                s["yellow_cards"] += 1
            elif "Red" in card:
                s["red_cards"] += 1
        elif etype == "Corner Kick":
            s["corners"] += 1
        elif etype == "Foul Committed":
            s["fouls"] += 1

    records = []
    home_sc = match.get("home_score", 0) or 0
    away_sc = match.get("away_score", 0) or 0

    for team, is_home, goals, conceded in [
        (home, True,  home_sc, away_sc),
        (away, False, away_sc, home_sc),
    ]:
        if team not in WK2026_TEAMS:
            continue
        s      = stats[team]
        passes = s["passes"]
        result = "W" if goals > conceded else ("D" if goals == conceded else "L")
        records.append({
            "match_id":        match_id,
            "team":            team,
            "is_home":         is_home,
            "goals":           goals,
            "goals_conceded":  conceded,
            "result":          result,
            "shots":           s["shots"],
            "shots_on_target": s["shots_on_target"],
            "xg":              round(s["xg"], 3),
            "passes":          passes,
            "pass_accuracy":   round(s["pass_success"] / passes * 100, 1) if passes else None,
            "tackles":         s["tackles"],
            "interceptions":   s["interceptions"],
            "yellow_cards":    s["yellow_cards"],
            "red_cards":       s["red_cards"],
            "corners":         s["corners"],
            "fouls":           s["fouls"],
        })
    return records


def load_statsbomb():
    print("\n[1/2] StatsBomb laden...")
    comps = fetch_json(f"{STATSBOMB_BASE}/competitions.json")
    relevant = [
        c for c in comps
        if c.get("competition_id") in SB_INTL_COMP_IDS
        and int(c.get("season_name", "0").split("/")[-1].split("-")[-1]) >= 2022
    ]
    print(f"      {len(relevant)} competitie-seizoenen gevonden")

    total = 0
    for comp in relevant:
        cid   = comp["competition_id"]
        sid   = comp["season_id"]
        cname = comp["competition_name"]
        sname = comp["season_name"]
        level = get_level(cname)

        try:
            matches = fetch_json(f"{STATSBOMB_BASE}/matches/{cid}/{sid}.json")
            time.sleep(DELAY)
        except Exception as e:
            print(f"  ⚠ {cname} {sname}: {e}")
            continue

        wk = [m for m in matches if has_wk_team(
            m.get("home_team", {}).get("home_team_name", ""),
            m.get("away_team", {}).get("away_team_name", "")
        )]
        print(f"  {cname} {sname}: {len(wk)} wedstrijden")

        for match in wk:
            mid    = f"sb_{match['match_id']}"
            home   = match.get("home_team", {}).get("home_team_name", "")
            away   = match.get("away_team", {}).get("away_team_name", "")
            mdate  = match.get("match_date", "")
            home_sc = match.get("home_score", 0) or 0
            away_sc = match.get("away_score", 0) or 0

            # Match opslaan
            upsert("matches", {
                "match_id":          mid,
                "source":            "statsbomb",
                "competition":       cname,
                "competition_level": level,
                "season":            sname,
                "match_date":        mdate,
                "home_team":         home,
                "away_team":         away,
                "home_score":        home_sc,
                "away_score":        away_sc,
                "venue":             match.get("stadium", {}).get("name"),
                "neutral_ground":    False,
                "match_type":        "tournament" if level <= 2 else "qualification",
                "raw_data":          match,
            }, "match_id")

            # Events + stats
            try:
                events = fetch_json(f"{STATSBOMB_BASE}/events/{match['match_id']}.json")
                time.sleep(DELAY)
                team_records = sb_team_stats(events, mid, match)
                upsert("team_stats", team_records, "match_id,team")
            except Exception:
                pass

            # Head-to-head
            if home in WK2026_TEAMS and away in WK2026_TEAMS:
                winner = home if home_sc > away_sc else (away if away_sc > home_sc else "Draw")
                upsert("head_to_head", [
                    {"match_id": mid, "team_a": home, "team_b": away,
                     "match_date": mdate, "team_a_score": home_sc,
                     "team_b_score": away_sc, "winner": winner,
                     "competition_level": level},
                    {"match_id": mid, "team_a": away, "team_b": home,
                     "match_date": mdate, "team_a_score": away_sc,
                     "team_b_score": home_sc, "winner": winner,
                     "competition_level": level},
                ], "match_id,team_a,team_b")

            total += 1

    print(f"      ✓ {total} StatsBomb wedstrijden verwerkt")
    return total


# ── OpenFootball JSON verwerking ──────────────────────────────────────────────

def parse_of_json(data: dict, comp_name: str, level: int, match_type: str) -> int:
    """Verwerk OpenFootball JSON (worldcup.json / euro.json formaat)."""
    total = 0
    for match in data.get("matches", []):
        home   = match.get("team1", "")
        away   = match.get("team2", "")
        if not has_wk_team(home, away):
            continue

        score  = match.get("score", {})
        ft     = score.get("ft", [None, None])
        home_sc = ft[0] if ft and len(ft) > 0 else None
        away_sc = ft[1] if ft and len(ft) > 1 else None
        mdate  = match.get("date", "")
        mid    = f"of_{comp_name.replace(' ', '_')}_{mdate}_{home}_{away}"

        upsert("matches", {
            "match_id":          mid,
            "source":            "openfootball",
            "competition":       comp_name,
            "competition_level": level,
            "season":            mdate[:4] if mdate else None,
            "match_date":        mdate or None,
            "home_team":         home,
            "away_team":         away,
            "home_score":        home_sc,
            "away_score":        away_sc,
            "venue":             match.get("ground"),
            "neutral_ground":    level == 1,  # WK op neutraal terrein
            "match_type":        match_type,
            "raw_data":          match,
        }, "match_id")

        # Basis team stats (geen xG beschikbaar via OpenFootball)
        if home_sc is not None and away_sc is not None:
            for team, is_home, goals, conceded in [
                (home, True,  home_sc, away_sc),
                (away, False, away_sc, home_sc),
            ]:
                if team not in WK2026_TEAMS:
                    continue
                result = "W" if goals > conceded else ("D" if goals == conceded else "L")
                upsert("team_stats", {
                    "match_id":       mid,
                    "team":           team,
                    "is_home":        is_home,
                    "goals":          goals,
                    "goals_conceded": conceded,
                    "result":         result,
                }, "match_id,team")

            # Head-to-head
            if home in WK2026_TEAMS and away in WK2026_TEAMS:
                winner = home if home_sc > away_sc else (away if away_sc > home_sc else "Draw")
                upsert("head_to_head", [
                    {"match_id": mid, "team_a": home, "team_b": away,
                     "match_date": mdate, "team_a_score": home_sc,
                     "team_b_score": away_sc, "winner": winner,
                     "competition_level": level},
                    {"match_id": mid, "team_a": away, "team_b": home,
                     "match_date": mdate, "team_a_score": away_sc,
                     "team_b_score": home_sc, "winner": winner,
                     "competition_level": level},
                ], "match_id,team_a,team_b")

        total += 1
    return total


def parse_of_txt(text: str, comp_name: str, level: int, match_type: str) -> int:
    """
    Verwerk OpenFootball .txt formaat (internationals repo).
    Formaat: "2022-03-26  Netherlands  2-1  Germany"
    """
    import re
    total   = 0
    pattern = re.compile(
        r"(\d{4}-\d{2}-\d{2})\s+(.+?)\s+(\d+)-(\d+)\s+(.+)"
    )

    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        m = pattern.match(line)
        if not m:
            continue

        mdate, home, home_sc, away_sc, away = (
            m.group(1), m.group(2).strip(),
            int(m.group(3)), int(m.group(4)), m.group(5).strip()
        )

        if not has_wk_team(home, away):
            continue

        mid    = f"of_{mdate}_{home.replace(' ', '_')}_{away.replace(' ', '_')}"
        winner = home if home_sc > away_sc else (away if away_sc > home_sc else "Draw")

        upsert("matches", {
            "match_id":          mid,
            "source":            "openfootball",
            "competition":       comp_name,
            "competition_level": level,
            "season":            mdate[:4],
            "match_date":        mdate,
            "home_team":         home,
            "away_team":         away,
            "home_score":        home_sc,
            "away_score":        away_sc,
            "neutral_ground":    False,
            "match_type":        match_type,
            "raw_data":          {"date": mdate, "home": home, "away": away,
                                  "home_score": home_sc, "away_score": away_sc},
        }, "match_id")

        for team, is_home, goals, conceded in [
            (home, True,  home_sc, away_sc),
            (away, False, away_sc, home_sc),
        ]:
            if team not in WK2026_TEAMS:
                continue
            result = "W" if goals > conceded else ("D" if goals == conceded else "L")
            upsert("team_stats", {
                "match_id": mid, "team": team, "is_home": is_home,
                "goals": goals, "goals_conceded": conceded, "result": result,
            }, "match_id,team")

        if home in WK2026_TEAMS and away in WK2026_TEAMS:
            upsert("head_to_head", [
                {"match_id": mid, "team_a": home, "team_b": away,
                 "match_date": mdate, "team_a_score": home_sc,
                 "team_b_score": away_sc, "winner": winner,
                 "competition_level": level},
                {"match_id": mid, "team_a": away, "team_b": home,
                 "match_date": mdate, "team_a_score": away_sc,
                 "team_b_score": home_sc, "winner": winner,
                 "competition_level": level},
            ], "match_id,team_a,team_b")

        total += 1
    return total


def load_openfootball():
    print("\n[2/2] OpenFootball laden...")
    total = 0

    for path, comp_name, level, match_type in OF_SOURCES:
        url = f"{OF_BASE}/{path}"
        print(f"  {comp_name}...")
        try:
            if path.endswith(".json"):
                data  = fetch_json(url)
                count = parse_of_json(data, comp_name, level, match_type)
            else:
                text  = fetch_text(url)
                count = parse_of_txt(text, comp_name, level, match_type)
            print(f"    ✓ {count} wedstrijden")
            total += count
            time.sleep(DELAY)
        except Exception as e:
            print(f"    ⚠ Fout: {e}")

    print(f"      ✓ {total} OpenFootball wedstrijden verwerkt")
    return total


# ── Hoofdlogica ───────────────────────────────────────────────────────────────

def run():
    print("=" * 55)
    print("  WK2026 ETL — StatsBomb + OpenFootball")
    print("=" * 55)

    sb_total = load_statsbomb()
    of_total = load_openfootball()

    print(f"\n{'=' * 55}")
    print(f"  Klaar!")
    print(f"  StatsBomb:    {sb_total} wedstrijden (met xG/stats)")
    print(f"  OpenFootball: {of_total} wedstrijden (scores + datums)")
    print(f"  Totaal:       {sb_total + of_total} wedstrijden")
    print(f"\n  Check per team:")
    print(f"  SELECT team, COUNT(*), AVG(xg)")
    print(f"  FROM team_stats GROUP BY team ORDER BY 2 DESC;")
    print("=" * 55)


if __name__ == "__main__":
    run()
