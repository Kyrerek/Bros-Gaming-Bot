import discord
import requests
import re
from datetime import datetime
import traceback
import math
import random
from game import Game
import embed_generator as eg
from field import Field
from psycopg_pool import AsyncConnectionPool
import psycopg
from config import ALERT_ROLE


async def register_commands(
    tree: discord.app_commands.CommandTree,
    client: discord.Client,
    db_pool: AsyncConnectionPool,
):
    @tree.command(name="subscribe", description="Get a role for gaming alerts")
    async def sub(interaction: discord.Interaction):
        role = discord.utils.get(interaction.guild.roles, name=ALERT_ROLE)
        try:
            if role:
                if role in interaction.user.roles:
                    await interaction.response.send_message(
                        embed=eg.success_embed("You have already subscribed before"),
                        ephemeral=True,
                    )
                    return
                await interaction.user.add_roles(role)
                await interaction.response.send_message(
                    embed=eg.success_embed(), ephemeral=True
                )
            else:
                await interaction.response.send_message(
                    embed=eg.error_embed(
                        f"Role {ALERT_ROLE} doens't exist on this server. Remember to put it under Bros Gaming Bot role!"
                    ),
                    ephemeral=True,
                )
        except discord.errors.Forbidden:
            traceback.print_exc()
            await interaction.response.send_message(
                embed=eg.error_embed(
                    f"Bot doens't have permission to add a role to this user. Maybe {ALERT_ROLE} role is above Bros Gaming Bot role"
                ),
                ephemeral=True,
            )
        except Exception:
            traceback.print_exc()
            await interaction.response.send_message(
                embed=eg.error_embed(), ephemeral=True
            )

    async def get_currency(server_id: int):
        async with db_pool.connection() as db_con:
            async with db_con.cursor() as db_cur:
                await db_cur.execute(
                    """SELECT game_currency FROM servers
                                WHERE server_id=%s""",
                    (server_id,),
                )
                row = await db_cur.fetchone()
        return row[0]

    @tree.command(name="add_link", description="Add a game by a link")
    @discord.app_commands.describe(link="Link to the game")
    async def add_link(interaction: discord.Interaction, link: str):
        if not re.match(r"https://store.steampowered.com/app/\d+/\w+/", link):
            await interaction.response.send_message(
                embed=eg.error_embed("This link is not a link to steam app"),
                ephemeral=True,
            )
            return
        server_id = interaction.guild_id

        cc = await get_currency(server_id)

        game_id = re.search(r"/app/(\d+)", link).group(1)
        try:
            game = Game(game_id, cc)
        except requests.exceptions.Timeout:
            await interaction.response.send_message(
                embed=eg.error_embed("Timeout. Try again"), ephemeral=True
            )
            return
        except NameError as e:
            embed = eg.error_embed(e.args[0])
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return
        except Exception:
            traceback.print_exc()
            await interaction.response.send_message(
                embed=eg.error_embed(), ephemeral=True
            )
            return

        game_name = game.title
        game_price = game.price_formatted
        not_out = game.not_out

        curr_date = datetime.now()

        try:
            async with db_pool.connection() as db_con:
                async with db_con.cursor() as db_cur:
                    await db_cur.execute(
                        """INSERT INTO games(server_index, name, link, date, store_id, platform, last_price, not_out) VALUES
                                    (%s, %s, %s, %s, %s, %s, %s, %s)""",
                        (
                            server_id,
                            game_name,
                            link,
                            curr_date,
                            game_id,
                            "steam",
                            game.price,
                            not_out,
                        ),
                    )
        except psycopg.errors.UniqueViolation:
            await interaction.response.send_message(
                embed=eg.error_embed(description="This game has been already added"),
                ephemeral=True,
            )
        except Exception:
            traceback.print_exc()
            await interaction.response.send_message(
                embed=eg.error_embed(), ephemeral=True
            )
        else:
            fields = [
                Field(name="Name", value=game_name, inline=True),
                Field(name="Price", value=game_price),
            ]
            if not_out:
                fields.append(Field(name="Release date", value=game.release_date))
            e = eg.custom_embed(
                title="Adding a game ✅",
                image=game.image,
                description=f"{interaction.user.mention} has just added {link}",
                color=discord.Color.dark_green(),
                fields=fields,
            )
            await interaction.response.send_message(embed=e)

    async def game_name_autocomplete(interaction: discord.Interaction, current: str):
        server_id = interaction.guild_id
        async with db_pool.connection() as db_con:
            async with db_con.cursor() as db_cur:
                await db_cur.execute(
                    """SELECT name FROM games
                        WHERE server_index = %s AND name LIKE %s
                        ORDER BY date DESC
                        LIMIT 25
                        """,
                    (server_id, current + "%"),
                )
                games = await db_cur.fetchall()
        return [discord.app_commands.Choice(name=g[0], value=g[0]) for g in games]

    @tree.command(name="delete_game", description="Delete a game")
    @discord.app_commands.describe(game_name="Name of the game to delete")
    @discord.app_commands.autocomplete(game_name=game_name_autocomplete)
    async def delete_game(interaction: discord.Interaction, game_name: str):
        server_id = interaction.guild_id

        try:
            async with db_pool.connection() as db_con:
                async with db_con.cursor() as db_cur:
                    await db_cur.execute(
                        """SELECT store_id FROM games
                                        WHERE server_index=%s AND name=%s""",
                        (server_id, game_name),
                    )
                    row = await db_cur.fetchone()
                    game_id = row[0]
                    await db_cur.execute(
                        """DELETE FROM games 
                                    WHERE store_id=%s AND server_index=%s""",
                        (game_id, server_id),
                    )
        except TypeError:
            await interaction.response.send_message(
                embed=eg.error_embed(
                    description=f"{game_name} does not appear on the list"
                ),
                ephemeral=True,
            )
        except Exception:
            traceback.print_exc()
            await interaction.response.send_message(
                embed=eg.error_embed(), ephemeral=True
            )
        else:
            await interaction.response.send_message(
                embed=eg.success_embed(), ephemeral=True
            )

    class GamesView(discord.ui.View):
        def __init__(self, games):
            super().__init__(timeout=300)
            self.games = games
            self.page = 0
            self.max_page = math.ceil(len(games) / 10)
            self._update_buttons()

        def _create_embed(self):
            start = self.page * 10
            end = start + 10
            l_games = self.games[start:end]
            embed = eg.custom_embed(
                title=f"List of games ({len(self.games)}) 📜",
                description="\n".join([f"* [{i[0]}]({i[1]})" for i in l_games]),
                color=discord.Color.blue(),
            )
            embed.set_footer(text=f"Page {self.page + 1}/{self.max_page}")
            return embed
        
        def _update_buttons(self):
            self.button_list_next.disabled = self.page + 1 == self.max_page
            self.button_list_prev.disabled = self.page == 0

        @discord.ui.button(label="Previous", style=discord.ButtonStyle.red, emoji="⬅️")
        async def button_list_prev(
            self, interaction: discord.Interaction, button: discord.ui.Button
        ):
            if self.page > 0:
                self.page -= 1
                self._update_buttons()
                await interaction.response.edit_message(
                    embed=self._create_embed(), view=self
                )

        @discord.ui.button(label="Next", style=discord.ButtonStyle.green, emoji="➡️")
        async def button_list_next(
            self, interaction: discord.Interaction, button: discord.ui.Button
        ):
            if self.page + 1 < self.max_page:
                self.page += 1
                self._update_buttons()
                await interaction.response.edit_message(
                    embed=self._create_embed(), view=self
                )

    # TODO: new embed and better look
    @tree.command(name="list_games", description="List 10 games, sorted by date added")
    async def list_games(interaction: discord.Interaction):
        server_id = interaction.guild_id

        async with db_pool.connection() as db_con:
            async with db_con.cursor() as db_cur:
                await db_cur.execute(
                    """SELECT name, link FROM games
                    WHERE server_index=%s
                    ORDER BY date""",
                    (server_id,),
                )
                games = await db_cur.fetchall()

        l_games = games[:10]

        embed = eg.custom_embed(
            title=f"List of games ({len(games)}) 📜",
            description="\n".join([f"* [{i[0]}]({i[1]})" for i in l_games])
            if games
            else "First use /add_link to add at least one game",
            color=discord.Color.blue(),
        )
        if games:
            embed.set_footer(text=f"Page 1/{math.ceil(len(games) / 10)}")
        view = GamesView(games)

        if len(games) > 10:
            await interaction.response.send_message(embed=embed, view=view)
        else:
            await interaction.response.send_message(embed=embed)

    @tree.command(
        name="get_random",
        description="Get random game from the list of already released games",
    )
    async def get_random(interaction: discord.Interaction):
        server_id = interaction.guild_id

        async with db_pool.connection() as db_con:
            async with db_con.cursor() as db_cur:
                await db_cur.execute(
                    """SELECT store_id, link FROM games
                    WHERE server_index=%s AND NOT not_out""",
                    (server_id,),
                )
                games = await db_cur.fetchall()
        if not games:
            await interaction.response.send_message(
                embed=eg.error_embed(
                    "The list of games is empty, or all games from the list have not yet been released. Use /add_link first"
                ),
                ephemeral=True,
            )
        game = random.choice(games)

        cc = await get_currency(server_id)

        try:
            game_details = Game(game[0], cc)
        except requests.exceptions.Timeout:
            await interaction.response.send_message(
                embed=eg.error_embed("Timeout. Try again"), ephemeral=True
            )
            return
        except Exception:
            traceback.print_exc()
            await interaction.response.send_message(
                embed=eg.error_embed(), ephemeral=True
            )
            return

        game_name = game_details.title
        game_price = game_details.price_formatted
        not_out = game_details.not_out
        game_link = game[1]
        game_image = game_details.image
        game_desc = game_details.desc

        fields = [
            Field(name="Name", value=game_name, inline=True),
            Field(name="Price", value=game_price),
            Field(name="Description", value=game_desc, inline=True),
            Field(name="Link", value=game_link),
        ]
        if not_out:
            fields.insert(
                2, Field(name="Release date", value=game_details.release_date)
            )
        e = eg.custom_embed(
            title="Random game 🎲",
            image=game_image,
            color=discord.Color.purple(),
            fields=fields,
        )
        await interaction.response.send_message(embed=e)

    @tree.command(name="get_details", description="Get details of the game")
    @discord.app_commands.describe(game_name="Name of the game")
    @discord.app_commands.autocomplete(game_name=game_name_autocomplete)
    async def get_details(interaction: discord.Interaction, game_name: str):
        server_id = interaction.guild_id

        async with db_pool.connection() as db_con:
            async with db_con.cursor() as db_cur:
                await db_cur.execute(
                    """SELECT store_id, link FROM games
                    WHERE server_index=%s AND name=%s""",
                    (server_id, game_name),
                )
                game = await db_cur.fetchone()

        if game is None:
            await interaction.response.send_message(
                embed=eg.error_embed(
                    description=f"{game_name} does not appear on the list"
                ),
                ephemeral=True,
            )
            return

        cc = await get_currency(server_id)
        try:
            game_details = Game(game[0], cc)
        except requests.exceptions.Timeout:
            await interaction.response.send_message(
                embed=eg.error_embed("Timeout. Try again"), ephemeral=True
            )
            return
        except Exception:
            traceback.print_exc()
            await interaction.response.send_message(
                embed=eg.error_embed(), ephemeral=True
            )
            return

        game_name = game_details.title
        game_price = game_details.price_formatted
        not_out = game_details.not_out
        game_link = game[1]
        game_image = game_details.image
        game_desc = game_details.desc

        fields = [
            Field(name="Name", value=game_name, inline=True),
            Field(name="Price", value=game_price),
            Field(name="Description", value=game_desc, inline=True),
            Field(name="Link", value=game_link),
        ]
        if not_out:
            fields.insert(
                2, Field(name="Release date", value=game_details.release_date)
            )
        e = eg.custom_embed(
            title="Game details 📄",
            image=game_image,
            color=discord.Color.dark_blue(),
            fields=fields,
        )
        await interaction.response.send_message(embed=e)

    @tree.command(
        name="set_alert_channel",
        description="Set a channel for gaming alerts (sales, releases)",
    )
    @discord.app_commands.describe(channel="Gaming alert channel")
    async def set_alert_channel(
        interaction: discord.Interaction, channel: discord.TextChannel
    ):
        channel_id = channel.id
        server_id = interaction.guild_id

        try:
            async with db_pool.connection() as db_con:
                async with db_con.cursor() as db_cur:
                    await db_cur.execute(
                        """UPDATE servers 
                                SET alert_channel_id=%s
                                WHERE server_id=%s""",
                        (channel_id, server_id),
                    )
        except Exception:
            traceback.print_exc()
            await interaction.response.send_message(
                embed=eg.error_embed(), ephemeral=True
            )
        else:
            await interaction.response.send_message(
                embed=eg.success_embed(), ephemeral=True
            )

    @tree.command(name="set_currency", description="Set currency for games")
    @discord.app_commands.describe(cc="Currency code (default is US)")
    @discord.app_commands.choices(
        cc=[
            discord.app_commands.Choice(name="US Dollar (USD)", value="US"),
            discord.app_commands.Choice(name="Euro (EUR)", value="DE"),
            discord.app_commands.Choice(name="British Pound (GBP)", value="GB"),
            discord.app_commands.Choice(name="Polish Złoty (PLN)", value="PL"),
            discord.app_commands.Choice(name="Japanese Yen (JPY)", value="JP"),
            discord.app_commands.Choice(name="Chinese Yuan (CNY)", value="CN"),
            discord.app_commands.Choice(name="South Korean Won (KRW)", value="KR"),
            discord.app_commands.Choice(name="Indian Rupee (INR)", value="IN"),
            discord.app_commands.Choice(name="Brazilian Real (BRL)", value="BR"),
            discord.app_commands.Choice(name="Russian Ruble (RUB)", value="RU"),
            discord.app_commands.Choice(name="Canadian Dollar (CAD)", value="CA"),
            discord.app_commands.Choice(name="Australian Dollar (AUD)", value="AU"),
            discord.app_commands.Choice(name="Mexican Peso (MXN)", value="MX"),
            discord.app_commands.Choice(name="Swiss Franc (CHF)", value="CH"),
            discord.app_commands.Choice(name="Norwegian Krone (NOK)", value="NO"),
            discord.app_commands.Choice(name="Hong Kong Dollar (HKD)", value="HK"),
            discord.app_commands.Choice(name="Singapore Dollar (SGD)", value="SG"),
            discord.app_commands.Choice(name="Thai Baht (THB)", value="TH"),
            discord.app_commands.Choice(name="Indonesian Rupiah (IDR)", value="ID"),
            discord.app_commands.Choice(name="Philippine Peso (PHP)", value="PH"),
            discord.app_commands.Choice(name="Malaysian Ringgit (MYR)", value="MY"),
            discord.app_commands.Choice(name="Vietnamese Dong (VND)", value="VN"),
            discord.app_commands.Choice(name="South African Rand (ZAR)", value="ZA"),
            discord.app_commands.Choice(name="Ukrainian Hryvnia (UAH)", value="UA"),
            discord.app_commands.Choice(name="Israeli Shekel (ILS)", value="IL"),
        ]
    )
    async def set_currency(interaction: discord.Interaction, cc: str):
        server_id = interaction.guild_id
        server_cc = await get_currency(server_id)
        if server_cc == cc:
            await interaction.response.send_message(
                embed=eg.success_embed(f"Currency has been already set to {cc}"),
                ephemeral=True,
            )
            return
        try:
            async with db_pool.connection() as db_con:
                async with db_con.cursor() as db_cur:
                    await db_cur.execute(
                        """SELECT store_id FROM games
                                WHERE server_index=%s""",
                        (server_id,),
                    )
                    games = [str(g[0]) for g in await db_cur.fetchall()]
            if games:
                games_str = ",".join(games)
                url = f"https://store.steampowered.com/api/appdetails?appids={games_str}&filters=price_overview&cc={cc}"
                response = requests.get(url, timeout=20)
                ids = []
                prices = []
                if response.status_code == 200:
                    data = response.json()
                    for g in games:
                        if data[g]["success"]:
                            if data[g]["data"]:
                                price = data[g]["data"]["price_overview"]["final"]
                                ids.append(int(g))
                                prices.append(price)
                            else:
                                ids.append(int(g))
                                prices.append(0)
            async with db_pool.connection() as db_con:
                async with db_con.cursor() as db_cur:
                    if games:
                        update_query = """UPDATE games
                                        SET last_price = data.last_price
                                        FROM (
                                            SELECT unnest(%s::bigint[]) as store_id,
                                            unnest(%s::int[]) as last_price
                                        ) 
                                        AS data
                                        WHERE games.store_id = data.store_id"""
                        await db_cur.execute(update_query, (ids, prices))
                    await db_cur.execute(
                        """UPDATE servers 
                                SET game_currency=%s
                                WHERE server_id=%s""",
                        (cc, server_id),
                    )
        except requests.exceptions.Timeout:
            await interaction.response.send_message(
                embed=eg.error_embed("Timeout. Try again"), ephemeral=True
            )
        except Exception:
            traceback.print_exc()
            await interaction.response.send_message(
                embed=eg.error_embed(), ephemeral=True
            )
        else:
            await interaction.response.send_message(
                embed=eg.success_embed(), ephemeral=True
            )

    @tree.command(
        name="lowest_price", description="Get the lowest prices of a given game"
    )
    @discord.app_commands.describe(game_name="Name of the game")
    @discord.app_commands.autocomplete(game_name=game_name_autocomplete)
    async def lowest_price(interaction: discord.Interaction, game_name: str):
        server_id = interaction.guild_id

        async with db_pool.connection() as db_con:
            async with db_con.cursor() as db_cur:
                await db_cur.execute(
                    """SELECT store_id FROM games
                                    WHERE server_index=%s AND name=%s""",
                    (server_id, game_name),
                )
                game_record = await db_cur.fetchone()
        if game_record is None:
            await interaction.response.send_message(
                embed=eg.error_embed(
                    description=f"{game_name} does not appear on the list"
                ),
                ephemeral=True,
            )
            return

        cc = await get_currency(server_id)
        try:
            game = Game(game_record[0], cc)
        except requests.exceptions.Timeout:
            await interaction.response.send_message(
                embed=eg.error_embed("Timeout. Try again"), ephemeral=True
            )
            return
        except NameError as e:
            traceback.print_exc()
            await interaction.response.send_message(
                embed=eg.error_embed(e.args[0]), ephemeral=True
            )
            return
        except Exception:
            traceback.print_exc()
            await interaction.response.send_message(
                embed=eg.error_embed(), ephemeral=True
            )
            return
        try:
            lowest = game.lowest_price()
        except requests.exceptions.Timeout:
            await interaction.response.send_message(
                embed=eg.error_embed("Timeout. Try again"), ephemeral=True
            )
            return
        except AttributeError as e:
            traceback.print_exc()
            await interaction.response.send_message(
                embed=eg.error_embed(e.args[0]), ephemeral=True
            )
            return
        except Exception:
            traceback.print_exc()
            await interaction.response.send_message(
                embed=eg.error_embed(), ephemeral=True
            )
            return
        if lowest[0]:
            lowest_retail = lowest[0] + " " + lowest[3]
        else:
            lowest_retail = "Not mentioned"

        if lowest[1]:
            lowest_keyshop = lowest[1] + " " + lowest[3]
        else:
            lowest_keyshop = "Not mentioned"
        lowest_url = lowest[2]

        fields = [
            Field(name="Name", value=game_name, inline=True),
            Field(name="Lowest retail price", value=lowest_retail),
            Field(name="Lowest keyshop price", value=lowest_keyshop),
            Field(name="GG Deals link", value=lowest_url, inline=True),
        ]
        e = eg.custom_embed(
            title="Lowest price 🤑",
            image=game.image,
            color=discord.Color.green(),
            fields=fields,
        )
        await interaction.response.send_message(embed=e)

    class HelpView(discord.ui.View):
        def __init__(self, pages, timeout=180):
            super().__init__(timeout=timeout)
            self.pages = pages
            self.page = 0
            self.max_page = 2
            self._update_buttons()

        def _update_buttons(self):
            self.button_list_next.disabled = self.page + 1 == self.max_page
            self.button_list_prev.disabled = self.page == 0

        @discord.ui.button(label="Previous", style=discord.ButtonStyle.red, emoji="⬅️")
        async def button_list_prev(
            self, interaction: discord.Interaction, button: discord.ui.Button
        ):
            if self.page > 0:
                self.page -= 1
                self._update_buttons()
                await interaction.response.edit_message(embed=self.pages[0], view=self)

        @discord.ui.button(label="Next", style=discord.ButtonStyle.green, emoji="➡️")
        async def button_list_next(
            self, interaction: discord.Interaction, button: discord.ui.Button
        ):
            if self.page + 1 < self.max_page:
                self.page += 1
                self._update_buttons()
                await interaction.response.edit_message(embed=self.pages[1], view=self)

    @tree.command(name="help", description="All commands with their descriptions")
    async def help(interaction: discord.Interaction):
        commands_field_1 = f"""1. `/subscribe` - gives you a role that bot uses to alert users about sales and releases of games. For this feature to work, admin must create a role named **\"{ALERT_ROLE}\"** and put it under **\"Bros Gaming Bot\"** role.
        \n1. `/add_link [link]` - command to add a game to the list by a link from platform with games. Available platforms: Steam. 
        * `link` - link to the game from available platform
        \n1. `/delete_game [game_name]` - delete a game from the list by a name. This command give you a list of all previously added games.
        * `game_name` - name of the game to delete
        \n1. `/list_games` - lists previously added games (10 per page), sorted by date added.
        \n1. `/get_random` - gives you a random game from the list of already released games.
        \n1. `/get_details [game_name]` - gives you details about provided game.
        * `game_name` - name of the game
        """
        commands_field_2 = f"""7. `/set_alert_channel [channel]` - sets a channel in which bot will send alerts about sales and releases. If this server has **\"{ALERT_ROLE}\"** role, bot will ping it. (look `/subscribe` description)
        * `channel` - channel from the server that is visible for **Bros Gaming Bot**
        \n7. `/set_currency [cc]` - sets the currency in which game prices will be displayed. Available currencies: USD, EUR, GBP, PLN, JPY, CNY, KRW, INR, BRL, RUB, CAD, AUD, MXN, CHF, NOK, HKD, SGD, THB, IDR, PHP, MYR, VND, ZAR, UAH, ILS. (default is USD)
        * `cc` - currency code (default is US)
        \n7. `/lowest_price [game_name]` - gives you the lowest prices (retail and keyshop) from [GG.deals](https://gg.deals) of the given game from the list of previously added games.
        * `game_name` - name of the game"""
        pages = [
            eg.custom_embed(
                title="Help 💡",
                description="This bot store all your gaming ideas in one place",
                color=discord.Color.dark_teal(),
                fields=[Field(name="Commands", value=commands_field_1)],
            ),
            eg.custom_embed(
                title="Help 💡",
                description="This bot store all your gaming ideas in one place",
                color=discord.Color.dark_teal(),
                fields=[Field(name="Commands", value=commands_field_2)],
            ),
        ]
        view = HelpView(pages=pages)
        await interaction.response.send_message(
            embed=pages[0], view=view, ephemeral=True
        )
