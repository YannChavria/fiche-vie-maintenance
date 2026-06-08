# Fiche de vie tiroir — données séparées (CSV) + moteur de rendu

Le graphe est désormais **piloté par des données CSV**. Le script Python ne
contient aucune donnée : il lit les CSV, fait l'analyse (échelons, trous de
réparation, transferts) et génère un HTML interactif par tiroir.

## Flux

```
positions.csv ─┐
               ├─►  render_graph.py  ─►  fiche_<tiroir>.html
cartes.csv ────┘
```

`make_sample_data.py` ne sert qu'à (re)générer le jeu d'exemple anonymisé.
Pour vos vraies données, vous l'ignorez et fournissez vos propres CSV.

## Format

### positions.csv — échelon N1 (séjours sur rame, zone HAUTE)

| colonne      | description |
|--------------|-------------|
| drawer       | identifiant du tiroir (regroupe une fiche) |
| position     | libellé de position, ex. `BAIE_A` → une ligne en haut |
| train        | rame |
| date_pose    | `YYYY-MM-DD`, début du séjour → flèche **verte** (retour service) |
| date_depose  | `YYYY-MM-DD` ou **vide** si encore en place → flèche **rouge** (dépose défaut) |
| ot           | identifiant OT, doit contenir le motif `\w+_OT_\d+` (pour le clic) |
| code         | type de maintenance (RA, EE, MO, CO…) |
| description  | texte court (modale) |
| commentaire  | texte (modale) |

### cartes.csv — échelon N3 (réparations de cartes, zone BASSE)

| colonne      | description |
|--------------|-------------|
| drawer       | identifiant du tiroir (même valeur que dans positions.csv) |
| carte        | libellé de carte, ex. `Carte UC` → une ligne en bas |
| date_depose  | `YYYY-MM-DD`, dépose de la carte pour réparation |
| date_repose  | `YYYY-MM-DD`, repose après réparation → **trou** tracé entre les deux |
| ot, code, description, commentaire | idem positions.csv |

### cartes_ref.csv — configuration des cartes du tiroir (lignes du bas)

| colonne | description |
|---------|-------------|
| drawer  | identifiant du tiroir |
| carte   | libellé de carte (un emplacement) |
| ordre   | entier (ordre d'affichage de bas en haut) |

Définit **toutes** les cartes du tiroir → chacune a sa ligne, même si elle n'a
jamais été réparée. Les réparations de `cartes.csv` viennent se superposer
(ticks + trous). Fichier **optionnel** mais recommandé : sans lui, seules les
cartes présentes dans `cartes.csv` apparaissent.

### transferts.csv — mouvements inter-atelier / mise en stock (flèches au milieu)

| colonne   | description |
|-----------|-------------|
| drawer    | identifiant du tiroir |
| datetime  | `YYYY-MM-DD` ou `YYYY-MM-DD HH:MM` |
| sens      | `retour` → flèche **verte** montante · `defaut` → flèche **rouge** descendante |
| label     | nom du stock / libellé du mouvement (ex. `STOCK MAG-10 → TR-101`) |

### tests.csv — tests du tiroir en atelier N3 (marqueurs sous la ligne)

| colonne     | description |
|-------------|-------------|
| drawer      | identifiant du tiroir |
| datetime    | `YYYY-MM-DD` ou `YYYY-MM-DD HH:MM` |
| resultat    | `RAS` → **cercle vert** · `KO` → **croix rouge** |
| commentaire | texte (survol) |

Marqueurs posés juste sous la ligne N1/N2 (y ≈ −1.1), sans modale. Fichier
**optionnel**.

Les flèches affichent ce `label` **au survol** et **n'ouvrent pas de modale**
(aucun OT n'y est associé). Fichier **optionnel** : s'il est absent, les
transferts sont dérivés automatiquement des poses/déposes de positions.csv.

> **Chronologie.** Le transfert est un événement distinct de la pose : la
> flèche **verte** marque l'arrivée du tiroir en N1 (sortie de stock), qui
> précède de quelques jours la **pose** sur le train (début du segment du
> haut). De même la flèche **rouge** (départ vers l'atelier) suit la dépose.
> C'est pourquoi `transferts.datetime` ≠ `positions.date_pose`/`date_depose`.

## Schémas particuliers (représentés par les données seules)

- **Switch le jour même (permutation).** Deux lignes `positions` consécutives
  avec `date_pose` du 2ᵉ = `date_depose` du 1ᵉ (même date), souvent rame
  différente, sans transfert : le tiroir est permuté directement d'une
  rame/baie à une autre le jour même. 1ᵉ segment `code = PE`.
- **Permutation de diagnostic (Baie A ↔ B, sans atelier).** Deux lignes
  `positions` consécutives sur le même train, baies différentes, avec
  `date_pose` du 2ᵉ ≈ `date_depose` du 1ᵉ et **aucune ligne `transferts`
  entre les deux** : le tiroir n'est pas redescendu en N2. Le 1ᵉ segment porte
  `code = PE` (permutation). Sert à isoler si le défaut suit le tiroir ou reste
  à la baie.
- **Réparation inefficace.** Cycle court : retour de N2 (verte) → montage →
  permutation A/B → le défaut persiste → retour N2 (rouge) dont le `label`
  mentionne « réparation inefficace ». Le commentaire du segment indique que le
  défaut suit le tiroir.

## Ce que le script déduit automatiquement

- Les **lignes et l'axe Y** : positions distinctes en haut (y = 2, 3, …),
  cartes distinctes en bas (y = −2, −3, …), `TRANSFERT N1/N2` au milieu.
- Les **bornes de vie** (début/fin) à partir des dates présentes.
- Les **transferts** (flèches) : lus depuis transferts.csv (nom du stock en
  survol, sans modale) ; à défaut, dérivés des poses/déposes.
- La **fusion** des fenêtres de réparation d'une même carte qui se chevauchent.
- Un **fichier HTML par tiroir** présent dans les données.

## Lancer

```bash
pip install -r requirements.txt
python render_graph.py        # lit les CSV -> docs/fiche_*.html + docs/index.html
```

Par défaut, les CSV sont lus **à côté du script** et le HTML est écrit dans `docs/`
(servi tel quel par GitHub Pages). Surcharge possible par variables d'environnement :

```bash
DATA_DIR=./mes_csv OUT_DIR=./build python render_graph.py
```

Les couleurs (`GREEN`, `RED`) se règlent en tête de `render_graph.py`.

## Démo en ligne (GitHub Pages)

Le site est généré dans `docs/` et publié via **GitHub Pages**.

👉 **https://&lt;votre-user&gt;.github.io/fiche-vie-maintenance/**

`docs/index.html` liste les fiches disponibles ; chaque fiche est un graphe Plotly
interactif (clic sur un point = détail OT, survol des flèches = transfert/stock).

### Activer Pages (une seule fois)

1. Pousser le dépôt sur GitHub (branche `main`).
2. Dépôt → **Settings** → **Pages**.
3. *Source* : **Deploy from a branch** → branche `main`, dossier **`/docs`** → **Save**.
4. Attendre ~1 min : l'URL ci-dessus devient active.

Après modification des CSV, relancer `python render_graph.py` puis committer `docs/`
pour mettre le site à jour.
