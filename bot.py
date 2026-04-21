import asyncio
import logging
import signal
import sys
import threading

import discord
from discord.ext import commands

from config import Config

logging.basicConfig(
    level=logging.DEBUG if Config.DEBUG else logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)
logger = logging.getLogger("QuizFootBot")


class QuizFootBot(commands.Bot):
    def __init__(self):
        intents = discord.Intents.default()
        intents.message_content = True
        intents.presences = False
        intents.members = False
        super().__init__(command_prefix=Config.PREFIX, intents=intents, help_command=None)

    async def setup_hook(self):
        from storage import ensure_data_dirs
        ensure_data_dirs()

        cogs = [
            "cogs.general",
            "cogs.questions",
            "cogs.matches",
            "cogs.tournaments",
            "cogs.seasons",
        ]

        for cog in cogs:
            try:
                await self.load_extension(cog)
                logger.info(f"Cog chargé: {cog}")
            except Exception as e:
                logger.error(f"Erreur chargement {cog}: {e}")

        logger.info("Commandes détectées dans l'arbre:")
        for cmd in self.tree.get_commands():
            logger.debug(f"  - {cmd.name}")

        try:
            synced = await self.tree.sync()
            logger.info(f"{len(synced)} commandes synchronisées")
        except Exception as e:
            logger.error(f"Erreur sync: {e}")

    async def on_ready(self):
        logger.info(f"Bot connecté: {self.user} (ID: {self.user.id})")

    async def close(self):
        logger.info("Arrêt du bot...")
        await super().close()


bot = QuizFootBot()

try:
    token = Config.BOT_TOKEN
except ValueError as e:
    logger.critical(str(e))
    sys.exit(1)

bot.run(token)