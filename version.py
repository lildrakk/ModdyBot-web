import discord
from discord.ext import commands
from discord import app_commands
import json
import os

OWNER_ID = 1394342273919225959
VERSION_FILE = "version.json"


# -----------------------------
# Cargar / Guardar versiones
# -----------------------------
def load_versions():
    if not os.path.exists(VERSION_FILE):
        return {"public": "v1.0", "dev": "v1.0"}
    with open(VERSION_FILE, "r") as f:
        return json.load(f)


def save_versions(data):
    with open(VERSION_FILE, "w") as f:
        json.dump(data, f, indent=4)


# -----------------------------
# COG PRINCIPAL
# -----------------------------
class VersionCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        versions = load_versions()
        print(f"[VERSIÓN] Pública: {versions['public']} | Dev: {versions['dev']}")

    @app_commands.command(name="version", description="Cambiar versión del bot")
    async def version(self, interaction: discord.Interaction, public: str, dev: str):

        if interaction.user.id != OWNER_ID:
            return await interaction.response.send_message(
                "No tienes permiso para usar este comando.",
                ephemeral=True
            )

        # Guardar nuevas versiones
        data = {"public": public, "dev": dev}
        save_versions(data)

        print(f"[VERSIÓN ACTUALIZADA] Pública: {public} | Dev: {dev}")

        await interaction.response.send_message(
            f"📌 Versión pública → **{public}**\n"
            f"📌 Versión dev → **{dev}**\n"
            f"🔄 Recargando módulos...",
            ephemeral=True
        )

        # -----------------------------
        # RECARGAR MÓDULOS SIN REINICIAR
        # -----------------------------
        if hasattr(self.bot, "load_modules_for_version"):
            await self.bot.load_modules_for_version()

        await interaction.followup.send(
            "✅ Versión actualizada y módulos recargados.",
            ephemeral=True
        )


async def setup(bot):
    await bot.add_cog(VersionCog(bot))
