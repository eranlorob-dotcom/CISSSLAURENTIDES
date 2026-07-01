#!/usr/bin/env python3
"""
Veille hebdomadaire — environnement bâti et santé
Éric Robitaille / DSP CISSS des Laurentides

Pipeline :
1. Interroge PubMed + Semantic Scholar (littérature scientifique)
2. Interroge les flux RSS/Google News configurés (médias)
3. Envoie tout à Claude pour filtrage de pertinence + résumé en français
4. Compose un digest HTML et l'envoie par courriel via Gmail SMTP

Variables d'environnement requises (voir README.md) :
  ANTHROPIC_API_KEY
  GMAIL_USER
  GMAIL_APP_PASSWORD
  RECIPIENT_EMAIL
"""

import os
import sys
import time
import smtplib
import ssl
from datetime import datetime, timedelta, timezone
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

import yaml
import requests
import feedparser
import anthropic

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CONFIG_DIR = os.path.join(BASE_DIR, "config")

# ---------- Config ----------

def load_config():
    with open(os.path.join(CONFIG_DIR, "keywords.yaml"), encoding="utf-8") as f:
        keywords = yaml.safe_load(f)
    with open(os.path.join(CONFIG_DIR, "rss_feeds.yaml"), encoding="utf-8") as f:
        rss = yaml.safe_load(f)
    return keywords, rss


# ---------- Sources : littérature scientifique ----------

def fetch_pubmed(query, max_results, days_back):
    """Recherche PubMed via l'API E-utilities (gratuite, sans clé)."""
    date_min = (datetime.now(timezone.utc) - timedelta(days=days_back)).strftime("%Y/%m/%d")
    date_max = datetime.now(timezone.utc).strftime("%Y/%m/%d")

    search_url = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi"
    params = {
        "db": "pubmed",
        "term": f"({query}) AND ({date_min}[Date - Publication] : {date_max}[Date - Publication])",
        "retmode": "json",
        "retmax": max_results,
        "sort": "most+recent",
    }
    try:
        r = requests.get(search_url, params=params, timeout=20)
        r.raise_for_status()
        ids = r.json().get("esearchresult", {}).get("idlist", [])
        if not ids:
            return []

        summary_url = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esummary.fcgi"
        params2 = {"db": "pubmed", "id": ",".join(ids), "retmode": "json"}
        r2 = requests.get(summary_url, params=params2, timeout=20)
        r2.raise_for_status()
        result = r2.json().get("result", {})

        items = []
        for pmid in ids:
            doc = result.get(pmid)
            if not doc:
                continue
            items.append({
                "titre": doc.get("title", "").strip(),
                "auteurs": ", ".join(a.get("name", "") for a in doc.get("authors", [])[:3]),
                "revue": doc.get("fulljournalname", ""),
                "date": doc.get("pubdate", ""),
                "url": f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/",
                "source": "PubMed",
                "requete": query,
            })
        return items
    except Exception as e:
        print(f"[PubMed] Erreur pour '{query}': {e}", file=sys.stderr)
        return []


def fetch_semantic_scholar(query, max_results, days_back):
    """Recherche Semantic Scholar via API publique (gratuite, rate-limited)."""
    year_min = (datetime.now(timezone.utc) - timedelta(days=days_back)).year
    url = "https://api.semanticscholar.org/graph/v1/paper/search"
    params = {
        "query": query,
        "limit": max_results,
        "fields": "title,authors,venue,year,url,publicationDate,abstract",
        "year": f"{year_min}-",
    }
    try:
        r = requests.get(url, params=params, timeout=20)
        if r.status_code == 429:
            print("[Semantic Scholar] Rate limited, on saute.", file=sys.stderr)
            return []
        r.raise_for_status()
        data = r.json().get("data", [])
        items = []
        cutoff = datetime.now(timezone.utc) - timedelta(days=days_back)
        for p in data:
            pub_date = p.get("publicationDate")
            if pub_date:
                try:
                    pd = datetime.strptime(pub_date, "%Y-%m-%d").replace(tzinfo=timezone.utc)
                    if pd < cutoff:
                        continue
                except ValueError:
                    pass
            items.append({
                "titre": p.get("title", "").strip(),
                "auteurs": ", ".join(a.get("name", "") for a in (p.get("authors") or [])[:3]),
                "revue": p.get("venue", ""),
                "date": p.get("publicationDate", str(p.get("year", ""))),
                "url": p.get("url", ""),
                "resume": (p.get("abstract") or "")[:500],
                "source": "Semantic Scholar",
                "requete": query,
            })
        return items
    except Exception as e:
        print(f"[Semantic Scholar] Erreur pour '{query}': {e}", file=sys.stderr)
        return []


