#!/usr/bin/env python3
"""Guardrail for the asset-loading order and the JS-free poster fallback.

Regression this locks down: main.js owns all interactivity (poster hover preview,
lightbox, theme, menu). It used to be a synchronous, parser-blocking script queued
behind the 450 KB lucide.min.js, so on a slow link it executed late or never and the
poster hover did nothing at all. These checks fail the CI build if any page reverts to
a blocking/reordered script block, drops the boot guard, or loses the --poster
variable that drives the CSS-only fallback preview.
"""
import re
import sys
import pathlib

ROOT = pathlib.Path(__file__).resolve().parent.parent
HTML = sorted(ROOT.glob('*.html'))
failures = []

SCRIPT_RE = re.compile(r'<script\b[^>]*src="assets/js/([a-z.]+\.js)(\?v=\d+)?"[^>]*>', re.I)
BTN_RE = re.compile(r'<(?:button|a|div)\b[^>]*class="[^"]*poster-btn[^"]*"[^>]*>', re.I)
POSTER_RE = re.compile(r"data-poster=\"([^\"]+)\"")
VAR_RE = re.compile(r"--poster:url\(['\"]?([^'\")]+)['\"]?\)")

for page in HTML:
    txt = page.read_text(encoding='utf-8')
    scripts = SCRIPT_RE.findall(txt)
    names = [s[0] for s in scripts]

    for name, ver in scripts:
        if not ver:
            failures.append(f'{page.name}: {name} has no cache-buster (?v=N)')
    for tag in re.findall(r'<script\b[^>]*src="assets/js/[^"]+"[^>]*>', txt, re.I):
        if 'defer' not in tag and 'async' not in tag:
            failures.append(f'{page.name}: blocking script found -> {tag.strip()[:80]}')

    if 'main.js' in names and 'lucide.min.js' in names:
        if names.index('main.js') > names.index('lucide.min.js'):
            failures.append(f'{page.name}: lucide.min.js must not precede main.js '
                            f'(interactivity would wait on the icon bundle)')

    if 'assets/css/style.css' in txt and not re.search(r'style\.css\?v=\d+', txt):
        failures.append(f'{page.name}: style.css without cache-buster')

    for btn in BTN_RE.findall(txt):
        dm = POSTER_RE.search(btn)
        if not dm:
            continue
        poster = dm.group(1)
        pm = VAR_RE.search(btn)
        if not pm:
            failures.append(f'{page.name}: .poster-btn[{poster}] has no --poster fallback')
            continue
        if not pm.group(1).startswith('/'):
            # A relative URL inside a custom property resolves against the *stylesheet*
            # that consumes it (assets/css/), which 404s — it must be root-relative.
            failures.append(f'{page.name}: --poster must be root-relative -> {pm.group(1)}')
        if not (ROOT / pm.group(1).lstrip('/')).exists():
            failures.append(f'{page.name}: --poster target missing on disk -> {pm.group(1)}')

main = (ROOT / 'assets/js/main.js').read_text(encoding='utf-8')
if 'dataset.rchepBooted' not in main:
    failures.append('main.js: missing duplicate-boot guard (dataset.rchepBooted)')
if "readyState === 'loading'" not in main:
    failures.append('main.js: missing late-execution boot (readyState check)')
if "classList.add('js-posters')" not in main:
    failures.append('main.js: never marks html.js-posters, CSS fallback would double up')

css = (ROOT / 'assets/css/style.css').read_text(encoding='utf-8')
if 'html.js-posters .poster-btn:hover::after' not in css:
    failures.append('style.css: JS-free fallback preview is not disabled once JS is live')
if '.poster-btn[style*="--poster"]:hover::after' not in css:
    failures.append('style.css: JS-free fallback preview rule is missing')

if failures:
    print('LOAD-ORDER GUARDRAIL FAILED')
    for f in failures:
        print(' -', f)
    sys.exit(1)

print(f'OK: load order, boot guard and CSS fallback verified across {len(HTML)} pages')
