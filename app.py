import os
import json
import discord
import psutil
from datetime import datetime, timezone
from discord import app_commands
from discord.ext import commands
from discord.ui import View, Button
from dotenv import load_dotenv
load_dotenv()

# ==========================
# CONFIG JSON
# ==========================

CONFIG_PATH = "config.json"

def load_config():
    if not os.path.exists(CONFIG_PATH):
        default = {
            "staff_roles": [],
            "category_id": None,
            "ticket_message": "Hola {user}, un miembro del staff te atenderá en breve.",
            "ticket_color": 0x3498db,
            "panel_title": "Panel de Soporte",
            "panel_description": "Presiona el botón para abrir un ticket."
        }
        with open(CONFIG_PATH, "w") as f:
            json.dump(default, f, indent=4)
        return default

    with open(CONFIG_PATH, "r") as f:
        return json.load(f)

def save_config():
    with open(CONFIG_PATH, "w") as f:
        json.dump(ticket_config, f, indent=4)

# ==========================
# CONFIG BÁSICA
# ==========================

TOKEN = os.getenv("TOKEN")
GUILD_ID = 1491397564799385670

intents = discord.Intents.default()
intents.members = True
intents.guilds = True

bot = commands.Bot(command_prefix="!", intents=intents)

# ==========================
# CONFIG DE TICKETS (CARGADA DESDE JSON)
# ==========================

ticket_config = load_config()

# ==========================
# SETUP
# ==========================

@bot.event
async def on_ready():
    await bot.tree.sync(guild=discord.Object(id=GUILD_ID))
    print(f"Bot listo como {bot.user}")

# ==========================
# PING
# ==========================

@bot.tree.command(name="ping", description="Latencia del bot", guild=discord.Object(id=GUILD_ID))
async def ping(interaction: discord.Interaction):
    await interaction.response.send_message(f"Pong! {round(bot.latency*1000)}ms", ephemeral=True)

# ==========================
# STATUS HOST
# ==========================

status = app_commands.Group(name="status", description="Estado del host", guild_ids=[GUILD_ID])

@status.command(name="host", description="CPU, RAM, Disco, Uptime")
async def host(interaction: discord.Interaction):
    cpu = psutil.cpu_percent(1)
    ram = psutil.virtual_memory()
    disk = psutil.disk_usage("/")
    uptime = datetime.now(timezone.utc) - datetime.fromtimestamp(psutil.boot_time(), timezone.utc)

    embed = discord.Embed(title="Status del Host", color=discord.Color.green())
    embed.add_field(name="CPU", value=f"{cpu}%")
    embed.add_field(name="RAM", value=f"{ram.percent}%")
    embed.add_field(name="Disco", value=f"{disk.percent}%")
    embed.add_field(name="Uptime", value=str(uptime).split(".")[0])

    await interaction.response.send_message(embed=embed, ephemeral=True)

bot.tree.add_command(status)

# ==========================
# BIENVENIDAS / DESPEDIDAS
# ==========================

welcome_channel = None
bye_channel = None

@bot.tree.command(name="bienvenidas", description="Configura canal de bienvenida", guild=discord.Object(id=GUILD_ID))
async def bienvenidas(interaction: discord.Interaction, canal: discord.TextChannel):
    global welcome_channel
    welcome_channel = canal.id
    await interaction.response.send_message("Canal de bienvenidas configurado.", ephemeral=True)

@bot.tree.command(name="despedidas", description="Configura canal de despedida", guild=discord.Object(id=GUILD_ID))
async def despedidas(interaction: discord.Interaction, canal: discord.TextChannel):
    global bye_channel
    bye_channel = canal.id
    await interaction.response.send_message("Canal de despedidas configurado.", ephemeral=True)

@bot.event
async def on_member_join(member):
    if welcome_channel:
        ch = bot.get_channel(welcome_channel)
        if ch:
            await ch.send(f"Bienvenid@ {member.mention}")

