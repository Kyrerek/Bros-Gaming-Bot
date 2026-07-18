import requests
import os
from dotenv import load_dotenv
load_dotenv()
gg_token = os.getenv('GG_DEALS_TOKEN')

class Game:
    title : str
    id : int
    is_free : bool
    desc : str
    image : str
    currency : str
    price : int = None
    price_formatted : str = None
    not_out : bool
    release_date : str = None

    def _get_game_deatils_by_steam(self, id, currency):
        url = f"https://store.steampowered.com/api/appdetails?appids={id}&cc={currency}"
        response = requests.get(url)
        if response.status_code == 200:
            data = response.json()
            data[str(id)]["data"]["short_description"] = data[str(id)]["data"]["short_description"].replace("&quot;", "\"")
            if data[str(id)]["success"]:
                return data[str(id)]["data"]
        return None
    
    def __init__(self, id : int, currency : str):
        data = self._get_game_deatils_by_steam(id, currency)
        if data is None:
            raise NameError(f"{id} is not an existing Steam app id or there is another error with Steam API")
        self.title = data["name"]
        self.id = id
        self.is_free = data["is_free"]
        self.desc = data["short_description"]
        self.image = data["header_image"]
        self.currency = currency
        self.price = 0
        self.price_formatted = "FREE"

        if not self.is_free:
            try:
                self.price = data["price_overview"]["final"]
                self.price_formatted = data["price_overview"]["final_formatted"]
            except Exception:
                self.price_formatted = "Not mentioned"
        
        self.not_out = data["release_date"]["coming_soon"]
        if self.not_out:
            self.release_date = data["release_date"]["date"]

    def lowest_price(self):
        if self.currency.lower() not in ["au", "be", "br", "ca", "ch", "de", "dk", "es", "eu", "fi", "fr", "gb", "ie", "it", "nl", "no", "pl", "se", "us"]:
            raise AttributeError(f"{self.currency} is not supported on gg.deals")
        url = f"https://api.gg.deals/v1/prices/by-steam-app-id/?ids={self.id}&key={gg_token}&region={self.currency.lower()}"
        response = requests.get(url)
        if response.status_code == 200:
            data = response.json()
            if data["success"]:
                game = data["data"][str(self.id)]
                return game["prices"]["currentRetail"], game["prices"]["currentKeyshops"], game["url"], game["prices"]["currency"]
        return None
        