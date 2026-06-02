"""
WK2026 Pro Betting — Complete StatsBomb ETL
Haalt wedstrijden, teamstats, spelerstatistieken en events op
voor alle WK 2026 deelnemende landen (2022-heden).
"""

import os
import time
import requests
from supabase import create_client

# ── Config ────────────────────────────────────────────────────────────────────
SUPABASE_URL   = os.environ["SUPABASE_URL"]
SUPABASE_KEY   = os.environ["SUPABASE_KEY"]
STATSBOMB_BASE = "https://raw.githubusercontent.com/statsbomb/open-data/master/data"
BATCH_SIZE     = 50
REQUEST_DELAY  = 0.3

# Alleen internationale toernooien (StatsBomb competition IDs)
INTERNATIONAL_COMPETITIONS = {
    43,   # FIFA World Cup
    55,   # UEFA Euro
    223,  # Copa America
    246,  # Africa Cup of Nations
    72,   # UEFA Nations League
    internationaal := True,
}

# Seizoenen vanaf 2022
MIN_SEASON_YEAR = 2022

# Alle 48 WK 2026 deelnemers
WK2026_TEAMS = {
    "Germany", "France", "Spain", "Portugal", "England",
    "Netherlands", "Belgium", "Italy", "Croatia", "Denmark",
    "Austria", "Switzerland", "Scotland", "Norway", "Serbia",
    "Turkey", "Brazil", "Argentina", "Uruguay", "Colombia",
    "Ecuador", "Chile", "Paraguay", "Venezuela", "United States",
    "Mexico", "Canada", "Jamaica", "Honduras", "Costa Rica",
    "Panama", "Cuba", "Haiti", "Curaçao", "Morocco", "Senegal",
    "Nigeria", "Cameroon", "Egypt", "South Africa", "Mali",
    "Tanzania", "Ivory Coast", "Cape Verde", "Japan", "South Korea",
    "Australia", "Iran", "Saudi Arabia", "Qatar", "Uzbekistan",
    "Jordan", "Iraq", "New Zealand",
}

# ── Setup ─────────────────────────────────────────────────────────────────────
sb      = create_client(SUPABASE_URL, SUPABASE_KEY)
session = requests.Session()


def fetch_json(path: str):
    resp = session.get(f"{STATSBOMB_BASE}/{path}", timeout=30)
    resp.raise_for_status()
    return resp.json()


def has_wk_team(match: dict) -> bool:
    home = match.get("home_team", {}).get("home_team_name", "")
    away = match.get("away_team", {}).get("away_team_name", "")
    return home in WK2026_TEAMS or away in WK2026_TEAMS


def season_year(season_name: str) -> int:
    """Haal het eindjaar uit een seizoensnaam zoals '2022/2023'."""
    try:
        return int(season_name.split("/")[-1])
    except Exception:
        try:
            return int(season_name)
        except Exception:
            return 0


# ── Match verwerken ───────────────────────────────────────────────────────────

def process_match(match: dict, competition: dict) -> dict:
    """Zet een StatsBomb match om naar ons matches-tabelformaat."""
    home = match.get("home_team", {}).get("home_team_name", "")
    away = match.get("away_team", {}).get("away_team_name", "")
    return {
        "match_id":   f"sb_{match['match_id']}",
        "source":     "statsbomb",
        "competition": competition.get("competition_name", ""),
        "season":     competition.get("season_name", ""),
        "match_date": match.get("match_date"),
        "home_team":  home,
        "away_team":  away,
        "home_score": match.get("home_score"),
        "away_score": match.get("away_score"),
        "match_type": "tournament",
        "raw_data":   match,
    }


