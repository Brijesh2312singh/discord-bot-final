import discord
from discord.ext import commands
import os
from dotenv import load_dotenv
import requests
import sqlite3
from datetime import datetime
import random

load_dotenv()
TOKEN = os.getenv('DISCORD_TOKEN')
GROQ_API_KEY = os.getenv('GROQ_API_KEY')
HF_API_KEY = os.getenv('HF_API_KEY')

print(f"✅ Discord Token: {TOKEN[:20]}...")
print(f"✅ Groq Key: {GROQ_API_KEY[:20]}..." if GROQ_API_KEY else "⚠️ No Groq Key!")
print(f"✅ HF Key: {HF_API_KEY[:20]}..." if HF_API_KEY else "⚠️ No HF Key!")

if not TOKEN:
    print("❌ DISCORD_TOKEN not found!")
    exit()

# Color Theme
class Colors:
    PRIMARY = 0x00a8ff
    SUCCESS = 0x00ff00
    ERROR = 0xff0000
    WARNING = 0xffaa00
    INFO = 0x7289da
    PURPLE = 0x9370db
    PINK = 0xff69b4
    GOLD = 0xffd700

# Emojis
EMOJIS = {
    "success": "✅",
    "error": "❌",
    "warning": "⚠️",
    "info": "ℹ️",
    "thinking": "🤔",
    "heart": "❤️",
    "star": "⭐",
    "fire": "🔥",
    "money": "💰",
    "level": "📊",
    "chat": "💬",
    "settings": "⚙️",
    "ai": "🤖",
    "image": "🎨",
    "trophy": "🏆",
    "up": "⬆️",
    "levelup": "🎉",
    "welcome": "👋",
    "role": "🎖️",
}

# Database Setup
def init_database():
    conn = sqlite3.connect('bot_database.db')
    c = conn.cursor()
    
    c.execute('''CREATE TABLE IF NOT EXISTS users
                 (user_id INTEGER PRIMARY KEY,
                  username TEXT,
                  coins INTEGER DEFAULT 0,
                  xp INTEGER DEFAULT 0,
                  level INTEGER DEFAULT 1,
                  warnings INTEGER DEFAULT 0,
                  model TEXT DEFAULT "llama-3.3-70b-versatile",
                  joined_date TEXT)''')
    
    c.execute('''CREATE TABLE IF NOT EXISTS server_settings
                 (server_id INTEGER PRIMARY KEY,
                  welcome_enabled INTEGER DEFAULT 1,
                  welcome_message TEXT,
                  welcome_channel_id INTEGER,
                  autorole_enabled INTEGER DEFAULT 0,
                  autorole_id INTEGER,
                  prefix TEXT DEFAULT "!")''')
    
    c.execute('''CREATE TABLE IF NOT EXISTS reaction_roles
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  server_id INTEGER,
                  message_id INTEGER,
                  emoji TEXT,
                  role_id INTEGER)''')
    
    conn.commit()
    conn.close()
    print("✅ Database initialized!")

init_database()

# Conversation History
conversation_history = {}

def get_user_history(user_id):
    if user_id not in conversation_history:
        conversation_history[user_id] = []
    return conversation_history[user_id]

def add_to_history(user_id, role, content):
    history = get_user_history(user_id)
    history.append({"role": role, "content": content})
    if len(history) > 10:
        history.pop(0)

def clear_history(user_id):
    if user_id in conversation_history:
        del conversation_history[user_id]

# Database Functions
def get_user(user_id):
    conn = sqlite3.connect('bot_database.db')
    c = conn.cursor()
    c.execute('SELECT * FROM users WHERE user_id = ?', (user_id,))
    user = c.fetchone()
    conn.close()
    return user

