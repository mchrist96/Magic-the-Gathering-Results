"""Recompute all derived stats from the game tracker.

Reads data/2026_mtg_tracker.csv (the file you edit by hand) and regenerates:
  - data/deck_results.csv                 per-deck stats, sorted by average placement
  - data/deck_results_5_or_more_games.csv same, filtered to decks with 5+ games
  - data/full_deck_list.csv              per-deck stats grouped by owner
  - data/player_summary.csv              per-player stats

Rules (matching the original Google Sheet):
  - A win is placement 1. Ties are allowed, so a game can have multiple
    winners or none recorded.
  - Last place is the worst (highest) placement among the players who
    played that game; everyone tied at that placement counts as last.
  - A blank placement means that player sat the game out.
  - Diversity score is total games played divided by unique decks played.
  - Decks are sometimes borrowed; a deck's stats pool across pilots. A
    deck's Owner comes from data/deck_owners.csv (add new decks there);
    a deck missing from that file falls back to its most frequent pilot
    and prints a warning.
  - Registered decks that have never been played still appear in
    full_deck_list.csv with zero games.

Usage:  python scripts/update_stats.py
"""

import csv
import os
from collections import defaultdict

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(ROOT, "data")
TRACKER = os.path.join(DATA, "2026_mtg_tracker.csv")
OWNERS = os.path.join(DATA, "deck_owners.csv")

PLAYERS = ["Mitchell", "Eric", "Hunter", "Harrison"]


def fmt(value, places=3):
    if isinstance(value, float):
        if value == int(value):
            return str(int(value))
        return f"{value:.{places}f}"
    return str(value)


def write_csv(name, header, rows):
    path = os.path.join(DATA, name)
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(header)
        writer.writerows(rows)
    print(f"wrote {name} ({len(rows)} rows)")


def main():
    with open(TRACKER, encoding="utf-8") as f:
        reader = csv.DictReader(f)
        games = list(reader)

    with open(OWNERS, encoding="utf-8") as f:
        owners = {r["Deck"].strip(): r["Owner"].strip()
                  for r in csv.DictReader(f) if r["Deck"].strip()}

    # deck -> stats; a deck name is assumed unique to one owner
    deck_stats = defaultdict(lambda: {"pilots": defaultdict(int), "games": 0,
                                      "wins": 0, "lasts": 0,
                                      "placement_sum": 0})
    player_stats = {p: {"games": 0, "wins": 0, "lasts": 0, "placement_sum": 0,
                        "decks": set()} for p in PLAYERS}

    game_count = 0
    for row in games:
        results = []  # (player, placement, deck)
        for p in PLAYERS:
            placement = row.get(f"{p} Placement", "").strip()
            deck = row.get(f"{p} Deck", "").strip()
            if placement:
                results.append((p, int(float(placement)), deck))
        if not results:
            continue
        game_count += 1
        worst = max(pl for _, pl, _ in results)

        for p, pl, deck in results:
            won = pl == 1
            last = pl == worst
            ps = player_stats[p]
            ps["games"] += 1
            ps["wins"] += won
            ps["lasts"] += last
            ps["placement_sum"] += pl
            if deck:
                ps["decks"].add(deck)
                ds = deck_stats[deck]
                ds["pilots"][p] += 1
                ds["games"] += 1
                ds["wins"] += won
                ds["lasts"] += last
                ds["placement_sum"] += pl

    # --- per-deck results, sorted by average placement then games played ---
    deck_rows = []
    for deck, ds in deck_stats.items():
        avg = ds["placement_sum"] / ds["games"]
        owner = owners.get(deck)
        if owner is None:
            owner = max(ds["pilots"], key=ds["pilots"].get)
            print(f"WARNING: '{deck}' not in deck_owners.csv; "
                  f"assuming owner {owner}")
        deck_rows.append([deck, owner, ds["games"], ds["wins"],
                          fmt(ds["wins"] / ds["games"]), fmt(avg),
                          ds["lasts"]])
    deck_rows.sort(key=lambda r: (float(r[5]), -r[2], r[0]))
    header = ["Deck", "Owner", "Games Played", "Wins", "Win Rate",
              "Average Placement", "Last Place Count"]
    write_csv("deck_results.csv", header, deck_rows)
    write_csv("deck_results_5_or_more_games.csv", header,
              [r for r in deck_rows if r[2] >= 5])

    # --- full deck list grouped by owner, best win rate first ---
    unplayed = [[deck, owner, 0, 0, "", "", 0]
                for deck, owner in owners.items() if deck not in deck_stats]
    owner_rows = sorted(
        deck_rows + unplayed,
        key=lambda r: (PLAYERS.index(r[1]), -float(r[4] or -1), r[0]))
    write_csv("full_deck_list.csv",
              ["Owner", "Deck", "Games Played", "Wins", "Win Rate",
               "Average Placement", "Last Place Count"],
              [[r[1], r[0], r[2], r[3], r[4], r[5], r[6]] for r in owner_rows])

    # --- player summary ---
    rows = []
    for p in PLAYERS:
        ps = player_stats[p]
        if ps["games"] == 0:
            continue
        unique = len(ps["decks"])
        rows.append([
            p,
            fmt(ps["placement_sum"] / ps["games"]),
            unique,
            ps["games"],
            fmt(ps["games"] / unique if unique else 0),
            ps["wins"],
            ps["lasts"],
            fmt(ps["wins"] / ps["games"]),
            fmt(ps["lasts"] / ps["games"]),
        ])
    write_csv("player_summary.csv",
              ["Player", "Average Placement", "Unique Decks Played",
               "Total Games Played", "Diversity Score", "Win Count",
               "Last Place Count", "Win Rate", "Last Place Rate"],
              rows)

    print(f"processed {game_count} games")


if __name__ == "__main__":
    main()
