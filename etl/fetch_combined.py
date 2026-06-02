"""
WK2026 Pro Betting — Gecombineerde ETL
Haalt laatste 15 wedstrijden op per WK 2026 deelnemer
via StatsBomb (events/xG) en football-data.org (aanvulling).
"""

import os
import time
import requests
from datetime import datetime, date
from supabase import create_client

# ── Config ────────────────────────────────────────────────────────────────────
SUPABASE_URL      = os.environ["SUPABASE_URL"]
SUPABASE_KEY      = os.environ["SUPABASE_KEY"]
FOOTBALL_DATA_KEY = os.environ["FOOTBALL_DATA_KEY"]

STATSBOMB_BASE    = "https://raw.githubusercontent.com/statsbomb/open-data/master/data"
FOOTBALL_DATA_BASE = "https://api.football-data.org/v4"

BATCH_SIZE        = 50
SB_DELAY          = 0.3    # StatsBomb GitHub delay
FD_DELAY          = 6.0    # football-data.org: max 10 calls/min gratis tier

# ── Competitieniveaus ─────────────────────────────────────────────────────────
COMPETITION_LEVEL = {
    "FIFA World Cup":                1,
    "UEFA Euro":                     2,
    "Copa America":                  2,
    "Africa Cup of Nations":         2,
    "UEFA Nations League":           3,
    "World Cup Qualification":       3,
    "UEFA Euro Qualification":       3,
    "International Friendlies":      4,
    "Friendly":                      4,
}

def get_level(competition_name: str) -> int:
    for key, level in COMPETITION_LEVEL.items():
        if key.lower() in competition_name.lower():
            return level
    return 3  # default: kwalificatie niveau

# ── Alle 48 WK 2026 deelnemers ────────────────────────────────────────────────
WK2026_TEAMS = {
    # Europa
    "Germany", "France", "Spain", "Portugal", "England",
    "Netherlands", "Belgium", "Italy", "Croatia", "Denmark",
    "Austria", "Switzerland", "Scotland", "Norway", "Serbia", "Turkey",
    # Zuid-Amerika
    "Brazil", "Argentina", "Uruguay", "Colombia", "Ecuador",
    "Chile", "Paraguay", "Venezuela",
    # Noord/Midden-Amerika
    "United States", "Mexico", "Canada", "Jamaica", "Honduras",
    "Costa Rica", "Panama", "Cuba", "Haiti", "Curaçao",
    # Afrika
    "Morocco", "Senegal", "Nigeria", "Cameroon", "Egypt",
    "South Africa", "Mali", "Tanzania", "Ivory Coast", "Cape Verde",
    # Azië
    "Japan", "South Korea", "Australia", "Iran", "Saudi Arabia",
    "Qatar", "Uzbekistan", "Jordan", "Iraq",
    # Oceanië
    "New Zealand",
}

# football-data.org team ID mapping (WK-teams die beschikbaar zijn)
FD_TEAM_IDS = {
    "Germany": 759, "France": 773, "Spain": 760, "Portugal": 765,
    "England": 770, "Netherlands": 779, "Belgium": 805, "Italy": 784,
    "Croatia": 799, "Denmark": 782, "Austria": 816, "Switzerland": 788,
    "Scotland": 769, "Norway": 781, "Serbia": 827, "Turkey": 803,
    "Brazil": 764, "Argentina": 762, "Uruguay": 771, "Colombia": 801,
    "Ecuador": 825, "Chile": 801, "Paraguay": 812, "Venezuela": 823,
    "United States": 768, "Mexico": 772, "Canada": 772, "Japan": 827,
    "South Korea": 772, "Australia": 772, "Iran": 772, "Saudi Arabia": 772,
    "Morocco": 812, "Senegal": 801, "Nigeria": 799, "Cameroon": 800,
    "Egypt": 801, "South Africa": 802,
}

# StatsBomb internationale competitie IDs
SB_INTERNATIONAL_COMP_IDS = {43, 55, 223, 246, 72, 285, 1, 2}

