#!/usr/bin/env python3
"""Wrap every page of the site in the shared layout (header, chapter nav,
"on this page", pager, footer) without touching the content or its ids.

Idempotent: the original content is kept between <!-- content:start --> and
<!-- content:end --> markers, so the script can be re-run after a page is
regenerated with pandoc or edited by hand.

    python3 tools/apply_layout.py          # rewrite all pages
    python3 tools/apply_layout.py --check  # only report what would change
"""
import html
import os
import re
import sys
import unicodedata

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SITE_TITLE = "Agrégation"
SITE_SUB = "English phonology"

# file, nav label, accent key, group
CHAPTERS = [
    ("graphophonemics.html", "Graphophonemics", "grapho"),
    ("stress.html", "Stress", "stress"),
    ("phonetic-processes.html", "Phonetic processes in connected speech", "processes"),
    ("suprasegmentals.html", "Suprasegmentals", "supraseg"),
    ("ssbe-ga.html", "SSBE and GA", "varieties"),
]
PRACTICE = [
    ("fleabag.html", "Fleabag", "practice"),
    ("zadie.html", "White Teeth", "practice"),
    ("earnest.html", "The Importance of Being Earnest", "practice"),
    ("angels.html", "Angels in America", "practice"),
]
REFERENCE = [
    ("consonants-vowels.html", "Phonemic chart", "reference"),
]
INDEX = ("index.html", "Home", "index")

ORDER = [INDEX] + CHAPTERS + PRACTICE + REFERENCE
PREWRAP = {"fleabag.html", "earnest.html", "angels.html"}  # scripts typed with hard line breaks

# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------

def read(path):
    with open(path, encoding="utf-8") as f:
        return f.read()


def write(path, text):
    with open(path, "w", encoding="utf-8") as f:
        f.write(text)


def strip_tags(s):
    s = re.sub(r"<[^>]+>", "", s)
    return html.unescape(re.sub(r"\s+", " ", s)).strip()


def slugify(text):
    text = unicodedata.normalize("NFKD", strip_tags(text)).lower()
    text = re.sub(r"[^\w\s-]", "", text)
    return re.sub(r"[\s_]+", "-", text).strip("-") or "section"


def extract_content(src):
    """Return the page's own content: what is between the markers if the
    layout was already applied, otherwise the inner HTML of <body>."""
    m = re.search(r"<!-- content:start -->(.*?)<!-- content:end -->", src, re.S)
    if m:
        return m.group(1).strip("\n"), True
    m = re.search(r"<body[^>]*>(.*?)</body>", src, re.S | re.I)
    return (m.group(1) if m else src).strip("\n"), False


def clean_content(name, content):
    c = content
    # old per-page footers and the scroll→picture-in-picture script
    c = re.sub(r"<footer\b[^>]*>.*?</footer>\s*", "", c, flags=re.S | re.I)
    c = re.sub(r"<script>\s*const videoContainer.*?</script>\s*", "", c, flags=re.S)
    # hint injected by a previous run (re-inserted below the title each time)
    c = re.sub(r'\n?<p class="ruby-hint">.*?</p>', "", c, flags=re.S)
    # Word artefacts on ruby annotations (5.5pt font size made them unreadable)
    c = re.sub(r"<(ruby|rt|rp)\s+style=\"[^\"]*\"\s*>", r"<\1>", c)
    # fixed inch sizes on images exported from Word
    c = re.sub(r'(<img\b[^>]*?)\s+style="[^"]*"', r"\1", c)
    # YouTube: no autoplay, lazy loading
    c = c.replace("?autoplay=1", "")
    c = re.sub(r'<iframe\b(?![^>]*loading=)', '<iframe loading="lazy"', c)
    # scripts rendered with pre-wrap: blank lines between block tags would show up as gaps
    if name in PREWRAP:
        c = re.sub(r'(<div id="content">)\s*(<h[12][^>]*>.*?</h[12]>)\s*', r"\1\2\n", c, count=1, flags=re.S)
        c = re.sub(r">\n\s*\n\s*<", ">\n<", c)
    # scrollable tables
    if "table-wrap" not in c:
        c = re.sub(r"<table\b", '<div class="table-wrap"><table', c)
        c = c.replace("</table>", "</table></div>")
    # give ids to headings that have none (needed for "on this page")
    used = set(re.findall(r'\bid="([^"]+)"', c))

    def add_id(m):
        tag, attrs, inner = m.group(1), m.group(2), m.group(3)
        if re.search(r'\bid="', attrs):
            return m.group(0)
        base = slugify(inner)
        slug, n = base, 2
        while slug in used:
            slug = f"{base}-{n}"
            n += 1
        used.add(slug)
        return f'<{tag}{attrs} id="{slug}">{inner}</{tag}>'

    c = re.sub(r"<(h[1-4])([^>]*)>(.*?)</\1>", add_id, c, flags=re.S)
    return c


