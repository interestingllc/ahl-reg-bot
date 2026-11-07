import os
import json
import requests

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
    print("Starting NHL Tracker...")
    prev_teams = []
    if os.path.exists(STATE_FILE):
        try:
            with open(STATE_FILE, "r", encoding="utf-8") as f:
                prev_teams = json.load(f)
        except Exception:
            pass

    current_hot = []
    nhl_results = []
    nhl_streaks, nhl_last_outcomes = {}, {}

    # 1. NHL Analysis
    for abbr, full_name in NHL_TEAM_MAP.items():
        try:
            res = requests.get(f"https://api-web.nhle.com/v1/club-schedule-season/{abbr}/now", timeout=10).json()
            games = [g for g in res.get("games", []) if g.get("gameType") == 2]
            completed = [g for g in games if g.get("gameState") in ["OFF", "FINAL"]]
            if completed:
                completed.sort(key=lambda x: x["gameDate"], reverse=True)
                last_g = completed[0]
                nhl_last_outcomes[abbr] = {
                    "period": last_g.get("gameOutcome", {}).get("lastPeriodType"),
                    "score": f"{last_g['awayTeam']['abbrev']} {last_g['awayTeam']['score']} - {last_g['homeTeam']['score']} {last_g['homeTeam']['abbrev']}"
                }
                cnt = 0
                for g in completed:
                    pt = g.get("gameOutcome", {}).get("lastPeriodType")
                    if pt in ["OT", "SO"]:
                        break
                    cnt += 1
                nhl_streaks[abbr] = cnt
        except Exception as e:
            print(f"NHL error for {abbr}: {e}")

    for abbr, streak in nhl_streaks.items():
        if streak >= MIN_STREAK:
            current_hot.append(f"NHL:{abbr}")
            step, units, total_amd = get_fibonacci_bet(streak, BASE_UNIT)
            last_score = nhl_last_outcomes[abbr]["score"]

            nhl_results.append({
                "team": f"NHL: {abbr}", "streak": streak, "step": step, "units": units,
                "total": total_amd, "score": last_score
            })

    # Build & Send Telegram message
    msg = ""
    if nhl_results:
        msg += "🏒 <b>NHL HOT REG STREAKS (7+ Games)</b>\n\n"
        for item in nhl_results:
            msg += f"• <b>{item['team']}</b> — <code>{item['streak']} խաղ</code> (REG)\n"
            msg += f"  📊 <b>Ֆիբոնաչի Քայլ {item['step']}:</b> <code>{item['units']} unit</code> (<b>{item['total']} ֏</b>)\n"
            msg += f"  ▫️ Վերջինը՝ <i>{item['score']}</i>\n\n"
        send_telegram(msg)
    else:
        print("7+ REG շարքով NHL թիմեր չեն գտնվել:")

    with open(STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(current_hot, f)

if __name__ == "__main__":
    run_tracker()
