def normalize_name(name: str) -> str:
    return "".join(c.lower() for c in name if c.isalnum())


def get_winrate(wins: int, matches: int) -> str:
    if matches <= 0:
        return "0%"
    return f"{int((wins / matches) * 100)}%"


def ensure_player_profile(data: dict, user_id: str, username: str):
    if "players" not in data:
        data["players"] = {}

    if user_id not in data["players"]:
        data["players"][user_id] = {
            "name": username,
            "points": 0,
            "wins": 0,
            "matches": 0,
            "streak": 0,
            "yellow_cards": 0
        }
