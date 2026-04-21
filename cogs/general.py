import asyncio
import logging
import random
from datetime import datetime

import discord
from discord import app_commands
from discord.ext import commands

from storage import load_data, save_data, load_questions
from utils.helpers import normalize_name, get_winrate, ensure_player_profile

logger = logging.getLogger("QuizFootBot.General")


ACHIEVEMENTS_LIST = {
    "first_win": {"name": "Premier Match Gagné", "desc": "Gagne ton premier match", "emoji": "🎉"},
    "hattrick": {"name": "Hat-Trick", "desc": "Gagne 3-0", "emoji": "🎯"},
    "streak5": {"name": "Série de 5", "desc": "5 victoires d'affilée", "emoji": "🔥"},
    "daily_streak": {"name": "Quotidien", "desc": "7 jours de suite", "emoji": "📅"},
}


class GeneralCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="help", description="Affiche toutes les commandes")
    async def help_command(self, interaction: discord.Interaction):
        await interaction.response.defer()

        embed = discord.Embed(title="⚽ QUIZ FOOT BOT - COMMANDES", color=0x00FF00)
        embed.add_field(name="🎮 Jouer", value="/quiz @joueur\n/train", inline=False)
        embed.add_field(name="⚡ Modes", value="/eliminator @joueur\n/speed @joueur", inline=False)
        embed.add_field(name="📊 Stats", value="/stats\n/ladder\n/achievements", inline=False)
        embed.add_field(name="❓ Questions", value="/question_count\n/question_list\n/add_question\n/delete_question", inline=False)
        embed.add_field(name="🏆 Tournoi", value="/create_tournament\n/join_tournament\n/start_tournament", inline=False)
        embed.add_field(name="🏅 Saison", value="/create_season\n/join_season\n/season_ranking", inline=False)
        embed.add_field(name="📜 Divers", value="/rules\n/daily\n/cancel", inline=False)

        await interaction.followup.send(embed=embed)

    @app_commands.command(name="rules", description="Voir le règlement")
    async def rules(self, interaction: discord.Interaction):
        await interaction.response.defer()

        embed = discord.Embed(title="⚽ QUIZ FOOT - Règlement", color=0x00FF00)
        embed.add_field(name="Jeu", value="5 questions, 10 secondes par question", inline=False)
        embed.add_field(name="Points", value="Victoire = 3, Nul = 1, Défaite = 0", inline=False)
        embed.add_field(name="Réponses", value="Format prénom + nom, sauf exceptions comme Pelé ou Kaká", inline=False)
        embed.add_field(name="VAR", value="Écris `La Var` en cas de contestation", inline=False)
        embed.add_field(name="Sanctions", value="Avertissement, jaune, rouge selon abus", inline=False)

        await interaction.followup.send(embed=embed)

    @app_commands.command(name="ladder", description="Voir le classement")
    async def ladder(self, interaction: discord.Interaction):
        await interaction.response.defer()

        data = load_data()
        players = sorted(data["players"].values(), key=lambda x: x.get("points", 0), reverse=True)

        if not players:
            await interaction.followup.send("📊 Aucun classement pour l'instant.")
            return

        embed = discord.Embed(title="🏆 Classement Quiz Foot", color=0xFFD700)
        for i, p in enumerate(players[:10], 1):
            wins = p.get("wins", 0)
            matches = p.get("matches", 0)
            winrate = get_winrate(wins, matches)
            embed.add_field(
                name=f"{i}. {p['name']}",
                value=f"{p.get('points', 0)} pts | {winrate}",
                inline=False
            )

        await interaction.followup.send(embed=embed)

    @app_commands.command(name="stats", description="Voir tes statistiques")
    async def stats(self, interaction: discord.Interaction):
        await interaction.response.defer()

        data = load_data()
        uid = str(interaction.user.id)

        if uid not in data["players"]:
            await interaction.followup.send("❌ Aucune stat pour le moment.")
            return

        p = data["players"][uid]
        matches = p.get("matches", 0)
        wr = get_winrate(p.get("wins", 0), matches)

        embed = discord.Embed(title=f"📊 Stats de {interaction.user.name}", color=0x00FF00)
        embed.add_field(name="Points", value=p.get("points", 0), inline=True)
        embed.add_field(name="Matchs", value=p.get("matches", 0), inline=True)
        embed.add_field(name="Victoires", value=p.get("wins", 0), inline=True)
        embed.add_field(name="Série", value=p.get("streak", 0), inline=True)
        embed.add_field(name="Win Rate", value=wr, inline=True)

        await interaction.followup.send(embed=embed)

    @app_commands.command(name="achievements", description="Voir tes achievements")
    async def achievements(self, interaction: discord.Interaction):
        await interaction.response.defer()

        data = load_data()
        uid = str(interaction.user.id)
        achs = data.get("achievements", {}).get(uid, [])

        if not achs:
            await interaction.followup.send("❌ Aucun achievement débloqué.")
            return

        embed = discord.Embed(title=f"🏅 Achievements de {interaction.user.name}", color=0xFFD700)
        for a in achs:
            if a in ACHIEVEMENTS_LIST:
                embed.add_field(
                    name=f"{ACHIEVEMENTS_LIST[a]['emoji']} {ACHIEVEMENTS_LIST[a]['name']}",
                    value=ACHIEVEMENTS_LIST[a]["desc"],
                    inline=False
                )

        await interaction.followup.send(embed=embed)

    @app_commands.command(name="daily", description="Quiz quotidien (+2 pts)")
    async def daily(self, interaction: discord.Interaction):
        await interaction.response.defer()

        questions = load_questions()
        if not questions:
            await interaction.followup.send("❌ Aucune question disponible. Ajoute des questions avec /add_question.", ephemeral=True)
            return

        data = load_data()
        uid = str(interaction.user.id)
        today = datetime.now().strftime("%Y-%m-%d")

        if "daily" not in data:
            data["daily"] = {}

        if today in data["daily"] and uid in data["daily"][today]:
            await interaction.followup.send("❌ Tu as déjà fait le daily aujourd'hui.", ephemeral=True)
            return

        try:
            q = random.choice(questions)
            if not isinstance(q, dict) or "question" not in q or "answer" not in q:
                await interaction.followup.send("❌ Erreur: question invalide.", ephemeral=True)
                return
        except IndexError:
            await interaction.followup.send("❌ Aucune question valide disponible.", ephemeral=True)
            return

        await interaction.followup.send(f"📅 **DAILY QUIZ**\n{q['question']}")

        def check(msg):
            return msg.channel == interaction.channel and msg.author == interaction.user

        try:
            msg = await self.bot.wait_for("message", timeout=15.0, check=check)

            if normalize_name(msg.content) == normalize_name(q["answer"]):
                ensure_player_profile(data, uid, interaction.user.name)
                data["players"][uid]["points"] += 2

                if today not in data["daily"]:
                    data["daily"][today] = []

                data["daily"][today].append(uid)
                save_data(data)

                await interaction.followup.send(f"✅ Correct ! Réponse : **{q['answer']}** (+2 pts)")
            else:
                await interaction.followup.send(f"❌ Faux. Réponse : **{q['answer']}**")

        except asyncio.TimeoutError:
            await interaction.followup.send("⏰ Temps écoulé.")
        except Exception as e:
            # FIX: supprimé la redéfinition de logger à l'intérieur du except
            logger.error(f"Erreur daily quiz: {e}")
            await interaction.followup.send("❌ Une erreur est survenue.")


async def setup(bot):
    await bot.add_cog(GeneralCog(bot))
