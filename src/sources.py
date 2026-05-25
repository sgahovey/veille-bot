"""Liste configurable des flux RSS suivis par le bot."""

from __future__ import annotations

SOURCES: list[dict] = [
    {
        "nom": "CERT-FR",
        "url": "https://www.cert.ssi.gouv.fr/feed/",
        "categorie": "securite",
    },
    {
        "nom": "NVD CVE",
        "url": "https://nvd.nist.gov/feeds/xml/cve/misc/nvd-rss.xml",
        "categorie": "securite",
    },
    {
        "nom": "The Hacker News",
        "url": "https://feeds.feedburner.com/TheHackersNews",
        "categorie": "securite",
    },
    {
        "nom": "OWASP",
        "url": "https://owasp.org/feed.xml",
        "categorie": "securite",
    },
    {
        "nom": "Dev.to",
        "url": "https://dev.to/feed/",
        "categorie": "general",
    },
    {
        "nom": "Hacker News (top)",
        "url": "https://hnrss.org/frontpage?points=100",
        "categorie": "general",
    },
    {
        "nom": "Symfony Blog",
        "url": "https://feeds.feedburner.com/symfony/blog",
        "categorie": "backend",
    },
    {
        "nom": "PHP.net",
        "url": "https://www.php.net/feed.atom",
        "categorie": "backend",
    },
    {
        "nom": "GreenIT",
        "url": "https://www.greenit.fr/feed/",
        "categorie": "general",
    },
    {
        "nom": "Journal du Hacker",
        "url": "https://www.journalduhacker.net/rss",
        "categorie": "general",
    },
    {
        "nom": "PHP Watch",
        "url": "https://php.watch/feed.atom",
        "categorie": "backend",
    },
    {
        "nom": "CSS-Tricks",
        "url": "https://css-tricks.com/feed/",
        "categorie": "frontend",
    },
    {
        "nom": "Smashing Magazine",
        "url": "https://www.smashingmagazine.com/feed/",
        "categorie": "frontend",
    },
    {
        "nom": "Snyk Blog",
        "url": "https://snyk.io/blog/feed/",
        "categorie": "securite",
    },
    {
        "nom": "Stack Overflow Blog",
        "url": "https://stackoverflow.blog/feed/",
        "categorie": "general",
    },
]