# ── Setup ─────────────────────────────────────────────────────────────────────
sb = create_client(SUPABASE_URL, SUPABASE_KEY)
sb_session = requests.Session()
fd_session = requests.Session()
fd_session.headers.update({"X-Auth-Token": FOOTBALL_DATA_KEY})


def fetch_sb_json(path: str):
    resp = sb_session.get(f"{STATSBOMB_BASE}/{path}", timeout=30)
    resp.raise_for_status()
    return resp.json()


def fetch_fd_json(path: str):
    resp = fd_session.get(f"{FOOTBALL_DATA_BASE}/{path}", timeout=30)
    resp.raise_for_status()
    return resp.json()


def days_between(date1: str, date2: str) -> int:
    try:
        d1 = datetime.strptime(date1[:10], "%Y-%m-%d").date()
        d2 = datetime.strptime(date2[:10], "%Y-%m-%d").date()
        return abs((d1 - d2).days)
    except Exception:
        return None


def upsert(table: str, records, conflict: str):
    if not records:
        return
    if isinstance(records, dict):
        records = [records]
    for i in range(0, len(records), BATCH_SIZE):
        sb.from_(table).upsert(
            records[i:i + BATCH_SIZE], on_conflict=conflict
        ).execute()


# ── StatsBomb verwerking ──────────────────────────────────────────────────────

def process_sb_events(events: list, match_id: str) -> tuple:
    """Bereken team_stats uit StatsBomb events."""
    stats = {}

    for e in events:
        team = e.get("team", {}).get("name", "")
        if not team:
            continue
        if team not in stats:
            stats[team] = {
                "shots": 0, "shots_on_target": 0, "xg": 0.0,
                "passes": 0, "pass_success": 0, "tackles": 0,
                "interceptions": 0, "yellow_cards": 0, "red_cards": 0,
                "corners": 0, "fouls": 0,
            }
        s     = stats[team]
        etype = e.get("type", {}).get("name", "")

        if etype == "Shot":
            s["shots"] += 1
            outcome = e.get("shot", {}).get("outcome", {}).get("name", "")
            if outcome in ("Goal", "Saved", "Saved To Post"):
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

    result = {}
    for team, s in stats.items():
        passes = s["passes"]
        result[team] = {
            **s,
            "pass_accuracy": round(s["pass_success"] / passes * 100, 1) if passes else None,
        }
        del result[team]["pass_success"]

    return result