def process_team_stats(match: dict, events: list) -> list:
    """Bereken teamstatistieken uit StatsBomb events."""
    match_id = f"sb_{match['match_id']}"
    home     = match.get("home_team", {}).get("home_team_name", "")
    away     = match.get("away_team", {}).get("away_team_name", "")

    stats = {
        home: {"team": home, "match_id": match_id, "is_home": True,
               "goals": match.get("home_score", 0), "shots": 0,
               "shots_on_target": 0, "passes": 0, "pass_success": 0,
               "xg": 0.0, "tackles": 0, "interceptions": 0,
               "yellow_cards": 0, "red_cards": 0, "corners": 0, "fouls": 0},
        away: {"team": away, "match_id": match_id, "is_home": False,
               "goals": match.get("away_score", 0), "shots": 0,
               "shots_on_target": 0, "passes": 0, "pass_success": 0,
               "xg": 0.0, "tackles": 0, "interceptions": 0,
               "yellow_cards": 0, "red_cards": 0, "corners": 0, "fouls": 0},
    }

    total_passes = {home: 0, away: 0}

    for e in events:
        team = e.get("team", {}).get("name", "")
        if team not in stats:
            continue
        etype = e.get("type", {}).get("name", "")

        if etype == "Shot":
            stats[team]["shots"] += 1
            outcome = e.get("shot", {}).get("outcome", {}).get("name", "")
            if outcome == "Goal":
                pass  # al geteld via match score
            elif outcome in ("Saved", "Saved To Post"):
                stats[team]["shots_on_target"] += 1
            xg_val = e.get("shot", {}).get("statsbomb_xg", 0) or 0
            stats[team]["xg"] += xg_val

        elif etype == "Pass":
            stats[team]["passes"] += 1
            total_passes[team] += 1
            outcome = e.get("pass", {}).get("outcome", {})
            if not outcome:  # geen outcome = succesvolle pass
                stats[team]["pass_success"] += 1

        elif etype == "Tackle":
            stats[team]["tackles"] += 1

        elif etype == "Interception":
            stats[team]["interceptions"] += 1

        elif etype == "Bad Behaviour":
            card = e.get("bad_behaviour", {}).get("card", {}).get("name", "")
            if "Yellow" in card:
                stats[team]["yellow_cards"] += 1
            elif "Red" in card:
                stats[team]["red_cards"] += 1

        elif etype == "50/50":
            pass

    # Pass accuracy berekenen
    records = []
    for team, s in stats.items():
        total = s.pop("pass_success", 0)
        passes = s.get("passes", 0)
        s["pass_accuracy"] = round(total / passes * 100, 1) if passes > 0 else None
        s["shots_on_target"] = s["shots_on_target"] + (
            s["goals"] if s["goals"] else 0
        )
        records.append(s)

    return records


def process_player_stats(match: dict, events: list) -> list:
    """Aggregeer spelerstatistieken uit events."""
    match_id = f"sb_{match['match_id']}"
    players  = {}

    for e in events:
        player = e.get("player", {})
        if not player:
            continue
        pid   = str(player.get("id", ""))
        pname = player.get("name", "")
        team  = e.get("team", {}).get("name", "")
        key   = f"{pname}_{team}"

        if key not in players:
            players[key] = {
                "match_id": match_id, "player_id": pid,
                "player_name": pname, "team": team,
                "minutes_played": None, "started": None,
                "goals": 0, "assists": 0, "shots": 0,
                "shots_on_target": 0, "xg": 0.0, "xa": 0.0,
                "passes": 0, "pass_success": 0, "key_passes": 0,
                "tackles": 0, "interceptions": 0,
                "yellow_cards": 0, "red_cards": 0,
            }

        p     = players[key]
        etype = e.get("type", {}).get("name", "")

        if etype == "Shot":
            p["shots"] += 1
            outcome = e.get("shot", {}).get("outcome", {}).get("name", "")
            if outcome == "Goal":
                p["goals"] += 1
                p["shots_on_target"] += 1
            elif outcome in ("Saved", "Saved To Post"):
                p["shots_on_target"] += 1
            p["xg"] += e.get("shot", {}).get("statsbomb_xg", 0) or 0

        elif etype == "Pass":
            p["passes"] += 1
            outcome = e.get("pass", {}).get("outcome", {})
            if not outcome:
                p["pass_success"] += 1
            if e.get("pass", {}).get("goal_assist"):
                p["assists"] += 1
            if e.get("pass", {}).get("shot_assist"):
                p["key_passes"] += 1
            p["xa"] += e.get("pass", {}).get("xa", 0) or 0

        elif etype == "Tackle":
            p["tackles"] += 1

        elif etype == "Interception":
            p["interceptions"] += 1

        elif etype == "Bad Behaviour":
            card = e.get("bad_behaviour", {}).get("card", {}).get("name", "")
            if "Yellow" in card:
                p["yellow_cards"] += 1
            elif "Red" in card:
                p["red_cards"] += 1

    records = []
    for p in players.values():
        total  = p.pop("pass_success", 0)
        passes = p.get("passes", 0)
        p["pass_accuracy"] = round(total / passes * 100, 1) if passes > 0 else None
        records.append(p)

    return records


