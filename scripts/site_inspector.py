#!/usr/bin/env python3
"""بازرس بیرونی تارنمای rchep.ir — پس از هر انتشار، خودِ سایت زنده را می‌سنجد.

کارکرد: صفحات منتشرشده را با منبع همین مخزن مقایسه می‌کند و سلامت کارت‌ها،
پوسترها، پیش‌نمایش‌ها، ترتیب اسکریپت‌ها و پیوندهای لنگر را بیرون از سایت
بررسی می‌کند. فقط در صورت ایراد، پیام می‌دهد و با کد ۱ بیرون می‌آید
(تا کارگاه CI سرخ شود و برای کاربر خبر برود).

نمونه:
    python3 scripts/site_inspector.py --base https://rchep.ir
    python3 scripts/site_inspector.py --base http://127.0.0.1:8899 --no-compare
"""
from __future__ import annotations

import argparse
import hashlib
import os
import re
import sys
import time
import urllib.error
import urllib.request

MAX_PREVIEW_BYTES = 160 * 1024
MIN_SHRINK = 1.5
MIN_POSTER_BYTES = 40 * 1024
LOGO_MAX_DIM = 600          # تصویر کوچک‌تر از این، اگر مربع‌گونه باشد، آرم است
LOGO_SQUARE_RATIO = 1.35

PAGE_PATTERN = re.compile(r'data-poster="([^"]+)"')
TAG_PATTERN = re.compile(r'<(?:button|a)\b[^>]*\bposter-btn\b[^>]*?>', re.S)
VAR_PATTERN = re.compile(r"--poster\s*:\s*url\(\s*['\"]?([^'\")]+)['\"]?\s*\)")
PREVIEW_ATTR_PATTERN = re.compile(r'data-preview="([^"]+)"')
PRELOAD_PATTERN = re.compile(r'<link rel="preload" as="image" href="([^"]+)">')
MAINJS_PATTERN = re.compile(r'assets/js/main\.js\?v=(\d+)')
STYLE_PATTERN = re.compile(r'assets/css/style\.css\?v=(\d+)')


def card_fields(tag: str) -> tuple[str | None, str | None, str | None]:
    """از یک برچسب کارت پوستر: (data-poster، پیش‌نمایش، مقدار --poster) را می‌کشد."""
    poster_m = PAGE_PATTERN.search(tag)
    preview_m = PREVIEW_ATTR_PATTERN.search(tag)
    var_m = VAR_PATTERN.search(tag)
    poster = poster_m.group(1) if poster_m else None
    preview_attr = preview_m.group(1) if preview_m else None
    var = var_m.group(1).strip() if var_m else None
    return poster, preview_attr, var


# ---------------------------------------------------------------- شبکه

class Fetcher:
    """واکشی مقاوم: بی‌فشرده‌سازی، بدون کش، با تلاش دوباره و سنجش بریدگی بدنه."""

    def __init__(self, attempts: int = 4, timeout: int = 45):
        self.attempts = attempts
        self.timeout = timeout
        self.log: list[str] = []

    def get(self, url: str) -> tuple[int, dict, bytes]:
        last = 'unknown'
        base, sep = (url.split('#')[0], '&' if '?' in url else '?')
        for attempt in range(self.attempts):
            probe = f'{base}{sep}cb={int(time.time() * 1000)}{attempt}'
            req = urllib.request.Request(probe, headers={
                'Accept-Encoding': 'identity',
                'Cache-Control': 'no-cache',
                'User-Agent': 'rchep-inspector/1.0',
            })
            try:
                with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                    body = resp.read()
                    declared = resp.headers.get('Content-Length') or resp.headers.get('content-length')
                    if declared is not None and len(body) != int(declared):
                        last = f'بدنهٔ بریده: {len(body)} از {declared} بایت'
                        self.log.append(f'{url} — {last} (تلاش {attempt + 1})')
                        time.sleep(3)
                        continue
                    return resp.status, {k.lower(): v for k, v in resp.headers.items()}, body
            except urllib.error.HTTPError as exc:
                hdrs = {k.lower(): v for k, v in (exc.headers or {}).items()} if hasattr(exc.headers, 'items') else {}
                return exc.code, hdrs, exc.read() if exc.fp else b''
            except Exception as exc:                      # noqa: BLE001
                last = f'{type(exc).__name__}: {exc}'
                self.log.append(f'{url} — {last} (تلاش {attempt + 1})')
                time.sleep(3)
        raise RuntimeError(f'واکشی ناموفق: {url} — {last}')


