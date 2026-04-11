import discord
from discord.ext import commands
from discord import app_commands
import json
import os
from datetime import datetime, timedelta

# ============================
# CONFIG
# ============================

# IDs del staff que puede gestionar la blacklist global
GLOBAL_STAFF_IDS = {
    1394342273919225959,  # tú
    # añade aquí más IDs si quieres
}

# Servidor de soporte (NO se banea ni se expulsa de aquí)
SUPPORT_GUILD_ID = 1464575509785612380
SUPPORT_INVITE = "https://discord.gg/wMseTwYz75"

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
# ARCHIVO GLOBAL
# ============================

blacklist_global_path = os.path.join(BASE_DIR, "blacklist_global.json")
blacklist_global = load_json(blacklist_global_path)

# ============================
# SISTEMA DE ESPERA DE PRUEBAS
# ============================

pending_proofs = {}  # staff_id -> entry

# ============================
# HELPERS
# ============================

def is_global_staff(user: discord.abc.User, bot: commands.Bot) -> bool:
    return user.id in GLOBAL_STAFF_IDS or user.id == bot.user.id

def normalize_user_input(raw: str) -> int | None:
    raw = raw.strip()
    if raw.startswith("<@") and raw.endswith(">"):
        raw = raw.replace("<@", "").replace(">", "").replace("!", "")
    try:
        return int(raw)
    except:
        return None

def parse_duration(raw: str) -> tuple[str, datetime | None]:
    """
    Acepta cosas como:
    - '30d' (30 días)
    - '6m'  (6 meses aprox = 30 días c/u)
    - '1y'  (1 año aprox = 365 días)
    - 'perma', 'perm', '' -> permanente
    Devuelve (texto_normalizado, fecha_expiración | None)
    """
    raw = (raw or "").strip().lower()
    if raw in ("", "perma", "perm", "permanente"):
        return "Permanente", None

    now = datetime.utcnow()

    try:
        num = int(raw[:-1])
        unit = raw[-1]
    except:
        # Si no se puede parsear, lo tratamos como permanente
        return "Permanente", None

    days = 0
    if unit == "d":
        days = num
        text = f"{num} día(s)"
    elif unit == "m":
        days = num * 30
        text = f"{num} mes(es)"
    elif unit == "y":
        days = num * 365
        text = f"{num} año(s)"
    else:
        # Unidad desconocida -> permanente
        return "Permanente", None

    expires_at = now + timedelta(days=days)
    return text, expires_at

def format_datetime(dt: datetime | None) -> str:
    if not dt:
        return "No aplica"
    return dt.strftime("%Y-%m-%d %H:%M UTC")

# ============================
# MODALS
# ============================

class GlobalAddModal(discord.ui.Modal, title="➕ Añadir a Blacklist Global"):
    usuario = discord.ui.TextInput(
        label="Usuario o ID",
        placeholder="Ej: @Juan / 123456789012345678",
        required=True
    )
    reason = discord.ui.TextInput(
        label="Motivo",
        placeholder="Razón de la sanción",
        required=True,
        style=discord.TextStyle.paragraph
    )
    duration = discord.ui.TextInput(
        label="Duración",
        placeholder="Ej: 30d, 6m, 1y, perma",
        required=False
    )

    def __init__(self, bot: commands.Bot):
        super().__init__()
        self.bot = bot

    async def on_submit(self, interaction: discord.Interaction):
        if not is_global_staff(interaction.user, self.bot):
            return await interaction.response.send_message(
                "❌ No puedes usar este modal.",
                ephemeral=True
            )

        raw_user = self.usuario.value
        reason = self.reason.value.strip()
        duration_raw = (self.duration.value or "").strip()

        target_id = normalize_user_input(raw_user)
        if target_id is None:
            return await interaction.response.send_message(
                "❌ Debes introducir un usuario válido o un ID.",
                ephemeral=True
            )

        duration_text, expires_at = parse_duration(duration_raw)

        pending_proofs[interaction.user.id] = {
            "target_id": str(target_id),
            "reason": reason,
            "staff": interaction.user.id,
            "timestamp": datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC"),
            "duration_text": duration_text,
            "expires_at": expires_at.isoformat() if expires_at else None
        }

        await interaction.response.send_message(
            "📎 **Ahora adjunta las pruebas (opcional).**\n"
            "Envía imágenes, vídeos o archivos **en tu siguiente mensaje**.\n\n"
            "Si no envías nada en 30 segundos, se guardará sin pruebas.",
            ephemeral=True
        )