def create_user(user_id, username):
    conn = sqlite3.connect('bot_database.db')
    c = conn.cursor()
    c.execute('INSERT INTO users (user_id, username, joined_date) VALUES (?, ?, ?)',
              (user_id, username, datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
    conn.commit()
    conn.close()

def add_xp(user_id, xp_amount):
    user = get_user(user_id)
    if user is None:
        return False
    
    current_xp = user[3]
    current_level = user[4]
    new_xp = current_xp + xp_amount
    
    # XP per level: 100
    xp_per_level = 100
    new_level = new_xp // xp_per_level
    
    conn = sqlite3.connect('bot_database.db')
    c = conn.cursor()
    c.execute('UPDATE users SET xp = ?, level = ? WHERE user_id = ?', 
              (new_xp, new_level, user_id))
    conn.commit()
    conn.close()
    
    # Level up check
    if new_level > current_level:
        return True, new_level  # Leveled up!
    return False

# Server settings functions
def get_server_settings(server_id):
    conn = sqlite3.connect('bot_database.db')
    c = conn.cursor()
    c.execute('SELECT * FROM server_settings WHERE server_id = ?', (server_id,))
    settings = c.fetchone()
    conn.close()
    
    if settings is None:
        # Create default settings
        conn = sqlite3.connect('bot_database.db')
        c = conn.cursor()
        c.execute('''INSERT INTO server_settings 
                     (server_id, welcome_enabled, welcome_message, welcome_channel_id) 
                     VALUES (?, 1, ?, ?)''',
                  (server_id, "Welcome to the server!", None))
        conn.commit()
        conn.close()
        return (server_id, 1, "Welcome to the server!", None, 0, None, "!")
    
    return settings

# Bot Setup
intents = discord.Intents.all()
bot = commands.Bot(command_prefix='!', intents=intents)

@bot.event
async def on_ready():
    print(f'\n{"="*50}')
    print(f'✅ Bot ready: {bot.user}')
    print(f'✅ Servers: {len(bot.guilds)}')
    print(f'{"="*50}\n')
    
    await bot.change_presence(
        activity=discord.Activity(
            type=discord.ActivityType.playing,
            name="!ask for help | !commands"
        )
    )

# ==================== MESSAGE & LEVELING ====================

@bot.event
async def on_message(message):
    print(f"[MESSAGE] {message.author.name}: {message.content}")
    
    if message.author == bot.user:
        return
    
    # XP System - Add XP on every message
    if not message.author.bot:
        user = get_user(message.author.id)
        if user is None:
            create_user(message.author.id, message.author.name)
        
        # Random XP (5-15)
        xp_earned = random.randint(5, 15)
        level_up = add_xp(message.author.id, xp_earned)
        
        if level_up:
            new_level = level_up[1]
            embed = discord.Embed(
                title=f"{EMOJIS['levelup']} Level Up!",
                description=f"{message.author.mention} reached **Level {new_level}**!",
                color=Colors.GOLD
            )
            try:
                await message.channel.send(embed=embed)
            except:
                pass
    
    # Auto-reply to greetings
    if message.content.lower() in ["hello", "hi", "hey", "hola", "namaste", "assalamualaikum"]:
        greetings = [
            f"👋 Hello {message.author.mention}! Kaise ho?",
            f"Hi {message.author.mention}! 😊",
            f"Namaste {message.author.mention}! 🙏",
            f"Hey {message.author.mention}! Kya haal hai?"
        ]
        embed = discord.Embed(
            description=random.choice(greetings),
            color=Colors.PRIMARY
        )
        await message.reply(embed=embed)
        return
    
    if not message.content.startswith('!'):
        return
    
    await bot.process_commands(message)

# ==================== WELCOME SYSTEM ====================

@bot.event
async def on_member_join(member):
    """Auto-welcome new members"""
    print(f"[JOIN] {member.name} joined {member.guild.name}")
    
    settings = get_server_settings(member.guild.id)
    
    if settings[1] == 0:  # Welcome disabled
        return
    
    # Create user entry
    user = get_user(member.id)
    if user is None:
        create_user(member.id, member.name)
    
    # Auto-role assign
    if settings[4] == 1 and settings[5] is not None:  # autorole_enabled and autorole_id
        try:
            role = member.guild.get_role(settings[5])
            if role:
                await member.add_roles(role)
                print(f"[AUTOROLE] Assigned {role.name} to {member.name}")
        except Exception as e:
            print(f"[ERROR] Could not assign role: {e}")
    
    # Welcome message
    welcome_channel_id = settings[3]
    welcome_message = settings[2]
    
    if welcome_channel_id:
        try:
            channel = member.guild.get_channel(welcome_channel_id)
            if channel:
                embed = discord.Embed(
                    title=f"{EMOJIS['welcome']} Welcome!",
                    description=f"{member.mention} - {welcome_message}",
                    color=Colors.PRIMARY
                )
                embed.add_field(name="Member Count", value=f"Server mein ab {member.guild.member_count} members hain!", inline=False)
                embed.set_footer(text=f"Joined at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
                await channel.send(embed=embed)
        except Exception as e:
            print(f"[ERROR] Welcome message error: {e}")

# ==================== WELCOME COMMANDS ====================

@bot.command(name='welcome')
@commands.has_permissions(administrator=True)
async def welcome_config(ctx, option: str = None, *, value: str = None):
    """Admin command to configure welcome system"""
    print(f"[COMMAND] WELCOME CONFIG - {ctx.author}")
    
    if option is None:
        embed = discord.Embed(
            title=f"{EMOJIS['welcome']} Welcome System Config",
            color=Colors.INFO
        )
        embed.add_field(name="!welcome channel #channel", value="Set welcome channel", inline=False)
        embed.add_field(name="!welcome message 'message'", value="Set welcome message", inline=False)
        embed.add_field(name="!welcome role @role", value="Set auto-role", inline=False)
        embed.add_field(name="!welcome enable", value="Enable welcome", inline=False)
        embed.add_field(name="!welcome disable", value="Disable welcome", inline=False)
        await ctx.send(embed=embed)
        return
    
    option = option.lower()
    conn = sqlite3.connect('bot_database.db')
    c = conn.cursor()
    
    if option == "channel":
        if ctx.message.mentions:
            return
        if ctx.message.channel_mentions:
            channel = ctx.message.channel_mentions[0]
            c.execute('UPDATE server_settings SET welcome_channel_id = ? WHERE server_id = ?',
                      (channel.id, ctx.guild.id))
            embed = discord.Embed(
                title=f"{EMOJIS['success']} Updated",
                description=f"Welcome channel set to {channel.mention}",
                color=Colors.SUCCESS
            )
            await ctx.send(embed=embed)
    
    elif option == "message":
        c.execute('UPDATE server_settings SET welcome_message = ? WHERE server_id = ?',
                  (value, ctx.guild.id))
        embed = discord.Embed(
            title=f"{EMOJIS['success']} Updated",
            description=f"Welcome message updated to: {value}",
            color=Colors.SUCCESS
        )
        await ctx.send(embed=embed)
    
    elif option == "role":
        if ctx.message.role_mentions:
            role = ctx.message.role_mentions[0]
            c.execute('UPDATE server_settings SET autorole_id = ?, autorole_enabled = 1 WHERE server_id = ?',
                      (role.id, ctx.guild.id))
            embed = discord.Embed(
                title=f"{EMOJIS['success']} Updated",
                description=f"Auto-role set to {role.mention}",
                color=Colors.SUCCESS
            )
            await ctx.send(embed=embed)
    
    elif option == "enable":
        c.execute('UPDATE server_settings SET welcome_enabled = 1 WHERE server_id = ?',
                  (ctx.guild.id,))
        embed = discord.Embed(
            title=f"{EMOJIS['success']} Enabled",
            description="Welcome system enabled!",
            color=Colors.SUCCESS
        )
        await ctx.send(embed=embed)
    
    elif option == "disable":
        c.execute('UPDATE server_settings SET welcome_enabled = 0 WHERE server_id = ?',
                  (ctx.guild.id,))
        embed = discord.Embed(
            title=f"{EMOJIS['success']} Disabled",
            description="Welcome system disabled!",
            color=Colors.SUCCESS
        )
        await ctx.send(embed=embed)
    
    conn.commit()
    conn.close()

# ==================== REACTION ROLES ====================

@bot.command(name='reactionrole')
@commands.has_permissions(administrator=True)
async def reaction_role(ctx, option: str = None):
    """Setup reaction roles"""
    print(f"[COMMAND] REACTIONROLE - {ctx.author}: {option}")
    
    if option is None or option.lower() == "help":
        embed = discord.Embed(
            title=f"{EMOJIS['role']} Reaction Roles Setup",
            color=Colors.INFO
        )
        embed.add_field(name="!reactionrole setup", value="Setup new reaction role", inline=False)
        embed.add_field(name="!reactionrole list", value="List all reaction roles", inline=False)
        embed.add_field(name="Steps:", value=
            "1. Create message with role info\n" +
            "2. React with emoji\n" +
            "3. Use !reactionrole add <message_id> <emoji> <@role>",
            inline=False)
        await ctx.send(embed=embed)
        return
    
    option = option.lower()
    
    if option == "setup":
        embed = discord.Embed(
            title=f"{EMOJIS['role']} React to get roles!",
            description=
                "👨‍💻 = Developer\n" +
                "🎮 = Gamer\n" +
                "🎨 = Artist\n" +
                "📚 = Student",
            color=Colors.PURPLE
        )
        msg = await ctx.send(embed=embed)
        
        embed = discord.Embed(
            title=f"{EMOJIS['success']} Setup Complete",
            description=f"Message ID: {msg.id}\n\nNow use:\n!reactionrole add {msg.id} 👨‍💻 @Developer",
            color=Colors.SUCCESS
        )
        await ctx.send(embed=embed)
    
    elif option == "add":
        # Format: !reactionrole add <message_id> <emoji> <@role>
        await ctx.send("Usage: !reactionrole add <message_id> <emoji> @role")
    
    elif option == "list":
        conn = sqlite3.connect('bot_database.db')
        c = conn.cursor()
        c.execute('SELECT emoji, role_id FROM reaction_roles WHERE server_id = ?', (ctx.guild.id,))
        roles = c.fetchall()
        conn.close()
        
        if not roles:
            embed = discord.Embed(
                title=f"{EMOJIS['info']} No Reaction Roles",
                description="Setup reaction roles using !reactionrole setup",
                color=Colors.INFO
            )
            await ctx.send(embed=embed)
            return
        
        embed = discord.Embed(
            title=f"{EMOJIS['role']} Reaction Roles",
            color=Colors.PURPLE
        )
        for emoji, role_id in roles:
            role = ctx.guild.get_role(role_id)
            if role:
                embed.add_field(name=emoji, value=role.mention, inline=False)
        await ctx.send(embed=embed)

@bot.event
async def on_raw_reaction_add(payload):
    """Handle reaction role assignment"""
    if payload.user_id == bot.user.id:
        return
    
    conn = sqlite3.connect('bot_database.db')
    c = conn.cursor()
    c.execute('SELECT role_id FROM reaction_roles WHERE server_id = ? AND message_id = ? AND emoji = ?',
              (payload.guild_id, payload.message_id, str(payload.emoji)))
    result = c.fetchone()
    conn.close()
    
    if result:
        guild = bot.get_guild(payload.guild_id)
        role = guild.get_role(result[0])
        member = guild.get_member(payload.user_id)
        
        if role and member:
            try:
                await member.add_roles(role)
                print(f"[REACTION ROLE] Added {role.name} to {member.name}")
            except Exception as e:
                print(f"[ERROR] Could not add role: {e}")

@bot.event
async def on_raw_reaction_remove(payload):
    """Handle reaction role removal"""
    if payload.user_id == bot.user.id:
        return
    
    conn = sqlite3.connect('bot_database.db')
    c = conn.cursor()
    c.execute('SELECT role_id FROM reaction_roles WHERE server_id = ? AND message_id = ? AND emoji = ?',
              (payload.guild_id, payload.message_id, str(payload.emoji)))
    result = c.fetchone()
    conn.close()
    
    if result:
        guild = bot.get_guild(payload.guild_id)
        role = guild.get_role(result[0])
        member = guild.get_member(payload.user_id)
        
        if role and member:
            try:
                await member.remove_roles(role)
                print(f"[REACTION ROLE] Removed {role.name} from {member.name}")
            except Exception as e:
                print(f"[ERROR] Could not remove role: {e}")

# ==================== LEVELING COMMANDS ====================

@bot.command(name='rank')
async def rank(ctx, user: discord.User = None):
    """👤 Apna rank dekho"""
    print(f"[COMMAND] RANK - {ctx.author}")
    
    if user is None:
        user = ctx.author
    
    db_user = get_user(user.id)
    
    if db_user is None:
        create_user(user.id, user.name)
        level = 1
        xp = 0
    else:
        level = db_user[4]
        xp = db_user[3]
    
    # XP for next level
    xp_per_level = 100
    current_level_xp = level * xp_per_level
    next_level_xp = (level + 1) * xp_per_level
    progress = xp - current_level_xp
    progress_max = next_level_xp - current_level_xp
    
    embed = discord.Embed(
        title=f"{EMOJIS['level']} {user.name}'s Rank",
        color=Colors.PURPLE
    )
    embed.add_field(name="Level", value=f"🎖️ {level}", inline=True)
    embed.add_field(name="Total XP", value=f"⭐ {xp}", inline=True)
    embed.add_field(name="Progress", value=f"`{progress}/{progress_max}` XP", inline=False)
    
    # Progress bar
    bar_length = 20
    filled = int(bar_length * progress / progress_max)
    bar = "█" * filled + "░" * (bar_length - filled)
    embed.add_field(name="Progress Bar", value=f"`{bar}`", inline=False)
    await ctx.send(embed=embed)

@bot.command(name='leaderboard_rank')
async def leaderboard_rank(ctx):
    """🏆 Top players by level"""
    print(f"[COMMAND] LEADERBOARD RANK - {ctx.author}")
    
    conn = sqlite3.connect('bot_database.db')
    c = conn.cursor()
    c.execute('SELECT username, level, xp FROM users ORDER BY level DESC, xp DESC LIMIT 10')
    users = c.fetchall()
    conn.close()
    
    if not users:
        embed = discord.Embed(
            title=f"{EMOJIS['error']} No users",
            description="Koi users nahi hain!",
            color=Colors.ERROR
        )
        await ctx.send(embed=embed)
        return
    
    embed = discord.Embed(
        title="🏆 Top 10 Players",
        color=Colors.GOLD
    )
    
    medals = ["🥇", "🥈", "🥉"]
    
    for i, (username, level, xp) in enumerate(users, 1):
        medal = medals[i-1] if i <= 3 else f"{i}."
        embed.add_field(name=f"{medal} {username}", value=f"Level {level} • {xp} XP", inline=False)
    
    await ctx.send(embed=embed)

# ==================== AI COMMANDS ====================

@bot.command(name='ask')
async def ask_groq(ctx, *, question):
    """🤖 Groq AI se pooch"""
    print(f"[COMMAND] ASK - {ctx.author}: {question}")
    
    if not GROQ_API_KEY:
        embed = discord.Embed(
            title=f"{EMOJIS['error']} Error",
            description="Groq API Key not configured!",
            color=Colors.ERROR
        )
        await ctx.send(embed=embed)
        return
    
    try:
        try:
            await ctx.channel.trigger_typing()
        except:
            pass
        
        add_to_history(ctx.author.id, "user", question)
        history = get_user_history(ctx.author.id)
        
        conn = sqlite3.connect('bot_database.db')
        c = conn.cursor()
        c.execute('SELECT model FROM users WHERE user_id = ?', (ctx.author.id,))
        result = c.fetchone()
        conn.close()
        
        model = result[0] if result and result[0] else "llama-3.3-70b-versatile"
        
        url = "https://api.groq.com/openai/v1/chat/completions"
        headers = {
            "Authorization": f"Bearer {GROQ_API_KEY}",
            "Content-Type": "application/json"
        }
        data = {
            "model": model,
            "messages": history,
            "max_tokens": 1500,
            "temperature": 0.7
        }
        
        response = requests.post(url, headers=headers, json=data)
        result = response.json()
        
        if "choices" in result:
            answer = result["choices"][0]["message"]["content"]
            add_to_history(ctx.author.id, "assistant", answer)
            
            if len(answer) > 2000:
                chunks = [answer[i:i+2000] for i in range(0, len(answer), 2000)]
                for chunk in chunks:
                    embed = discord.Embed(
                        description=chunk,
                        color=Colors.PRIMARY
                    )
                    await ctx.send(embed=embed)
            else:
                embed = discord.Embed(
                    title=f"{EMOJIS['ai']} AI Assistant",
                    description=answer,
                    color=Colors.PRIMARY
                )
                await ctx.send(embed=embed)
            
            print(f"[RESPONSE] Groq AI reply sent")
        else:
            embed = discord.Embed(
                title=f"{EMOJIS['error']} Error",
                description=f"{result}",
                color=Colors.ERROR
            )
            await ctx.send(embed=embed)
        
    except Exception as e:
        print(f"[ERROR] {e}")
        embed = discord.Embed(
            title=f"{EMOJIS['error']} Error",
            description=f"{str(e)[:100]}",
            color=Colors.ERROR
        )
        await ctx.send(embed=embed)

@bot.command(name='model')
async def change_model(ctx, *, model_name=None):
    """🤖 Model change karo"""
    print(f"[COMMAND] MODEL - {ctx.author}: {model_name}")
    
    available_models = {
        "llama": "llama-3.3-70b-versatile",
        "mixtral": "mixtral-8x7b-32768",
        "gemma": "gemma2-9b-it",
    }
    
    if model_name is None:
        embed = discord.Embed(
            title="🤖 Available Models",
            color=Colors.PURPLE
        )
        for name, model in available_models.items():
            embed.add_field(name=f"!model {name}", value=model, inline=False)
        await ctx.send(embed=embed)
        return
    
    model_name = model_name.lower()
    
    if model_name in available_models:
        conn = sqlite3.connect('bot_database.db')
        c = conn.cursor()
        c.execute('UPDATE users SET model = ? WHERE user_id = ?', 
                  (available_models[model_name], ctx.author.id))
        conn.commit()
        conn.close()
        
        embed = discord.Embed(
            title=f"{EMOJIS['success']} Model Changed",
            description=f"Model: {available_models[model_name]}",
            color=Colors.SUCCESS
        )
        await ctx.send(embed=embed)
    else:
        embed = discord.Embed(
            title=f"{EMOJIS['error']} Error",
            description="Model available nahi hai!",
            color=Colors.ERROR
        )
        await ctx.send(embed=embed)

@bot.command(name='newchat')
async def new_chat(ctx):
    """✨ Naya conversation"""
    print(f"[COMMAND] NEWCHAT - {ctx.author}")
    
    clear_history(ctx.author.id)
    
    embed = discord.Embed(
        title="✨ New Chat Started",
        description="Fresh conversation!",
        color=Colors.INFO
    )
    await ctx.send(embed=embed)

@bot.command(name='history')
async def show_history(ctx):
    """📜 Chat history"""
    print(f"[COMMAND] HISTORY - {ctx.author}")
    
    history = get_user_history(ctx.author.id)
    
    if not history:
        embed = discord.Embed(
            title=f"{EMOJIS['info']} No History",
            description="Koi chat history nahi hai!",
            color=Colors.INFO
        )
        await ctx.send(embed=embed)
        return
    
    embed = discord.Embed(
        title="📜 Chat History",
        color=Colors.PURPLE
    )
    
    for i, msg in enumerate(history[-5:], 1):
        role = "👤 You" if msg["role"] == "user" else "🤖 AI"
        content = msg["content"][:80] + "..." if len(msg["content"]) > 80 else msg["content"]
        embed.add_field(name=f"{role}", value=content, inline=False)
    
    await ctx.send(embed=embed)

@bot.command(name='explain')
async def explain(ctx, *, topic):
    """📚 Detailed explanation"""
    print(f"[COMMAND] EXPLAIN - {ctx.author}: {topic}")
    
    if not GROQ_API_KEY:
        embed = discord.Embed(
            title=f"{EMOJIS['error']} Error",
            description="Groq API Key not configured!",
            color=Colors.ERROR
        )
        await ctx.send(embed=embed)
        return
    
    try:
        try:
            await ctx.channel.trigger_typing()
        except:
            pass
        
        prompt = f"""Please explain {topic} in detail with examples"""
        
        url = "https://api.groq.com/openai/v1/chat/completions"
        headers = {
            "Authorization": f"Bearer {GROQ_API_KEY}",
            "Content-Type": "application/json"
        }
        data = {
            "model": "llama-3.3-70b-versatile",
            "messages": [{"role": "user", "content": prompt}],
            "max_tokens": 2000,
            "temperature": 0.7
        }
        
        response = requests.post(url, headers=headers, json=data)
        result = response.json()
        
        if "choices" in result:
            answer = result["choices"][0]["message"]["content"]
            
            if len(answer) > 2000:
                chunks = [answer[i:i+2000] for i in range(0, len(answer), 2000)]
                for chunk in chunks:
                    embed = discord.Embed(
                        title=f"📚 {topic}",
                        description=chunk,
                        color=Colors.INFO
                    )
                    await ctx.send(embed=embed)
            else:
                embed = discord.Embed(
                    title=f"📚 {topic}",
                    description=answer,
                    color=Colors.INFO
                )
                await ctx.send(embed=embed)
        
    except Exception as e:
        print(f"[ERROR] {e}")

@bot.command(name='imagine')
async def imagine(ctx, *, prompt):
    """🎨 Image generation"""
    print(f"[COMMAND] IMAGINE - {ctx.author}: {prompt}")
    
    try:
        try:
            await ctx.channel.trigger_typing()
        except:
            pass
        
        from urllib.parse import quote
        encoded_prompt = quote(prompt)
        url = f"https://image.pollinations.ai/prompt/{encoded_prompt}"
        
        embed = discord.Embed(
            title="🎨 Image Generated!",
            description=f"**Prompt:** {prompt}",
            color=Colors.PURPLE
        )
        embed.set_image(url=url)
        await ctx.send(embed=embed)
        
    except Exception as e:
        print(f"[ERROR] {e}")

# ==================== ECONOMY ====================

@bot.command(name='balance')
async def balance(ctx):
    """💰 Balance"""
    print(f"[COMMAND] BALANCE - {ctx.author}")
    
    user = get_user(ctx.author.id)
    
    if user is None:
        create_user(ctx.author.id, ctx.author.name)
        coins = 0
    else:
        coins = user[2]
    
    embed = discord.Embed(
        title=f"{EMOJIS['money']} Balance",
        color=Colors.GOLD
    )
    embed.add_field(name="Coins", value=f"💰 {coins}", inline=False)
    await ctx.send(embed=embed)

@bot.command(name='daily')
async def daily(ctx):
    """🎁 Daily reward"""
    print(f"[COMMAND] DAILY - {ctx.author}")
    
    user = get_user(ctx.author.id)
    
    if user is None:
        create_user(ctx.author.id, ctx.author.name)
        coins = 100
    else:
        coins = user[2] + 100
    
    conn = sqlite3.connect('bot_database.db')
    c = conn.cursor()
    c.execute('UPDATE users SET coins = ? WHERE user_id = ?', (coins, ctx.author.id))
    conn.commit()
    conn.close()
    
    embed = discord.Embed(
        title=f"{EMOJIS['success']} Daily Reward",
        description=f"✅ 100 coins milgaye!",
        color=Colors.SUCCESS
    )
    embed.add_field(name="Total Coins", value=f"💰 {coins}", inline=False)
    await ctx.send(embed=embed)

@bot.command(name='profile')
async def profile(ctx, user: discord.User = None):
    """👤 Profile"""
    print(f"[COMMAND] PROFILE - {ctx.author}")
    
    if user is None:
        user = ctx.author
    
    db_user = get_user(user.id)
    
    if db_user is None:
        create_user(user.id, user.name)
        coins = 0
        xp = 0
        level = 1
    else:
        coins = db_user[2]
        xp = db_user[3]
        level = db_user[4]
    
    embed = discord.Embed(
        title=f"👤 {user.name}'s Profile",
        color=Colors.PRIMARY
    )
    embed.add_field(name="Level", value=f"🎖️ {level}", inline=True)
    embed.add_field(name="XP", value=f"⭐ {xp}", inline=True)
    embed.add_field(name="Coins", value=f"💰 {coins}", inline=False)
    await ctx.send(embed=embed)

@bot.command(name='leaderboard')
async def leaderboard(ctx):
    """🏆 Leaderboard"""
    print(f"[COMMAND] LEADERBOARD - {ctx.author}")
    
    conn = sqlite3.connect('bot_database.db')
    c = conn.cursor()
    c.execute('SELECT username, coins FROM users ORDER BY coins DESC LIMIT 10')
    users = c.fetchall()
    conn.close()
    
    if not users:
        embed = discord.Embed(
            title=f"{EMOJIS['error']} No users",
            color=Colors.ERROR
        )
        await ctx.send(embed=embed)
        return
    
    embed = discord.Embed(
        title="🏆 Top 10 Richest",
        color=Colors.GOLD
    )
    
    medals = ["🥇", "🥈", "🥉"]
    
    for i, (username, coins) in enumerate(users, 1):
        medal = medals[i-1] if i <= 3 else f"{i}."
        embed.add_field(name=f"{medal} {username}", value=f"💰 {coins}", inline=False)
    
    await ctx.send(embed=embed)

# ==================== FUN ====================

@bot.command(name='joke')
async def joke(ctx):
    """😂 Joke"""
    print(f"[COMMAND] JOKE - {ctx.author}")
    
    try:
        response = requests.get("https://official-joke-api.appspot.com/random_joke")
        data = response.json()
        
        if "setup" in data:
            embed = discord.Embed(
                title="😂 Random Joke",
                color=Colors.PINK
            )
            embed.add_field(name="Setup", value=data["setup"], inline=False)
            embed.add_field(name="Punchline", value=data["punchline"], inline=False)
            await ctx.send(embed=embed)
    except Exception as e:
        print(f"[ERROR] {e}")

@bot.command(name='quote')
async def quote(ctx):
    """✨ Quote"""
    print(f"[COMMAND] QUOTE - {ctx.author}")
    
    try:
        response = requests.get("https://api.quotable.io/random")
        data = response.json()
        
        if "content" in data:
            embed = discord.Embed(
                title="✨ Random Quote",
                description=f'"{data["content"]}"',
                color=Colors.PURPLE
            )
            embed.set_footer(text=f"— {data.get('author', 'Unknown')}")
            await ctx.send(embed=embed)
    except Exception as e:
        print(f"[ERROR] {e}")

@bot.command(name='dice')
async def dice_game(ctx, sides: int = 6):
    """🎲 Dice"""
    print(f"[COMMAND] DICE - {ctx.author}")
    
    if sides < 2 or sides > 100:
        embed = discord.Embed(
            title=f"{EMOJIS['error']} Error",
            color=Colors.ERROR
        )
        await ctx.send(embed=embed)
        return
    
    result = random.randint(1, sides)
    
    embed = discord.Embed(
        title="🎲 Dice Roll",
        color=Colors.PRIMARY
    )
    embed.add_field(name="Result", value=f"**{result}**", inline=False)
    await ctx.send(embed=embed)

@bot.command(name='rps')
async def rps(ctx, choice: str):
    """🎮 RPS"""
    print(f"[COMMAND] RPS - {ctx.author}: {choice}")
    
    choice = choice.lower()
    
    if choice not in ["rock", "paper", "scissors"]:
        embed = discord.Embed(
            title=f"{EMOJIS['error']} Error",
            color=Colors.ERROR
        )
        await ctx.send(embed=embed)
        return
    
    bot_choice = random.choice(["rock", "paper", "scissors"])
    
    if choice == bot_choice:
        result = "🤝 Draw!"
    elif (choice == "rock" and bot_choice == "scissors") or \
         (choice == "paper" and bot_choice == "rock") or \
         (choice == "scissors" and bot_choice == "paper"):
        result = f"{EMOJIS['success']} You won!"
    else:
        result = f"{EMOJIS['error']} You lost!"
    
    embed = discord.Embed(
        title="🎮 Rock Paper Scissors",
        color=Colors.PRIMARY
    )
    embed.add_field(name="Your Choice", value=choice.capitalize(), inline=True)
    embed.add_field(name="Bot Choice", value=bot_choice.capitalize(), inline=True)
    embed.add_field(name="Result", value=result, inline=False)
    await ctx.send(embed=embed)

# ==================== INFO ====================

@bot.command(name='test')
async def test(ctx):
    """✅ Test"""
    embed = discord.Embed(
        title=f"{EMOJIS['success']} Bot Working!",
        color=Colors.SUCCESS
    )
    await ctx.send(embed=embed)

@bot.command(name='ping')
async def ping(ctx):
    """🏓 Ping"""
    latency = round(bot.latency * 1000)
    embed = discord.Embed(
        title="🏓 Pong!",
        description=f"Latency: {latency}ms",
        color=Colors.PRIMARY
    )
    await ctx.send(embed=embed)

@bot.command(name='commands')
async def commands_list(ctx):
    """📚 Commands"""
    embed = discord.Embed(
        title="📚 All Commands",
        color=Colors.INFO
    )
    
    embed.add_field(name="🎖️ Leveling", value=
        "!rank - Your rank\n" +
        "!leaderboard_rank - Top players",
        inline=False)
    
    embed.add_field(name="👋 Welcome", value=
        "!welcome - Configure welcome\n" +
        "Auto-greet new members",
        inline=False)
    
    embed.add_field(name="🎖️ Reaction Roles", value=
        "!reactionrole setup - Setup roles\n" +
        "!reactionrole list - List roles",
        inline=False)
    
    embed.add_field(name="🤖 AI Chat", value=
        "!ask - Chat with AI\n" +
        "!explain - Detailed info\n" +
        "!model - Change model",
        inline=False)
    
    embed.add_field(name="💰 Economy", value=
        "!balance - View coins\n" +
        "!daily - Daily reward\n" +
        "!leaderboard - Top richest",
        inline=False)
    
    embed.add_field(name="🎮 Fun", value=
        "!joke - Random joke\n" +
        "!dice - Dice roll\n" +
        "!rps - Rock Paper Scissors",
        inline=False)
    
    await ctx.send(embed=embed)

print("🚀 Starting bot...")
try:
    bot.run(TOKEN)
except Exception as e:
    print(f"ERROR: {e}")
    import traceback
    traceback.print_exc()