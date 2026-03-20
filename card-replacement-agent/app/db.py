import os
import uuid
from typing import Dict, List, Optional
from datetime import datetime
from enum import Enum

import psycopg2
import psycopg2.extras
from pydantic import BaseModel, Field


########################################################
# Schema (source of truth)
########################################################

class CardType(str, Enum):
    DEBIT = "DEBIT"
    CREDIT = "CREDIT"
    VIRTUAL = "virtual"


class CardStatus(str, Enum):
    ACTIVE = "active"
    CANCELLED = "cancelled"
    FROZEN = "frozen"


class CardReplacementStatus(str, Enum):
    REQUESTED = "requested"
    MAILED = "mailed"
    DELIVERED = "delivered"


class Card(BaseModel):
    id: str
    user_id: str
    name: str
    last4: str
    type: CardType
    status: CardStatus
    created_at: str
    updated_at: str


class User(BaseModel):
    id: str
    name: str
    email: str
    phone: Optional[str] = None
    address: Optional[str] = None
    cards: List[str] = Field(default_factory=list)


########################################################
# PostgreSQL wrapper
########################################################

def _get_dsn() -> str:
    return os.getenv("DATABASE_URL")


def _conn():
    conn = psycopg2.connect(_get_dsn(), cursor_factory=psycopg2.extras.RealDictCursor)
    conn.set_client_encoding('UTF8')
    return conn


def _ts(val) -> str:
    """Convert a datetime/string to ISO string."""
    if hasattr(val, "isoformat"):
        return val.isoformat()
    return str(val)


class Database:
    @staticmethod
    def now_iso() -> str:
        return datetime.utcnow().isoformat() + "Z"

    def get_user_by_id(self, user_id: str) -> Optional[Dict]:
        with _conn() as conn, conn.cursor() as cur:
            cur.execute("SELECT * FROM users WHERE id = %s", (user_id,))
            row = cur.fetchone()
            if not row:
                return None
            user = dict(row)
            cur.execute("SELECT id FROM cards WHERE user_id = %s", (user_id,))
            user["cards"] = [r["id"] for r in cur.fetchall()]
            return user

    def update_user(self, user_id: str, patch: Dict) -> Optional[Dict]:
        allowed = {"name", "email", "phone", "address"}
        updates = {k: v for k, v in patch.items() if k in allowed}
        if not updates:
            return self.get_user_by_id(user_id)
        set_clause = ", ".join(f"{k} = %s" for k in updates)
        values = list(updates.values()) + [user_id]
        with _conn() as conn, conn.cursor() as cur:
            cur.execute(f"UPDATE users SET {set_clause} WHERE id = %s RETURNING *", values)
            row = cur.fetchone()
            if not row:
                return None
            user = dict(row)
            cur.execute("SELECT id FROM cards WHERE user_id = %s", (user_id,))
            user["cards"] = [r["id"] for r in cur.fetchall()]
            return user

    def search_users(self, query_text: str) -> List[Dict]:
        pattern = f"%{query_text.lower().strip()}%"
        with _conn() as conn, conn.cursor() as cur:
            cur.execute(
                "SELECT * FROM users WHERE LOWER(name) LIKE %s OR LOWER(email) LIKE %s",
                (pattern, pattern),
            )
            rows = cur.fetchall()
            results = []
            for row in rows:
                user = dict(row)
                cur.execute("SELECT id FROM cards WHERE user_id = %s", (user["id"],))
                user["cards"] = [r["id"] for r in cur.fetchall()]
                results.append(user)
            return results

    def get_card_by_id(self, card_id: str) -> Optional[Dict]:
        with _conn() as conn, conn.cursor() as cur:
            cur.execute("SELECT * FROM cards WHERE id = %s", (card_id,))
            row = cur.fetchone()
            if not row:
                return None
            card = dict(row)
            card["created_at"] = _ts(card["created_at"])
            card["updated_at"] = _ts(card["updated_at"])
            return card

    def find_card_by_last4(self, last4: str) -> Optional[Dict]:
        with _conn() as conn, conn.cursor() as cur:
            cur.execute("SELECT * FROM cards WHERE last4 = %s LIMIT 1", (last4,))
            row = cur.fetchone()
            if not row:
                return None
            card = dict(row)
            card["created_at"] = _ts(card["created_at"])
            card["updated_at"] = _ts(card["updated_at"])
            return card

    def update_card_status(self, card_id: str, new_status: str) -> Optional[Dict]:
        now = self.now_iso()
        with _conn() as conn, conn.cursor() as cur:
            cur.execute(
                "UPDATE cards SET status = %s, updated_at = %s WHERE id = %s RETURNING *",
                (new_status, now, card_id),
            )
            row = cur.fetchone()
            if not row:
                return None
            card = dict(row)
            card["created_at"] = _ts(card["created_at"])
            card["updated_at"] = _ts(card["updated_at"])
            return card

    def create_card(self, card: Dict) -> Dict:
        with _conn() as conn, conn.cursor() as cur:
            cur.execute(
                """INSERT INTO cards (id, user_id, name, last4, type, status, created_at, updated_at)
                   VALUES (%(id)s, %(user_id)s, %(name)s, %(last4)s, %(type)s, %(status)s, %(created_at)s, %(updated_at)s)
                   RETURNING *""",
                card,
            )
            row = cur.fetchone()
            result = dict(row)
            result["created_at"] = _ts(result["created_at"])
            result["updated_at"] = _ts(result["updated_at"])
            return result

    def add_card_to_user(self, user_id: str, card_id: str) -> None:
        # Cards are linked via user_id FK — no action needed
        pass