class GlobalRemoveModal(discord.ui.Modal, title="➖ Eliminar de Blacklist Global"):
    usuario = discord.ui.TextInput(
        label="Usuario o ID",
        placeholder="Ej: @Juan / 123456789012345678",
        required=True
    )
    reason = discord.ui.TextInput(
        label="Motivo del desban (solo informativo)",
        placeholder="Opcional",
        required=False,
        style=discord.TextStyle.paragraph
    )

    def __init__(self, bot: commands.Bot):
        super().__init__()
        self.bot = bot

    async def on_submit(self, interaction: discord.Interaction):
        if not is_global_staff(interaction.user, self.bot):
            return await interaction.response.send_message(
                "❌ No puedes usar este modal.",
                ephemeral=True
            )

        raw_user = self.usuario.value
        uid_int = normalize_user_input(raw_user)
        if uid_int is None:
            return await interaction.response.send_message(
                "❌ Debes introducir un usuario válido o un ID.",
                ephemeral=True
            )

        uid = str(uid_int)

        if uid not in blacklist_global:
            return await interaction.response.send_message(
                "ℹ️ Ese usuario no está en la blacklist global.",
                ephemeral=True
            )

        data = blacklist_global[uid]
        razon_original = data.get("razon", "No especificada")
        pruebas = data.get("pruebas", [])
        fecha_ban = data.get("fecha_ban", "Desconocida")
        fecha_desban = datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")

        del blacklist_global[uid]
        save_json(blacklist_global_path, blacklist_global)

        # Desban global (excepto servidor soporte)
        for guild in interaction.client.guilds:
            if guild.id == SUPPORT_GUILD_ID:
                continue
            try:
                await guild.unban(discord.Object(id=int(uid)))
            except:
                pass

        embed = discord.Embed(
            title="<:nose:1491491155198607440> Usuario Desbaneado Globalmente (ModdyBot)",
            description=(
                f"<:link:1483506560935268452> **ID:** `{uid}`\n\n"
                f"<:iinfo:1483506560935268452> **Razón original del ban:** {razon_original}\n"
                f"<:calendario:1492176498197532725> *Fecha del ban:** {fecha_ban}\n"
                f"<:ruedita:1491491111557140570> **Fecha del desban:** {fecha_desban}\n\n"
                f"<a:flechazul:1492182951532826684> **Pruebas:**\n"
                + ("\n".join(pruebas) if pruebas else "No se adjuntaron pruebas.") +
                "\n\nSi quieres apelar tu sanción, entra al servidor de soporte:\n"
                f"{SUPPORT_INVITE}"
            ),
            color=discord.Color(0x0A3D62)
        )

        if pruebas:
            embed.set_image(url=pruebas[0])

        # DM al usuario
        try:
            user_obj = await interaction.client.fetch_user(int(uid))
            await user_obj.send(embed=embed)
        except:
            pass

        await interaction.response.send_message(
            f"✅ Usuario `{uid}` eliminado de la blacklist global.",
            ephemeral=True
        )

