"""Tests de la couche modèles : construction et immutabilité."""

from __future__ import annotations

from dataclasses import FrozenInstanceError
from datetime import datetime, timezone

import pytest

from src.domain.models import Article, ArticleAnalyse, Digest


def _article_fixture() -> Article:
    return Article(
        titre="Test",
        resume="Un résumé",
        lien="https://example.com/article",
        source="ExampleSource",
        date_pub=datetime(2026, 5, 25, 6, 0, tzinfo=timezone.utc),
        hash_unique="abc123",
        categorie_source="general",
    )


def test_article_construction_et_acces_aux_attributs() -> None:
    article = _article_fixture()
    assert article.titre == "Test"
    assert article.hash_unique == "abc123"
    assert article.categorie_source == "general"


def test_article_est_immuable() -> None:
    article = _article_fixture()
    with pytest.raises(FrozenInstanceError):
        article.titre = "Autre titre"  # type: ignore[misc]


def test_article_analyse_porte_un_article_et_des_metadonnees() -> None:
    article = _article_fixture()
    analyse = ArticleAnalyse(
        article=article,
        garde=True,
        criticite="important",
        score=8,
        raison_courte="Pertinent pour la stack",
        categorie="backend",
    )
    assert analyse.article is article
    assert analyse.garde is True
    assert analyse.score == 8
    assert analyse.titre_traduit == ""  # défaut


def test_article_analyse_accepte_un_titre_traduit() -> None:
    article = _article_fixture()
    analyse = ArticleAnalyse(
        article=article,
        garde=True,
        criticite="important",
        score=8,
        raison_courte="Pertinent",
        categorie="ia",
        titre_traduit="Nouveau modèle GPT publié",
    )
    assert analyse.titre_traduit == "Nouveau modèle GPT publié"
    assert analyse.categorie == "ia"


def test_digest_initialise_les_listes_vides_par_defaut() -> None:
    digest = Digest(
        date_generation=datetime(2026, 5, 25, 5, 0, tzinfo=timezone.utc),
        nb_articles_analyses=0,
        nb_articles_retenus=0,
    )
    assert digest.top_priorites == []
    assert digest.autres_articles == []
    assert digest.tldr == ""
    assert digest.synthese_journee == ""


def test_digest_accepte_un_tldr() -> None:
    digest = Digest(
        date_generation=datetime(2026, 5, 25, 5, 0, tzinfo=timezone.utc),
        nb_articles_analyses=10,
        nb_articles_retenus=4,
        tldr="CVE critique Symfony 7.2 corrigée en urgence.",
        synthese_journee="Journée dominée par la sécurité.",
    )
    assert digest.tldr.startswith("CVE critique")


def test_digest_est_immuable() -> None:
    digest = Digest(
        date_generation=datetime(2026, 5, 25, 5, 0, tzinfo=timezone.utc),
        nb_articles_analyses=0,
        nb_articles_retenus=0,
    )
    with pytest.raises(FrozenInstanceError):
        digest.nb_articles_analyses = 99  # type: ignore[misc]
