CREATE TABLE users (
    id      TEXT PRIMARY KEY,
    name    TEXT NOT NULL,
    email   TEXT NOT NULL,
    phone   TEXT,            -- e.g. '+1-555-0101'
    address TEXT             -- full mailing address for card delivery
);

COMMENT ON TABLE users IS 'Bank customers who may hold one or more cards.';

CREATE TABLE cards (
    id         TEXT PRIMARY KEY,
    user_id    TEXT NOT NULL REFERENCES users(id),
    name       TEXT NOT NULL,                          -- cardholder name
    last4      TEXT NOT NULL,                          -- last 4 digits of card number
    type       TEXT NOT NULL CHECK (type   IN ('DEBIT', 'CREDIT', 'virtual')),
    status     TEXT NOT NULL DEFAULT 'active'
                             CHECK (status IN ('active', 'cancelled', 'frozen')),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

COMMENT ON TABLE cards IS 'Payment cards belonging to users. Status transitions: active → frozen → cancelled. A frozen card can be unfrozen back to active.';
COMMENT ON COLUMN cards.type   IS 'Card type: DEBIT, CREDIT, or virtual.';
COMMENT ON COLUMN cards.status IS 'Card status: active, cancelled, or frozen.';

CREATE INDEX idx_cards_user_id ON cards(user_id);
CREATE INDEX idx_cards_last4   ON cards(last4);
