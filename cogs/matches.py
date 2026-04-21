import asyncio
import logging
import random
import threading
from datetime import datetime

import discord
from discord import app_commands
from discord.ext import commands

from storage import load_data, save_data, load_questions_safe
from utils.helpers import normalize_name, ensure_player_profile

logger = logging.getLogger("QuizFootBot.Matches")

MAX_QUESTIONS_PER_MATCH = 5

pending_challenges = {}
_challenges_lock = threading.Lock()


def add_pending_challenge(challenger_id, data):
    with _challenges_lock:
        pending_challenges[challenger_id] = data


def remove_pending_challenge(challenger_id):
    with _challenges_lock:
        return pending_challenges.pop(challenger_id, None)


def get_pending_for_adversary(adversary_id):
    with _challenges_lock:
        for challenger_id, data in list(pending_challenges.items()):
            if data["adversary"].id == adversary_id:
                return challenger_id, data
        return None, None


def has_pending_challenge(user_id):
    with _challenges_lock:
        return user_id in pending_challenges


class QuizMatch:
    def __init__(self, bot, player1, player2, channel, mode="normal", is_cpu=False):
        self.bot = bot
        self.player1 = player1
        self.player2 = player2
        self.channel = channel
        self.mode = mode
        self.is_cpu = is_cpu
        self.score1 = 0
        self.score2 = 0
        questions = load_questions_safe()
        self.questions = random.sample(questions, min(MAX_QUESTIONS_PER_MATCH, len(questions))) if questions else []
        self.current_q = 0
        self.warnings = {}
        self.yellow_cards = {}
        self.var_requested = False
        self.game_over = False
        self.eliminated = None

    async def get_cpu_answer(self, q):
        await asyncio.sleep(random.uniform(2, 6))
        if random.random() < 0.6:
            return q["answer"]
        return "Mauvaise réponse"


def check_achievement(data, uid, achievement_key):
    if "achievements" not in data:
        data["achievements"] = {}
    if uid not in data["achievements"]:
        data["achievements"][uid] = []
    if achievement_key not in data["achievements"][uid]:
        data["achievements"][uid].append(achievement_key)
        return True
    return False


async def show_score(match: QuizMatch):
    await match.channel.send(
        f"📊 **SCORE** : {match.player1.display_name} **{match.score1}** - **{match.score2}** {match.player2.display_name}"
    )


async def handle_var(match: QuizMatch, requester, correct_answer):
    if match.var_requested:
        await match.channel.send("⛔ VAR déjà demandée sur cette question.")
        return

    match.var_requested = True
    other_player = match.player2 if requester == match.player1 else match.player1

    await match.channel.send(
        f"📺 **{requester.mention} demande la VAR !**\n"
        f"Arbitre : {other_player.mention}\n"
        f"Réponse exacte : **{correct_answer}**\n"
        f"Réponds par `valide` ou `reject`."
    )

    def check(msg):
        return (
            msg.channel == match.channel
            and msg.author == other_player
            and msg.content.lower() in ["valide", "valid", "reject", "refuse"]
        )

    try:
        decision = await asyncio.wait_for(
            match.bot.wait_for("message", check=check),
            timeout=15.0
        )
        if decision.content.lower() in ["valide", "valid"]:
            if requester == match.player1:
                match.score1 += 1
            else:
                match.score2 += 1
            await match.channel.send(f"✅ VAR validée : +1 pour {requester.mention}")
        else:
            await match.channel.send(f"❌ VAR rejetée : pas de point pour {requester.mention}")
    except asyncio.TimeoutError:
        await match.channel.send("⏰ Pas de décision VAR à temps.")
        match.warnings[requester.id] = match.warnings.get(requester.id, 0) + 1

        if match.warnings[requester.id] == 1:
            await match.channel.send(f"⚠️ Avertissement verbal pour {requester.mention}")
        elif match.warnings[requester.id] == 2:
            match.yellow_cards[requester.id] = match.yellow_cards.get(requester.id, 0) + 1
            await match.channel.send(f"🟨 Carton jaune pour {requester.mention}")
        elif match.warnings[requester.id] >= 3:
            match.yellow_cards[requester.id] = match.yellow_cards.get(requester.id, 0) + 1
            await match.channel.send(f"🟨 Nouveau jaune pour {requester.mention}")


