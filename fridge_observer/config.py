"""Application configuration loaded from the database settings table."""
from dataclasses import dataclass, field
from fridge_observer.db import get_db


@dataclass
class Settings:
    spoilage_threshold_fruits: int = 3
    spoilage_threshold_vegetables: int = 2
    spoilage_threshold_dairy: int = 3
    spoilage_threshold_beverages: int = 5
    spoilage_threshold_meat: int = 1
    spoilage_threshold_packaged_goods: int = 7
    temp_threshold_fridge: float = 8.0
    temp_threshold_freezer: float = -15.0
    shopping_list_enabled: bool = True
    echo_dot_enabled: bool = True
    gamification_enabled: bool = False
    shopping_list_webhook_url: str = ""

    def get_spoilage_threshold(self, category: str) -> int:
        """Return the spoilage threshold for a given food category."""
        attr = f"spoilage_threshold_{category}"
        return getattr(self, attr, 3)


# Global settings instance
_settings: Settings = Settings()


def get_settings() -> Settings:
    """Return the current settings instance."""
    return _settings


async def reload() -> None:
    """Reload settings from the database."""
    global _settings
    async with get_db() as db:
        cursor = await db.execute("SELECT key, value FROM settings")
        rows = await cursor.fetchall()
        data: dict[str, str] = {row["key"]: row["value"] for row in rows}

    new_settings = Settings(
        spoilage_threshold_fruits=int(data.get("spoilage_threshold_fruits", "3")),
        spoilage_threshold_vegetables=int(data.get("spoilage_threshold_vegetables", "2")),
        spoilage_threshold_dairy=int(data.get("spoilage_threshold_dairy", "3")),
        spoilage_threshold_beverages=int(data.get("spoilage_threshold_beverages", "5")),
        spoilage_threshold_meat=int(data.get("spoilage_threshold_meat", "1")),
        spoilage_threshold_packaged_goods=int(data.get("spoilage_threshold_packaged_goods", "7")),
        temp_threshold_fridge=float(data.get("temp_threshold_fridge", "8.0")),
        temp_threshold_freezer=float(data.get("temp_threshold_freezer", "-15.0")),
        shopping_list_enabled=data.get("shopping_list_enabled", "true").lower() == "true",
        echo_dot_enabled=data.get("echo_dot_enabled", "true").lower() == "true",
        gamification_enabled=data.get("gamification_enabled", "false").lower() == "true",
        shopping_list_webhook_url=data.get("shopping_list_webhook_url", ""),
    )
    _settings = new_settings