########################################################
# API layer (validated facade over Database)
########################################################

class BCSAPI(BaseModel):
    db: Database = Field(default_factory=Database)

    model_config = {"arbitrary_types_allowed": True}

    # User operations
    def search_users(self, search_query: str) -> List[User]:
        docs = self.db.search_users(search_query)
        return [User(**doc) for doc in docs]

    def get_user_info(self, user_id: str) -> User:
        doc = self.db.get_user_by_id(user_id)
        return User(**doc) if doc else None

    def update_user_info(self, user_id: str, user_patch: Dict) -> User:
        if not isinstance(user_patch, dict):
            raise ValueError("user_patch must be an object")
        updated = self.db.update_user(user_id, user_patch)
        if updated is None:
            raise ValueError("user not found")
        return User(**updated)

    # Card operations
    def find_card_by_last4(self, last4: str) -> Card:
        doc = self.db.find_card_by_last4(last4)
        return Card(**doc) if doc else None

    def get_card_info(self, card_id: str) -> Card:
        doc = self.db.get_card_by_id(card_id)
        return Card(**doc) if doc else None

    def update_card_status(self, card_id: str, new_status: CardStatus) -> Card:
        current = self.db.get_card_by_id(card_id)
        if not current:
            raise ValueError("card not found")
        if current.get("status") == CardStatus.CANCELLED and new_status != CardStatus.CANCELLED:
            raise ValueError("cannot change status of a cancelled card")
        updated = self.db.update_card_status(card_id, new_status)
        if updated is None:
            raise ValueError("card not found")
        return Card(**updated)

    def request_card_replacement(self, card_id: str) -> Card:
        old = self.db.get_card_by_id(card_id)
        if not old:
            raise ValueError("card not found")
        if old.get("status") == "cancelled":
            raise ValueError("cannot replace an already cancelled card")

        self.update_card_status(card_id, CardStatus.CANCELLED)

        now = datetime.utcnow().isoformat() + "Z"
        new_id = f"c_{uuid.uuid4().hex[:8]}"
        new_last4 = f"{uuid.uuid4().int % 10000:04d}"
        successor = Card(
            id=new_id,
            user_id=old["user_id"],
            name=f"{old['name']} (replacement)",
            last4=new_last4,
            type=old["type"],
            status=CardStatus.ACTIVE,
            created_at=now,
            updated_at=now,
        )

        self.db.create_card(successor.model_dump())
        return successor
