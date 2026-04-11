import discord
from discord.ext import commands
from discord import app_commands
import json
import os

# ============================
# RUTA BASE
# ============================

BASE_DIR = os.path.dirname(os.path.dirname(__file__))

# ============================
# JSON HELPERS
# ============================

def load_json(path):
    if not os.path.exists(path):
        with open(path, "w") as f:
            json.dump({}, f, indent=4)
        return {}
    with open(path, "r") as f:
        return json.load(f)

def save_json(path, data):
    with open(path, "w") as f:
        json.dump(data, f, indent=4)

# ============================
# ARCHIVO POR SERVIDOR
# ============================

blacklist_servers_path = os.path.join(BASE_DIR, "blacklist_servers.json")
blacklist_servers = load_json(blacklist_servers_path)

# ============================
# COG PRINCIPAL
# ============================

class BlacklistServer(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(
        name="blacklist",
        description="Añade un usuario a la blacklist del servidor"
    )
    @app_commands.describe(
        usuario="Usuario a añadir",
        accion="kick / mute / ban / block",
        minutos="Solo para mute (0 = permanente)",
        razon="Razón"
    )
    async def blacklist_cmd(
        self,
        interaction: discord.Interaction,
        usuario: discord.User,
        accion: str,
        minutos: int = 10,
        razon: str = "No especificada"
    ):
        user = interaction.user

        if not (user.guild_permissions.administrator or user.guild_permissions.manage_guild):
            return await interaction.response.send_message(
                "❌ No tienes permisos.",
                ephemeral=True
            )

        accion = accion.lower()
        if accion not in ["kick", "mute", "ban", "block"]:
            return await interaction.response.send_message(
                "❌ Acciones válidas: kick / mute / ban / block",
                ephemeral=True
            )

        gid = str(interaction.guild.id)
        uid = str(usuario.id)

        if gid not in blacklist_servers:
            blacklist_servers[gid] = {"users": {}}

        blacklist_servers[gid]["users"][uid] = {
            "accion": accion,
            "minutos": minutos if accion == "mute" else 0,
            "razon": razon
        }

        save_json(blacklist_servers_path, blacklist_servers)

        await interaction.response.send_message(
            f"🚫 {usuario.mention} añadido a la blacklist del servidor.\n"
            f"**Acción:** {accion}\n"
            f"**Razón:** {razon}",
            ephemeral=True
        )

    @app_commands.command(
        name="unblacklist",
        description="Quita un usuario de la blacklist del servidor"
    )
    async def unblacklist_cmd(
        self,
        interaction: discord.Interaction,
        usuario: discord.User
    ):
        user = interaction.user

        if not (user.guild_permissions.administrator or user.guild_permissions.manage_guild):
            return await interaction.response.send_message(
                "❌ No tienes permisos.",
                ephemeral=True
            )

        gid = str(interaction.guild.id)
        uid = str(usuario.id)

        if gid not in blacklist_servers or uid not in blacklist_servers[gid]["users"]:
            return await interaction.response.send_message(
                "ℹ️ Ese usuario no está en la blacklist.",
                ephemeral=True
            )

        del blacklist_servers[gid]["users"][uid]
        save_json(blacklist_servers_path, blacklist_servers)

        await interaction.response.send_message(
            f"✅ {usuario.mention} eliminado de la blacklist del servidor.",
            ephemeral=True
        )

    @app_commands.command(
        name="blacklistlist",
        description="Lista la blacklist del servidor"
    )
    async def blacklistlist_cmd(self, interaction: discord.Interaction):
        gid = str(interaction.guild.id)

        if gid not in blacklist_servers or not blacklist_servers[gid]["users"]:
            return await interaction.response.send_message(
                "📭 La blacklist está vacía.",
                ephemeral=True
            )

        embed = discord.Embed(
            title=f"📜 Blacklist de {interaction.guild.name}",
            color=discord.Color.red()
        )

        for uid, data in blacklist_servers[gid]["users"].items():
            accion = data["accion"]
            minutos = data.get("minutos", 0)

            if accion == "mute" and minutos == 0:
                accion_texto = "mute permanente"
            elif accion == "mute":
                accion_texto = f"mute {minutos} min"
            else:
                accion_texto = accion

            embed.add_field(
                name=f"Usuario ID: {uid}",
                value=f"Acción: **{accion_texto}**\nRazón: {data['razon']}",
                inline=False
            )

        await interaction.response.send_message(embed=embed, ephemeral=True)

# ============================
# SETUP DEL COG
# ============================

async def setup(bot: commands.Bot):
    await bot.add_cog(BlacklistServer(bot))