def headings(content, levels=("h2", "h3", "h4")):
    out = []
    for m in re.finditer(r"<(h[1-4])([^>]*)>(.*?)</\1>", content, re.S):
        tag, attrs, inner = m.groups()
        if tag not in levels:
            continue
        idm = re.search(r'\bid="([^"]+)"', attrs)
        if not idm:
            continue
        out.append((tag, idm.group(1), strip_tags(inner).rstrip(":")))
    return out


def practice_wrap(name, content):
    """Practice pages: put the video, the instructions and the text in a grid
    container so the video can sit in a side column on wide screens."""
    if 'id="video-container"' not in content or "practice-grid" in content:
        return content
    m = re.search(r"(<div id=\"content\">.*?</div>)(\s*)", content, re.S)
    if not m:
        return content
    # everything after #content (exercises, scripts) is grouped
    head, tail = content[: m.end(1)], content[m.end(1):].strip()
    tail_html = f'\n<div class="practice-after">\n{tail}\n</div>' if tail else ""
    return f'<div class="practice-grid">\n{head.strip()}{tail_html}\n</div>'


# ---------------------------------------------------------------------------
# templates
# ---------------------------------------------------------------------------

def nav_html(current, chapter_heads):
    home_cur = ' aria-current="page"' if current == "index.html" else ""
    parts = [f'<ul class="nav-home"><li><a href="index.html"{home_cur}>Home / contents</a></li></ul>', "<h2>Chapters</h2>", "<ul>"]
    for i, (f, label, _key) in enumerate(CHAPTERS, 1):
        is_cur = f == current
        subs = "".join(
            f'<li><a href="{f}#{hid}">{html.escape(txt)}</a></li>'
            for tag, hid, txt in chapter_heads.get(f, []) if tag == "h2"
        )
        parts.append(
            f'<li><details{" open" if is_cur else ""}{" class=\"current\"" if is_cur else ""}>'
            f'<summary><span class="nav-num">{i}</span>'
            f'<a href="{f}"{" aria-current=\"page\"" if is_cur else ""}>{html.escape(label)}</a></summary>'
            f"<ul>{subs}</ul></details></li>"
        )
    parts.append("</ul>")
    parts.append("<h2>Practice</h2><ul>")
    for f, label, _key in PRACTICE:
        cur = ' aria-current="page"' if f == current else ""
        parts.append(f'<li><a href="{f}"{cur}>{html.escape(label)}</a></li>')
    parts.append("</ul><h2>Reference</h2><ul>")
    for f, label, _key in REFERENCE:
        cur = ' aria-current="page"' if f == current else ""
        parts.append(f'<li><a href="{f}"{cur}>{html.escape(label)}</a></li>')
    parts.append("</ul>")
    return "\n".join(parts)


def toc_lists(heads):
    if len(heads) < 2:
        return ""
    items = "".join(
        f'<li class="lvl{tag[1]}"><a href="#{hid}">{html.escape(txt)}</a></li>' for tag, hid, txt in heads
    )
    return f"<ul>{items}</ul>"


