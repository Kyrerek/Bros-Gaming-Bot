import discord
from discord.ext import tasks
import psycopg2
import requests

bot_role = "Gamer" 


async def get_game_deatils(id, currency):
    url = f"https://store.steampowered.com/api/appdetails?appids={id}&cc={currency}"
    response = requests.get(url)
    if response.status_code == 200:
        data = response.json()
        if data[str(id)]["success"]:
            return data[str(id)]["data"]
    return None

async def register_tasks(tree: discord.app_commands.CommandTree, client: discord.Client, db):

    @tasks.loop(hours=1)
    async def check_sales():
        db_cursor = db.cursor()
        db_cursor.execute("""SELECT server_id, alert_channel_id, game_currency FROM servers""")
        servers = db_cursor.fetchall()

        for s in servers:
            if s[1] is not None:
                channel = client.get_channel(s[1])
                if channel is None:
                    continue
                server = channel.guild
                role = discord.utils.get(server.roles, name = bot_role)

                db_cursor.execute("""SELECT store_id, last_price, name, link FROM games
                                  WHERE server_index=%s""", (s[0],))
                games = db_cursor.fetchall()
                for g in games:
                    game_details = await get_game_deatils(g[0], s[2])

                    if game_details is None:
                        continue
                    
                    if game_details.get("price_overview") is None:
                        continue
                    
                    price = game_details["price_overview"]["final"]
                    if  price < g[1]:

                        e = discord.Embed(title="🚨!DISCOUNT ALERT!🚨", color=discord.Color.dark_gold())
                        e.description = f'[{g[2]}]({g[3]}) is currently on sale! 🚨'
                        e.set_image(url=game_details["header_image"])
                        e.add_field(name="Name", value=game_details['name'])
                        e.add_field(name="New price", value=game_details["price_overview"]["final_formatted"])
                        e.add_field(name="Discount (%)", value=game_details["price_overview"]["discount_percent"])

                        await channel.send(content=role.mention, embed=e)

                        db_cursor.execute("""UPDATE games SET last_price = %s
                                          WHERE store_id=%s""", (price, g[0]))
                        db.commit()
                    elif price > g[1]:
                        db_cursor.execute("""UPDATE games SET last_price = %s
                                          WHERE store_id=%s""", (price, g[0]))
                        db.commit()
    check_sales.start()

    @tasks.loop(hours=1)
    async def check_release():
        db_cursor = db.cursor()
        db_cursor.execute("""SELECT server_id, alert_channel_id, game_currency FROM servers""")
        servers = db_cursor.fetchall()

        for s in servers:
            if s[1] is not None:
                channel = client.get_channel(s[1])
                if channel is None:
                    continue
                server = channel.guild
                role = discord.utils.get(server.roles, name = bot_role)

                db_cursor.execute("""SELECT store_id, not_out, name, link FROM games
                                  WHERE server_index=%s""", (s[0],))
                games = db_cursor.fetchall()
                for g in games:
                    game_details = await get_game_deatils(g[0], s[2])
                    
                    if game_details is None:
                        continue

                    if g[1] and not game_details["release_date"]["coming_soon"]:
                        game_price = ""
                        try:
                            game_price = "free" if game_details["is_free"] else game_details["price_overview"]["final_formatted"]
                        except:
                            game_price = "Not mentioned"

                        e = discord.Embed(title="🚨!RELEASE ALERT!🚨", color=discord.Color.dark_gold())
                        e.description = f'[{g[2]}]({g[3]}) has just released! 🚨'
                        e.set_image(url=game_details["header_image"])
                        e.add_field(name="Name", value=game_details['name'])
                        e.add_field(name="Price", value=game_price)

                        await channel.send(content=role.mention, embed=e)

                        db_cursor.execute("""UPDATE games SET not_out = %s
                                          WHERE store_id=%s""", (False, g[0]))
                        db.commit()
    check_release.start()


