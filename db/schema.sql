-- =====================================================================
--  Partage de dépenses : schéma SQLite  (SQLite >= 3.25 requis : fonctions de fenêtrage)
--  Les montants sont stockés en CENTIMES (INTEGER) => aucun arrondi flottant.
--  Les dates sont au format ISO 'YYYY-MM-DD'.
-- =====================================================================
PRAGMA foreign_keys = ON;   -- à exécuter à CHAQUE connexion

-- "Group" est un mot réservé en SQL : on le met entre guillemets.
CREATE TABLE "Group" (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    name       TEXT NOT NULL CHECK (length(trim(name)) > 0),
    start_date TEXT NOT NULL CHECK (date(start_date) = start_date),
    end_date   TEXT NOT NULL CHECK (date(end_date)   = end_date),
    CHECK (end_date >= start_date)
);

CREATE TABLE Person (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    name          TEXT NOT NULL CHECK (length(trim(name)) > 0),
    password_hash TEXT DEFAULT NULL
);

CREATE TABLE Member (
    id        INTEGER PRIMARY KEY AUTOINCREMENT,
    person_id INTEGER NOT NULL REFERENCES Person(id)  ON DELETE RESTRICT,
    group_id  INTEGER NOT NULL REFERENCES "Group"(id) ON DELETE CASCADE,
    UNIQUE (person_id, group_id)          -- une personne n'est membre qu'une fois d'un groupe
);

CREATE TABLE Expense (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    label        TEXT    NOT NULL CHECK (length(trim(label)) > 0),
    -- nombre entier de centimes, strictement positif
    amount_cents INTEGER NOT NULL CHECK (typeof(amount_cents) = 'integer' AND amount_cents > 0),
    date         TEXT    NOT NULL CHECK (date(date) = date),
    person_id    INTEGER NOT NULL REFERENCES Person(id),        -- le payeur
    group_id     INTEGER NOT NULL REFERENCES "Group"(id) ON DELETE CASCADE,
    -- le payeur doit être membre DU groupe de la dépense :
    FOREIGN KEY (person_id, group_id) REFERENCES Member(person_id, group_id)
);

CREATE TABLE ExpenseParticipant (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,   -- l'ordre des id = ordre d'ajout
    member_id  INTEGER NOT NULL REFERENCES Member(id)  ON DELETE RESTRICT,
    expense_id INTEGER NOT NULL REFERENCES Expense(id) ON DELETE CASCADE,
    UNIQUE (member_id, expense_id)
);

CREATE INDEX idx_member_group      ON Member(group_id);
CREATE INDEX idx_expense_group     ON Expense(group_id);
CREATE INDEX idx_participant_exp   ON ExpenseParticipant(expense_id);

-- ---------------------------------------------------------------------
--  RÈGLES MÉTIER (triggers)
-- ---------------------------------------------------------------------

-- La date d'une dépense est comprise dans le séjour (bornes incluses)
CREATE TRIGGER trg_expense_date_ins
BEFORE INSERT ON Expense
WHEN NEW.date NOT BETWEEN (SELECT start_date FROM "Group" WHERE id = NEW.group_id)
                      AND (SELECT end_date   FROM "Group" WHERE id = NEW.group_id)
BEGIN
    SELECT RAISE(ABORT, 'La date de la dépense est en dehors du séjour');
END;

CREATE TRIGGER trg_expense_date_upd
BEFORE UPDATE OF date, group_id ON Expense
WHEN NEW.date NOT BETWEEN (SELECT start_date FROM "Group" WHERE id = NEW.group_id)
                      AND (SELECT end_date   FROM "Group" WHERE id = NEW.group_id)
BEGIN
    SELECT RAISE(ABORT, 'La date de la dépense est en dehors du séjour');
END;

-- Les dates du groupe ne peuvent pas exclure une dépense existante
CREATE TRIGGER trg_group_dates_upd
BEFORE UPDATE OF start_date, end_date ON "Group"
WHEN EXISTS (SELECT 1 FROM Expense
             WHERE group_id = NEW.id
               AND date NOT BETWEEN NEW.start_date AND NEW.end_date)
BEGIN
    SELECT RAISE(ABORT, 'Des dépenses existent en dehors des nouvelles dates du séjour');
END;

-- Un participant doit appartenir au même groupe que la dépense
CREATE TRIGGER trg_participant_same_group
BEFORE INSERT ON ExpenseParticipant
WHEN (SELECT group_id FROM Member  WHERE id = NEW.member_id)
  IS NOT (SELECT group_id FROM Expense WHERE id = NEW.expense_id)
BEGIN
    SELECT RAISE(ABORT, 'Le participant n''appartient pas au groupe de la dépense');
END;

-- On ne peut pas retirer le dernier participant d'une dépense qui existe encore
-- (la suppression en cascade d'une dépense reste possible : la dépense n'existe plus à ce moment-là)
CREATE TRIGGER trg_participant_keep_one
BEFORE DELETE ON ExpenseParticipant
WHEN EXISTS (SELECT 1 FROM Expense WHERE id = OLD.expense_id)
 AND (SELECT COUNT(*) FROM ExpenseParticipant WHERE expense_id = OLD.expense_id) <= 1
BEGIN
    SELECT RAISE(ABORT, 'Une dépense doit avoir au moins un participant');
END;

-- ---------------------------------------------------------------------
--  VUES : répartition à parts égales + soldes
-- ---------------------------------------------------------------------

-- Part de chaque participant. Part de base = montant / n (division entière).
-- Les centimes restants (montant % n) sont donnés un par un, dans l'ordre d'ajout (id croissants) :
-- avec 2 centimes restants, le premier et le deuxième participant en reçoivent chacun un.
CREATE VIEW v_share AS
SELECT
    ep.id         AS participant_id,
    ep.expense_id,
    ep.member_id,
    e.group_id,
    e.amount_cents / COUNT(*) OVER w
      + CASE WHEN ROW_NUMBER() OVER (PARTITION BY ep.expense_id ORDER BY ep.id)
                  <= e.amount_cents % COUNT(*) OVER w
             THEN 1 ELSE 0 END AS share_cents
FROM ExpenseParticipant ep
JOIN Expense e ON e.id = ep.expense_id
WINDOW w AS (PARTITION BY ep.expense_id);

-- Solde par membre = ce qu'il a payé - ce qu'il doit.  (> 0 : on lui doit de l'argent)
CREATE VIEW v_balance AS
SELECT
    m.group_id,
    m.id   AS member_id,
    p.name AS person_name,
    COALESCE((SELECT SUM(e.amount_cents) FROM Expense e
              WHERE e.group_id = m.group_id AND e.person_id = m.person_id), 0)
  - COALESCE((SELECT SUM(s.share_cents) FROM v_share s
              WHERE s.member_id = m.id), 0)  AS balance_cents
FROM Member m
JOIN Person p ON p.id = m.person_id;
