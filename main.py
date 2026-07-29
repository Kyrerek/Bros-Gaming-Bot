import discord
import logging
from dotenv import load_dotenv
import os
from psycopg_pool import AsyncConnectionPool
from commands import register_commands
from tasks import register_tasks

load_dotenv()
token = os.getenv("DISCORD_TOKEN")

handler = logging.FileHandler(filename="discord.log", encoding="utf-8", mode="w")
intents = discord.Intents.default()

client = discord.Client(intents=intents)
tree = discord.app_commands.CommandTree(client)
db_pool = AsyncConnectionPool(
    conninfo=os.getenv("DATABASE_URL"), min_size=2, max_size=10, open=False
)


@client.event
async def on_ready():
    await db_pool.open()
    await register_commands(tree, client, db_pool)
    await register_tasks(tree, client, db_pool)
    await tree.sync()
    print(f"Bot is ready: {client.user.name}")


@client.event
async def on_guild_join(guild):
    server_name = guild.name
    server_id = guild.id
    print(f"Bot added to: {server_name} {server_id}")
    async with db_pool.connection() as db_con:
        async with db_con.cursor() as db_cur:
            await db_cur.execute(
                """INSERT INTO servers(server_id, server_name) VALUES
                (%s, %s)""",
                (server_id, server_name),
            )


@client.event
async def on_guild_remove(guild):
    server_name = guild.name
    server_id = guild.id
    print(f"Bot removed from: {server_name} {server_id}")
    async with db_pool.connection() as db_con:
        async with db_con.cursor() as db_cur:
            await db_cur.execute(
                """DELETE FROM games 
                WHERE server_index=%s""",
                (server_id,),
            )
            await db_cur.execute(
                """DELETE FROM servers 
                WHERE server_id=%s""",
                (server_id,),
            )


client.run(token, log_handler=handler, log_level=logging.DEBUG)
