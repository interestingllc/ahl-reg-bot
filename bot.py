import os
import json
import requests
from datetime import datetime, timezone

TELEGRAM_TOKEN = "9222342874:AAE5HcLB6w-niLGjblNfSyN5D3uxXrA96iw"
TELEGRAM_CHAT_ID = "207711581"
API_KEY_ODDS = "9b60552be1354eeca4cf50ceb83c52ef"
MIN_STREAK = 7
BASE_UNIT = 100  # 100 AMD
STATE_FILE = "last_streaks.json"

NHL_TEAM_MAP = {
    "ANA": "Anaheim Ducks", "BOS": "Boston Bruins", "BUF": "Buffalo Sabres", "CGY": "Calgary Flames",
    "CAR": "Carolina Hurricanes", "CHI": "Chicago Blackhawks", "COL": "Colorado Avalanche", "CBJ": "Columbus Blue Jackets",
    "DAL": "Dallas Stars", "DET": "Detroit Red Wings", "EDM": "Edmonton Oilers", "FLA": "Florida Panthers",
    "LAK": "Los Angeles Kings", "MIN": "Minnesota Wild", "MTL": "Montreal Canadiens", "NSH": "Nashville Predators",
    "NJD": "New Jersey Devils", "NYI": "New York Islanders", "NYR": "New York Rangers", "OTT": "Ottawa Senators",
    "PHI": "Philadelphia Flyers", "PIT": "Pittsburgh Penguins", "SJS": "San Jose Sharks", "SEA": "Seattle Kraken",
    "STL": "St Louis Blues", "TBL": "Tampa Bay Lightning", "TOR": "Toronto Maple Leafs", "UTA": "Utah Hockey Club",
    "VAN": "Vancouver Canucks", "VGK": "Vegas Golden Knights", "WSH": "Washington Capitals", "WPG": "Winnipeg Jets"
}

FIBONACCI = [1, 1, 2, 3, 5, 8, 13, 21, 34, 55, 89, 144]

def get_fibonacci_bet(streak, base_amount=100):
    idx = max(0, streak - 7)
    if idx >= len(FIBONACCI):
        idx = len(FIBONACCI) - 1
    units = FIBONACCI[idx]
    return idx + 1, units, f"{units * base_amount:,}"

def send_telegram(msg):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {"chat_id": TELEGRAM_CHAT_ID, "text": msg, "parse_mode": "HTML"}
    try:
        requests.post(url, json=payload, timeout=10)
    except Exception as e:
        print(f"Telegram error: {e}")

