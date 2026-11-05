# Partage de frais

> **Noter les dépenses d’un séjour entre amis et savoir à tout moment qui doit combien à qui.**

Séance 1 · En binôme · Comme vous le faites d’habitude, avec ou sans IA, ChatGPT compris.

[Démarrer](#démarrer)

## Le contexte

Un groupe d’amis part une semaine en vacances. Chacun paie des choses pour les autres : les courses pour tout le monde, l’essence pour ceux qui sont dans la voiture, une activité pour une partie du groupe. Les tickets s’accumulent, et à la fin plus personne ne sait qui doit combien à qui.

## Les données

| Objet | Ce qu’on enregistre |
|---|---|
| **Groupe** | nom, dates du séjour, membres |
| **Dépense** | libellé, montant, date, payeur, participants |

## Ce que l’application doit faire

- [ ] Créer un groupe et ses membres
- [ ] Ajouter ou supprimer une dépense
- [ ] Afficher le solde de chaque membre

## Les règles

- Une dépense a un montant positif et au moins un participant.
- Le payeur et les participants appartiennent au groupe.
- La date d’une dépense est comprise dans le séjour, dates de début et de fin incluses.
- Une dépense est partagée à parts égales entre ses participants. Le centime restant va au premier participant ajouté.
- Les soldes sont exacts au centime près et leur somme vaut toujours 0.

## Pour vérifier

Groupe : Alice, Bob et Chloé. Les lignes s’enchaînent.

| Action | Résultat attendu |
|---|---|
| Alice paie 30 € pour Alice, Bob et Chloé | Alice +20,00 ; Bob −10,00 ; Chloé −10,00 |
| Une dépense datée hors du séjour | Refusée, soldes inchangés |
| Une dépense de 0 € | Refusée, soldes inchangés |
| Sur un nouveau groupe, Alice paie 10 € pour les trois | Alice +6,66 ; Bob −3,33 ; Chloé −3,33 |

## Si vous avez fini

Modifier une dépense, filtrer les dépenses par membre ou par période, exporter en CSV.

## Ce qui est libre

Le framework (Flask ou Streamlit), l’organisation du code et l’interface. La base SQLite est fournie avec des exemples, et vous pouvez la modifier. Python, SQLite et pytest sont imposés.

## À la fin de la séance

- Le but : une application qui fonctionne, avec les fonctionnalités demandées.
- Poussez votre travail sur GitHub.

---

# Démarrer

Python 3.11 ou plus est nécessaire.

## Préparer Git

Une seule fois par PC :

```bash
git config --global user.name "Votre nom"
git config --global user.email "votre@adresse.be"
```

GitHub n'accepte pas votre mot de passe dans le terminal. Si `git clone` refuse la connexion, installez [GitHub CLI](https://cli.github.com) et lancez `gh auth login`.

## Créer votre dépôt

1. Un membre du binôme ouvre <https://github.com/umons-ig/codelab-sans-agent>, clique sur **Use this template**, puis **Create a new repository**, et choisit **Private**.
2. Dans **Settings**, puis **Collaborators**, il ajoute son partenaire. Le partenaire accepte l'invitation.
3. Chacun récupère le dépôt sur sa machine, puis ouvre le dossier :

```bash
git clone <adresse-de-votre-dépôt>
```

## Choisir votre dossier

- `code-streamlit` : le plus simple. [Premiers pas](https://docs.streamlit.io/get-started).
- `code-flask` : plus de contrôle. [Démarrage rapide](https://flask.palletsprojects.com/en/stable/quickstart/).

Gardez un dossier et supprimez l'autre. Chacun contient un `app.py` qui lit la base, l'affiche et donne un exemple de formulaire.

## Installer et lancer

Avec Streamlit, remplacez `code-flask` par `code-streamlit`.

macOS ou Linux, depuis la racine du dépôt :

```bash
cd code-flask
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
pytest
```

Windows (PowerShell), depuis la racine du dépôt :

```powershell
cd code-flask
py -m venv .venv
Set-ExecutionPolicy -Scope Process RemoteSigned
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
pytest
```

Puis lancez l'application :

- Flask : `python app.py`, puis <http://127.0.0.1:5000>
- Streamlit : `streamlit run app.py`

Sur Mac, gardez `127.0.0.1` pour Flask. Avec `localhost`, vous pouvez tomber sur AirPlay, qui utilise aussi le port 5000, et obtenir une erreur 403.

## Comprendre le code

Vous travaillez dans `app.py`. `base.py` ouvre la base : vous n'avez pas besoin de le modifier.

- **Flask** : chaque adresse a sa fonction. `accueil` lit la base et affiche `PAGE`, qui contient le HTML. `ajouter_membre` reçoit le formulaire, écrit dans la base et revient à l'accueil. Pour une nouvelle fonctionnalité, ajoutez un formulaire dans `PAGE` et une fonction.
- **Streamlit** : le fichier s'exécute de haut en bas, puis à nouveau à chaque clic. Pour une nouvelle fonctionnalité, ajoutez vos champs, vos boutons et vos requêtes à la suite du fichier.

## La base

`base.sql` contient les tables et des exemples. `data.db` se crée au premier lancement. Pour repartir de zéro, ou après un changement de `base.sql`, supprimez `data.db`. [Documentation de `sqlite3`](https://docs.python.org/3/library/sqlite3.html).

| Table | Colonnes |
|---|---|
| `groupes` | `id`, `nom`, `date_debut`, `date_fin` |
| `membres` | `id`, `groupe_id`, `nom` |
| `depenses` | `id`, `groupe_id`, `libelle`, `montant_centimes`, `date`, `payeur_id` |
| `participants` | `depense_id`, `membre_id` |

Les montants sont en centimes : 3000 = 30,00 €. Les dates sont au format `2026-07-02`. `participants` relie une dépense aux membres qui la partagent.

## Travailler à deux

Chacun travaille sur son PC. `git pull` avant de travailler, `git push` après chaque commit :

```bash
git pull
```

```bash
git add -A
git commit -m "ajout de la fonctionnalité"
git push
```

Si `git push` est refusé, votre partenaire a poussé entre-temps. Récupérez son travail, puis poussez à nouveau :

```bash
git pull --no-rebase --no-edit
git push
```

En cas de conflit, corrigez les fichiers indiqués, puis faites `git add -A`, `git commit -m "fusion"` et `git push`.
