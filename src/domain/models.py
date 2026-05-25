"""Modèles de domaine immuables (dataclasses frozen).

Cette couche est volontairement isolée de toute dépendance externe (I/O,
réseau, base de données). Elle représente le vocabulaire métier du bot
de veille et garantit l'immutabilité des valeurs transportées entre les
couches infrastructure et application.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime


@dataclass(frozen=True)
class Article:
    """Article unitaire extrait d'un flux RSS.

    Attributes:
        titre: Titre brut de l'article.
        resume: Résumé nettoyé du HTML, tronqué à 500 caractères.
        lien: URL canonique de l'article.
        source: Nom lisible de la source (ex: "CERT-FR").
        date_pub: Date de publication en UTC.
        hash_unique: SHA-256 hex du lien — clé de déduplication.
        categorie_source: Catégorie d'origine déclarée dans sources.py
            ("securite", "backend", "frontend", "devops", "general").
    """

    titre: str
    resume: str
    lien: str
    source: str
    date_pub: datetime
    hash_unique: str
    categorie_source: str


@dataclass(frozen=True)
class ArticleAnalyse:
    """Article enrichi par l'analyse Gemini.

    Attributes:
        article: Article d'origine.
        garde: Indique si l'article est retenu dans le digest publié.
        criticite: "critique" | "important" | "interessant" | "ignore".
        score: Note de pertinence entre 1 et 10.
        raison_courte: Une phrase justifiant la criticité.
        categorie: "securite" | "backend" | "frontend" | "devops" | "ia" | "general".
        titre_traduit: Titre traduit en français par l'IA. Vide si non fourni
            — utiliser ``article.titre`` comme fallback.
    """

    article: Article
    garde: bool
    criticite: str
    score: int
    raison_courte: str
    categorie: str
    titre_traduit: str = ""


@dataclass(frozen=True)
class Digest:
    """Digest quotidien prêt à être publié sur Discord.

    Attributes:
        date_generation: Horodatage UTC de la génération du digest.
        nb_articles_analyses: Nombre total d'articles soumis à l'IA.
        nb_articles_retenus: Nombre d'articles avec ``garde=True``.
        top_priorites: Articles "critique" + "important" (max 3).
        autres_articles: Articles retenus hors top priorité.
        tldr: Une seule phrase choc résumant la journée (max 100 caractères).
        synthese_journee: Résumé global de 2-3 phrases produit par l'IA.
    """

    date_generation: datetime
    nb_articles_analyses: int
    nb_articles_retenus: int
    top_priorites: list[ArticleAnalyse] = field(default_factory=list)
    autres_articles: list[ArticleAnalyse] = field(default_factory=list)
    tldr: str = ""
    synthese_journee: str = ""