def pager_html(current):
    idx = [f for f, _l, _k in ORDER].index(current)
    prev = ORDER[idx - 1] if idx > 0 else None
    nxt = ORDER[idx + 1] if idx < len(ORDER) - 1 else None
    a = []
    if prev:
        a.append(f'<a class="prev" href="{prev[0]}"><small>Previous</small>{html.escape(prev[1])}</a>')
    else:
        a.append("<span></span>")
    if nxt:
        a.append(f'<a class="next" href="{nxt[0]}"><small>Next</small>{html.escape(nxt[1])}</a>')
    return '<nav class="pager" aria-label="Previous and next page">' + "".join(a) + "</nav>"


def page_html(name, label, key, content, chapter_heads):
    # practice pages carry their instructions at the top: no second table of contents
    heads = headings(content) if key not in ("index", "practice") else []
    toc = toc_lists(heads)
    title = f"{label} · {SITE_TITLE} · {SITE_SUB}" if name != "index.html" else f"{SITE_TITLE} · {SITE_SUB}"
    body_cls = ["page-" + os.path.splitext(name)[0]]
    if name in PREWRAP:
        body_cls.append("script-prewrap")
    if not toc:
        body_cls.append("no-toc")
    ruby_hint = (
        '<p class="ruby-hint">Transcriptions are shown above the words. Use the <b>Transcriptions</b> '
        "switch in the top bar to show them inline, or to hide them and test yourself "
        "(tap a word to reveal its transcription).</p>"
    )
    toc_inline = (
        f'<details class="toc-inline"><summary>On this page</summary>{toc}</details>' if toc else ""
    )
    toc_aside = (
        f'<aside class="toc" aria-label="On this page"><div class="toc-sticky"><h2>On this page</h2>{toc}</div></aside>'
        if toc
        else '<aside class="toc" aria-hidden="true"></aside>'
    )
    # the ruby hint sits under the chapter title rather than above it
    if "<ruby" in content:
        m = re.search(r"</h1>", content)
        if m:
            content = content[: m.end()] + "\n" + ruby_hint + content[m.end():]
        else:
            content = ruby_hint + "\n" + content
    ruby_hint = ""
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{html.escape(title)}</title>
<meta name="description" content="Study notes for the phonology part of the agrégation d'anglais: graphophonemics, stress, connected speech, intonation, SSBE and GA.">
<link rel="stylesheet" href="styles.css">
<script>try{{var m=localStorage.getItem("rubyMode");if(m)document.documentElement.setAttribute("data-ruby",m)}}catch(e){{}}</script>
</head>
<body class="{' '.join(body_cls)}" data-chapter="{key}">
<a class="skip" href="#main">Skip to content</a>
<header class="site-header">
  <button class="nav-toggle" type="button" aria-controls="site-nav" aria-expanded="false"><span class="burger"></span>Menu</button>
  <a class="brand" href="index.html">{SITE_TITLE} <span>· {SITE_SUB}</span></a>
  <div class="header-tools">
    <div class="ruby-switch" role="group" aria-label="Transcription display">
      <span class="label">Transcriptions</span>
      <button type="button" data-ruby="above" aria-pressed="true">above</button>
      <button type="button" data-ruby="inline" aria-pressed="false">inline</button>
      <button type="button" data-ruby="hidden" aria-pressed="false">quiz</button>
    </div>
  </div>