async def ask_question(match: QuizMatch):
    if match.current_q >= len(match.questions):
        return

    q = match.questions[match.current_q]
    match.var_requested = False  # FIX: reset VAR à chaque nouvelle question
    await match.channel.send(f"📋 **Question {match.current_q + 1}/5** : {q['question']}")
    await match.channel.send(f"🏷️ Catégorie : **{q.get('category', 'Général')}**")
    if match.mode == "speed":
        await match.channel.send("⚡ **MODE SPEED** : réponse rapide recommandée")

    answers = {}
    start_time = datetime.now()

    # FIX: en mode CPU, lancer la réponse du bot en parallèle
    cpu_task = None
    if match.is_cpu:
        cpu_task = asyncio.create_task(match.get_cpu_answer(q))

    def check(msg):
        return (
            msg.channel == match.channel
            and msg.author in [match.player1, match.player2]
            and not match.is_cpu  # FIX: en mode CPU, player2 est le bot, pas un vrai user
        )

    # FIX: check corrigé pour mode CPU (player2 = bot, ne répond pas via messages)
    def check_human(msg):
        return (
            msg.channel == match.channel
            and msg.author == match.player1
        )

    actual_check = check_human if match.is_cpu else check

    while True:
        try:
            remaining = 10 - (datetime.now() - start_time).total_seconds()
            if remaining <= 0:
                break

            msg = await asyncio.wait_for(match.bot.wait_for("message", check=actual_check), timeout=remaining)

            if msg.author in answers:
                continue

            if msg.content.lower() == "la var":
                await handle_var(match, msg.author, q["answer"])
                continue

            answers[msg.author] = msg.content

            if not match.is_cpu:
                if len(answers) == 2:
                    break
            else:
                break  # en mode CPU, on attend juste le joueur humain

        except asyncio.TimeoutError:
            break

    # Récupère la réponse CPU si mode CPU
    if match.is_cpu and cpu_task:
        try:
            cpu_answer = await asyncio.wait_for(cpu_task, timeout=1.0)
        except asyncio.TimeoutError:
            cpu_answer = "Mauvaise réponse"
        answers[match.player2] = cpu_answer

    correct_players = []
    for author, answer in answers.items():
        if normalize_name(answer) == normalize_name(q["answer"]):
            correct_players.append(author)

    if len(correct_players) == 2:
        match.score1 += 1
        match.score2 += 1
        await match.channel.send(f"✅ Les deux ont bon ! Réponse : **{q['answer']}**")
    elif len(correct_players) == 1:
        winner = correct_players[0]

        if winner == match.player1:
            match.score1 += 1
        else:
            match.score2 += 1

        await match.channel.send(f"✅ {winner.mention} a bon ! Réponse : **{q['answer']}**")

        if match.mode == "eliminator":
            loser = match.player2 if winner == match.player1 else match.player1
            match.eliminated = loser
            match.game_over = True
            await match.channel.send(f"💀 **{loser.mention} est éliminé !**")
    else:
        await match.channel.send(f"❌ Aucune bonne réponse. Réponse : **{q['answer']}**")

    await show_score(match)


