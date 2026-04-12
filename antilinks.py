import discord
from discord.ext import commands
from discord import app_commands
import json, time, re, unicodedata
from datetime import timedelta

CONFIG_FILE = "antilinks.json"

def load_config():
    try:
        with open(CONFIG_FILE, "r") as f:
            return json.load(f)
    except:
        return {}

def save_config(data):
    with open(CONFIG_FILE, "w") as f:
        json.dump(data, f, indent=4)

# ============================================================
# DETECCIÓN AVANZADA DE INVITACIONES OCULTAS
# ============================================================

def normalize_text(text: str) -> str:
    text = unicodedata.normalize("NFKC", text)
    invisibles = ["\u200b", "\u2060", "\u202f", "\u2800"]
    for inv in invisibles:
        text = text.replace(inv, "")
    return text.replace(" ", "")

INVITE_REGEX = re.compile(
    r"(discord\.gg\/[a-zA-Z0-9]+|discord\.com\/invite\/[a-zA-Z0-9]+|discordapp\.com\/invite\/[a-zA-Z0-9]+)"
)

# ============================================================
# COG PRINCIPAL
# ============================================================

class AntiLinks(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.config = load_config()
        self.warns = {}

    def ensure_guild(self, guild_id: int):
        gid = str(guild_id)
        if gid not in self.config:
            self.config[gid] = {
                "enabled": False,
                "accion": "mute",
                "mute_time": 600,
                "allow_invites": False,
                "whitelist_users": [],
                "whitelist_roles": [],
                "log_channel": None
            }
            save_config(self.config)
        return self.config[gid]

    async def send_log(self, guild, cfg, embed):
        if cfg["log_channel"]:
            canal = guild.get_channel(cfg["log_channel"])
            if canal:
                try:
                    await canal.send(embed=embed)
                except:
                    pass

    # ============================================================
    # /antilinks
    # ============================================================

    @app_commands.command(name="antilinks", description="Configura el sistema Anti‑Links.")
    @app_commands.describe(
        estado="Activar o desactivar el Anti‑Links",
        accion="Acción al detectar enlaces prohibidos",
        mute_time="Tiempo de mute en segundos",
        allow_invites="Permitir invitaciones de Discord",
        log_channel="Canal donde se enviarán los logs"
    )
    @app_commands.choices(
        estado=[
            app_commands.Choice(name="Activar", value="activar"),
            app_commands.Choice(name="Desactivar", value="desactivar")
        ],
        accion=[
            app_commands.Choice(name="Mute", value="mute"),
            app_commands.Choice(name="Kick", value="kick"),
            app_commands.Choice(name="Ban", value="ban")
        ],
        allow_invites=[
            app_commands.Choice(name="Sí", value="si"),
            app_commands.Choice(name="No", value="no")
        ]
    )
    async def antilinks_cmd(
        self,
        interaction: discord.Interaction,
        estado: str = None,
        accion: str = None,
        mute_time: int = None,
        allow_invites: str = None,
        log_channel: discord.TextChannel = None
    ):
        guild = interaction.guild
        cfg = self.ensure_guild(guild.id)

        if estado is not None:
            cfg["enabled"] = (estado == "activar")
        if accion is not None:
            cfg["accion"] = accion
        if mute_time is not None:
            cfg["mute_time"] = max(1, mute_time)
        if allow_invites is not None:
            cfg["allow_invites"] = (allow_invites == "si")
        if log_channel is not None:
            cfg["log_channel"] = log_channel.id

        save_config(self.config)

        embed = discord.Embed(
            title="<:warnwarnnormal:1491858539222925364> Configuración Anti‑Links actualizada",
            color=discord.Color(0x0A3D62)
        )
        embed.add_field(name="Estado", value="Activado" if cfg["enabled"] else "Desactivado", inline=False)
        embed.add_field(name="Acción", value=cfg["accion"].capitalize(), inline=True)
        embed.add_field(name="Mute time", value=f"{cfg['mute_time']}s", inline=True)
        embed.add_field(name="Permitir invites", value="Sí" if cfg["allow_invites"] else "No", inline=True)
        embed.add_field(
            name="Log channel",
            value=f"<#{cfg['log_channel']}>" if cfg["log_channel"] else "No configurado",
            inline=False
        )

        await interaction.response.send_message(embed=embed, ephemeral=True)

    # ============================================================
    # WHITELIST
    # ============================================================

    @app_commands.command(
        name="antilinks_whitelist",
        description="Gestiona la whitelist de usuarios o roles."
    )
    @app_commands.describe(
        accion="Añadir o eliminar de la whitelist.",
        tipo="Selecciona si quieres modificar un usuario o un rol.",
        usuario="Usuario a añadir o eliminar.",
        rol="Rol a añadir o eliminar."
    )
    @app_commands.choices(
        accion=[
            app_commands.Choice(name="Añadir", value="añadir"),
            app_commands.Choice(name="Eliminar", value="eliminar")
        ],
        tipo=[
            app_commands.Choice(name="Usuario", value="usuario"),
            app_commands.Choice(name="Rol", value="rol")
        ]
    )
    async def whitelist_action(
        self,
        interaction: discord.Interaction,
        accion: str,
        tipo: str,
        usuario: discord.Member = None,
        rol: discord.Role = None
    ):
        cfg = self.ensure_guild(interaction.guild.id)

        if tipo == "usuario" and usuario is None:
            return await interaction.response.send_message("Debes seleccionar un usuario.", ephemeral=True)

        if tipo == "rol" and rol is None:
            return await interaction.response.send_message("Debes seleccionar un rol.", ephemeral=True)

        lista = cfg["whitelist_users"] if tipo == "usuario" else cfg["whitelist_roles"]
        objetivo = usuario if tipo == "usuario" else rol

        if accion == "añadir":
            if objetivo.id not in lista:
                lista.append(objetivo.id)
                save_config(self.config)
                msg = f"<a:ao_Tick:1485072554879357089> {tipo.capitalize()} añadido a la whitelist."
            else:
                msg = f"<:warnnormal:1491858539222925364> Ese {tipo} ya está en la whitelist."
        else:
            if objetivo.id in lista:
                lista.remove(objetivo.id)
                save_config(self.config)
                msg = f"<a:ao_Tick:1485072554879357089> {tipo.capitalize()} eliminado de la whitelist."
            else:
                msg = f"<:warnnormal:1491858539222925364> Ese {tipo} no está en la whitelist."

        embed = discord.Embed(description=msg, color=discord.Color(0x0A3D62))
        await interaction.response.send_message(embed=embed, ephemeral=True)

    # ============================================================
    # DETECCIÓN DE LINKS
    # ============================================================

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if message.author.bot or not message.guild:
            return

        guild = message.guild
        cfg = self.ensure_guild(guild.id)
        user = message.author
        content = message.content.lower()

        if not cfg["enabled"]:
            return

        if user.id in cfg["whitelist_users"]:
            return
        if any(r.id in cfg["whitelist_roles"] for r in user.roles):
            return

        # Normalizar texto para detectar invitaciones ocultas
        normalized = normalize_text(content)
        detected_invite = bool(INVITE_REGEX.search(normalized))

        # Permitir invites si está activado
        if cfg["allow_invites"] and detected_invite:
            return

        # Detectar enlaces normales o invitaciones ocultas
        if not detected_invite and not ("http://" in content or "https://" in content):
            return

        # Eliminar mensaje
        try:
            await message.delete()
        except:
            pass

        uid = user.id
        now = time.time()
        if uid not in self.warns:
            self.warns[uid] = []
        self.warns[uid].append(now)
        self.warns[uid] = [t for t in self.warns[uid] if now - t <= 300]
        warn_count = len(self.warns[uid])

        # PRIMER AVISO
        if warn_count == 1:
            embed = discord.Embed(
                title="<:warnnormal:1491858539222925364> Enlace no permitido",
                description=(
                    f"<:link:1483506560935268452> {user.mention}, has enviado un enlace que **no está permitido**.\n"
                    f"Evita repetirlo o se aplicará una sanción."
                ),
                color=discord.Color(0x0A3D62)
            )
            await message.channel.send(embed=embed)

            log_embed = discord.Embed(
                title="<:warnnormal:1491858539222925364> Anti‑Links | Advertencia registrada",
                description=(
                    f"Usuario: {user.mention}\n"
                    f"Advertencia: 1/2\n"
                    f"Motivo: Enlace bloqueado\n"
                    f"Canal: {message.channel.mention}"
                ),
                color=discord.Color(0x0A3D62)
            )
            await self.send_log(guild, cfg, log_embed)
            return

        # SEGUNDA VEZ → SANCIÓN
        await self.apply_action(message, cfg)

    # ============================================================
    # APLICAR SANCIÓN
    # ============================================================

    async def apply_action(self, message: discord.Message, cfg):
        user = message.author
        guild = message.guild
        action = cfg["accion"]
        sancionado = False

        try:
            if action == "ban":
                await guild.ban(user, reason="Anti‑Links")
            elif action == "kick":
                await guild.kick(user, reason="Anti‑Links")
            elif action == "mute":
                duration = cfg["mute_time"]
                await user.timeout(discord.utils.utcnow() + timedelta(seconds=duration), reason="Anti‑Links")
            sancionado = True
        except:
            sancionado = False

        if not sancionado:
            embed = discord.Embed(
                title="<:warnnormal:1491858539222925364> Enlace detectado",
                description=(
                    f"<:link:1483506560935268452> Detecté un enlace prohibido de {user.mention}, "
                    f"pero **no pude aplicar la sanción**."
                ),
                color=discord.Color(0x0A3D62)
            )
            await message.channel.send(embed=embed)
            await self.send_log(guild, cfg, embed)
            return

        embed = discord.Embed(
            title="<a:advertencia:1483506898509758690> Sanción aplicada",
            description=(
                f"Usuario: {user.mention}\n"
                f"Acción: **{action}**\n"
                f"Razón: Enviar enlaces no permitidos <:link:1483506560935268452>"
            ),
            color=discord.Color(0x0A3D62)
        )
        await message.channel.send(embed=embed)
        await self.send_log(guild, cfg, embed)

async def setup(bot):
    await bot.add_cog(AntiLinks(bot))