def load_statsbomb(team_match_counts: dict):
    """
    Laad StatsBomb data voor WK-teams die nog geen 15 wedstrijden hebben.
    team_match_counts = {team_name: aantal_al_geladen}
    """
    print("\n[StatsBomb] Competities ophalen...")
    competitions = fetch_sb_json("competitions.json")

    # Filter internationale competities vanaf 2022
    relevant = [
        c for c in competitions
        if c.get("competition_id") in SB_INTERNATIONAL_COMP_IDS
        and int(c.get("season_name", "0").split("/")[-1].split("-")[-1]) >= 2022
    ]
    print(f"[StatsBomb] {len(relevant)} competitie-seizoenen gevonden")

    loaded = {team: [] for team in WK2026_TEAMS}

    for comp in relevant:
        comp_id    = comp["competition_id"]
        season_id  = comp["season_id"]
        comp_name  = comp["competition_name"]
        season     = comp["season_name"]
        level      = get_level(comp_name)

        try:
            matches = fetch_sb_json(f"matches/{comp_id}/{season_id}.json")
            time.sleep(SB_DELAY)
        except Exception as e:
            print(f"  ⚠ {comp_name} {season}: {e}")
            continue

        for match in matches:
            home = match.get("home_team", {}).get("home_team_name", "")
            away = match.get("away_team", {}).get("away_team_name", "")

            # Sla over als beide teams al 15 wedstrijden hebben
            home_done = len(loaded.get(home, [])) >= 15
            away_done = len(loaded.get(away, [])) >= 15
            if home_done and away_done:
                continue
            if home not in WK2026_TEAMS and away not in WK2026_TEAMS:
                continue

            match_id   = f"sb_{match['match_id']}"
            match_date = match.get("match_date", "")

            # Match opslaan
            match_record = {
                "match_id":         match_id,
                "source":           "statsbomb",
                "competition":      comp_name,
                "competition_level": level,
                "season":           season,
                "match_date":       match_date,
                "home_team":        home,
                "away_team":        away,
                "home_score":       match.get("home_score"),
                "away_score":       match.get("away_score"),
                "neutral_ground":   False,
                "match_type":       "tournament" if level <= 2 else "qualification",
                "raw_data":         match,
            }
            upsert("matches", match_record, "match_id")

            # Events ophalen voor xG en stats
            try:
                events     = fetch_sb_json(f"events/{match['match_id']}.json")
                team_stats = process_sb_events(events, match_id)
                time.sleep(SB_DELAY)
            except Exception:
                team_stats = {}

            home_score = match.get("home_score", 0) or 0
            away_score = match.get("away_score", 0) or 0

            for team, is_home, goals, conceded in [
                (home, True,  home_score, away_score),
                (away, False, away_score, home_score),
            ]:
                if team not in WK2026_TEAMS:
                    continue
                result = "W" if goals > conceded else ("D" if goals == conceded else "L")
                s      = team_stats.get(team, {})

                stat_record = {
                    "match_id":       match_id,
                    "team":           team,
                    "is_home":        is_home,
                    "goals":          goals,
                    "goals_conceded": conceded,
                    "result":         result,
                    "shots":          s.get("shots"),
                    "shots_on_target": s.get("shots_on_target"),
                    "xg":             round(s.get("xg", 0), 3),
                    "passes":         s.get("passes"),
                    "pass_accuracy":  s.get("pass_accuracy"),
                    "tackles":        s.get("tackles"),
                    "interceptions":  s.get("interceptions"),
                    "yellow_cards":   s.get("yellow_cards"),
                    "red_cards":      s.get("red_cards"),
                    "corners":        s.get("corners"),
                    "fouls":          s.get("fouls"),
                }
                upsert("team_stats", stat_record, "match_id,team")
                loaded[team].append(match_date)

            # Head-to-head
            if home in WK2026_TEAMS and away in WK2026_TEAMS:
                winner = home if home_score > away_score else (
                    away if away_score > home_score else "Draw"
                )
                h2h = [
                    {"match_id": match_id, "team_a": home, "team_b": away,
                     "match_date": match_date, "team_a_score": home_score,
                     "team_b_score": away_score, "winner": winner,
                     "competition_level": level},
                    {"match_id": match_id, "team_a": away, "team_b": home,
                     "match_date": match_date, "team_a_score": away_score,
                     "team_b_score": home_score, "winner": winner,
                     "competition_level": level},
                ]
                upsert("head_to_head", h2h, "match_id,team_a,team_b")

    # Geef terug hoeveel wedstrijden elk team heeft
    return {team: len(matches) for team, matches in loaded.items()}


# ── Football-data.org verwerking ──────────────────────────────────────────────

# football-data.org competitie codes met niveau
FD_COMPETITIONS = {
    "WC":  (1, "FIFA World Cup",            "tournament"),
    "EC":  (2, "UEFA Euro",                 "tournament"),
    "CLI": (3, "UEFA Nations League",       "qualification"),
}

