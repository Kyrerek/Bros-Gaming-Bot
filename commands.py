import discord
import requests
import re
import sqlite3
from datetime import datetime
import traceback
import math
import random

bot_role = "Gamer" 

async def get_game_deatils(id):
    url = f"https://store.steampowered.com/api/appdetails?appids={id}"
    response = requests.get(url)
    if response.status_code == 200:
        data = response.json()
        if data[str(id)]["success"]:
            return data[str(id)]["data"]
    return None

async def register_commands(tree: discord.app_commands.CommandTree, client, db: sqlite3.Connection):

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
        game_id = re.search(r'/app/(\d+)', link).group(1)
        game_details = await get_game_deatils(game_id)
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

        server_id = interaction.guild_id
        curr_date = datetime.now()

        e = discord.Embed()

        try:
            db_cursor = db.cursor()
            db_cursor.execute(f"""INSERT INTO games(server_index, name, link, date, store_id, platform) VALUES
                            (%s, %s, %s, %s, %s, %s)""", (server_id, game_name, link, curr_date, game_id, "steam"))
            db.commit()
        except:
            traceback.print_exc()
            e.title = "Error"
            e.description = "This game already exists on the list"
            await interaction.response.send_message(embed=e)
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

        game_details = await get_game_deatils(game[0])
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
    async def get_details(interaction: discord.Interaction, game_name: str):
        server_id = interaction.guild_id

        db_cursor = db.cursor()
        db_cursor.execute(f"""SELECT store_id, link FROM games
                            WHERE server_index=%s AND name=%s""", (server_id, game_name))  
        game = db_cursor.fetchone()

        if game is None:
            await interaction.response.send_message(embed=discord.Embed(title="Error", description=f"{game_name} does not exist on the list"), ephemeral=True)
            return

        game_details = await get_game_deatils(game[0])
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

        
        





