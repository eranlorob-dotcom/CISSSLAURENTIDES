# Veille hebdomadaire — Environnements alimentaires

Même pipeline que la veille "environnement bâti et santé" d'Éric, mais avec les mots-clés
et le contexte adaptés aux environnements alimentaires, systèmes alimentaires territoriaux (SAT)
et sécurité alimentaire.

## Deux façons de la déployer

### Option A — Dans le même repo GitHub que la veille d'Éric (`CISSSLAURENTIDES`)

Le plus simple si ta collègue n'a pas de repo GitHub à elle et qu'Éric gère le dépôt.

1. Copie le dossier `veille-alimentaire/` à la racine du repo, à côté du dossier `veille/` existant
2. Déplace `.github/workflows/veille-hebdo-alimentaire.yml` dans `.github/workflows/` à la racine (à côté de `veille-hebdo.yml`)
3. Ajoute ces secrets **en plus** de ceux déjà configurés pour la veille d'Éric (`Settings → Secrets and variables → Actions`) :

   | Nom | Valeur |
   |---|---|
   | `GMAIL_USER_ALIMENTAIRE` | l'adresse Gmail de ta collègue |
   | `GMAIL_APP_PASSWORD_ALIMENTAIRE` | son mot de passe d'application Gmail (même procédure, voir ci-dessous) |
   | `RECIPIENT_EMAIL_ALIMENTAIRE` | l'adresse où elle veut recevoir le digest |

   Note : `ANTHROPIC_API_KEY` est réutilisé (déjà configuré pour la veille d'Éric) — pas besoin de le dupliquer.

### Option B — Dans un repo GitHub séparé (elle a/crée son propre repo)

Plus indépendant : elle garde le contrôle total sur sa propre veille.

1. Elle crée un nouveau repo GitHub (public ou privé, peu importe)
2. Copie **tout le contenu** de `veille-alimentaire/` à la racine de son repo, y compris `.github/workflows/`
3. Renomme le dossier `veille-alimentaire/` en simplement `veille/` si elle préfère (ajuster alors les chemins dans le fichier `.github/workflows/veille-hebdo-alimentaire.yml`, lignes `pip install -r ...` et `python ...`)
4. Configure ses propres 4 secrets dans son repo :

   | Nom | Valeur |
   |---|---|
   | `ANTHROPIC_API_KEY` | sa propre clé API Anthropic (ou celle d'Éric si partagée) |
   | `GMAIL_USER` | son adresse Gmail |
   | `GMAIL_APP_PASSWORD` | son mot de passe d'application |
   | `RECIPIENT_EMAIL` | l'adresse de réception |

   (Dans ce cas, garde les noms `veille.py`, `GMAIL_USER`, etc. tels quels dans le workflow — pas besoin des suffixes `_ALIMENTAIRE`.)

## Créer le mot de passe d'application Gmail (pour elle)

Même procédure que pour Éric :
1. Vérifie que la validation en 2 étapes est activée : https://myaccount.google.com/security
2. Génère le mot de passe ici : https://myaccount.google.com/apppasswords
3. Nomme-le "Veille GitHub Actions", copie le code à 16 caractères

## Obtenir une clé API Anthropic (si pas partagée avec Éric)

https://console.anthropic.com/settings/keys

## Tester

Une fois les fichiers poussés et les secrets configurés : onglet `Actions` du repo → sélectionner
le workflow "Veille hebdomadaire - environnements alimentaires" → bouton `Run workflow`.

## Ajuster les mots-clés

Tout se passe dans `veille-alimentaire/config/keywords.yaml` (thèmes scientifiques/médias) et
`config/rss_feeds.yaml` (flux à surveiller) — aucune modification de code nécessaire.

## Horaire

Programmé le **mardi 7h** (Éric est le lundi) pour étaler la charge. Modifiable dans la ligne
`cron` du fichier workflow.
