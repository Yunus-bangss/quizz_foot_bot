import discord
from discord import app_commands
from discord.ext import commands

from storage import load_data, save_data


def ensure_root(data):
    if not isinstance(data, dict):
        data = {}
    data.setdefault("players", {})
    data.setdefault("tournaments", {})
    data.setdefault("seasons", {})
    return data


def safe_int_key(value):
    try:
        return int(value)
    except Exception:
        return 0


def next_numeric_id(mapping):
    numeric_ids = [safe_int_key(k) for k in mapping.keys()]
    return str(max(numeric_ids, default=0) + 1)


def ensure_player(data, uid, display_name):
    players = data["players"]
    if uid not in players or not isinstance(players[uid], dict):
        players[uid] = {
            "name": display_name,
            "points": 0,
            "wins": 0,
            "matches": 0,
            "streak": 0,
            "yellow_cards": 0
        }
    else:
        players[uid].setdefault("name", display_name)
        players[uid].setdefault("points", 0)
        players[uid].setdefault("wins", 0)
        players[uid].setdefault("matches", 0)
        players[uid].setdefault("streak", 0)
        players[uid].setdefault("yellow_cards", 0)
        players[uid]["name"] = display_name
    return players[uid]


def member_name(interaction, uid, players):
    try:
        if interaction.guild:
            m = interaction.guild.get_member(int(uid))
            if m:
                return m.display_name
    except Exception:
        pass
    return players.get(uid, {}).get("name", f"User {uid}")


def create_bracket(participants):
    participants = [p for p in participants if isinstance(p, str) and p]
    if len(participants) < 2:
        return []

    size = 1
    while size < len(participants):
        size *= 2

    padded = participants + [None] * (size - len(participants))
    rounds = []
    current = padded

    while len(current) > 1:
        round_matches = []
        next_round = []
        for i in range(0, len(current), 2):
            p1 = current[i]
            p2 = current[i + 1]
            match = {
                "player1": p1,
                "player2": p2,
                "winner": None,
                "played": False
            }
            round_matches.append(match)

            if p1 is not None and p2 is None:
                next_round.append(p1)
                match["winner"] = p1
                match["played"] = True
            elif p1 is None and p2 is not None:
                next_round.append(p2)
                match["winner"] = p2
                match["played"] = True

        rounds.append(round_matches)
        current = next_round if next_round else []

        if len(current) == 1:
            break

    if len(rounds) == 0:
        rounds.append([])

    return rounds


class TournamentsCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="create_tournament", description="Créer un tournoi")
    @app_commands.describe(name="Nom du tournoi")
    async def create_tournament(self, interaction: discord.Interaction, name: str):
        await interaction.response.defer()

        name = name.strip()
        if not name:
            await interaction.followup.send("❌ Le nom du tournoi ne peut pas être vide.")
            return

        data = ensure_root(load_data())
        tournaments = data["tournaments"]
        tid = next_numeric_id(tournaments)

        tournaments[tid] = {
            "name": name,
            "creator_id": interaction.user.id,
            "creator_name": interaction.user.display_name,
            "participants": [],
            "started": False,
            "finished": False,
            "rounds": [],
            "current_round": 0,
            "current_match": 0,
            "winner_id": None
        }

        save_data(data)

        await interaction.followup.send(
            f"🏆 Tournoi créé : **{name}**\nID : `{tid}`"
        )

    @app_commands.command(name="join_tournament", description="Rejoindre un tournoi")
    @app_commands.describe(tournament_id="ID du tournoi")
    async def join_tournament(self, interaction: discord.Interaction, tournament_id: str):
        await interaction.response.defer()

        data = ensure_root(load_data())
        tournaments = data["tournaments"]

        if tournament_id not in tournaments or not isinstance(tournaments[tournament_id], dict):
            await interaction.followup.send("❌ Tournoi introuvable.")
            return

        tournament = tournaments[tournament_id]
        uid = str(interaction.user.id)

        if tournament.get("started", False):
            await interaction.followup.send("❌ Le tournoi a déjà commencé.")
            return

        participants = tournament.setdefault("participants", [])
        if uid in participants:
            await interaction.followup.send("⚠️ Tu es déjà inscrit.")
            return

        participants.append(uid)
        ensure_player(data, uid, interaction.user.display_name)
        save_data(data)

        await interaction.followup.send(
            f"✅ {interaction.user.mention} a rejoint **{tournament.get('name', 'Tournoi')}**."
        )

    @app_commands.command(name="leave_tournament", description="Quitter un tournoi")
    @app_commands.describe(tournament_id="ID du tournoi")
    async def leave_tournament(self, interaction: discord.Interaction, tournament_id: str):
        await interaction.response.defer()

        data = ensure_root(load_data())
        tournaments = data["tournaments"]

        if tournament_id not in tournaments or not isinstance(tournaments[tournament_id], dict):
            await interaction.followup.send("❌ Tournoi introuvable.")
            return

        tournament = tournaments[tournament_id]
        uid = str(interaction.user.id)

        if tournament.get("started", False):
            await interaction.followup.send("❌ Impossible de quitter un tournoi déjà commencé.")
            return

        participants = tournament.setdefault("participants", [])
        if uid not in participants:
            await interaction.followup.send("❌ Tu n’es pas inscrit.")
            return

        participants.remove(uid)
        save_data(data)

        await interaction.followup.send(
            f"✅ {interaction.user.mention} a quitté **{tournament.get('name', 'Tournoi')}**."
        )

    @app_commands.command(name="start_tournament", description="Lancer un tournoi")
    @app_commands.describe(tournament_id="ID du tournoi")
    async def start_tournament(self, interaction: discord.Interaction, tournament_id: str):
        await interaction.response.defer()

        data = ensure_root(load_data())
        tournaments = data["tournaments"]

        if tournament_id not in tournaments or not isinstance(tournaments[tournament_id], dict):
            await interaction.followup.send("❌ Tournoi introuvable.")
            return

        tournament = tournaments[tournament_id]
        if tournament.get("creator_id") != interaction.user.id:
            await interaction.followup.send("⛔ Seul le créateur peut lancer le tournoi.")
            return

        if tournament.get("started", False):
            await interaction.followup.send("⚠️ Le tournoi est déjà lancé.")
            return

        participants = tournament.get("participants", [])
        participants = [uid for uid in participants if isinstance(uid, str)]
        if len(participants) < 2:
            await interaction.followup.send("❌ Il faut au moins 2 participants.")
            return

        tournament["rounds"] = create_bracket(participants)
        tournament["started"] = True
        tournament["finished"] = False
        tournament["current_round"] = 0
        tournament["current_match"] = 0
        tournament["winner_id"] = None

        save_data(data)

        await interaction.followup.send(
            f"🚀 Tournoi **{tournament.get('name', 'Tournoi')}** démarré.\n"
            f"Participants : {len(participants)}\n"
            f"Rounds générés : {len(tournament['rounds'])}"
        )

    @app_commands.command(name="advance_tournament", description="Valider le gagnant du match courant")
    @app_commands.describe(tournament_id="ID du tournoi", winner_id="ID du gagnant")
    async def advance_tournament(self, interaction: discord.Interaction, tournament_id: str, winner_id: str):
        await interaction.response.defer()

        data = ensure_root(load_data())
        tournaments = data["tournaments"]

        if tournament_id not in tournaments or not isinstance(tournaments[tournament_id], dict):
            await interaction.followup.send("❌ Tournoi introuvable.")
            return

        tournament = tournaments[tournament_id]
        if not tournament.get("started", False) or tournament.get("finished", False):
            await interaction.followup.send("❌ Tournoi non actif.")
            return

        if interaction.user.id != tournament.get("creator_id"):
            await interaction.followup.send("⛔ Seul le créateur peut valider les résultats.")
            return

        rounds = tournament.get("rounds", [])
        r = tournament.get("current_round", 0)
        m = tournament.get("current_match", 0)

        if r >= len(rounds) or m >= len(rounds[r]):
            await interaction.followup.send("❌ Aucun match courant à valider.")
            return

        match = rounds[r][m]
        if match.get("played", False):
            await interaction.followup.send("⚠️ Ce match a déjà été validé.")
            return

        p1 = match.get("player1")
        p2 = match.get("player2")
        winner_id = str(winner_id)

        if winner_id not in {p1, p2}:
            await interaction.followup.send("❌ Le gagnant doit être un des deux joueurs du match.")
            return

        match["winner"] = winner_id
        match["played"] = True

        next_round_index = r + 1
        if next_round_index >= len(rounds):
            tournament["finished"] = True
            tournament["winner_id"] = winner_id
            save_data(data)
            await interaction.followup.send(
                f"🏁 Match validé.\n🏆 Tournoi terminé ! Gagnant : **{member_name(interaction, winner_id, data['players'])}**"
            )
            return

        if not rounds[next_round_index]:
            rounds[next_round_index] = []

        next_round = rounds[next_round_index]
        placed = False
        for slot in next_round:
            if slot.get("player1") is None:
                slot["player1"] = winner_id
                placed = True
                break
            if slot.get("player2") is None:
                slot["player2"] = winner_id
                placed = True
                break

        if not placed:
            next_round.append({
                "player1": winner_id,
                "player2": None,
                "winner": None,
                "played": False
            })

        tournament["current_match"] = m + 1
        if tournament["current_match"] >= len(rounds[r]):
            tournament["current_round"] = r + 1
            tournament["current_match"] = 0

        save_data(data)

        await interaction.followup.send(
            f"✅ Match validé. Gagnant : **{member_name(interaction, winner_id, data['players'])}**"
        )

    @app_commands.command(name="tournament_status", description="Voir l'état d'un tournoi")
    @app_commands.describe(tournament_id="ID du tournoi")
    async def tournament_status(self, interaction: discord.Interaction, tournament_id: str):
        await interaction.response.defer()

        data = ensure_root(load_data())
        tournaments = data["tournaments"]

        if tournament_id not in tournaments or not isinstance(tournaments[tournament_id], dict):
            await interaction.followup.send("❌ Tournoi introuvable.")
            return

        tournament = tournaments[tournament_id]
        players = data["players"]

        status = "Terminé" if tournament.get("finished") else ("En cours" if tournament.get("started") else "En inscription")

        embed = discord.Embed(
            title=f"🏆 {tournament.get('name', 'Tournoi')}",
            color=0xFFD700
        )
        embed.add_field(name="ID", value=tournament_id, inline=True)
        embed.add_field(name="Créateur", value=tournament.get("creator_name", "Inconnu"), inline=True)
        embed.add_field(name="Statut", value=status, inline=True)
        embed.add_field(name="Participants", value=str(len(tournament.get("participants", []))), inline=True)

        if tournament.get("winner_id"):
            embed.add_field(
                name="Vainqueur",
                value=member_name(interaction, tournament["winner_id"], players),
                inline=False
            )

        participants = tournament.get("participants", [])
        if participants:
            names = [member_name(interaction, uid, players) for uid in participants[:20]]
            embed.add_field(name="Liste", value="\n".join(names), inline=False)

        await interaction.followup.send(embed=embed)

    @app_commands.command(name="tournament_delete", description="Supprimer un tournoi")
    @app_commands.describe(tournament_id="ID du tournoi")
    async def tournament_delete(self, interaction: discord.Interaction, tournament_id: str):
        await interaction.response.defer()

        data = ensure_root(load_data())
        tournaments = data["tournaments"]

        if tournament_id not in tournaments or not isinstance(tournaments[tournament_id], dict):
            await interaction.followup.send("❌ Tournoi introuvable.")
            return

        tournament = tournaments[tournament_id]
        if tournament.get("creator_id") != interaction.user.id:
            await interaction.followup.send("⛔ Seul le créateur peut supprimer ce tournoi.")
            return

        del tournaments[tournament_id]
        save_data(data)

        await interaction.followup.send(f"🗑️ Tournoi **{tournament.get('name', 'Tournoi')}** supprimé.")

async def setup(bot):
    await bot.add_cog(TournamentsCog(bot))