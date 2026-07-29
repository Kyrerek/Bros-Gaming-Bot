# Bros Gaming Bot
Discord bot to list and track games. Created for small friend group servers but it should also work on bigger ones.
## Commands
1. `/help` - list of all commands and descriptions for them
1. `/subscribe` - gives you a role that bot uses to alert users about sales and releases of games. For this feature to work, admin must create a role named like `alert_role` from [config.ini](config.ini) and put it under **\"Bros Gaming Bot\"** role.
1. `/add_link [link]` - command to add a game to the list by a link from platform with games. Available platforms: Steam. 
    * `link` - link to the game from available platform
1. `/delete_game [game_name]` - delete a game from the list by a name.
    * `game_name` - name of the game to delete
1. `/list_games` - lists previously added games (10 per page), sorted by date added.
1. `/get_random` - gives you a random game from the list of already released games.
1. `/get_details [game_name]` - gives you details about provided game.
    * `game_name` - name of the game
1. `/set_alert_channel [channel]` - sets a channel in which bot will send alerts about sales and releases. If your server has `alert_role` role from [config.ini](config.ini), bot will ping it. (look `/subscribe` description)
    * `channel` - channel from the server that is visible for **Bros Gaming Bot**
1. `/set_currency [cc]` - sets the currency in which game prices will be displayed. Available currencies: USD, EUR, GBP, PLN, JPY, CNY, KRW, INR, BRL, RUB, CAD, AUD, MXN, CHF, NOK, HKD, SGD, THB, IDR, PHP, MYR, VND, ZAR, UAH, ILS. (default is USD)
    * `cc` - currency code (default is US)
1. `/lowest_price [game_name]` - gives you the lowest prices (retail and keyshop) from [GG.deals](https://gg.deals) of the given game from the list of previously added games.
    * `game_name` - name of the game
## Local setup
1. Make sure you have [Python 3.14+](https://www.python.org/downloads/) and [uv](https://docs.astral.sh/uv/getting-started/installation/) installed
1. Clone this project into your code editor or just download it
    ```bash
    git clone https://github.com/Kyrerek/Bros-Gaming-Bot.git
    cd Bros-Gaming-Bot
    ```
1. Create a new application on the [Discord Developer Portal](https://discord.com/developers/applications), then:
    - go to the **Bot** tab, click **Reset Token** to get your bot token, and enable it
    - invite the bot to your server using the OAuth2 URL Generator with `bot` and `applications.commands` scopes, and at least the **Manage Roles**, **Send Messages**, and **Use Slash Commands** permissions
1. Create a Postgres database (e.g. via [Supabase](https://supabase.com/)) and run the SQL from the [Database structure](#database-structure) section below in its SQL editor
1. Create an account on [GG.deals](https://gg.deals) to get an API token for the lowest-price feature
1. Create a `.env` file in the project root with:
    - DISCORD_TOKEN=your_discord_bot_token
    - DATABASE_URL=your_postgres_connection_string
    - GG_DEALS_TOKEN=your_gg_deals_token
1. Install dependencies and run the bot
    ```bash
    uv sync
    uv run main.py
    ```
## Database structure
```sql
create table public.servers (
  server_id bigint not null,
  server_name text not null,
  alert_channel_id bigint null,
  game_currency text not null default 'US'::text,
  constraint servers_pkey primary key (server_id)
) TABLESPACE pg_default;

create table public.games (
  game_index serial not null,
  server_index bigint not null,
  name text not null,
  link text not null,
  date timestamp with time zone not null,
  store_id bigint not null,
  platform text not null,
  last_price integer null,
  not_out boolean not null default true,
  constraint games_pkey primary key (game_index),
  constraint games_server_index_store_id_key unique (server_index, store_id),
  constraint games_server_index_fkey foreign KEY (server_index) references servers (server_id)
) TABLESPACE pg_default;
```
## Ideas
1. **More stores with games** - e.g. epic games, gog, ubisoft store etc.