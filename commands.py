import discord
import requests
import re
import psycopg2
from datetime import datetime
import traceback
import math
import random

bot_role = "Gamer" 

async def get_game_deatils(id, currency):
    url = f"https://store.steampowered.com/api/appdetails?appids={id}&cc={currency}"
    response = requests.get(url)
    if response.status_code == 200:
        data = response.json()
        if data[str(id)]["success"]:
            return data[str(id)]["data"]
    return None

async def register_commands(tree: discord.app_commands.CommandTree, client: discord.Client, db):

    @tree.command(name="subscribe", description="Get a role for gaming alerts")
    async def sub(interaction: discord.Interaction):
        role = discord.utils.get(interaction.guild.roles, name=bot_role)
        if role:
            await interaction.user.add_roles(role)
            e = discord.Embed()
            e.title = "Success"
            e.description = f"{interaction.user.mention} got a role {role}"
            await interaction.response.send_message(embed=e, ephemeral=True)

    @tree.command(name="add_link", description="Add a game by a link")
    @discord.app_commands.describe(link="Link to the game")
    async def add_link(interaction: discord.Interaction, link: str):
        server_id = interaction.guild_id

        db_cursor = db.cursor()
        db_cursor.execute("""SELECT game_currency FROM servers
                          WHERE server_id=%s""", (server_id,))
        cc = db_cursor.fetchone()[0]

        game_id = re.search(r'/app/(\d+)', link).group(1)
        game_details = await get_game_deatils(game_id, cc)
        if game_details is None:
            await interaction.response.send_message(embed=discord.Embed(title="Error", description=f"{game_name} does not exist on Steam or there is another error"), ephemeral=True)
            return
        game_name = game_details['name']
        game_price = ""
        try:
            game_price = "free" if game_details["is_free"] else game_details["price_overview"]["final_formatted"]
        except:
            game_price = "Not mentioned"
        
        game_image = game_details["header_image"]
        not_out = game_details["release_date"]["coming_soon"]

        curr_date = datetime.now()

        e = discord.Embed()

        try:
            db_cursor.execute("""INSERT INTO games(server_index, name, link, date, store_id, platform, last_price, not_out) VALUES
                            (%s, %s, %s, %s, %s, %s, %s, %s)""", (server_id, 
                                                          game_name, 
                                                          link, 
                                                          curr_date, 
                                                          game_id, 
                                                          "steam", 
                                                          game_details["price_overview"]["final"] if game_price != "Not mentioned" and game_price != "free" else 0,
                                                          not_out))
            db.commit()
        except:
            traceback.print_exc()
            e.title = "Error"
            e.description = "This game already exists on the list"
            await interaction.response.send_message(embed=e, ephemeral=True)
        else:
            e.title = 'Adding a game'
            e.description = f'{interaction.user.mention} has just added {link}'
            e.set_image(url=game_image)
            e.add_field(name="Name", value=game_name)
            e.add_field(name="Price", value=game_price)
            if not_out:
                e.add_field(name="Release date", value=game_details["release_date"]["date"])
            await interaction.response.send_message(embed=e)
    
    @tree.command(name="delete_game", description="Delete a game")
    @discord.app_commands.describe(game_name = "Name of the game to delete")
    async def delete_game(interaction: discord.Interaction, game_name: str):
        server_id = interaction.guild_id

        e = discord.Embed()

        try:
            db_cursor = db.cursor()
            db_cursor.execute(f"""SELECT store_id FROM games
                                WHERE server_index=%s AND name=%s""", (server_id, game_name))
            game_id = db_cursor.fetchone()[0]
            db_cursor.execute(f"""DELETE FROM games 
                              WHERE store_id=%s AND server_index=%s""", (game_id, server_id))
            db.commit()
        except Exception as ex:
            traceback.print_exc()
            e.title = "Error"
            e.description = "Something went wrong :c"
            await interaction.response.send_message(embed=e, ephemeral=True)
        else:
            e.title = "Success"
            e.description = "Everything went good c:"
            await interaction.response.send_message(embed=e, ephemeral=True)
    
    class GamesView(discord.ui.View):
        def __init__(self, games):
            super().__init__(timeout=60)
            self.games = games
            self.page = 0
            self.max_page = math.ceil(len(games)/10)

        def create_embed(self):
            start = self.page*10
            end = start+10
            l_games = self.games[start:end]
            embed = discord.Embed(title="List of games", 
                              description="\n".join([f"* [{i[0]}]({i[1]})" for i in l_games]), 
                              color=discord.Color.blue())
            embed.set_thumbnail(url="https://preview.redd.it/galactus-is-coming-waltuh-v0-nnopft4eilgf1.jpeg?width=640&crop=smart&auto=webp&s=be4554d63dab3ed682f59dc136376e9183d85161")
            embed.set_footer(text=f"Page {self.page+1}/{self.max_page}")
            return embed
        
        @discord.ui.button(label="Previous", style=discord.ButtonStyle.red, emoji="⬅️")
        async def button_list_prev(self, interaction: discord.Interaction, button: discord.ui.Button):
            if self.page > 0:
                self.page-=1
                await interaction.response.edit_message(embed=self.create_embed(), view=self)

        @discord.ui.button(label="Next", style=discord.ButtonStyle.green, emoji="➡️")
        async def button_list_next(self, interaction: discord.Interaction, button: discord.ui.Button):
            if self.page+1 < self.max_page:
                self.page+=1
                await interaction.response.edit_message(embed=self.create_embed(), view=self)

    @tree.command(name="list_games", description="List 10 games, sorted by date")
    async def list_games(interaction: discord.Interaction):
        server_id = interaction.guild_id

        db_cur = db.cursor()
        db_cur.execute(f"""SELECT name, link FROM games
                        WHERE server_index=%s""", (server_id,))
        games = db_cur.fetchall()

        l_games = games[:10]

        embed = discord.Embed(title="List of games", 
                              description="\n".join([f"* [{i[0]}]({i[1]})" for i in l_games]) if games else "First use /add_link to add at least one game", 
                              color=discord.Color.blue())
        embed.set_thumbnail(url="https://preview.redd.it/galactus-is-coming-waltuh-v0-nnopft4eilgf1.jpeg?width=640&crop=smart&auto=webp&s=be4554d63dab3ed682f59dc136376e9183d85161")
        if games:
            embed.set_footer(text=f"Page 1/{math.ceil(len(games)/10)}")
        view = GamesView(games)
        
        if len(games) > 10: 
            await interaction.response.send_message(embed=embed, view=view)
        else:
            await interaction.response.send_message(embed=embed)

    @tree.command(name="get_random", description="Get random game from the list")
    async def get_random(interaction: discord.Interaction):
        server_id = interaction.guild_id

        db_cur = db.cursor()
        db_cur.execute(f"""SELECT store_id, link FROM games
                        WHERE server_index=%s""", (server_id,))
        games = db_cur.fetchall()
        
        game = random.choice(games)

        db_cur.execute("""SELECT game_currency FROM servers
                       WHERE server_id=%s""", (server_id,))
        cc = db_cur.fetchone()
        game_details = await get_game_deatils(game[0], cc[0])
        if game_details is None:
            await interaction.response.send_message(embed=discord.Embed(title="Error", description=f"{game_name} does not exist on Steam or there is another error"), ephemeral=True)
            return
        game_link = game[1]
        game_name = game_details['name']
        game_price = ""
        try:
            game_price = "free" if game_details["is_free"] else game_details["price_overview"]["final_formatted"]
        except:
            game_price = "Not mentioned"
        
        game_image = game_details["header_image"]
        not_out = game_details["release_date"]["coming_soon"]
        game_desc = game_details["short_description"]

        e = discord.Embed(title="Random game")
        e.set_image(url=game_image)    
        e.add_field(name="Name", value=game_name)
        e.add_field(name="Price", value=game_price)
        e.add_field(name="Link", value=game_link)
        e.add_field(name="Description", value=game_desc, inline=True)
        if not_out:
            e.add_field(name="Release date", value=game_details["release_date"]["date"])
        await interaction.response.send_message(embed=e)

    @tree.command(name="get_details", description="Get details of the game")
    @discord.app_commands.describe(game_name = "Name of the game")
    async def get_details(interaction: discord.Interaction, game_name: str):
        server_id = interaction.guild_id

        db_cursor = db.cursor()
        db_cursor.execute(f"""SELECT store_id, link FROM games
                            WHERE server_index=%s AND name=%s""", (server_id, game_name))  
        game = db_cursor.fetchone()

        if game is None:
            await interaction.response.send_message(embed=discord.Embed(title="Error", description=f"{game_name} does not exist on the list"), ephemeral=True)
            return

        db_cursor.execute("""SELECT game_currency FROM servers
                       WHERE server_id=%s""", (server_id,))
        cc = db_cursor.fetchone()
        game_details = await get_game_deatils(game[0], cc[0])
        if game_details is None:
            await interaction.response.send_message(embed=discord.Embed(title="Error", description=f"{game_name} does not exist on Steam or there is another error"), ephemeral=True)
            return
        
        game_link = game[1]
        game_name = game_details['name']
        game_price = ""
        try:
            game_price = "free" if game_details["is_free"] else game_details["price_overview"]["final_formatted"]
        except:
            game_price = "Not mentioned"
        
        game_image = game_details["header_image"]
        not_out = game_details["release_date"]["coming_soon"]
        game_desc = game_details["short_description"]

        e = discord.Embed(title="Game details")
        e.set_image(url=game_image)    
        e.add_field(name="Name", value=game_name)
        e.add_field(name="Price", value=game_price)
        e.add_field(name="Link", value=game_link)
        e.add_field(name="Description", value=game_desc, inline=True)
        if not_out:
            e.add_field(name="Release date", value=game_details["release_date"]["date"])
        await interaction.response.send_message(embed=e)

    @tree.command(name="set_alert_channel", description="Set a channel for gaming alerts (sales, releases)")
    @discord.app_commands.describe(channel = "Gaming alert channel")
    async def set_alert_channel(interaction: discord.Interaction, channel: discord.TextChannel):
        channel_id = channel.id
        server_id = interaction.guild_id

        e = discord.Embed()

        try:
            db_cursor = db.cursor()
            db_cursor.execute("""UPDATE servers 
                          SET alert_channel_id=%s
                          WHERE server_id=%s""", (channel_id, server_id))
            db.commit()
        except:
            traceback.print_tb()
            m = traceback.format_exc()
            e.title = "Error"
            e.description = f"Something went wrong :c\n{m}"
        else:
            e.title = "Success"
            e.description = "Everything went good c:"
        
        await interaction.response.send_message(embed=e, ephemeral=True)
    
    @tree.command(name="set_currency", description="Set currency for games")
    @discord.app_commands.describe(cc = "Currency code (default is US)")
    @discord.app_commands.choices(cc = [
        discord.app_commands.Choice(name="Polish Zloty (PLN)", value="PL"),
        discord.app_commands.Choice(name="US Dollar (USD)", value="US"),
        discord.app_commands.Choice(name="Euro - Germany (EUR)", value="DE"),
        discord.app_commands.Choice(name="Euro - France (EUR)", value="FR"),
        discord.app_commands.Choice(name="British Pound (GBP)", value="GB"),
        discord.app_commands.Choice(name="Ukrainian Hryvnia (UAH)", value="UA"),
        discord.app_commands.Choice(name="Czech Koruna (CZK)", value="CZ"),
        discord.app_commands.Choice(name="Hungarian Forint (HUF)", value="HU"),
        discord.app_commands.Choice(name="Norwegian Krone (NOK)", value="NO"),
        discord.app_commands.Choice(name="Swedish Krona (SEK)", value="SE"),
        discord.app_commands.Choice(name="Danish Krone (DKK)", value="DK"),
        discord.app_commands.Choice(name="Swiss Franc (CHF)", value="CH"),
        discord.app_commands.Choice(name="Canadian Dollar (CAD)", value="CA"),
        discord.app_commands.Choice(name="Australian Dollar (AUD)", value="AU"),
        discord.app_commands.Choice(name="Brazilian Real (BRL)", value="BR"),
        discord.app_commands.Choice(name="Turkish Lira (TRY)", value="TR"),
        discord.app_commands.Choice(name="Russian Ruble (RUB)", value="RU"),
        discord.app_commands.Choice(name="Japanese Yen (JPY)", value="JP"),
        discord.app_commands.Choice(name="South Korean Won (KRW)", value="KR"),
        discord.app_commands.Choice(name="Chinese Yuan (CNY)", value="CN"),
        discord.app_commands.Choice(name="Indian Rupee (INR)", value="IN"),
        discord.app_commands.Choice(name="Mexican Peso (MXN)", value="MX"),
        discord.app_commands.Choice(name="Argentine Peso (ARS)", value="AR"),
        discord.app_commands.Choice(name="New Zealand Dollar (NZD)", value="NZ"),
        discord.app_commands.Choice(name="Singapore Dollar (SGD)", value="SG")
    ])
    async def set_currency(interaction: discord.Interaction, cc: str):
        server_id = interaction.guild_id

        e = discord.Embed()

        try:
            db_cursor = db.cursor()
            db_cursor.execute("""UPDATE servers 
                          SET game_currency=%s
                          WHERE server_id=%s""", (cc, server_id))
            db.commit()
        except:
            traceback.print_tb()
            m = traceback.format_exc()
            e.title = "Error"
            e.description = f"Something went wrong :c\n{m}"
        else:
            e.title = "Success"
            e.description = "Everything went good c:"
        
        await interaction.response.send_message(embed=e, ephemeral=True)

    #TODO 
    # 1. update price when changing currency
    # 1. more platforms
    # 2. command for lowest price omn the internet


        
        