async def end_match(match: QuizMatch):
    match.game_over = True

    if match.score1 > match.score2:
        pts1, pts2 = 3, 0
        winner = match.player1
    elif match.score2 > match.score1:
        pts1, pts2 = 0, 3
        winner = match.player2
    else:
        pts1, pts2 = 1, 1
        winner = None

    if match.mode == "eliminator" and match.eliminated:
        if match.eliminated == match.player1:
            pts1, pts2 = 0, 3
            winner = match.player2
        else:
            pts1, pts2 = 3, 0
            winner = match.player1

    await match.channel.send(
        f"🏁 **FIN DU MATCH**\n"
        f"{match.player1.display_name} : **{match.score1}**\n"
        f"{match.player2.display_name} : **{match.score2}**\n"
        f"Points classement : {pts1} - {pts2}"
    )

    if winner:
        await match.channel.send(f"🏆 Victoire de {winner.mention}")
    else:
        await match.channel.send("🤝 Match nul")

    # FIX: en mode CPU, on ne sauvegarde les stats que pour le joueur humain (player1)
    data = load_data()

    p1id = str(match.player1.id)
    ensure_player_profile(data, p1id, match.player1.name)

    data["players"][p1id]["matches"] += 1
    data["players"][p1id]["points"] += pts1

    if not match.is_cpu:
        p2id = str(match.player2.id)
        ensure_player_profile(data, p2id, match.player2.name)
        data["players"][p2id]["matches"] += 1
        data["players"][p2id]["points"] += pts2

        if pts1 == 3:
            data["players"][p1id]["wins"] += 1
            data["players"][p1id]["streak"] += 1
            data["players"][p2id]["streak"] = 0
            check_achievement(data, p1id, "first_win")
        elif pts2 == 3:
            data["players"][p2id]["wins"] += 1
            data["players"][p2id]["streak"] += 1
            data["players"][p1id]["streak"] = 0
            check_achievement(data, p2id, "first_win")
        else:
            data["players"][p1id]["streak"] = 0
            data["players"][p2id]["streak"] = 0

        if data["players"][p1id]["streak"] >= 5:
            check_achievement(data, p1id, "streak5")
        if data["players"][p2id]["streak"] >= 5:
            check_achievement(data, p2id, "streak5")

        if match.score1 == 3 and match.score2 == 0:
            check_achievement(data, p1id, "hattrick")
        if match.score2 == 3 and match.score1 == 0:
            check_achievement(data, p2id, "hattrick")
    else:
        # Mode CPU : stats uniquement pour le joueur humain
        if pts1 == 3:
            data["players"][p1id]["wins"] += 1
            data["players"][p1id]["streak"] += 1
            check_achievement(data, p1id, "first_win")
        else:
            data["players"][p1id]["streak"] = 0

        if data["players"][p1id]["streak"] >= 5:
            check_achievement(data, p1id, "streak5")
        if match.score1 == 3 and match.score2 == 0:
            check_achievement(data, p1id, "hattrick")

    save_data(data)


async def start_match(match: QuizMatch):
    if not match.questions:
        await match.channel.send("❌ Aucune question disponible. Ajoute des questions avec /add_question.")
        return

    if len(match.questions) < 5:
        logger.warning(f"Nombre insuffisant de questions: {len(match.questions)}, besoin de 5")

    mode_emoji = {"normal": "⚽", "eliminator": "💀", "speed": "⚡", "training": "🤖"}
    await match.channel.send(
        f"{mode_emoji.get(match.mode, '⚽')} **QUIZ FOOT - MODE {match.mode.upper()}**\n"
        f"**{match.player1.display_name}** vs **{match.player2.display_name}**\n"
        f"5 questions - 10 secondes par question"
    )

    while match.current_q < min(5, len(match.questions)) and not match.game_over:
        await ask_question(match)
        match.current_q += 1
        if not match.game_over:
            await asyncio.sleep(2)

    await end_match(match)


class MatchesCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="quiz", description="Défier un joueur")
    @app_commands.describe(adversary="Le joueur à défier")
    async def quiz(self, interaction: discord.Interaction, adversary: discord.Member):
        await interaction.response.defer()

        if interaction.user == adversary:
            await interaction.followup.send("❌ Tu ne peux pas jouer contre toi-même.")
            return

        if adversary.bot:  # FIX: empêcher de défier un bot
            await interaction.followup.send("❌ Tu ne peux pas défier un bot. Utilise /train pour jouer contre le bot.")
            return

        if has_pending_challenge(interaction.user.id):
            await interaction.followup.send("⚠️ Tu as déjà un défi en attente.")
            return

        match = QuizMatch(self.bot, interaction.user, adversary, interaction.channel, mode="normal")
        add_pending_challenge(interaction.user.id, {
            "adversary": adversary,
            "match": match,
            "mode": "normal"
        })

        await interaction.followup.send(
            f"⚽ {interaction.user.mention} défie {adversary.mention}\n"
            f"Utilise `/accept` pour accepter ou `/refuse` pour refuser."
        )

    @app_commands.command(name="eliminator", description="Mode élimination")
    @app_commands.describe(adversary="Le joueur à défier")
    async def eliminator(self, interaction: discord.Interaction, adversary: discord.Member):
        await interaction.response.defer()

        if interaction.user == adversary:
            await interaction.followup.send("❌ Tu ne peux pas jouer contre toi-même.")
            return

        if adversary.bot:
            await interaction.followup.send("❌ Tu ne peux pas défier un bot.")
            return

        if has_pending_challenge(interaction.user.id):
            await interaction.followup.send("⚠️ Tu as déjà un défi en attente.")
            return

        match = QuizMatch(self.bot, interaction.user, adversary, interaction.channel, mode="eliminator")
        add_pending_challenge(interaction.user.id, {
            "adversary": adversary,
            "match": match,
            "mode": "eliminator"
        })

        await interaction.followup.send(
            f"💀 {interaction.user.mention} défie {adversary.mention} en mode Eliminator.\nUtilise `/accept`."
        )

    @app_commands.command(name="speed", description="Mode speed")
    @app_commands.describe(adversary="Le joueur à défier")
    async def speed(self, interaction: discord.Interaction, adversary: discord.Member):
        await interaction.response.defer()

        if interaction.user == adversary:
            await interaction.followup.send("❌ Tu ne peux pas jouer contre toi-même.")
            return

        if adversary.bot:
            await interaction.followup.send("❌ Tu ne peux pas défier un bot.")
            return

        if has_pending_challenge(interaction.user.id):
            await interaction.followup.send("⚠️ Tu as déjà un défi en attente.")
            return

        match = QuizMatch(self.bot, interaction.user, adversary, interaction.channel, mode="speed")
        add_pending_challenge(interaction.user.id, {
            "adversary": adversary,
            "match": match,
            "mode": "speed"
        })

        await interaction.followup.send(
            f"⚡ {interaction.user.mention} défie {adversary.mention} en mode Speed.\nUtilise `/accept`."
        )

    @app_commands.command(name="accept", description="Accepter un défi")
    async def accept(self, interaction: discord.Interaction):
        await interaction.response.defer()

        challenger_id, data = get_pending_for_adversary(interaction.user.id)
        if challenger_id and data:
            match = data["match"]
            remove_pending_challenge(challenger_id)
            await interaction.followup.send(f"✅ {interaction.user.mention} accepte le défi.")
            await start_match(match)
            return

        await interaction.followup.send("❌ Aucun défi en attente pour toi.")

    @app_commands.command(name="refuse", description="Refuser un défi")
    async def refuse(self, interaction: discord.Interaction):
        await interaction.response.defer()

        challenger_id, data = get_pending_for_adversary(interaction.user.id)
        if challenger_id and data:
            remove_pending_challenge(challenger_id)
            await interaction.followup.send("❌ Défi refusé.")
            return

        await interaction.followup.send("❌ Aucun défi à refuser.")

    @app_commands.command(name="cancel", description="Annuler ton défi")
    async def cancel(self, interaction: discord.Interaction):
        await interaction.response.defer()

        if has_pending_challenge(interaction.user.id):
            remove_pending_challenge(interaction.user.id)
            await interaction.followup.send("❌ Défi annulé.")
        else:
            await interaction.followup.send("❌ Aucun défi en attente.")

    @app_commands.command(name="train", description="Jouer contre le bot")
    async def train(self, interaction: discord.Interaction):
        await interaction.response.defer()

        bot_user = interaction.guild.me if interaction.guild else self.bot.user
        match = QuizMatch(self.bot, interaction.user, bot_user, interaction.channel, mode="training", is_cpu=True)
        await interaction.followup.send("🤖 Mode entraînement lancé.")
        await start_match(match)


async def setup(bot):
    await bot.add_cog(MatchesCog(bot))
