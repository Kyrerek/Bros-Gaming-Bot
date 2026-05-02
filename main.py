import discord
from discord.ext import commands
import logging
from dotenv import load_dotenv
import os
import psycopg2
from commands import register_commands


load_dotenv()
token = os.getenv('DISCORD_TOKEN')

handler = logging.FileHandler(filename='discord.log', encoding='utf-8', mode='w')
intents = discord.Intents.default()

client = discord.Client(intents=intents)
tree = discord.app_commands.CommandTree(client)
db_con = psycopg2.connect(os.getenv("DATABASE_URL"))
db_con.autocommit = False

@client.event
async def on_ready():
    await register_commands(tree, client, db_con)
    await tree.sync()
    print(f"Bot is ready: {client.user.name}")

@client.event
async def on_guild_join(guild):
    server_name = guild.name
    server_id = guild.id
    print(f"Bot added to: {server_name} {server_id}")
    db_cur = db_con.cursor()
    db_cur.execute("""INSERT INTO servers(server_id, server_name) VALUES
                   (%s, %s)""", (server_id, server_name))
    db_con.commit()

@client.event
async def on_guild_remove(guild):
    server_name = guild.name
    server_id = guild.id
    print(f"Bot removed from: {server_name} {server_id}")
    db_cur = db_con.cursor()
    db_cur.execute(f"""DELETE FROM games 
                              WHERE server_index=%s""", (server_id,))
    db_cur.execute(f"""DELETE FROM servers WHERE server_id=%s""", (server_id,))
    db_con.commit()

client.run(token, log_handler=handler, log_level=logging.DEBUG)
 