</header>
<div class="nav-backdrop"></div>
<div class="layout">
<nav id="site-nav" class="site-nav" aria-label="Site navigation">
{nav_html(name, chapter_heads)}
</nav>
<main id="main" class="content">
<article class="doc">
{ruby_hint}
{toc_inline}
<!-- content:start -->
{content}
<!-- content:end -->
</article>
{pager_html(name)}
</main>
{toc_aside}
</div>
<footer class="site-footer">Leonardo Contreras Roa · Université de Picardie Jules Verne · <a href="https://github.com/lcontrerasroa/agregation">source</a></footer>
<button class="back-to-top" type="button" aria-label="Back to top">↑</button>
<script src="site.js"></script>
</body>
</html>
"""


# ---------------------------------------------------------------------------
# index page content (kept in one place so links stay in sync with the nav)
# ---------------------------------------------------------------------------

def index_content(chapter_heads):
    cards = []
    for i, (f, label, key) in enumerate(CHAPTERS, 1):
        items = []
        for tag, hid, txt in chapter_heads.get(f, []):
            if tag == "h2":
                items.append(f'<li><a href="{f}#{hid}">{html.escape(txt)}</a></li>')
            elif tag == "h3":
                items.append(f'<li class="sub"><a href="{f}#{hid}">{html.escape(txt)}</a></li>')
        cards.append(
            f'<li class="card c-{key}"><h3><span class="num">{i}</span><a href="{f}">{html.escape(label)}</a></h3>'
            f'<ul>{"".join(items)}</ul></li>'
        )
    practice = "".join(
        f'<li class="card c-practice"><h3><a href="{f}">{html.escape(label)}</a></h3><p>{desc}</p></li>'
        for (f, label, _k), desc in zip(
            PRACTICE,
            [
                "Video + script. Graphophonemics: find the five graphic vowels in all their values.",
                "Novel excerpt. Word stress, weak forms and a prosody exercise on highlighted lines.",
                "Video + script. Phonemic transcription of the pink passages, prosody of the green ones.",
                "Video + script. SSBE vs GA contrasts, and phonetic processes you can actually hear.",
            ],
        )
    )
    reference = (
        '<li class="card c-reference"><h3><a href="consonants-vowels.html">Phonemic chart</a></h3>'
        "<p>The SSBE vowel, diphthong, triphthong and consonant symbols with a keyword for each.</p></li>"
    )
    return f"""<div class="hero">
<h1>English phonology for the agrégation</h1>
<p>Study notes for the phonology part of the <em>épreuve de linguistique</em>: the rules you need to justify a transcription, a stress pattern, a vowel value, a connected-speech process or an intonation pattern. Each chapter can be read on its own; the practice pages give you texts to work on.</p>
</div>
<h2 id="how-to-use">How to use this site</h2>
<ol class="howto">
<li>Read the chapter announced for the week before class. The left menu (or the <b>Menu</b> button on a phone) opens every chapter with its sections.</li>
<li>Learn the rules as sentences you can write down in English. The exam rewards a rule stated in full, then applied.</li>
<li>In the Graphophonemics chapter, switch the <b>Transcriptions</b> display to <em>quiz</em>: transcriptions are blurred until you tap a word. Test yourself before you check.</li>
<li>Use the practice texts to write full answers under time, then compare with the chapter.</li>
</ol>
<h2 id="table-of-contents">Chapters</h2>
<ul class="cards">
{"".join(cards)}
</ul>
<h2 id="practice-material">Practice material</h2>
<ul class="cards">
{practice}
</ul>
<h2 id="reference">Reference</h2>
<ul class="cards">
{reference}
</ul>"""


# ---------------------------------------------------------------------------
# main
# ---------------------------------------------------------------------------

def main(check=False):
    pages = {}
    for f, label, key in ORDER:
        path = os.path.join(ROOT, f)
        if not os.path.exists(path):
            print("missing:", f)
            continue
        src = read(path)
        content, _had = extract_content(src)
        if f != "index.html":
            content = clean_content(f, content)
            if key == "practice":
                content = practice_wrap(f, content)
        pages[f] = (label, key, content, src)

    chapter_heads = {f: headings(pages[f][2]) for f, _l, _k in CHAPTERS if f in pages}

    changed = 0
    for f, (label, key, content, src) in pages.items():
        if f == "index.html":
            content = index_content(chapter_heads)
        out = page_html(f, label, key, content, chapter_heads)
        if out != src:
            changed += 1
            if check:
                print("would rewrite:", f)
            else:
                write(os.path.join(ROOT, f), out)
                print("rewrote:", f)
    print(f"{changed} page(s) {'to update' if check else 'updated'}")


if __name__ == "__main__":
    main(check="--check" in sys.argv)
