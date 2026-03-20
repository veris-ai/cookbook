from pydantic import Field
from agents import function_tool, RunContextWrapper

from ..db import BCSAPI, CardStatus, CardReplacementStatus, Card, User
from ..session_manager import BCSRunContext
api = BCSAPI()

@function_tool
def display_user_info(ctx: RunContextWrapper[BCSRunContext], user_id: str = Field(..., description="The user's ID")) -> User:
    """Display a user's information."""
    user = api.get_user_info(user_id)
    user_info = user.model_dump() if user else {}
    return user_info


@function_tool
def display_card_info_by_last4(ctx: RunContextWrapper[BCSRunContext], last4: str = Field(..., description="The card's last4")) -> Card:
    """Display a card's information."""
    card = api.find_card_by_last4(last4)
    card_info = card.model_dump() if card else {}
    return card_info

@function_tool
def display_card_info(ctx: RunContextWrapper[BCSRunContext], card_id: str = Field(..., description="The card's ID")) -> Card:
    """Display a card's information."""
    card = api.get_card_info(card_id)
    card_info = card.model_dump() if card else {}
    return card_info

@function_tool
def change_card_status(
    ctx: RunContextWrapper[BCSRunContext],
    card_id: str = Field(..., description="The card's ID"),
    new_status: CardStatus = Field(..., description="The card's new status")) -> Card:
    """Change a card's status."""
    card = api.update_card_status(card_id, new_status)
    return card

@function_tool
def request_card_replacement(ctx: RunContextWrapper[BCSRunContext], card_id: str = Field(..., description="The card's ID")) -> Card:
    """Request a card replacement."""
    card = api.request_card_replacement(card_id)
    return card

@function_tool
def update_card_replacement_status(ctx: RunContextWrapper[BCSRunContext], card_id: str = Field(..., description="The card's ID"), new_status: CardReplacementStatus = Field(..., description="The card's new status")) -> str:
    """Update a card replacement status."""
    card = api.update_card_replacement_status(card_id, new_status)
    return card