class GlobalInspectModal(discord.ui.Modal, title="🔍 Inspeccionar usuario"):
    usuario = discord.ui.TextInput(
        label="Usuario o ID",
        placeholder="Ej: @Juan / 123456789012345678",
        required=True
    )

    def __init__(self, bot: commands.Bot):
        super().__init__()
        self.bot = bot

    async def on_submit(self, interaction: discord.Interaction):
        if not is_global_staff(interaction.user, self.bot):
            return await interaction.response.send_message(
                "❌ No puedes usar este modal.",
                ephemeral=True
            )

        raw_user = self.usuario.value
        uid_int = normalize_user_input(raw_user)
        if uid_int is None:
            return await interaction.response.send_message(
                "❌ Debes introducir un usuario válido o un ID.",
                ephemeral=True
            )

        uid = str(uid_int)

        if uid not in blacklist_global:
            return await interaction.response.send_message(
                "ℹ️ Ese usuario no está en la blacklist global.",
                ephemeral=True
            )

        data = blacklist_global[uid]

        razon = data.get("razon", "No especificada")
        pruebas = data.get("pruebas", [])
        staff = data.get("staff", "Desconocido")
        fecha_ban = data.get("fecha_ban", "Desconocida")
        duracion = data.get("duracion", "Permanente")
        expira = data.get("expira", None)

        embed = discord.Embed(
            title=f"🔍 Inspección de usuario {uid}",
            color=discord.Color.orange()
        )

        embed.add_field(name="Motivo", value=razon, inline=False)
        embed.add_field(name="Staff", value=f"<@{staff}>", inline=False)
        embed.add_field(name="Fecha del ban", value=fecha_ban, inline=False)
        embed.add_field(name="Duración", value=duracion, inline=False)
        embed.add_field(
            name="Fecha de fin (teórica)",
            value=expira if expira else "No aplica (permanente)",
            inline=False
        )

        if pruebas:
            embed.add_field(
                name="Pruebas",
                value="\n".join(f"[Archivo]({url})" for url in pruebas),
                inline=False
            )
            embed.set_image(url=pruebas[0])
        else:
            embed.add_field(name="Pruebas", value="No se adjuntaron pruebas.", inline=False)

        await interaction.response.send_message(embed=embed, ephemeral=True)

# ============================
# VIEW DEL PANEL
# ============================

class GlobalBlacklistView(discord.ui.View):
    def __init__(self, bot: commands.Bot):
        super().__init__(timeout=120)
        self.bot = bot

    @discord.ui.select(
        placeholder="Selecciona una opción...",
        options=[
            discord.SelectOption(label="➕ Añadir a blacklist global", value="add"),
            discord.SelectOption(label="📜 Listar blacklist global", value="list"),
            discord.SelectOption(label="➖ Quitar de blacklist global", value="remove"),
            discord.SelectOption(label="🔍 Inspeccionar usuario", value="inspect"),
            discord.SelectOption(label="🧪 Blacklist global prueba", value="test_ban"),
            discord.SelectOption(label="🧪 Unblacklist global prueba", value="test_unban"),
        ]
    )
    async def select_callback(self, interaction: discord.Interaction, select: discord.ui.Select):
        if not is_global_staff(interaction.user, self.bot):
            return await interaction.response.send_message(
                "❌ No puedes usar este panel.",
                ephemeral=True
            )

        value = select.values[0]

        if value == "add":
            return await interaction.response.send_modal(GlobalAddModal(self.bot))

        if value == "remove":
            return await interaction.response.send_modal(GlobalRemoveModal(self.bot))

        if value == "inspect":
            return await interaction.response.send_modal(GlobalInspectModal(self.bot))

        if value == "list":
            if not blacklist_global:
                return await interaction.response.send_message(
                    "📭 La blacklist global está vacía.",
                    ephemeral=True
                )

            embed = discord.Embed(
                title="🌐 Lista de Blacklist Global (ModdyBot)",
                description="Usuarios actualmente baneados globalmente:",
                color=discord.Color.blurple()
            )

            for uid, data in blacklist_global.items():
                razon = data.get("razon", "No especificada")
                fecha = data.get("fecha_ban", "Desconocida")
                staff = data.get("staff", "Desconocido")
                duracion = data.get("duracion", "Permanente")
                expira = data.get("expira", None)

                texto = (
                    f"**Razón:** {razon}\n"
                    f"**Fecha del ban:** {fecha}\n"
                    f"**Duración:** {duracion}\n"
                    f"**Fin teórico:** {expira if expira else 'No aplica'}\n"
                    f"**Staff:** <@{staff}>"
                )

                embed.add_field(
                    name=f"ID: `{uid}`",
                    value=texto,
                    inline=False
                )

            embed.set_footer(text="Solo el staff autorizado puede ver esta información.")

            return await interaction.response.send_message(embed=embed, ephemeral=True)

        if value == "test_ban":
            fecha = datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")
            embed_dm = discord.Embed(
                title="<a:alarmazul:1491858094043693177> Has sido baneado globalmente (ModdyBot)",
                description=(
                    f"Has sido añadido a la **Blacklist Global de ModdyBot**.\n\n"
                    f"<:iinfo:1491858536895090708> **Razón:** {reason}\n"
                    f"<:calendario:1492176498197532725> **Fecha del ban:** {timestamp}\n"
                    f"<:cronometro:1492176494422659087> **Duración:** {duration_text}\n\n"
                    f"<a:flechazul:1492182951532826684> **Pruebas:**\n"
                    + ("\n".join(proofs) if proofs else "No se adjuntaron pruebas.") +
                    "\n\nSi quieres apelar tu sanción, entra al servidor de soporte:\n"
                    f"{SUPPORT_INVITE}"
                ),
                color=discord.Color(0x0A3D62)
            )
            try:
                await interaction.user.send(embed=embed_dm)
            except:
                pass

            return await interaction.response.send_message(
                "🧪 Simulación de ban global enviada a tu DM.",
                ephemeral=True
            )

        if value == "test_unban":
            fecha_ban = "2026-01-01 12:00 UTC"
            fecha_desban = datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")

            embed = discord.Embed(
                    title="<:nose:1491491155198607440> Usuario Desbaneado Globalmente (ModdyBot)",
            description=(
                f"<:link:1483506560935268452> **ID:** `{uid}`\n\n"
                f"<:iinfo:1483506560935268452> **Razón original del ban:** {razon_original}\n"
                f"<:calendario:1492176498197532725> *Fecha del ban:** {fecha_ban}\n"
                f"<:ruedita:1491491111557140570> **Fecha del desban:** {fecha_desban}\n\n"
                f"<a:flechazul:1492182951532826684> **Pruebas:**\n"
                + ("\n".join(pruebas) if pruebas else "No se adjuntaron pruebas.") +
                "\n\nSi quieres apelar tu sanción, entra al servidor de soporte:\n"
                f"{SUPPORT_INVITE}"
            ),
            color=discord.Color(0x0A3D62)
            )

            try:
                await interaction.user.send(embed=embed)
            except:
                pass

            return await interaction.response.send_message(
                "🧪 Simulación de unban global enviada a tu DM.",
                ephemeral=True
            )

