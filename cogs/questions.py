import discord
from discord import app_commands
from discord.ext import commands

from storage import load_questions, save_questions


class QuestionsCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="question_count", description="Voir le nombre de questions")
    async def question_count(self, interaction: discord.Interaction):
        await interaction.response.defer()
        questions = load_questions()
        await interaction.followup.send(f"📚 Il y a **{len(questions)}** questions dans la base.")

    @app_commands.command(name="question_list", description="Voir la liste des questions")
    async def question_list(self, interaction: discord.Interaction):
        await interaction.response.defer()

        questions = load_questions()
        if not questions:
            await interaction.followup.send("❌ Aucune question disponible.")
            return

        embed = discord.Embed(title=f"❓ Liste des questions ({len(questions)})", color=0x00FF00)

        for i, q in enumerate(questions[:10], 1):
            q_text = q["question"][:60] + ("..." if len(q["question"]) > 60 else "")
            embed.add_field(
                name=f"{i}. {q_text}",
                value=f"✅ {q['answer']} | 🏷️ {q.get('category', 'Général')}",
                inline=False
            )

        if len(questions) > 10:
            embed.set_footer(text=f"Et {len(questions) - 10} autres questions...")

        await interaction.followup.send(embed=embed)

    @app_commands.command(name="add_question", description="Ajouter une question")
    @app_commands.checks.has_permissions(administrator=True)
    @app_commands.describe(question="La question", answer="La réponse", category="Catégorie")
    async def add_question(self, interaction: discord.Interaction, question: str, answer: str, category: str = "Général"):
        await interaction.response.defer()

        questions = load_questions()
        questions.append({
            "question": question.strip(),
            "answer": answer.strip(),
            "category": category.strip()
        })
        save_questions(questions)

        await interaction.followup.send(
            f"✅ Question ajoutée\nQ : {question}\nR : {answer}\nCatégorie : {category}"
        )

    @app_commands.command(name="delete_question", description="Supprimer une question par numéro")
    @app_commands.checks.has_permissions(administrator=True)
    @app_commands.describe(index="Le numéro de la question")
    async def delete_question(self, interaction: discord.Interaction, index: int):
        await interaction.response.defer()

        questions = load_questions()

        if not questions:
            await interaction.followup.send("❌ Aucune question à supprimer.")
            return

        if index < 1 or index > len(questions):
            await interaction.followup.send(f"❌ Numéro invalide. Entre 1 et {len(questions)}.")
            return

        removed = questions.pop(index - 1)
        save_questions(questions)

        await interaction.followup.send(
            f"🗑️ Question supprimée\nQ : {removed['question']}\nR : {removed['answer']}"
        )

    @add_question.error
    @delete_question.error
    async def question_admin_error(self, interaction: discord.Interaction, error):
        if isinstance(error, app_commands.errors.MissingPermissions):
            if interaction.response.is_done():
                await interaction.followup.send("⛔ Commande réservée aux administrateurs.", ephemeral=True)
            else:
                await interaction.response.send_message("⛔ Commande réservée aux administrateurs.", ephemeral=True)


async def setup(bot):
    await bot.add_cog(QuestionsCog(bot))