def image_size(data: bytes) -> tuple[int, int] | None:
    """ابعاد JPEG/PNG را بدون کتابخانهٔ بیرونی می‌خواند."""
    if data[:8] == b'\x89PNG\r\n\x1a\n' and data[12:16] == b'IHDR':
        return int.from_bytes(data[16:20], 'big'), int.from_bytes(data[20:24], 'big')
    if data[:2] == b'\xff\xd8':
        i = 2
        while i + 9 < len(data):
            if data[i] != 0xFF:
                i += 1
                continue
            marker = data[i + 1]
            if marker in (0xD8, 0x01) or 0xD0 <= marker <= 0xD7:
                i += 2
                continue
            length = int.from_bytes(data[i + 2:i + 4], 'big')
            if marker in (0xC0, 0xC1, 0xC2, 0xC3, 0xC5, 0xC6, 0xC7,
                          0xC9, 0xCA, 0xCB, 0xCD, 0xCE, 0xCF):
                height = int.from_bytes(data[i + 5:i + 7], 'big')
                width = int.from_bytes(data[i + 7:i + 9], 'big')
                return width, height
            i += 2 + length
    return None


# ---------------------------------------------------------------- بررسی

class Report:
    def __init__(self) -> None:
        self.problems: list[str] = []
        self.checks = 0

    def ok(self) -> None:
        self.checks += 1

    def fail(self, message: str) -> None:
        self.checks += 1
        self.problems.append(message)


def preview_url(poster: str) -> str:
    return re.sub(r'\.[a-zA-Z0-9]+$', '', poster) + '-preview.jpg'


def local(path: str) -> str:
    return os.path.join(ROOT, path.lstrip('/'))


def md5(data: bytes) -> str:
    return hashlib.md5(data).hexdigest()


