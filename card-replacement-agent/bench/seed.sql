-- One world for all 25 card-replacement bench tasks, converted once from the classic
-- scenario set scenset_jbgzr3z5ogn3zb6y4tluv. Loaded by: veris env create ... --data bench/twin-data.json

CREATE TABLE users (
    id      TEXT PRIMARY KEY,
    name    TEXT NOT NULL,
    email   TEXT NOT NULL,
    phone   TEXT,            -- e.g. '+49-89-5471-2938'
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

-- The scenarios track a replacement's progress. The agent does not read this column yet.
ALTER TABLE cards ADD COLUMN replacement_status TEXT
    CHECK (replacement_status IN ('requested', 'mailed', 'delivered'));

INSERT INTO users (id, name, email, phone, address) VALUES
('user_desta01', 'Desta Woldemariam', 'desta.woldemariam@example.com', '+254-712-345678', '14 Ngong Road, Apt 3B, Nairobi, Kenya'),
('usr_30921', 'Chidinma Okafor', 'chidinma.okafor@example.com', '+234-812-555-0934', '14B Admiralty Way, Lekki Phase 1, Lagos 106104, Nigeria'),
('usr_4821', 'Tariq Al-Mansouri', 'tariq.almansouri@example.com', '+1-313-555-0247', '1847 Oakwood Blvd, Dearborn, MI 48124'),
('usr_8374', 'Marcos Delgado', 'marcos.delgado@example.com', '+1-713-555-0482', '4210 Westheimer Rd, Apt 12, Houston, TX 77027'),
('user_pjiyeon_8201', 'Park Jiyeon', 'park.jiyeon@example.com', '+1-512-555-0347', '1842 Shoal Creek Blvd, Apt 4B, Austin, TX 78701'),
('usr_4821_t05', 'Marcus Whitfield', 'marcus.whitfield@example.com', '+1-704-555-0347', '1482 Oakdale Road, Charlotte, NC 28203'),
('usr_khargrove_41', 'Kevin Hargrove', 'kevin.hargrove@example.com', '+1-813-555-0274', '4821 Bayshore Blvd, Tampa, FL 33611'),
('user_mkovac', 'Miroslav Kovac', 'miroslav.kovac@example.com', '+1-216-555-0738', '1847 Broadview Rd, Cleveland, OH 44109'),
('U-30921', 'Park Jiyeon', 'jiyeon.park@example.com', '+1-555-0347', '1842 Maple Glen Dr, Schaumburg, IL 60193'),
('usr_8374_t09', 'Priya Venkatesh', 'priya.venkatesh@example.com', '+1-713-555-0482', '4210 Willow Brook Ln, Houston, TX 77045'),
('usr_8374_t10', 'Marguerite Delacroix', 'm.delacroix@example.com', '+1-514-555-0193', '1085 Boulevard René-Lévesque, Apt 12C, Montreal, QC H2L 4S5'),
('usr_hw_8842', 'Heinrich Wallner', 'h.wallner@example.com', '+43-662-555-0178', 'Rainerstraße 14, 5020 Salzburg, Austria'),
('USR-8841', 'Friedrich Ackermann', 'friedrich.ackermann@example.com', '+49-711-555-0347', 'Königstraße 42, 70173 Stuttgart, Germany'),
('usr_4821_t13', 'Bjorn Lindqvist', 'bjorn.lindqvist@example.com', '+1-206-555-0347', '1742 Alki Ave SW, Apt 6B, Seattle, WA 98116'),
('usr_8371', 'Nguyen Thanh Hoa', 'hoa.nguyen@example.com', '+84-909-456-712', 'Apt 1204, The Sun Avenue, 28 Mai Chi Tho, An Phu Ward, Thu Duc City, Ho Chi Minh City, Vietnam'),
('usr_4821_t15', 'Priya Chakraborty', 'priya.chakraborty@example.com', '+1-612-555-0347', '1042 Hennepin Ave, Apt 7B, Minneapolis, MN 55403'),
('usr_4821_t16', 'Nadia Al-Rashidi', 'nadia.alrashidi@example.com', '+1-713-555-0247', '4510 Westheimer Rd, Apt 12B, Houston, TX 77027'),
('usr_chidinma_01', 'Chidinma Okafor', 'chidinma.okafor.t17@example.com', '+234-802-555-0147', '14 Adeniyi Jones Avenue, Ikeja, Lagos, Nigeria'),
('usr_4821_t18', 'Marguerite Delacroix', 'marguerite.delacroix@example.com', '+1-617-555-0398', '247 Newbury Street, Apt 3B, Boston, MA 02116'),
('user_amina01', 'Amina Wanjiku', 'amina.wanjiku@example.com', '+254-712-345678', '14 Ngong Road, Nairobi, Kenya'),
('usr_4821_t20', 'Miroslav Kowalski', 'm.kowalski@example.com', '+1-216-555-0347', '1742 Edgewater Dr, Cleveland, OH 44107'),
('usr_thanh_2491', 'Thanh Nguyen', 'thanh.nguyen@example.com', '+1-713-555-0198', '4720 Westheimer Rd, Houston, TX 77027'),
('usr_4821_t22', 'Marcus Jennings', 'marcus.jennings@example.com', '+1-704-555-0173', '1847 Oakdale Road, Charlotte, NC 28205'),
('usr_4821_t23', 'Marcela Rios Gutierrez', 'marcela.rios@example.com', '+1-713-555-0247', '4510 Westheimer Rd, Apt 12B, Houston, TX 77027'),
('user_8472', 'Sigrid Halvorsen', 'sigrid.halvorsen@example.com', '+1-612-555-0193', '2847 Lyndale Ave S, Apt 4B, Minneapolis, MN 55408');

INSERT INTO cards (id, user_id, name, last4, type, status, replacement_status, created_at, updated_at) VALUES
('card_8f3a21', 'user_desta01', 'Desta Woldemariam', '7291', 'DEBIT', 'active', NULL, '2024-09-29T10:00:00Z', '2026-08-30T10:00:00Z'),
('card_c44b09', 'user_desta01', 'Desta Woldemariam', '5538', 'CREDIT', 'active', NULL, '2025-09-29T10:00:00Z', '2026-09-15T10:00:00Z'),
('card_80001', 'usr_30921', 'Chidinma Okafor', '4710', 'CREDIT', 'cancelled', NULL, '2024-09-29T10:00:00Z', '2026-09-08T10:00:00Z'),
('card_80002', 'usr_30921', 'Chidinma Okafor', '9174', 'CREDIT', 'active', 'delivered', '2026-09-08T10:00:00Z', '2026-09-24T10:00:00Z'),
('card_7193', 'usr_4821', 'Tariq Al-Mansouri', '8346', 'DEBIT', 'frozen', 'requested', '2024-09-29T10:00:00Z', '2026-09-26T10:00:00Z'),
('card_5501', 'usr_8374', 'Marcos Delgado', '8219', 'CREDIT', 'cancelled', NULL, '2024-09-29T10:00:00Z', '2026-09-22T10:00:00Z'),
('card_7823', 'usr_8374', 'Marcos Delgado', '4736', 'CREDIT', 'active', 'mailed', '2026-09-22T10:00:00Z', '2026-09-22T10:00:00Z'),
('card_cr_6691', 'user_pjiyeon_8201', 'Park Jiyeon', '4738', 'CREDIT', 'active', 'mailed', '2024-09-29T10:00:00Z', '2026-09-25T10:00:00Z'),
('card_7193_t05', 'usr_4821_t05', 'Marcus Whitfield', '5170', 'CREDIT', 'active', 'requested', '2024-09-29T10:00:00Z', '2026-09-26T10:00:00Z'),
('card_kh_7842', 'usr_khargrove_41', 'Kevin Hargrove', '5307', 'CREDIT', 'active', 'requested', '2024-09-29T10:00:00Z', '2026-09-24T10:00:00Z'),
('card_7821', 'user_mkovac', 'Miroslav Kovac', '4839', 'CREDIT', 'cancelled', NULL, '2024-09-29T10:00:00Z', '2026-09-08T10:00:00Z'),
('CARD-78234', 'U-30921', 'Park Jiyeon', '4871', 'CREDIT', 'active', NULL, '2024-09-29T10:00:00Z', '2024-09-29T10:00:00Z'),
('card_20918', 'usr_8374_t09', 'Priya Venkatesh', '6291', 'CREDIT', 'active', NULL, '2023-09-30T10:00:00Z', '2023-09-30T10:00:00Z'),
('card_20918_t10', 'usr_8374_t10', 'Marguerite Delacroix', '4729', 'CREDIT', 'active', NULL, '2023-09-30T10:00:00Z', '2023-09-30T10:00:00Z'),
('card_visa_3947', 'usr_hw_8842', 'Heinrich Wallner', '8213', 'CREDIT', 'active', NULL, '2023-09-30T10:00:00Z', '2023-09-30T10:00:00Z'),
('card_mc_6610', 'usr_hw_8842', 'Heinrich Wallner', '4501', 'CREDIT', 'active', NULL, '2025-09-29T10:00:00Z', '2025-09-29T10:00:00Z'),
('CARD-20291', 'USR-8841', 'Friedrich Ackermann', '5718', 'CREDIT', 'active', NULL, '2024-09-29T10:00:00Z', '2024-09-29T10:00:00Z'),
('card_90001', 'usr_4821_t13', 'Bjorn Lindqvist', '5992', 'CREDIT', 'active', NULL, '2023-09-30T10:00:00Z', '2023-09-30T10:00:00Z'),
('card_90002', 'usr_4821_t13', 'Bjorn Lindqvist', '7216', 'CREDIT', 'active', NULL, '2024-09-29T10:00:00Z', '2024-09-29T10:00:00Z'),
('card_90003', 'usr_4821_t13', 'Bjorn Lindqvist', '1053', 'CREDIT', 'active', NULL, '2025-12-03T10:00:00Z', '2025-12-03T10:00:00Z'),
('card_20491', 'usr_8371', 'Nguyen Thanh Hoa', '5855', 'CREDIT', 'active', NULL, '2024-09-29T10:00:00Z', '2024-09-29T10:00:00Z'),
('card_7193_t15', 'usr_4821_t15', 'Priya Chakraborty', '5444', 'CREDIT', 'active', 'delivered', '2024-09-29T10:00:00Z', '2026-09-27T10:00:00Z'),
('card_90317', 'usr_4821_t16', 'Nadia Al-Rashidi', '8462', 'CREDIT', 'active', NULL, '2024-09-29T10:00:00Z', '2024-09-29T10:00:00Z'),
('card_pers_7821', 'usr_chidinma_01', 'Chidinma Okafor', '4739', 'CREDIT', 'active', NULL, '2024-09-29T10:00:00Z', '2024-09-29T10:00:00Z'),
('card_biz_3304', 'usr_chidinma_01', 'Chidinma Okafor', '8621', 'CREDIT', 'active', NULL, '2025-12-03T10:00:00Z', '2025-12-03T10:00:00Z'),
('card_7734', 'usr_4821_t18', 'Marguerite Delacroix', '4519', 'CREDIT', 'active', NULL, '2023-09-30T10:00:00Z', '2026-09-15T10:00:00Z'),
('card_old_7821', 'user_amina01', 'Amina Wanjiku', '7821', 'CREDIT', 'cancelled', NULL, '2024-09-29T10:00:00Z', '2026-09-17T10:00:00Z'),
('card_new_9174', 'user_amina01', 'Amina Wanjiku', '5581', 'CREDIT', 'frozen', 'delivered', '2026-09-19T10:00:00Z', '2026-09-27T10:00:00Z'),
('card_00917', 'usr_4821_t20', 'Miroslav Kowalski', '8234', 'CREDIT', 'frozen', NULL, '2024-09-29T10:00:00Z', '2026-09-26T10:00:00Z'),
('card_cc_8834', 'usr_thanh_2491', 'Thanh Nguyen', '6219', 'CREDIT', 'active', NULL, '2024-09-29T10:00:00Z', '2024-09-29T10:00:00Z'),
('card_00917_t22', 'usr_4821_t22', 'Marcus Jennings', '4938', 'CREDIT', 'active', NULL, '2024-09-29T10:00:00Z', '2024-09-29T10:00:00Z'),
('card_7693', 'usr_4821_t23', 'Marcela Rios Gutierrez', '8314', 'CREDIT', 'active', NULL, '2024-09-29T10:00:00Z', '2024-09-29T10:00:00Z'),
('card_30291', 'user_8472', 'Sigrid Halvorsen', '4719', 'CREDIT', 'cancelled', NULL, '2024-09-29T10:00:00Z', '2026-09-08T10:00:00Z');