def process_events(match: dict, events: list) -> list:
    """Verwerk StatsBomb events naar ons events-tabelformaat."""
    match_id = f"sb_{match['match_id']}"
    records  = []

    for e in events:
        loc = e.get("location") or []
        records.append({
            "match_id":   match_id,
            "event_id":   e.get("id", ""),
            "event_type": e.get("type", {}).get("name", ""),
            "minute":     e.get("minute"),
            "second":     e.get("second"),
            "team":       e.get("team", {}).get("name", ""),
            "player_name": e.get("player", {}).get("name", ""),
            "location_x": loc[0] if len(loc) > 0 else None,
            "location_y": loc[1] if len(loc) > 1 else None,
            "outcome":    (
                e.get("shot", {}) or
                e.get("pass", {}) or
                e.get("tackle", {}) or {}
            ).get("outcome", {}).get("name"),
            "raw_data":   e,
        })

    return records


def upload(table: str, records: list, conflict: str):
    """Upload records in batches."""
    for i in range(0, len(records), BATCH_SIZE):
        chunk = records[i:i + BATCH_SIZE]
        sb.from_(table).upsert(chunk, on_conflict=conflict).execute()


# ── Hoofdlogica ───────────────────────────────────────────────────────────────

def run():
    print("=" * 55)
    print("  StatsBomb Complete ETL — WK2026 Pro Betting")
    print("=" * 55)

    competitions = fetch_json("competitions.json")
    # Filter: alleen internationale toernooien + seizoen >= 2022
    relevant = [
        c for c in competitions
        if c.get("competition_international") is True
        and season_year(c.get("season_name", "0")) >= MIN_SEASON_YEAR
    ]
    print(f"\n{len(relevant)} relevante competitie-seizoenen gevonden\n")

    total_matches = 0
    errors        = []

    for comp in relevant:
        comp_id   = comp["competition_id"]
        season_id = comp["season_id"]
        comp_name = comp["competition_name"]
        season    = comp["season_name"]

        try:
            matches = fetch_json(f"matches/{comp_id}/{season_id}.json")
            time.sleep(REQUEST_DELAY)
        except Exception as e:
            errors.append(f"{comp_name} {season}: {e}")
            continue

        wk_matches = [m for m in matches if has_wk_team(m)]
        print(f"  {comp_name} {season} — {len(wk_matches)}/{len(matches)} wedstrijden")

        for match in wk_matches:
            match_id_sb = match["match_id"]
            match_id    = f"sb_{match_id_sb}"

            try:
                # 1. Match opslaan
                match_record = process_match(match, comp)
                sb.from_("matches").upsert(
                    match_record, on_conflict="match_id"
                ).execute()

                # 2. Events ophalen
                raw_events = fetch_json(f"events/{match_id_sb}.json")
                time.sleep(REQUEST_DELAY)

                # 3. Team stats
                team_records = process_team_stats(match, raw_events)
                upload("team_stats", team_records, "match_id,team")

                # 4. Speler stats
                player_records = process_player_stats(match, raw_events)
                upload("player_stats", player_records, "match_id,player_name,team")

                # 5. Events opslaan
                event_records = process_events(match, raw_events)
                upload("events", event_records, "event_id")

                total_matches += 1
                print(f"    ✓ {match_id} verwerkt ({total_matches} totaal)")

            except Exception as e:
                errors.append(f"Match {match_id}: {e}")
                continue

    print(f"\n{'=' * 55}")
    print(f"  Klaar! {total_matches} wedstrijden volledig verwerkt")
    if errors:
        print(f"\n  ⚠ {len(errors)} fouten:")
        for err in errors[:10]:
            print(f"    - {err}")
    print("=" * 55)


if __name__ == "__main__":
    run()
