import discord
from discord.ext import tasks
import embed_generator as eg
from field import Field
import traceback
from game import Game
from psycopg_pool import AsyncConnectionPool
from config import ALERT_ROLE

async def register_tasks(tree: discord.app_commands.CommandTree, client: discord.Client, db_pool : AsyncConnectionPool):

    async def get_servers_info():
        async with db_pool.connection() as db_con:
            async with db_con.cursor() as db_cur:
                await db_cur.execute("""SELECT server_id, alert_channel_id, game_currency FROM servers""")
                servers = await db_cur.fetchall()
        return servers

    @tasks.loop(hours=1)
    async def check_sales():
        servers = await get_servers_info()

        for s in servers:
            if s[1] is not None:
                channel = client.get_channel(s[1])
                if channel is None:
                    continue
                server = channel.guild
                role = discord.utils.get(server.roles, name = ALERT_ROLE)
                async with db_pool.connection() as db_con:
                    async with db_con.cursor() as db_cur:
                        await db_cur.execute("""SELECT store_id, last_price, name, link FROM games
                                        WHERE server_index=%s""", (s[0],))
                        games = await db_cur.fetchall()
                for g in games:
                    try:
                        game_details = Game(g[0], s[2])
                    except Exception:
                        traceback.print_exc()
                        continue

                    if game_details.not_out:
                        continue
                    
                    price = game_details.price
                    try:
                        if  price < g[1]:
                            fields = [Field(name="Name", value=game_details.title, inline=True),
                                    Field(name="New price", value=game_details.price_formatted),
                                    Field(name="Discount", value=str(game_details.discount)+'%')]
                            e = eg.custom_embed(title="DISCOUNT ALERT! 💸",
                                                description=f'[{g[2]}]({g[3]}) is currently on sale!',
                                                image=game_details.image, 
                                                color=discord.Color.dark_gold(),
                                                fields=fields)

                            await channel.send(content=role.mention, embed=e)
                            async with db_pool.connection() as db_con:
                                async with db_con.cursor() as db_cur:
                                    await db_cur.execute("""UPDATE games SET last_price = %s
                                                    WHERE store_id=%s""", (price, g[0]))
                        elif price > g[1]:
                            async with db_pool.connection() as db_con:
                                async with db_con.cursor() as db_cur:
                                    await db_cur.execute("""UPDATE games SET last_price = %s
                                                    WHERE store_id=%s""", (price, g[0]))
                    except Exception:
                        traceback.print_exc()
                        continue
    check_sales.start()

    @tasks.loop(hours=1)
    async def check_release():
        servers = await get_servers_info()

        for s in servers:
            if s[1] is not None:
                channel = client.get_channel(s[1])
                if channel is None:
                    continue
                server = channel.guild
                role = discord.utils.get(server.roles, name = ALERT_ROLE)

                async with db_pool.connection() as db_con:
                    async with db_con.cursor() as db_cur:
                        await db_cur.execute("""SELECT store_id, not_out, name, link FROM games
                                        WHERE server_index=%s""", (s[0],))
                        games = await db_cur.fetchall()
                for g in games:
                    try:
                        game_details = Game(g[0], s[2])
                    except Exception:
                        traceback.print_exc()
                        continue

                    if g[1] and not game_details.not_out:
                        game_price = game_details.price_formatted
                        
                        fields = [Field(name="Name", value=game_details.title, inline=True),
                                  Field(name="Price", value=game_price)]
                        e = eg.custom_embed(title="RELEASE ALERT! 📆",
                                            image=game_details.image,
                                            description= f'[{g[2]}]({g[3]}) has just released! 🚨',
                                            color=discord.Color.blurple(),
                                            fields=fields)

                        await channel.send(content=role.mention, embed=e)
                        try:
                            async with db_pool.connection() as db_con:
                                async with db_con.cursor() as db_cur:
                                    await db_cur.execute("""UPDATE games SET not_out = %s
                                                    WHERE store_id=%s""", (False, g[0]))
                        except Exception:
                            traceback.print_exc()
                            continue
    check_release.start()


