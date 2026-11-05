-- =====================================================================
--  REQUÊTES (paramètres nommés :xxx). Montants en centimes.
--  Dans une appli, exécuter chaque bloc "SET" dans une transaction.
-- =====================================================================

-- ============================ SET ====================================

-- Créer un groupe
INSERT INTO "Group"(name, start_date, end_date)
VALUES (:name, :start_date, :end_date);

-- Créer une personne
INSERT INTO Person(name) VALUES (:name);

-- Ajouter une personne comme membre d'un groupe
INSERT INTO Member(person_id, group_id) VALUES (:person_id, :group_id);

-- Ajouter une dépense (payeur = person_id, qui doit être membre du groupe)
INSERT INTO Expense(label, amount_cents, date, person_id, group_id)
VALUES (:label, :amount_cents, :date, :person_id, :group_id);

-- Ajouter un participant à une dépense (appeler dans l'ordre voulu : les centimes restants sont donnés un par un, en commençant par le 1er)
INSERT INTO ExpenseParticipant(member_id, expense_id)
VALUES (:member_id, :expense_id);

-- Ajouter une dépense avec tous les membres du groupe comme participants (ordre = ordre d'ajout au groupe)
-- (à exécuter juste après l'INSERT Expense, avec :expense_id = last_insert_rowid())
INSERT INTO ExpenseParticipant(member_id, expense_id)
SELECT m.id, :expense_id
FROM Member m
WHERE m.group_id = (SELECT group_id FROM Expense WHERE id = :expense_id)
ORDER BY m.id;

-- Supprimer une dépense (ses participants partent en cascade)
DELETE FROM Expense WHERE id = :expense_id;

-- Vérification "au moins un participant" à lancer avant le COMMIT :
-- doit retourner 0 ligne, sinon faire un ROLLBACK
SELECT e.id FROM Expense e
WHERE e.id = :expense_id
  AND NOT EXISTS (SELECT 1 FROM ExpenseParticipant WHERE expense_id = e.id);

-- ============================ GET ====================================

-- Liste des groupes
SELECT id, name, start_date, end_date FROM "Group" ORDER BY start_date;

-- Liste des personnes
SELECT id, name FROM Person ORDER BY name;

-- Membres d'un groupe
SELECT m.id AS member_id, p.id AS person_id, p.name
FROM Member m JOIN Person p ON p.id = m.person_id
WHERE m.group_id = :group_id
ORDER BY m.id;

-- Dépenses d'un groupe avec payeur et nombre de participants
SELECT e.id, e.date, e.label, e.amount_cents / 100.0 AS amount,
       p.name AS payer,
       (SELECT COUNT(*) FROM ExpenseParticipant ep WHERE ep.expense_id = e.id) AS nb_participants
FROM Expense e JOIN Person p ON p.id = e.person_id
WHERE e.group_id = :group_id
ORDER BY e.date, e.id;

-- Détail des parts d'une dépense
SELECT s.participant_id, p.name, s.share_cents / 100.0 AS share
FROM v_share s
JOIN Member m ON m.id = s.member_id
JOIN Person p ON p.id = m.person_id
WHERE s.expense_id = :expense_id
ORDER BY s.participant_id;

-- >>> SOLDE DE CHAQUE MEMBRE d'un groupe
SELECT member_id, person_name,
       balance_cents,
       printf('%.2f', balance_cents / 100.0) AS balance
FROM v_balance
WHERE group_id = :group_id
ORDER BY member_id;

-- Contrôle : la somme des soldes vaut toujours 0
SELECT group_id, SUM(balance_cents) AS total   -- doit valoir 0
FROM v_balance GROUP BY group_id;
