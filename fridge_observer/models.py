"""Pydantic models and enums for the Fridge Observer API."""
from __future__ import annotations

from datetime import date, datetime
from enum import Enum
from typing import Literal, TypedDict

from pydantic import BaseModel, model_validator


class FoodCategory(str, Enum):
    fruits = "fruits"
    vegetables = "vegetables"
    dairy = "dairy"
    beverages = "beverages"
    meat = "meat"
    packaged_goods = "packaged_goods"


class FoodItem(BaseModel):
    id: int
    name: str
    category: FoodCategory
    quantity: int
    expiry_date: date | None
    expiry_source: Literal["estimated", "manual"]
    added_at: datetime
    thumbnail: str | None = None
    notes: str | None = None
    days_until_expiry: int | None = None
    expiry_status: Literal["ok", "warning", "expired"] = "ok"

    # Spoilage threshold used for computing expiry_status (injected at query time)
    _spoilage_threshold: int = 3

    @model_validator(mode="after")
    def compute_expiry_fields(self) -> "FoodItem":
        if self.expiry_date is None:
            self.days_until_expiry = None
            self.expiry_status = "ok"
            return self

        today = date.today()
        delta = (self.expiry_date - today).days
        self.days_until_expiry = delta

        threshold = getattr(self, "_spoilage_threshold", 3)

        if delta <= 0:
            self.expiry_status = "expired"
        elif delta <= threshold:
            self.expiry_status = "warning"
        else:
            self.expiry_status = "ok"

        return self

    @classmethod
    def with_threshold(cls, data: dict, threshold: int) -> "FoodItem":
        """Create a FoodItem and compute expiry_status using the given threshold."""
        item = cls(**data)
        if item.expiry_date is not None:
            today = date.today()
            delta = (item.expiry_date - today).days
            item.days_until_expiry = delta
            if delta <= 0:
                item.expiry_status = "expired"
            elif delta <= threshold:
                item.expiry_status = "warning"
            else:
                item.expiry_status = "ok"
        return item


class FoodItemCreate(BaseModel):
    name: str
    category: FoodCategory
    quantity: int = 1
    expiry_date: date | None = None
    expiry_source: Literal["estimated", "manual"] = "estimated"
    notes: str | None = None


class FoodItemUpdate(BaseModel):
    name: str | None = None
    quantity: int | None = None
    expiry_date: date | None = None
    expiry_source: Literal["estimated", "manual"] | None = None
    notes: str | None = None


class RecipeIngredient(BaseModel):
    id: int
    recipe_id: int
    name: str
    category: str | None = None
    is_pantry_staple: bool = False


class Recipe(BaseModel):
    id: int
    name: str
    description: str | None = None
    cuisine: str | None = None
    dietary_tags: list[str] = []
    prep_minutes: int | None = None
    instructions: str
    image_url: str | None = None
    ingredients: list[RecipeIngredient] = []
    is_favorite: bool = False


class ScoredRecipe(BaseModel):
    recipe: Recipe
    urgency_score: float
    matching_expiring_items: list[str] = []


class ActivityLogEntry(BaseModel):
    id: int
    item_id: int | None
    item_name: str
    action: Literal["added", "removed", "updated", "expired"]
    source: Literal["automatic", "manual"]
    occurred_at: datetime


class TemperatureReading(BaseModel):
    id: int
    compartment: Literal["fridge", "freezer"]
    value_celsius: float
    recorded_at: datetime


# WebSocket message types
class InventoryUpdateMessage(TypedDict):
    type: Literal["inventory_update"]
    payload: list[dict]


class NotificationMessage(TypedDict):
    type: Literal["notification"]
    payload: dict  # {"level": "warning|info", "message": "..."}


class TemperatureUpdateMessage(TypedDict):
    type: Literal["temperature_update"]
    payload: dict  # {"fridge": float, "freezer": float}


class ConnectionStatusMessage(TypedDict):
    type: Literal["connection_status"]
    payload: dict  # {"status": "connected"}


class PingMessage(TypedDict):
    type: Literal["ping"]
