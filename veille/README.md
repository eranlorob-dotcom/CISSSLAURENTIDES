# Veille hebdomadaire — Environnement bâti et santé

Agent autonome qui envoie chaque lundi matin un digest par courriel couvrant :
- **Littérature scientifique** récente (PubMed + Semantic Scholar)
- **Médias québécois** (Radio-Canada, Le Devoir, La Presse, Google News)

filtrés et résumés en français par Claude selon tes mots-clés.

## 1. Où mettre ces fichiers

Copie le dossier `veille/` (et son contenu) à la racine de ton repo `CISSSLAURENTIDES`, en gardant la structure :

```
CISSSLAURENTIDES/
  veille/
    config/
      keywords.yaml
      rss_feeds.yaml
    scripts/
      veille.py
    requirements.txt
  .github/
    workflows/
      veille-hebdo.yml    <-- va dans .github/workflows/ à la racine du repo
```

⚠️ Le dossier `.github/workflows/` doit être à la **racine** du repo (pas dans `veille/`), sinon GitHub Actions ne le détecte pas.

## 2. Créer le mot de passe d'application Gmail

Gmail bloque les connexions SMTP avec ton mot de passe habituel. Il faut un "mot de passe d'application" :

1. Va sur https://myaccount.google.com/apppasswords (nécessite la validation en 2 étapes activée sur ton compte)
2. Crée un mot de passe pour "Mail" / "Autre (nom personnalisé)" → nomme-le "Veille GitHub Actions"
3. Copie le mot de passe généré (16 caractères, sans espaces)

## 3. Obtenir une clé API Anthropic

1. Va sur https://console.anthropic.com/settings/keys
2. Crée une clé API (ce sera facturé à l'usage — le coût hebdo de ce script est de l'ordre de quelques cents)

## 4. Configurer les secrets GitHub

Dans ton repo `CISSSLAURENTIDES` sur GitHub :
`Settings` → `Secrets and variables` → `Actions` → `New repository secret`

Ajoute ces 4 secrets :

| Nom | Valeur |
|---|---|
| `ANTHROPIC_API_KEY` | ta clé API Anthropic |
| `GMAIL_USER` | ton adresse Gmail complète |
| `GMAIL_APP_PASSWORD` | le mot de passe d'application généré à l'étape 2 |
| `RECIPIENT_EMAIL` | l'adresse où tu veux recevoir le digest (peut être la même que GMAIL_USER) |

## 5. Tester manuellement

Une fois les fichiers poussés et les secrets configurés :
1. Va dans l'onglet `Actions` de ton repo
2. Clique sur "Veille hebdomadaire - environnement bâti et santé"
3. Clique sur `Run workflow` (bouton à droite) pour déclencher un test immédiat
4. Vérifie les logs — puis ta boîte courriel

## 6. Horaire

Par défaut : tous les **lundis à 7h00 heure de Montréal**. Pour changer, modifie la ligne `cron` dans `.github/workflows/veille-hebdo.yml` (format cron standard, en UTC).

## 7. Ajuster les mots-clés

Édite simplement `veille/config/keywords.yaml` (thèmes scientifiques et médias séparés) et `veille/config/rss_feeds.yaml` (flux RSS à surveiller) — aucun besoin de toucher au code Python. Les changements prennent effet au prochain envoi.

## Limites connues

- **Semantic Scholar** applique un rate-limit assez strict sans clé API. Si tu obtiens beaucoup d'erreurs 429 dans les logs, on peut demander une clé gratuite sur https://www.semanticscholar.org/product/api pour augmenter le quota — dis-le-moi et je l'intègre.
- **PubMed** couvre surtout les revues biomédicales/santé publique ; certaines revues d'urbanisme/géographie pure (ex. certaines revues d'aménagement) sont mieux couvertes par Semantic Scholar.
- Le filtrage de pertinence dépend de la qualité des résumés/titres retournés par les APIs — occasionnellement Claude peut laisser passer un faux positif ou en rejeter un pertinent. Tu peux ajuster les consignes de filtrage directement dans `build_digest_with_claude()` si besoin.
