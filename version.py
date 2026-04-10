import discord
from discord.ext import commands
from discord import app_commands
import json
import os

# Tu ID
OWNER_ID = 1394342273919225959

# Archivo donde se guardan las versiones
VERSION_FILE = "version.json"


# -----------------------------
# Funciones para cargar/guardar
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

        # Mostrar en consola al iniciar
        versions = load_versions()
        print(f"[VERSIÓN] Pública: {versions['public']} | Dev: {versions['dev']}")

    @app_commands.command(name="version", description=" ")
    async def version(self, interaction: discord.Interaction, public: str, dev: str):

        # Solo tú puedes usarlo
        if interaction.user.id != OWNER_ID:
            return await interaction.response.send_message(
                "No tienes permiso para usar este comando.",
                ephemeral=True
            )

        # Guardar nuevas versiones
        data = {"public": public, "dev": dev}
        save_versions(data)

        # Mostrar en consola
        print(f"[VERSIÓN ACTUALIZADA] Pública: {public} | Dev: {dev}")

        await interaction.response.send_message(
            f"Versión pública → **{public}**\n"
            f"Versión dev → **{dev}**",
            ephemeral=True
        )


async def setup(bot):
    await bot.add_cog(VersionCog(bot))
