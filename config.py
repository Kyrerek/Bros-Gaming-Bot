from configparser import ConfigParser
import os.path

if not os.path.isfile("config.ini"):
    raise FileNotFoundError("Config file does not exist! Create one first")
_cfg = ConfigParser()
_cfg.read("config.ini")

ALERT_ROLE = _cfg.get("role", "alert_role", fallback="Gamer")