@bot.event
async def on_member_remove(member):
    if bye_channel:
        ch = bot.get_channel(bye_channel)
        if ch:
            await ch.send(f"{member.mention} salió del servidor")

# ==========================
# TICKET CONFIG
# ==========================

@bot.tree.command(name="ticket_config", description="Configura el sistema de tickets", guild=discord.Object(id=GUILD_ID))
@app_commands.describe(
    staff_rol="Rol de staff que podrá ver y gestionar tickets",
    categoria="Categoría donde se crearán los tickets",
    mensaje_ticket="Mensaje inicial dentro del ticket (usa {user} para mencionar al usuario)",
    color_hex="Color del embed en formato HEX (ej: #3498db)",
    panel_titulo="Título del panel de tickets",
    panel_descripcion="Descripción del panel de tickets"
)
async def ticket_config_cmd(
    interaction: discord.Interaction,
    staff_rol: discord.Role | None = None,
    categoria: discord.CategoryChannel | None = None,
    mensaje_ticket: str | None = None,
    color_hex: str | None = None,
    panel_titulo: str | None = None,
    panel_descripcion: str | None = None
):
    changed = []

    if staff_rol is not None:
        if staff_rol.id not in ticket_config["staff_roles"]:
            ticket_config["staff_roles"].append(staff_rol.id)
        changed.append(f"➕ Rol staff añadido: {staff_rol.mention}")
        save_config()

    if categoria is not None:
        ticket_config["category_id"] = categoria.id
        changed.append(f"📂 Categoría de tickets: {categoria.mention}")
        save_config()

    if mensaje_ticket is not None:
        ticket_config["ticket_message"] = mensaje_ticket
        changed.append("💬 Mensaje inicial del ticket actualizado.")
        save_config()

    if color_hex is not None:
        try:
            ticket_config["ticket_color"] = int(color_hex.replace("#", ""), 16)
            changed.append(f"🎨 Color del embed: {color_hex}")
            save_config()
        except ValueError:
            return await interaction.response.send_message("❌ Color inválido. Usa formato HEX, por ejemplo: `#3498db`.", ephemeral=True)

    if panel_titulo is not None:
        ticket_config["panel_title"] = panel_titulo
        changed.append("📝 Título del panel actualizado.")
        save_config()

    if panel_descripcion is not None:
        ticket_config["panel_description"] = panel_descripcion
        changed.append("📝 Descripción del panel actualizada.")
        save_config()

    if not changed:
        return await interaction.response.send_message("No se ha cambiado nada en la configuración.", ephemeral=True)

    texto = "**Configuración de tickets actualizada:**\n" + "\n".join(changed)
    await interaction.response.send_message(texto, ephemeral=True)

# ==========================
# VISTA DEL TICKET
# ==========================

def es_staff(user: discord.Member) -> bool:
    if not ticket_config["staff_roles"]:
        return False
    return any(r.id in ticket_config["staff_roles"] for r in user.roles)

class TicketView(View):
    def __init__(self, autor_id: int):
        super().__init__(timeout=None)
        self.autor_id = autor_id

    @discord.ui.button(label="Reclamar", style=discord.ButtonStyle.green)
    async def reclamar(self, interaction: discord.Interaction, button: Button):
        if not es_staff(interaction.user):
            return await interaction.response.send_message("❌ Solo el staff puede reclamar tickets.", ephemeral=True)

        button.disabled = True
        button.label = f"Reclamado por {interaction.user.name}"
        await interaction.message.edit(view=self)

        await interaction.response.send_message(f"✅ Ticket reclamado por {interaction.user.mention}.", ephemeral=True)

    @discord.ui.button(label="Cerrar", style=discord.ButtonStyle.danger)
    async def cerrar(self, interaction: discord.Interaction, button: Button):
        if not (es_staff(interaction.user) or interaction.user.id == self.autor_id):
            return await interaction.response.send_message("❌ Solo el staff o el creador del ticket pueden cerrarlo.", ephemeral=True)

        await interaction.response.send_message("🔒 Cerrando ticket...", ephemeral=True)
        await interaction.channel.delete()