def main() -> int:
    global ROOT
    parser = argparse.ArgumentParser(description='بازرس بیرونی rchep.ir')
    parser.add_argument('--base', default='https://rchep.ir')
    parser.add_argument('--repo', default=os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    parser.add_argument('--no-compare', action='store_true',
                        help='مقایسهٔ زنده با پرونده‌های همین مخزن را انجام نده')
    parser.add_argument('--report', default=None, help='نوشتن گزارش در این پرونده')
    parser.add_argument('--attempts', type=int, default=4)
    parser.add_argument('--deploy-wait', type=int, default=3,
                        help='چند بار برای رسیدن انتشار تازه به سایت صبر شود')
    parser.add_argument('--deploy-sleep', type=float, default=25.0,
                        help='فاصلهٔ صبر میان بازخوانی‌های انتشار (ثانیه)')
    args = parser.parse_args()

    ROOT = os.path.abspath(args.repo)
    base = args.base.rstrip('/')
    net = Fetcher(attempts=args.attempts)
    rep = Report()
    pages = sorted(p for p in os.listdir(ROOT) if p.endswith('.html'))
    if not pages:
        print('!! هیچ صفحهٔ HTML در مخزن پیدا نشد')
        return 1

    print(f'بازرس rchep.ir — پایه: {base} — {len(pages)} صفحه — '
          f'{time.strftime("%Y-%m-%d %H:%M:%S")}')

    live_html: dict[str, str] = {}
    for page in pages:
        url = f'{base}/{page}'
        try:
            status, headers, body = net.get(url)
        except RuntimeError as exc:
            rep.fail(f'!! {page}: سایت زنده پاسخ نداد — {exc}')
            continue
        if status != 200:
            rep.fail(f'!! {page}: کد پاسخ {status} (انتظار ۲۰۰)')
            continue
        text = body.decode('utf-8', 'replace')
        live_html[page] = text
        rep.ok()
        if not args.no_compare and os.path.isfile(local(page)):
            want = open(local(page), 'rb').read()
            # انتشار تازه چند لحظه تا رسیدن به لبه‌های گیت‌هاب پیجز فاصله دارد؛
            # برای پرهیز از هشدار کاذب، چند بار بازخوانی می‌کنیم.
            for wait_no in range(max(1, args.deploy_wait)):
                if md5(text.encode('utf-8')) == md5(want):
                    break
                if wait_no == max(1, args.deploy_wait) - 1:
                    break
                print(f'   ... {page}: نسخهٔ زنده هنوز تازه نیست؛ '
                      f'{args.deploy_sleep:g} ثانیه صبر و بازخوانی')
                time.sleep(args.deploy_sleep)
                try:
                    st2, _h2, b2 = net.get(url)
                except RuntimeError as exc:
                    net.log.append(f'{url} — بازخوانی انتشار: {exc}')
                    continue
                if st2 == 200:
                    body, text = b2, b2.decode('utf-8', 'replace')
                    live_html[page] = text
            if md5(text.encode('utf-8')) != md5(want):
                extra = f' (زنده {len(text.encode("utf-8"))} بایت / مخزن {len(want)} بایت)'
                if len(text.encode('utf-8')) < len(want):
                    extra += ' — احتمالاً بدنهٔ صفحه بریده یا انتشار عقب است'
                rep.fail(f'!! {page}: نسخهٔ منتشرشده با مخزن یکی نیست{extra}')
            else:
                rep.ok()

    # --- سلامت ساختاری هر صفحه
    biggest_version = 0
    for page in pages:
        if os.path.isfile(local(page)):
            m = MAINJS_PATTERN.search(open(local(page), encoding='utf-8').read())
            if m:
                biggest_version = max(biggest_version, int(m.group(1)))

    for page, text in live_html.items():
        m = MAINJS_PATTERN.search(text)
        if not m:
            rep.fail(f'!! {page}: ارجاع به assets/js/main.js?v=… پیدا نشد')
        elif int(m.group(1)) != biggest_version:
            rep.fail(f'!! {page}: نگارش main.js روی سایت v{m.group(1)} است '
                     f'ولی مخزن v{biggest_version} — کش مرورگر کهنه می‌ماند')
        else:
            rep.ok()

        if not STYLE_PATTERN.search(text):
            rep.fail(f'!! {page}: ارجاع به assets/css/style.css?v=… پیدا نشد')

        # ترتیب و حالت اسکریپت‌ها: main.js باید defer و پیش از lucide باشد
        tags = re.findall(r'<script[^>]*src="[^"]*"[^>]*>', text)
        idx_main = next((i for i, t in enumerate(tags) if 'main.js' in t), None)
        idx_lucide = next((i for i, t in enumerate(tags) if 'lucide' in t), None)
        if idx_main is None:
            pass
        elif 'defer' not in tags[idx_main]:
            rep.fail(f'!! {page}: main.js بدون defer — بارگذاری صفحه را می‌بندد')
        elif idx_lucide is not None and idx_main > idx_lucide:
            rep.fail(f'!! {page}: main.js بعد از lucide.min.js می‌آید — '
                     'خرامش پوستر دیر فعال می‌شود')
        else:
            rep.ok()

        # شناسه‌های تکراری
        ids = re.findall(r'\sid="([^"]+)"', text)
        dupes = sorted({i for i in ids if ids.count(i) > 1})
        if dupes:
            rep.fail(f'!! {page}: شناسهٔ تکراری {", ".join(dupes)}')
        else:
            rep.ok()

        # پیش‌بارگذاری پیش‌نمایش پوستر سمینار جاری
        tags_all = TAG_PATTERN.findall(text)
        if tags_all:
            scope = re.search(r'id="hep-upcoming"(.*?)(?:</section>|$)', text, re.S)
            scoped = TAG_PATTERN.findall(scope.group(1)) if scope else []
            first = (scoped or tags_all)[0]
            _, pv_attr, pv_var = card_fields(first)
            href = pv_attr or pv_var
            if href and not href.startswith('/'):
                href = '/' + href
            preloads = PRELOAD_PATTERN.findall(text)
            if href and href not in preloads:
                rep.fail(f'!! {page}: پیش‌بارگذاری پیش‌نمایش سمینار جاری ({href}) در <head> '
                         'نیست — روی پیوند کند خرامش دیر ظاهر می‌شود')
            else:
                rep.ok()

    # --- پوسترها و پیش‌نمایش‌هاشان
    seen: set[tuple[str, str]] = set()
    for page, text in live_html.items():
        for tag in TAG_PATTERN.findall(text):
            poster, pv_attr, pv_var = card_fields(tag)
            if not poster:
                rep.fail(f'!! {page}: کارت پوستر بدون data-poster')
                continue
            mismatch = None
            if pv_var and not pv_var.startswith('/'):
                mismatch = (f'مقدار --poster نسبی است ({pv_var}) — در برابر شیوه‌نامهٔ '
                            'assets/css/ حل می‌شود و ۴۰۴ می‌گیرد')
            elif pv_var and (os.path.basename(pv_var)
                             != os.path.basename(preview_url('/' + poster.lstrip('./')))):
                mismatch = (f'--poster ({pv_var}) با پوستر همین کارت ({poster}) یکی نیست — '
                            'خرامش پوستر سمینار دیگری را نشان می‌دهد')
            if mismatch:
                rep.fail(f'!! {page}: {mismatch}')
                continue

            poster_path = '/' + poster.lstrip('./')
            preview_path = pv_attr or pv_var or preview_url(poster_path)
            if preview_path.startswith('./'):
                preview_path = '/' + preview_path[2:]
            if not preview_path.startswith('/'):
                preview_path = '/' + preview_path
            if (poster_path, preview_path) in seen:
                continue
            seen.add((poster_path, preview_path))

            try:
                status, headers, data = net.get(f'{base}{poster_path}')
            except RuntimeError as exc:
                rep.fail(f'!! پوستر {poster_path}: دریافت نشد — {exc}')
                continue
            if status != 200:
                rep.fail(f'!! پوستر {poster_path}: کد پاسخ {status}')
                continue
            ctype = (headers.get('content-type') or '').lower()
            if not ctype.startswith('image/'):
                rep.fail(f'!! پوستر {poster_path}: نوع محتوا {ctype or "نامعلوم"} است، نه تصویر')
                continue
            if len(data) < MIN_POSTER_BYTES:
                rep.fail(f'!! پوستر {poster_path}: تنها {len(data) // 1024}KB — '
                         'احتمالاً آرم/تصویر جانبی به‌جای پوستر ذخیره شده است')
                continue
            dims = image_size(data)
            if dims:
                w, h = dims
                ratio = max(w, h) / max(1, min(w, h))
                if max(w, h) <= LOGO_MAX_DIM and ratio <= LOGO_SQUARE_RATIO:
                    rep.fail(f'!! پوستر {poster_path}: {w}×{h} مربع‌گونه و کوچک است — '
                             'شبیه آرم است، نه پوستر سمینار')
                    continue
            rep.ok()

            try:
                pstatus, _, pdata = net.get(f'{base}{preview_path}')
            except RuntimeError as exc:
                rep.fail(f'!! پیش‌نمایش {preview_path}: دریافت نشد — {exc}')
                continue
            if pstatus != 200:
                rep.fail(f'!! پیش‌نمایش {preview_path}: کد پاسخ {pstatus} — خرامش روی کارت '
                         'تصویر نشان نمی‌دهد')
            elif len(pdata) > MAX_PREVIEW_BYTES:
                rep.fail(f'!! پیش‌نمایش {preview_path}: {len(pdata) // 1024}KB '
                         f'(سقف {MAX_PREVIEW_BYTES // 1024}KB) — روی پیوند کند خرامش دیر می‌شود')
            elif len(pdata) * MIN_SHRINK > len(data):
                rep.fail(f'!! پیش‌نمایش {preview_path}: به‌قدر کافی سبک‌تر از اصل نیست '
                         f'({len(pdata) // 1024}KB در برابر {len(data) // 1024}KB)')
            else:
                pdims = image_size(pdata)
                if pdims is None:
                    rep.fail(f'!! پیش‌نمایش {preview_path}: سرصفحهٔ تصویر خوانده نشد — '
                             'فایل خراب است یا جای تصویر، متن ذخیره شده')
                elif dims and max(pdims) < 0.3 * max(dims):
                    rep.fail(f'!! پیش‌نمایش {preview_path}: {pdims[0]}×{pdims[1]} در برابر '
                             f'اصل {dims[0]}×{dims[1]} — بیش از اندازه کوچک است')
                else:
                    rep.ok()

    # --- پشتیبان CSS خرامش و منطق گرم‌کردن
    try:
        _, _, css = net.get(f'{base}/assets/css/style.css?v=0')
        css_text = css.decode('utf-8', 'replace')
        if '--poster' not in css_text or ':hover::after' not in css_text:
            rep.fail('!! style.css: قاعدهٔ پشتیبان خرامش پوستر (--poster/:hover::after) نیست')
        else:
            rep.ok()
    except RuntimeError as exc:
        rep.fail(f'!! style.css دریافت نشد — {exc}')

    try:
        _, _, js = net.get(f'{base}/assets/js/main.js?v=0')
        js_text = js.decode('utf-8', 'replace')
        for needle, why in (('warmPosters', 'گرم‌کردن پیش‌نمایش'),
                            ('preloadPoster(previewPath(', 'گرم‌کردن تنها فایل پیش‌نمایش'),
                            ('rchepBooted', 'گارد بوت یک‌بارهٔ رویدادها')):
            if needle not in js_text:
                rep.fail(f'!! main.js: «{needle}» ({why}) نیست — منطق خرامش پوستر ناقص است')
            else:
                rep.ok()
    except RuntimeError as exc:
        rep.fail(f'!! main.js دریافت نشد — {exc}')

    # --- پیوندهای لنگر درون‌سایتی
    anchors: set[tuple[str, str]] = set()
    for page, text in live_html.items():
        for href in re.findall(r'href="([a-z0-9_.-]+\.html)#([A-Za-z0-9_.:-]+)"', text, re.I):
            anchors.add(href)
    for target, anchor in sorted(anchors):
        text = live_html.get(target)
        if text is None:
            rep.fail(f'!! پیوند به صفحهٔ ناموجود: {target}#{anchor}')
        elif f'id="{anchor}"' not in text:
            rep.fail(f'!! لنگر گمشده: {target}#{anchor} — این پیوند به جایی نمی‌رود')
        else:
            rep.ok()

    # --- گزارش
    lines = [f'بازرس تارنما — {rep.checks} بررسی روی {len(live_html)} صفحهٔ زنده']
    if rep.problems:
        lines.append(f'یافته‌ها ({len(rep.problems)}):')
        lines.extend(rep.problems)
    else:
        lines.append('همه‌چیز سالم است: کارت‌ها، پوسترها، پیش‌نمایش‌ها، ترتیب اسکریپت‌ها')
    if net.log:
        lines.append('یادداشت شبکه:')
        lines.extend(f'  - {entry}' for entry in net.log[-6:])
    out = '\n'.join(lines)
    print(out)
    if args.report:
        with open(args.report, 'w', encoding='utf-8') as fh:
            fh.write(out + '\n')
    return 1 if rep.problems else 0


if __name__ == '__main__':
    sys.exit(main())
