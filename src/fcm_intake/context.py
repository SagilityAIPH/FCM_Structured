from dataclasses import dataclass

@dataclass
class BotContext:
    cms_username: str = ""
    cms_password: str = ""
