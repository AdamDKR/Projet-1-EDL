-- Copie temporaire du schéma convenu, utilisée uniquement par les tests.
-- À remplacer par le vrai schéma dès qu'il est disponible (voir SCHEMA dans conftest.py).
CREATE TABLE Groups (
    id INTEGER PRIMARY KEY,
    name TEXT NOT NULL,
    startDate TEXT NOT NULL,
    endDate TEXT NOT NULL
);
CREATE TABLE Person (
    id INTEGER PRIMARY KEY,
    name TEXT NOT NULL
);
CREATE TABLE Member (
    id INTEGER PRIMARY KEY,
    personId INTEGER NOT NULL REFERENCES Person(id),
    groupId INTEGER NOT NULL REFERENCES Groups(id),
    UNIQUE (personId, groupId)
);
CREATE TABLE Expense (
    id INTEGER PRIMARY KEY,
    label TEXT NOT NULL,
    amountCents INTEGER NOT NULL,
    date TEXT NOT NULL,
    payerMemberId INTEGER NOT NULL REFERENCES Member(id),
    groupId INTEGER NOT NULL REFERENCES Groups(id)
);
CREATE TABLE ExpenseParticipant (
    expenseId INTEGER NOT NULL REFERENCES Expense(id),
    memberId INTEGER NOT NULL REFERENCES Member(id),
    position INTEGER NOT NULL,
    PRIMARY KEY (expenseId, memberId)
);
