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


class SeasonsCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="create_season", description="Créer une saison")
    @app_commands.describe(name="Nom de la saison")
    async def create_season(self, interaction: discord.Interaction, name: str):
        await interaction.response.defer()

        name = name.strip()
        if not name:
            await interaction.followup.send("❌ Le nom de la saison ne peut pas être vide.")
            return

        data = ensure_root(load_data())
        seasons = data["seasons"]
        sid = next_numeric_id(seasons)

        seasons[sid] = {
            "name": name,
            "creator_id": interaction.user.id,
            "creator_name": interaction.user.display_name,
            "participants": [],
            "active": True,
            "finished": False
        }

        save_data(data)

        await interaction.followup.send(
            f"🏅 Saison créée : **{name}**\nID : `{sid}`"
        )

    @app_commands.command(name="join_season", description="Rejoindre une saison")
    @app_commands.describe(season_id="ID de la saison")
    async def join_season(self, interaction: discord.Interaction, season_id: str):
        await interaction.response.defer()

        data = ensure_root(load_data())
        seasons = data["seasons"]

        if season_id not in seasons or not isinstance(seasons[season_id], dict):
            await interaction.followup.send("❌ Saison introuvable.")
            return

        season = seasons[season_id]
        if not season.get("active", False):
            await interaction.followup.send("❌ Cette saison n’est plus active.")
            return

        uid = str(interaction.user.id)
        participants = season.setdefault("participants", [])

        if uid in participants:
            await interaction.followup.send("⚠️ Tu es déjà inscrit à cette saison.")
            return

        participants.append(uid)
        ensure_player(data, uid, interaction.user.display_name)
        save_data(data)

        await interaction.followup.send(
            f"✅ {interaction.user.mention} a rejoint la saison **{season.get('name', 'Saison')}**."
        )

    @app_commands.command(name="leave_season", description="Quitter une saison")
    @app_commands.describe(season_id="ID de la saison")
    async def leave_season(self, interaction: discord.Interaction, season_id: str):
        await interaction.response.defer()

        data = ensure_root(load_data())
        seasons = data["seasons"]

        if season_id not in seasons or not isinstance(seasons[season_id], dict):
            await interaction.followup.send("❌ Saison introuvable.")
            return

        season = seasons[season_id]
        if not season.get("active", False):
            await interaction.followup.send("❌ Impossible de quitter une saison fermée.")
            return

        uid = str(interaction.user.id)
        participants = season.setdefault("participants", [])

        if uid not in participants:
            await interaction.followup.send("❌ Tu n’es pas inscrit à cette saison.")
            return

        participants.remove(uid)
        save_data(data)

        await interaction.followup.send(
            f"✅ {interaction.user.mention} a quitté la saison **{season.get('name', 'Saison')}**."
        )

    @app_commands.command(name="season_status", description="Voir l'état d'une saison")
    @app_commands.describe(season_id="ID de la saison")
    async def season_status(self, interaction: discord.Interaction, season_id: str):
        await interaction.response.defer()

        data = ensure_root(load_data())
        seasons = data["seasons"]

        if season_id not in seasons or not isinstance(seasons[season_id], dict):
            await interaction.followup.send("❌ Saison introuvable.")
            return

        season = seasons[season_id]
        players = data["players"]
        participants = season.get("participants", [])

        status = "Terminée" if season.get("finished") else ("Active" if season.get("active") else "Fermée")

        embed = discord.Embed(
            title=f"🏅 {season.get('name', 'Saison')}",
            color=0x00FF00
        )
        embed.add_field(name="ID", value=season_id, inline=True)
        embed.add_field(name="Créateur", value=season.get("creator_name", "Inconnu"), inline=True)
        embed.add_field(name="Statut", value=status, inline=True)
        embed.add_field(name="Participants", value=str(len(participants)), inline=True)

        if participants:
            names = [member_name(interaction, uid, players) for uid in participants[:20]]
            embed.add_field(name="Liste", value="\n".join(names), inline=False)

        await interaction.followup.send(embed=embed)

    @app_commands.command(name="season_ranking", description="Voir le classement de la saison")
    @app_commands.describe(season_id="ID de la saison")
    async def season_ranking(self, interaction: discord.Interaction, season_id: str):
        await interaction.response.defer()

        data = ensure_root(load_data())
        seasons = data["seasons"]
        players = data["players"]

        if season_id not in seasons or not isinstance(seasons[season_id], dict):
            await interaction.followup.send("❌ Saison introuvable.")
            return

        season = seasons[season_id]
        participants = [uid for uid in season.get("participants", []) if isinstance(uid, str)]
        if not participants:
            await interaction.followup.send("❌ Aucun participant dans cette saison.")
            return

        ranking_ids = sorted(
            participants,
            key=lambda uid: (
                players.get(uid, {}).get("points", 0),
                players.get(uid, {}).get("wins", 0),
                players.get(uid, {}).get("matches", 0)
            ),
            reverse=True
        )

        embed = discord.Embed(
            title=f"🏆 Classement - {season.get('name', 'Saison')}",
            color=0xFFD700
        )

        for i, uid in enumerate(ranking_ids[:10], 1):
            p = players.get(uid, {})
            embed.add_field(
                name=f"{i}. {member_name(interaction, uid, players)}",
                value=f"{p.get('points', 0)} pts | {p.get('wins', 0)} victoires | {p.get('matches', 0)} matchs",
                inline=False
            )

        await interaction.followup.send(embed=embed)

    @app_commands.command(name="end_season", description="Terminer une saison")
    @app_commands.describe(season_id="ID de la saison")
    async def end_season(self, interaction: discord.Interaction, season_id: str):
        await interaction.response.defer()

        data = ensure_root(load_data())
        seasons = data["seasons"]

        if season_id not in seasons or not isinstance(seasons[season_id], dict):
            await interaction.followup.send("❌ Saison introuvable.")
            return

        season = seasons[season_id]

        if season.get("creator_id") != interaction.user.id:
            await interaction.followup.send("⛔ Seul le créateur peut terminer la saison.")
            return

        if not season.get("active", False):
            await interaction.followup.send("⚠️ La saison est déjà fermée.")
            return

        season["active"] = False
        season["finished"] = True
        save_data(data)

        await interaction.followup.send(
            f"🏁 Saison **{season.get('name', 'Saison')}** terminée."
        )

    @app_commands.command(name="season_delete", description="Supprimer une saison")
    @app_commands.describe(season_id="ID de la saison")
    async def season_delete(self, interaction: discord.Interaction, season_id: str):
        await interaction.response.defer()

        data = ensure_root(load_data())
        seasons = data["seasons"]

        if season_id not in seasons or not isinstance(seasons[season_id], dict):
            await interaction.followup.send("❌ Saison introuvable.")
            return

        season = seasons[season_id]

        if season.get("creator_id") != interaction.user.id:
            await interaction.followup.send("⛔ Seul le créateur peut supprimer la saison.")
            return

        del seasons[season_id]
        save_data(data)

        await interaction.followup.send(
            f"🗑️ Saison **{season.get('name', 'Saison')}** supprimée."
        )

async def setup(bot):
    await bot.add_cog(SeasonsCog(bot))