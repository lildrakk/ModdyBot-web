import discord
from discord.ext import commands
from discord import app_commands
import json
import os
from datetime import datetime, timezone

CONFIG_FILE = "antialts_config.json"


# -----------------------------
# Cargar / Guardar Config
# -----------------------------
def load_config():
    if not os.path.exists(CONFIG_FILE):
        return {}
    with open(CONFIG_FILE, "r") as f:
        return json.load(f)


def save_config(data):
    with open(CONFIG_FILE, "w") as f:
        json.dump(data, f, indent=4)


# -----------------------------
# COG PRINCIPAL
# -----------------------------
class AntiAlts(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.config = load_config()

    # -------------------------
    # Comando para configurar
    # -------------------------
    @app_commands.command(name="antialts", description="Configura el anti-alts del servidor.")
    @app_commands.describe(
        dias="Mínimo de días que debe tener la cuenta",
        canal_logs="Canal donde se enviarán los logs"
    )
    async def antialts(self, interaction: discord.Interaction, dias: int, canal_logs: discord.TextChannel):

        guild_id = str(interaction.guild.id)

        self.config[guild_id] = {
            "dias": dias,
            "logs": canal_logs.id
        }

        save_config(self.config)

        await interaction.response.send_message(
            f"<a:ao_Tick:1485072554879357089> Anti‑alts configurado:\n"
            f"- Mínimo días: **{dias}**\n"
            f"- Canal logs: {canal_logs.mention}",
            ephemeral=True
        )

    # -------------------------
    # Evento: usuario entra
    # -------------------------
    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member):

        guild_id = str(member.guild.id)

        if guild_id not in self.config:
            return  # No configurado

        dias_min = self.config[guild_id]["dias"]
        canal_logs_id = self.config[guild_id]["logs"]

        canal_logs = member.guild.get_channel(canal_logs_id)
        if not canal_logs:
            return

        # Fecha de creación de la cuenta
        ahora = datetime.now(timezone.utc)
        edad_cuenta = (ahora - member.created_at).days

        if edad_cuenta < dias_min:
            embed = discord.Embed(
                title="<:warnnormal:1491858539222925364> Posible ALT detectado",
                color=discord.Color(0x0A3D62)
            )
            embed.add_field(name="Usuario", value=f"{member.mention} (`{member.id}`)", inline=False)
            embed.add_field(name="Edad de la cuenta", value=f"{edad_cuenta} días", inline=False)
            embed.add_field(name="Mínimo requerido", value=f"{dias_min} días", inline=False)
            embed.timestamp = ahora

            await canal_logs.send(embed=embed)


async def setup(bot):
    await bot.add_cog(AntiAlts(bot))