# ============================
# COG PRINCIPAL
# ============================

class BlacklistGlobal(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.check_task = bot.loop.create_task(self.check_expired_bans())

    def cog_unload(self):
        self.check_task.cancel()

    # PANEL PRINCIPAL
    @app_commands.command(
        name="global_blacklist",
        description="Panel de gestión de la blacklist global"
    )
    async def global_blacklist_cmd(self, interaction: discord.Interaction):
        if not is_global_staff(interaction.user, self.bot):
            return await interaction.response.send_message(
                "❌ Solo el staff autorizado puede usar este comando.",
                ephemeral=True
            )

        embed = discord.Embed(
            title="🌐 Sistema de Blacklist Global",
            description=(
                "Gestiona la blacklist global de ModdyBot.\n\n"
                "• Añadir usuarios\n"
                "• Listar blacklist\n"
                "• Eliminar usuarios\n"
                "• Inspeccionar casos\n"
                "• Probar mensajes de ban/unban\n\n"
                f"Servidor de soporte: {SUPPORT_INVITE}"
            ),
            color=discord.Color.blurple()
        )

        view = GlobalBlacklistView(self.bot)
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)

    # CAPTURA DE PRUEBAS
    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if message.author.bot:
            return

        staff_id = message.author.id

        if staff_id not in pending_proofs:
            return

        entry = pending_proofs[staff_id]
        target_id = entry["target_id"]
        reason = entry["reason"]
        staff = entry["staff"]
        timestamp = entry["timestamp"]
        duration_text = entry["duration_text"]
        expires_at = entry["expires_at"]

        proofs = [a.url for a in message.attachments]

        blacklist_global[target_id] = {
            "razon": reason,
            "pruebas": proofs,
            "staff": staff,
            "fecha_ban": timestamp,
            "duracion": duration_text,
            "expira": expires_at,
            "expira_notificado": False
        }
        save_json(blacklist_global_path, blacklist_global)

        del pending_proofs[staff_id]

        # DM al usuario
        try:
            user_obj = await self.bot.fetch_user(int(target_id))
            embed = discord.Embed(
                title="<a:alarmazul:1491858094043693177> Has sido baneado globalmente (ModdyBot)",
                description=(
                    f"Has sido añadido a la **Blacklist Global de ModdyBot**.\n\n"
                    f"<:iinfo:1491858536895090708> **Razón:** {reason}\n"
                    f"<:calendario:1492176498197532725> **Fecha del ban:** {timestamp}\n"
                    f"<:cronometro:1492176494422659087> **Duración:** {duration_text}\n\n"
                    f"<a:flechazul:1492182951532826684> **Pruebas:**\n"
                    + ("\n".join(proofs) if proofs else "No se adjuntaron pruebas.") +
                    "\n\nSi quieres apelar tu sanción, entra al servidor de soporte:\n"
                    f"{SUPPORT_INVITE}"
                ),
                color=discord.Color(0x0A3D62)
            )
            if proofs:
                embed.set_image(url=proofs[0])
            await user_obj.send(embed=embed)
        except:
            pass

        # Ban global inmediato (excepto servidor soporte)
        for guild in self.bot.guilds:
            if guild.id == SUPPORT_GUILD_ID:
                continue
            member = guild.get_member(int(target_id))
            if member:
                try:
                    await member.ban(reason="Blacklist global")
                except:
                    pass

        await message.channel.send(
            f"🌐 Usuario `{target_id}` añadido a la blacklist global.\n"
            f"Pruebas guardadas: **{len(proofs)}**",
            delete_after=10
        )

    # AUTO-BAN GLOBAL AL ENTRAR
    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member):
        if member.guild.id == SUPPORT_GUILD_ID:
            return

        uid = str(member.id)

        if uid not in blacklist_global:
            return

        data = blacklist_global[uid]
        razon = data.get("razon", "No especificada")
        pruebas = data.get("pruebas", [])
        fecha_ban = data.get("fecha_ban", "Desconocida")
        duracion = data.get("duracion", "Permanente")

        # DM
        try:
            embed = discord.Embed(
    title="<a:alarmazul:1491858094043693177> Acceso denegado (ModdyBot)",
    description=(
        "Has intentado entrar a un servidor donde está ModdyBot, "
        "pero estás **baneado globalmente**.\n\n"
        f"<:iinfo:1491858536895090708> **Razón:** {razon}\n"
        f"**Fecha del ban:** {fecha_ban}\n"
        f"**Duración:** {duracion}\n\n"
        f"**Pruebas:**\n"
        + ("<a:flechazul:1492182951532826684> " + "\n".join(pruebas) if pruebas else "<a:flechazul:1492182951532826684> No se adjuntaron pruebas.")
        + "\n\n"
        f"Si quieres apelar tu sanción, entra al servidor de soporte:\n{SUPPORT_INVITE}"
    ),
    color=discord.Color(0x0A3D62)
            )
            if pruebas:
                embed.set_image(url=pruebas[0])

            await member.send(embed=embed)
        except:
            pass

        # Ban automático
        try:
            await member.ban(reason="Blacklist global")
        except:
            pass

    # TAREA: AVISAR CUANDO CUMPLE LA DURACIÓN
    async def check_expired_bans(self):
        await self.bot.wait_until_ready()
        while not self.bot.is_closed():
            now = datetime.utcnow()
            changed = False

            for uid, data in list(blacklist_global.items()):
                expira = data.get("expira", None)
                notificado = data.get("expira_notificado", False)

                if not expira or notificado:
                    continue

                try:
                    expira_dt = datetime.fromisoformat(expira)
                except:
                    continue

                if now >= expira_dt:
                    # Enviar DM de que puede solicitar revisión
                    try:
                        user_obj = await self.bot.fetch_user(int(uid))
                        embed = discord.Embed(
                            title="⏰ Tu sanción global ha cumplido su duración",
                            description=(
                                "Tu sanción en la **Blacklist Global de ModdyBot** ha cumplido el plazo configurado.\n\n"
                                "Esto **no significa** que hayas sido desbaneado automáticamente,\n"
                                "pero puedes solicitar una revisión abriendo un ticket en el servidor de soporte:\n"
                                f"{SUPPORT_INVITE}\n\n"
                                "Incluye toda la información posible para que el equipo de moderación revise tu caso."
                            ),
                            color=discord.Color.gold()
                        )
                        await user_obj.send(embed=embed)
                    except:
                        pass

                    data["expira_notificado"] = True
                    changed = True

            if changed:
                save_json(blacklist_global_path, blacklist_global)

            await discord.utils.sleep_until(datetime.utcnow() + timedelta(minutes=10))

# ============================
# SETUP DEL COG
# ============================

async def setup(bot: commands.Bot):
    await bot.add_cog(BlacklistGlobal(bot))