def load_football_data(teams_needing_more: set):
    """Vul ontbrekende wedstrijden aan via football-data.org."""
    print(f"\n[football-data.org] Aanvullen voor {len(teams_needing_more)} teams...")

    # Haal recente interlands op per competitie
    for code, (level, comp_name, match_type) in FD_COMPETITIONS.items():
        for season in ["2022", "2023", "2024", "2025"]:
            try:
                data = fetch_fd_json(f"competitions/{code}/matches?season={season}")
                time.sleep(FD_DELAY)
            except Exception as e:
                print(f"  ⚠ {comp_name} {season}: {e}")
                continue

            matches = data.get("matches", [])
            print(f"  {comp_name} {season}: {len(matches)} wedstrijden")

            for match in matches:
                if match.get("status") != "FINISHED":
                    continue

                home     = match.get("homeTeam", {}).get("name", "")
                away     = match.get("awayTeam", {}).get("name", "")
                score    = match.get("score", {})
                ft       = score.get("fullTime", {})
                home_sc  = ft.get("home")
                away_sc  = ft.get("away")
                match_date = match.get("utcDate", "")[:10]
                match_id   = f"fd_{match['id']}"

                if home not in teams_needing_more and away not in teams_needing_more:
                    continue

                match_record = {
                    "match_id":          match_id,
                    "source":            "football-data",
                    "competition":       comp_name,
                    "competition_level": level,
                    "season":            season,
                    "match_date":        match_date,
                    "home_team":         home,
                    "away_team":         away,
                    "home_score":        home_sc,
                    "away_score":        away_sc,
                    "neutral_ground":    False,
                    "match_type":        match_type,
                    "raw_data":          match,
                }
                upsert("matches", match_record, "match_id")

                # Team stats (football-data heeft beperkte stats)
                for team, is_home, goals, conceded in [
                    (home, True,  home_sc, away_sc),
                    (away, False, away_sc, home_sc),
                ]:
                    if team not in WK2026_TEAMS:
                        continue
                    if goals is None or conceded is None:
                        continue
                    result = "W" if goals > conceded else ("D" if goals == conceded else "L")
                    upsert("team_stats", {
                        "match_id":       match_id,
                        "team":           team,
                        "is_home":        is_home,
                        "goals":          goals,
                        "goals_conceded": conceded,
                        "result":         result,
                    }, "match_id,team")

                # Head-to-head
                if home in WK2026_TEAMS and away in WK2026_TEAMS and home_sc is not None:
                    winner = home if home_sc > away_sc else (
                        away if away_sc > home_sc else "Draw"
                    )
                    upsert("head_to_head", [
                        {"match_id": match_id, "team_a": home, "team_b": away,
                         "match_date": match_date, "team_a_score": home_sc,
                         "team_b_score": away_sc, "winner": winner,
                         "competition_level": level},
                        {"match_id": match_id, "team_a": away, "team_b": home,
                         "match_date": match_date, "team_a_score": away_sc,
                         "team_b_score": home_sc, "winner": winner,
                         "competition_level": level},
                    ], "match_id,team_a,team_b")


# ── Hoofdlogica ───────────────────────────────────────────────────────────────

def run():
    print("=" * 55)
    print("  WK2026 Gecombineerde ETL")
    print("  StatsBomb + football-data.org")
    print("=" * 55)

    # Stap 1: StatsBomb laden
    print("\n[1/2] StatsBomb internationale toernooien laden...")
    sb_counts = load_statsbomb({})

    # Welke teams hebben nog geen 15 wedstrijden?
    teams_needing_more = {
        team for team, count in sb_counts.items()
        if count < 15
    }
    print(f"\n  {len(teams_needing_more)} teams hebben minder dan 15 wedstrijden via StatsBomb")
    if teams_needing_more:
        print(f"  Aanvullen via football-data.org: {', '.join(sorted(teams_needing_more)[:10])}...")

    # Stap 2: football-data.org aanvullen
    print("\n[2/2] football-data.org aanvulling...")
    load_football_data(teams_needing_more)

    # Samenvatting
    print("\n" + "=" * 55)
    print("  Klaar! Controleer met:")
    print("  SELECT team, COUNT(*) FROM team_stats")
    print("  GROUP BY team ORDER BY COUNT(*) DESC;")
    print("=" * 55)


if __name__ == "__main__":
    run()