# ---------- Sources : médias ----------

def fetch_rss(feeds, keywords, max_par_flux, days_back):
    cutoff = datetime.now(timezone.utc) - timedelta(days=days_back)
    items = []
    for flux in feeds:
        try:
            parsed = feedparser.parse(flux["url"])
            count = 0
            for entry in parsed.entries:
                if count >= max_par_flux:
                    break
                titre = entry.get("title", "")
                resume = entry.get("summary", "")
                texte = f"{titre} {resume}".lower()

                # Pour Google News (déjà filtré par requête), on prend tout.
                # Pour les flux généraux, on filtre par mots-clés.
                est_google_news = "news.google.com" in flux["url"]
                match = est_google_news or any(kw.lower() in texte for kw in keywords)
                if not match:
                    continue

                items.append({
                    "titre": titre,
                    "resume": resume[:400],
                    "url": entry.get("link", ""),
                    "date": entry.get("published", ""),
                    "source": flux["nom"],
                })
                count += 1
        except Exception as e:
            print(f"[RSS] Erreur pour '{flux['nom']}': {e}", file=sys.stderr)
    return items


# ---------- Déduplication ----------

def dedupe(items, key="titre"):
    seen = set()
    out = []
    for it in items:
        norm = it.get(key, "").strip().lower()[:80]
        if norm and norm not in seen:
            seen.add(norm)
            out.append(it)
    return out


# ---------- Claude : filtrage + résumé ----------

def build_digest_with_claude(client, sci_items, media_items):
    sci_block = "\n\n".join(
        f"- TITRE: {it['titre']}\n  AUTEURS: {it.get('auteurs','')}\n  REVUE: {it.get('revue','')}\n  DATE: {it.get('date','')}\n  URL: {it['url']}\n  RÉSUMÉ_BRUT: {it.get('resume','')[:400]}"
        for it in sci_items
    )
    media_block = "\n\n".join(
        f"- TITRE: {it['titre']}\n  SOURCE: {it['source']}\n  DATE: {it.get('date','')}\n  URL: {it['url']}\n  EXTRAIT: {it.get('resume','')[:300]}"
        for it in media_items
    )

    prompt = f"""Tu prépares un digest de veille hebdomadaire pour Éric Robitaille, chercheur en santé publique et aménagement du territoire (environnement bâti, ÉIS, géomatique de la santé, Laurentides/Québec).

Voici les résultats bruts de cette semaine.

=== LITTÉRATURE SCIENTIFIQUE (bruts) ===
{sci_block if sci_block else "(aucun résultat)"}

=== MÉDIAS (bruts) ===
{media_block if media_block else "(aucun résultat)"}

Consignes :
1. Élimine les doublons et tout ce qui n'est PAS pertinent pour l'environnement bâti et la santé publique (aménagement du territoire, urbanisme, transport actif, densification, accessibilité, désert alimentaire, climat urbain, etc.). Sois sélectif — mieux vaut 5 items pertinents que 15 dilués.
2. Pour chaque item retenu, écris un résumé de 2-3 phrases EN FRANÇAIS, dans tes propres mots (jamais de citation verbatim), qui explique pourquoi c'est pertinent pour Éric.
3. Organise la sortie en HTML simple avec deux sections : "Littérature scientifique" et "Médias". Utilise des balises <h2>, <ul>, <li>, <a href="...">titre</a>, <p> pour les résumés. Pas de <html>/<head>/<body>, juste le contenu.
4. Si une section est vide, écris "Aucun résultat pertinent cette semaine." dans cette section.
5. Ne produis QUE le HTML, sans préambule ni commentaire.
"""

    response = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=4000,
        messages=[{"role": "user", "content": prompt}],
    )
    text_parts = [b.text for b in response.content if b.type == "text"]
    return "".join(text_parts).strip()