# ==========================
# PANEL CON BOTÓN
# ==========================

class PanelView(View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="Abrir Ticket", style=discord.ButtonStyle.green)
    async def abrir_ticket(self, interaction: discord.Interaction, button: Button):
        guild = interaction.guild

        if ticket_config["category_id"] is None:
            return await interaction.response.send_message("❌ No hay categoría configurada. Usa `/ticket_config`.", ephemeral=True)

        categoria = guild.get_channel(ticket_config["category_id"])
        if not isinstance(categoria, discord.CategoryChannel):
            return await interaction.response.send_message("❌ La categoría configurada ya no existe.", ephemeral=True)

        overwrites = {
            guild.default_role: discord.PermissionOverwrite(view_channel=False),
            interaction.user: discord.PermissionOverwrite(view_channel=True, send_messages=True),
        }

        for role_id in ticket_config["staff_roles"]:
            rol = guild.get_role(role_id)
            if rol:
                overwrites[rol] = discord.PermissionOverwrite(view_channel=True, send_messages=True)

        channel = await guild.create_text_channel(
            name=f"ticket-{interaction.user.name}",
            category=categoria,
            overwrites=overwrites
        )

        msg_text = ticket_config["ticket_message"].format(user=interaction.user.mention)
        embed = discord.Embed(
            title="🎫 Ticket de Soporte",
            description=msg_text,
            color=ticket_config["ticket_color"]
        )
        embed.add_field(name="Usuario", value=interaction.user.mention, inline=True)

        view = TicketView(autor_id=interaction.user.id)
        await channel.send(embed=embed, view=view)

        await interaction.response.send_message(f"✅ Ticket creado: {channel.mention}", ephemeral=True)

@bot.tree.command(name="panel", description="Enviar panel de tickets a un canal", guild=discord.Object(id=GUILD_ID))
async def panel(interaction: discord.Interaction, canal: discord.TextChannel):
    embed = discord.Embed(
        title=ticket_config["panel_title"],
        description=ticket_config["panel_description"],
        color=discord.Color.blurple()
    )
    await canal.send(embed=embed, view=PanelView())
    await interaction.response.send_message(f"✅ Panel enviado a {canal.mention}", ephemeral=True)

# ==========================
# COMANDOS ANTIGUOS
# ==========================

ticket = app_commands.Group(name="ticket", description="Gestión de tickets", guild_ids=[GUILD_ID])

def is_ticket(ch: discord.abc.GuildChannel):
    return isinstance(ch, discord.TextChannel) and ch.name.startswith("ticket-")

@ticket.command(name="cerrar", description="Cerrar ticket")
async def cerrar_cmd(interaction: discord.Interaction):
    if is_ticket(interaction.channel):
        await interaction.response.send_message("Cerrando ticket...", ephemeral=True)
        await interaction.channel.delete()

@ticket.command(name="reclamar", description="Reclamar ticket")
async def reclamar_cmd(interaction: discord.Interaction):
    if is_ticket(interaction.channel):
        await interaction.response.send_message(f"{interaction.user.mention} reclamó el ticket")

@ticket.command(name="añadir", description="Añadir usuario")
async def añadir(interaction: discord.Interaction, miembro: discord.Member):
    if is_ticket(interaction.channel):
        await interaction.channel.set_permissions(miembro, view_channel=True, send_messages=True)
        await interaction.response.send_message("Usuario añadido", ephemeral=True)

@ticket.command(name="eliminar", description="Eliminar usuario")
async def eliminar(interaction: discord.Interaction, miembro: discord.Member):
    if is_ticket(interaction.channel):
        await interaction.channel.set_permissions(miembro, overwrite=None)
        await interaction.response.send_message("Usuario eliminado", ephemeral=True)

bot.tree.add_command(ticket)

# ==========================
# RUN
# ==========================

bot.run(TOKEN)