def run_tracker():
    print("Starting NHL Tracker with chronological sorting...")
    
    prev_teams = []
    if os.path.exists(STATE_FILE):
        try:
            with open(STATE_FILE, "r", encoding="utf-8") as f:
                prev_teams = json.load(f)
        except Exception:
            pass

    all_odds = []
    try:
        odds_url = f"https://api.the-odds-api.com/v4/sports/icehockey_nhl/odds/?apiKey={API_KEY_ODDS}&regions=us,eu&markets=h2h,h2h_3way"
        r = requests.get(odds_url, timeout=10)
        if r.status_code == 200:
            all_odds = r.json()
    except Exception as e:
        print(f"Odds API error: {e}")

    current_hot = []
    nhl_results = []
    nhl_streaks, nhl_schedules, nhl_last_outcomes = {}, {}, {}

    # 1. NHL Analysis
    for abbr, full_name in NHL_TEAM_MAP.items():
        try:
            res = requests.get(f"https://api-web.nhle.com/v1/club-schedule-season/{abbr}/now", timeout=10).json()
            games = [g for g in res.get("games", []) if g.get("gameType") == 2]
            if games:
                nhl_schedules[abbr] = games
                completed = [g for g in games if g.get("gameState") in ["OFF", "FINAL"]]
                if completed:
                    completed.sort(key=lambda x: x["gameDate"], reverse=True)
                    last_g = completed[0]
                    nhl_last_outcomes[abbr] = {
                        "period": last_g.get("gameOutcome", {}).get("lastPeriodType"),
                        "score": f"{last_g['awayTeam']['abbrev']} {last_g['awayTeam']['score']} - {last_g['homeTeam']['score']} {last_g['homeTeam']['abbrev']}"
                    }
                    
                    # Calculate consecutive REG games (not reaching OT/SO)
                    cnt = 0
                    for g in completed:
                        pt = g.get("gameOutcome", {}).get("lastPeriodType")
                        if pt in ["OT", "SO"]:
                            break
                        cnt += 1
                    nhl_streaks[abbr] = cnt
        except Exception as e:
            print(f"NHL error for {abbr}: {e}")

    # Check for streak breaks/resets
    reset_message = ""
    for prev_item in prev_teams:
        if prev_item.startswith("NHL:"):
            p_team = prev_item.split(":")[1]
            if p_team in nhl_streaks and nhl_streaks[p_team] < MIN_STREAK:
                reset_message += f"⚠️ <b>ՇԱՐՔԸ ԸՆԴՀԱՏՎԵՑ</b>\n"
                reset_message += f"• <b>NHL: {p_team}</b> — Անընդմեջ REG շարքը նվազել է (< 7)\n  ❌ Թիմը դուրս եկավ ցուցակից:\n\n"

    for abbr, streak in nhl_streaks.items():
        if streak >= MIN_STREAK:
            current_hot.append(f"NHL:{abbr}")
            step, units, total_amd = get_fibonacci_bet(streak, BASE_UNIT)
            last_score = nhl_last_outcomes[abbr]["score"]
            full_name = NHL_TEAM_MAP[abbr]

            games = nhl_schedules.get(abbr, [])
            upcoming = [g for g in games if g.get("gameState") in ["FUT", "PRE"]]
            upcoming.sort(key=lambda x: x.get("startTimeUTC", ""))

            next_opp = "Անհայտ"
            next_opp_abbr = ""
            next_time = "Անհայտ"
            raw_datetime = None
            opp_streak_str = ""
            game_odds_str = ""

            if upcoming:
                ng = upcoming[0]
                is_home = (ng.get("homeTeam", {}).get("abbrev") == abbr)
                if is_home:
                    next_opp_abbr = ng.get("awayTeam", {}).get("abbrev")
                    next_opp = f"vs {next_opp_abbr}"
                else:
                    next_opp_abbr = ng.get("homeTeam", {}).get("abbrev")
                    next_opp = f"@ {next_opp_abbr}"

                if next_opp_abbr in nhl_streaks:
                    opp_streak_str = f" (շարքը՝ {nhl_streaks[next_opp_abbr]} խաղ)"
                else:
                    opp_streak_str = " (շարքը՝ 0 խաղ)"

                start_time_utc = ng.get("startTimeUTC")
                if start_time_utc:
                    try:
                        dt = datetime.fromisoformat(start_time_utc.replace("Z", "+00:00"))
                        raw_datetime = dt
                        next_time = dt.strftime("%d.%m.%Y %H:%M")
                    except Exception:
                        next_time = start_time_utc

                opp_full_name = NHL_TEAM_MAP.get(next_opp_abbr, "")
                for o_game in all_odds:
                    home_team = o_game.get("home_team")
                    away_team = o_game.get("away_team")
                    if (home_team == full_name and away_team == opp_full_name) or (home_team == opp_full_name and away_team == full_name):
                        target_bm = None
                        target_market = None
                        for bm in o_game.get("bookmakers", []):
                            m3 = [m for m in bm.get("markets", []) if m.get("key") == "h2h_3way"]
                            if m3:
                                target_bm = bm
                                target_market = m3[0]
                                break
                        if not target_market and o_game.get("bookmakers"):
                            target_bm = o_game["bookmakers"][0]
                            m2 = [m for m in target_bm.get("markets", []) if m.get("key") == "h2h"]
                            if m2:
                                target_market = m2[0]

                        if target_market:
                            bm_title = target_bm.get("title", "")
                            game_odds_str = f"  💰 <b>Գործակիցներ ({bm_title}):</b>\n"
                            draw_price = ""
                            for out in target_market.get("outcomes", []):
                                out_name = out.get("name")
                                out_price = out.get("price")
                                if out_name == "Draw":
                                    draw_price = out_price
                                else:
                                    t_abbr = out_name
                                    for k, v in NHL_TEAM_MAP.items():
                                        if v == out_name:
                                            t_abbr = k
                                            break
                                    game_odds_str += f"     • {t_abbr}: <b>{out_price}</b>\n"
                            if draw_price != "":
                                game_odds_str += f"     • <b>Ոչ-Ոքի (X): {draw_price}</b>\n"
                        break

            nhl_results.append({
                "team": f"NHL: {abbr}", "streak": streak, "step": step, "units": units,
                "total": total_amd, "score": last_score, "opp": f"{next_opp}{opp_streak_str}",
                "time": next_time, "raw_time": raw_datetime, "odds": game_odds_str
            })

    # Sort results chronologically by next match time (closest game first)
    nhl_results.sort(key=lambda x: x["raw_time"] if x["raw_time"] is not None else datetime.max.replace(tzinfo=timezone.utc))

    # Build & Send Telegram message
    final_msg = ""
    if reset_message:
        final_msg += reset_message

    if nhl_results:
        final_msg += "🏒 <b>NHL HOT REG STREAKS (7+ Games)</b>\n\n"
        for item in nhl_results:
            final_msg += f"• <b>{item['team']}</b> — <code>{item['streak']} խաղ</code> անընդմեջ (REG)\n"
            final_msg += f"  📊 <b>Ֆիբոնաչի Քայլ {item['step']}:</b> <code>{item['units']} unit</code> (<b>{item['total']} ֏</b>)\n"
            final_msg += f"  ▫️ Վերջինը՝ <i>{item['score']}</i>\n"
            final_msg += f"  ▫️ Հաջորդը՝ <b>{item['opp']}</b>\n"
            final_msg += f"  📅 Ժամը՝ <code>{item['time']}</code>\n"
            if item['odds']:
                final_msg += f"{item['odds']}"
            final_msg += "\n"

    if final_msg:
        send_telegram(final_msg)
    else:
        print("7+ REG շարքով թիմեր չեն գտնվել:")

    with open(STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(current_hot, f)

if __name__ == "__main__":
    run_tracker()