# ---------- Email ----------

def send_email(html_body, subject, gmail_user, gmail_app_password, recipient):
    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = gmail_user
    msg["To"] = recipient

    full_html = f"""
    <html>
    <body style="font-family: 'Segoe UI', Arial, sans-serif; color: #1a1a1a; max-width: 700px; margin: auto;">
      <div style="background: #140C74; color: white; padding: 16px 24px; border-radius: 6px 6px 0 0;">
        <h1 style="margin:0; font-size: 20px;">Veille — Environnement bâti et santé</h1>
        <p style="margin:4px 0 0 0; font-size: 13px; opacity: 0.85;">{datetime.now().strftime('%d %B %Y')}</p>
      </div>
      <div style="padding: 20px 24px; border: 1px solid #e0e0e0; border-top: none; border-radius: 0 0 6px 6px;">
        {html_body}
      </div>
    </body>
    </html>
    """
    msg.attach(MIMEText(full_html, "html", "utf-8"))

    context = ssl.create_default_context()
    with smtplib.SMTP_SSL("smtp.gmail.com", 465, context=context) as server:
        server.login(gmail_user, gmail_app_password)
        server.sendmail(gmail_user, recipient, msg.as_string())


# ---------- Main ----------

def main():
    anthropic_key = os.environ["ANTHROPIC_API_KEY"]
    gmail_user = os.environ["GMAIL_USER"]
    gmail_app_password = os.environ["GMAIL_APP_PASSWORD"]
    recipient = os.environ["RECIPIENT_EMAIL"]

    keywords_cfg, rss_cfg = load_config()
    limites = keywords_cfg["limites"]
    fenetre = keywords_cfg["fenetre_jours_scientifique"]

    print("Récupération PubMed...")
    sci_items = []
    for q in keywords_cfg["scientifique"]:
        sci_items += fetch_pubmed(q, limites["pubmed_max_results"], fenetre)
        time.sleep(0.4)  # NCBI recommande <3 req/s sans clé API

    print("Récupération Semantic Scholar...")
    for q in keywords_cfg["scientifique"]:
        sci_items += fetch_semantic_scholar(q, limites["semantic_scholar_max_results"], fenetre)
        time.sleep(1.0)  # rate limit plus strict sans clé API

    sci_items = dedupe(sci_items, key="titre")
    print(f"  -> {len(sci_items)} items scientifiques après dédup")

    print("Récupération flux RSS/médias...")
    media_items = fetch_rss(rss_cfg["flux"], keywords_cfg["medias"], limites["rss_max_par_flux"], fenetre)
    media_items = dedupe(media_items, key="titre")
    print(f"  -> {len(media_items)} items médias après dédup")

    print("Filtrage et résumé via Claude...")
    client = anthropic.Anthropic(api_key=anthropic_key)
    html_digest = build_digest_with_claude(client, sci_items, media_items)

    print("Envoi du courriel...")
    subject = f"Veille environnement bâti & santé — {datetime.now().strftime('%d %b %Y')}"
    send_email(html_digest, subject, gmail_user, gmail_app_password, recipient)

    print("Terminé.")


if __name__ == "__main__":
    main()
