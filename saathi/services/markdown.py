"""Markdown rendering behind a hard sanitize boundary.

The ONLY path from user markdown to HTML in the app: render with raw-HTML
parsing disabled, then strip everything outside an explicit nh3 allowlist.
Wrapping in Markup here — post-sanitize — is the sanctioned equivalent of
|safe; no template may apply |safe to note content (CONVENTIONS §4.2).
"""

from __future__ import annotations

import html
import re

import nh3
from markdown_it import MarkdownIt
from markupsafe import Markup, escape

_md = MarkdownIt("js-default", {"html": False, "breaks": True})
# markdown-it-py 4.x js-default ships tables ON but strikethrough OFF
# (B08 claimed both on) — enable it explicitly; html stays disabled twice over.
_md.enable(["strikethrough"])

# Explicit policy pin: nh3's built-in defaults can widen between releases
# (B08 pitfall #1), so every knob is passed even where it matches today.
NH3_TAGS = {
    "p",
    "br",
    "strong",
    "em",
    "del",
    "s",
    "code",
    "pre",
    "blockquote",
    "ul",
    "ol",
    "li",
    "h1",
    "h2",
    "h3",
    "h4",
    "h5",
    "h6",
    "hr",
    "a",
    "img",
    "table",
    "thead",
    "tbody",
    "tr",
    "th",
    "td",
}
NH3_ATTRS = {"*": set(), "a": {"href", "title"}, "img": {"src", "alt", "title"}}
NH3_SCHEMES = {"http", "https", "mailto"}

_cleaner = nh3.Cleaner(
    tags=NH3_TAGS,
    attributes=NH3_ATTRS,
    url_schemes=NH3_SCHEMES,
    link_rel="noopener noreferrer",
)

_TAG_STRIP_RE = re.compile(r"<[^>]+>")
_WS_RE = re.compile(r"\s+")


def sanitize_html(html_text: str) -> str:
    """HTML fragment -> allowlist-cleaned fragment. The app's single trust boundary."""
    return _cleaner.clean(html_text)


def render_md(md_text: str) -> Markup:
    """Jinja `md` filter: markdown -> HTML -> cleaned; Markup only after cleaning."""
    return Markup(sanitize_html(_md.render(md_text or "")))


def excerpt(content: str, n: int = 160) -> str:
    """Plain-text teaser for list views.

    Sanitize-render-strip order matters (B08 §1c): raw markdown sliced
    directly leaks asterisks/headings into the UI. Entities are unescaped so
    display-time autoescaping shows readable text instead of &lt;b&gt; noise.
    """
    rendered = sanitize_html(_md.render(content or ""))
    plain = _WS_RE.sub(" ", _TAG_STRIP_RE.sub(" ", rendered))
    plain = html.unescape(plain).strip()
    if len(plain) <= n:
        return plain
    return f"{plain[:n].rsplit(' ', 1)[0]}…"


def highlight(plain: str, term: str) -> Markup:
    """Wrap literal case-insensitive matches of term in <mark>.

    Escape happens BEFORE wrapping so neither term nor text can smuggle
    markup through the result; a term containing &, < or > simply won't
    match its escaped form (accepted edge, documented in B08 search).
    """
    escaped = escape(plain)
    if not term:
        return Markup(escaped)
    pattern = re.compile(re.escape(term), re.IGNORECASE)
    marked = pattern.sub(lambda m: f"<mark>{m.group(0)}</mark>", escaped)
    return Markup(marked)
