from pydantic import Field
from agents import function_tool, RunContextWrapper

from ..db import BCSAPI, CardStatus, CardReplacementStatus, Card, User
from ..session_manager import BCSRunContext

api = BCSAPI()

@function_tool
def display_user_info(ctx: RunContextWrapper[BCSRunContext], user_id: str = Field(..., description="The user's ID")) -> User | dict:
    """Retrieve comprehensive user account information.

    Input:
        user_id: The unique identifier for the user account

    Output:
        Dictionary containing user information:
        - id: User's unique identifier
        - name: Full name (always present)
        - email: Email address (always present)
        - phone: Contact phone number (optional, may be None)
        - address: Delivery/mailing address (optional, may be None)
        - cards: List of card IDs associated with this user

        Returns empty dict {} if user not found.

    Use this when you need to verify user identity, confirm delivery address,
    check contact information, or list all cards belonging to a user.
    """
    user = api.get_user_info(user_id)
    user_info = user.model_dump() if user else {}
    return user_info


@function_tool
def display_card_info_by_last4(ctx: RunContextWrapper[BCSRunContext], last4: str = Field(..., description="The card's last4")) -> Card | dict:
    """Retrieve card information using the last 4 digits of the card number.

    Input:
        last4: The last 4 digits of the card number (e.g., "1234")

    Output:
        Dictionary containing card information:
        - id: Card's unique identifier (e.g., "c_12345678")
        - user_id: ID of the card owner
        - name: Card nickname or descriptive label
        - last4: Last 4 digits of card number
        - type: Card type - "DEBIT", "CREDIT", or "virtual"
        - status: Current status - "active", "frozen", or "cancelled" (lowercase)
        - created_at: Card creation timestamp (ISO 8601 format)
        - updated_at: Last modification timestamp (ISO 8601 format)

        Returns empty dict {} if card not found.

    Use this when the user refers to their card by the last 4 digits rather than the card ID.
    This is the most user-friendly way to identify a specific card.
    """
    card = api.find_card_by_last4(last4)
    card_info = card.model_dump() if card else {}
    return card_info

@function_tool
def display_card_info(ctx: RunContextWrapper[BCSRunContext], card_id: str = Field(..., description="The card's ID")) -> Card | dict:
    """Retrieve card information using the card's unique identifier.

    Input:
        card_id: The card's unique identifier (e.g., "c_12345678")

    Output:
        Dictionary containing card information:
        - id: Card's unique identifier
        - user_id: ID of the card owner
        - name: Card nickname or descriptive label
        - last4: Last 4 digits of card number
        - type: Card type - "DEBIT", "CREDIT", or "virtual"
        - status: Current status - "active", "frozen", or "cancelled" (lowercase)
        - created_at: Card creation timestamp (ISO 8601 format)
        - updated_at: Last modification timestamp (ISO 8601 format)

        Returns empty dict {} if card not found.

    Use this when you already have the card ID from previous operations or from
    the user's card list. Prefer display_card_info_by_last4 when interacting with users.
    """
    card = api.get_card_info(card_id)
    card_info = card.model_dump() if card else {}
    return card_info

@function_tool
def change_card_status(
    ctx: RunContextWrapper[BCSRunContext],
    card_id: str = Field(..., description="The card's ID"),
    new_status: CardStatus = Field(..., description="The card's new status")) -> Card:
    """Update a card's status to active, frozen, or cancelled.

    Input:
        card_id: The card's unique identifier
        new_status: The desired status - CardStatus.ACTIVE, CardStatus.FROZEN, or CardStatus.CANCELLED

    Output:
        Card object (NOT dict) with updated status and timestamp:
        - status: Set to the new status value ("active", "frozen", or "cancelled")
        - updated_at: Updated to current timestamp

    Important Status Rules:
        - "active": Card is operational and can process transactions
        - "frozen": Temporarily blocks transactions, can be changed back to active
        - "cancelled": Permanently deactivates the card
        - A "cancelled" card can only be set to "cancelled" (idempotent)
        - A "cancelled" card CANNOT be changed to "active" or "frozen"
        - Raises ValueError if trying to change cancelled card to non-cancelled status

    Use this to freeze a card (e.g., for lost/stolen cards), activate a replacement card,
    or cancel a card during the replacement process.
    """
    card = api.update_card_status(card_id, new_status)
    return card

@function_tool
def request_card_replacement(ctx: RunContextWrapper[BCSRunContext], card_id: str = Field(..., description="The card's ID")) -> Card:
    """Request a replacement card for a lost, stolen, or damaged card.

    Input:
        card_id: The unique identifier of the card to be replaced

    Output:
        Card object (NOT dict) representing the NEW replacement card:
        - id: New card ID (format: "c_" + 8 random hex chars)
        - last4: New random last 4 digits
        - type: Same card type as the original ("DEBIT", "CREDIT", or "virtual")
        - status: "active" (immediately usable)
        - name: Original name + " (replacement)"
        - user_id: Same user as the original card
        - created_at: Current timestamp
        - updated_at: Current timestamp

    Side Effects (IMPORTANT):
        - The OLD card is automatically set to "cancelled" status
        - The NEW card is automatically added to the user's cards list
        - Cannot replace an already "cancelled" card (raises ValueError)

    Note: If you want to freeze the old card BEFORE replacing (e.g., for lost/stolen),
    you must call change_card_status separately BEFORE calling this function.
    This function does not freeze - it only cancels the old card.
    """
    card = api.request_card_replacement(card_id)
    return card

@function_tool
def update_card_replacement_status(ctx: RunContextWrapper[BCSRunContext], card_id: str = Field(..., description="The card's ID"), new_status: CardReplacementStatus = Field(..., description="The card's new status")) -> str:
    """Update the delivery status of a card replacement request.

    Input:
        card_id: The unique identifier of the replacement card
        new_status: The new delivery status (CardReplacementStatus.REQUESTED, MAILED, or DELIVERED)

    Output:
        Updated card information

    Status Values:
        - "requested": Replacement card has been ordered but not yet shipped
        - "mailed": Replacement card has been shipped and is in transit
        - "delivered": Replacement card has been delivered to the user's address
    """
    card = api.update_card_replacement_status(card_id, new_status)
    return card
