#!/usr/bin/env python3
"""Browser-level inspector for RCHEP's critical language/theme controls.

Uses Chrome DevTools Protocol directly so CI needs no Node/Python browser package.
The test blocks every external site JavaScript file: the critical inline fallback
must still switch language and theme and preserve both choices across reload.
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.request
from typing import Any


def chrome_path(explicit: str | None) -> str | None:
    candidates = [
        explicit,
        os.environ.get('CHROME_PATH'),
        shutil.which('google-chrome'),
        shutil.which('google-chrome-stable'),
        shutil.which('chromium'),
        shutil.which('chromium-browser'),
        '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',
    ]
    return next((path for path in candidates if path and os.path.exists(path)), None)


def free_port() -> int:
    with socket.socket() as sock:
        sock.bind(('127.0.0.1', 0))
        return int(sock.getsockname()[1])


def json_get(url: str, timeout: float = 5, method: str = 'GET') -> Any:
    request = urllib.request.Request(url, method=method)
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return json.load(response)


class CDP:
    def __init__(self, websocket_url: str):
        # websocket-client is preinstalled on GitHub's Ubuntu image. Keep import
        # here so --help and path validation remain useful if it is absent.
        import websocket  # type: ignore[import-not-found]
        self.ws = websocket.create_connection(websocket_url, timeout=15)
        self.number = 0

    def call(self, method: str, **params: Any) -> Any:
        self.number += 1
        ident = self.number
        self.ws.send(json.dumps({'id': ident, 'method': method, 'params': params}))
        while True:
            message = json.loads(self.ws.recv())
            if message.get('id') != ident:
                continue
            if 'error' in message:
                raise RuntimeError(f'{method}: {message["error"]}')
            return message.get('result', {})

    def evaluate(self, expression: str) -> Any:
        result = self.call('Runtime.evaluate', expression=expression,
                           awaitPromise=True, returnByValue=True)
        remote = result.get('result', {})
        if remote.get('subtype') == 'error':
            raise RuntimeError(remote.get('description', 'JavaScript evaluation failed'))
        return remote.get('value')

    def wait_complete(self, timeout: float = 30) -> None:
        deadline = time.time() + timeout
        while time.time() < deadline:
            if self.evaluate('document.readyState') == 'complete':
                return
            time.sleep(0.1)
        raise TimeoutError('page did not reach document.readyState=complete')


def main() -> int:
    parser = argparse.ArgumentParser(description='رفتار دکمه‌های زبان و شب/روز را در مرورگر می‌سنجد')
    parser.add_argument('--base', default='https://rchep.ir')
    parser.add_argument('--chrome', default=None)
    parser.add_argument('--timeout', type=float, default=45)
    args = parser.parse_args()

    chrome = chrome_path(args.chrome)
    if not chrome:
        print('!! مرورگر Chrome/Chromium پیدا نشد')
        return 1

    port = free_port()
    profile = os.path.join(os.environ.get('RUNNER_TEMP', '/tmp'), f'rchep-chrome-{os.getpid()}')
    command = [
        chrome, '--headless=new', '--no-sandbox', '--disable-gpu',
        '--disable-dev-shm-usage', '--remote-allow-origins=*',
        f'--remote-debugging-port={port}', f'--user-data-dir={profile}',
        'about:blank',
    ]
    process = subprocess.Popen(command, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    cdp: CDP | None = None
    try:
        deadline = time.time() + 20
        version = None
        while time.time() < deadline:
            try:
                version = json_get(f'http://127.0.0.1:{port}/json/version')
                break
            except (OSError, urllib.error.URLError):
                time.sleep(0.2)
        if not version:
            raise RuntimeError('Chrome DevTools endpoint did not start')

        target = json_get(f'http://127.0.0.1:{port}/json/new?about:blank',
                          timeout=5, method='PUT')
        cdp = CDP(target['webSocketDebuggerUrl'])
        cdp.call('Page.enable')
        cdp.call('Network.enable')
        cdp.call('Network.setBlockedURLs', urls=[
            '*assets/js/translations.js*', '*assets/js/main.js*', '*assets/js/lucide.min.js*'
        ])

        url = args.base.rstrip('/') + '/index.html?inspector=controls'
        cdp.call('Page.navigate', url=url)
        cdp.wait_complete(args.timeout)
        cdp.evaluate('localStorage.clear()')
        cdp.call('Page.reload', ignoreCache=True)
        cdp.wait_complete(args.timeout)

        before = cdp.evaluate('''({
          fallback: window.__rchepCriticalControls === true,
          mainBooted: document.documentElement.dataset.rchepBooted || null,
          theme: document.documentElement.dataset.theme,
          lang: document.documentElement.lang,
          dir: document.documentElement.dir,
          languageButton: !!document.querySelector('#lang-toggle'),
          themeButton: !!document.querySelector('#theme-toggle')
        })''')
        failures: list[str] = []
        if not before.get('fallback'):
            failures.append('پشتیبان درون‌صفحه‌ای راه نیفتاد')
        if before.get('mainBooted'):
            failures.append('آزمون معتبر نیست: main.js با وجود مسدودسازی اجرا شد')
        if not before.get('languageButton') or not before.get('themeButton'):
            failures.append('یکی از دو دکمه در صفحه نیست')

        language = cdp.evaluate('''(() => {
          document.querySelector('#lang-toggle').click();
          return {
            lang: document.documentElement.lang,
            dir: document.documentElement.dir,
            label: document.querySelector('#lang-toggle').textContent.trim(),
            stored: localStorage.getItem('rchep_lang'),
            translated: document.querySelector('[data-en]')?.textContent.trim() || ''
          };
        })()''')
        if language.get('lang') != 'en' or language.get('dir') != 'ltr':
            failures.append('زنش دکمهٔ زبان، صفحه را انگلیسی/LTR نکرد')
        if language.get('label') != 'فارسی' or language.get('stored') != 'en':
            failures.append('برچسب یا ماندگاری زبان درست نیست')

        theme = cdp.evaluate('''(() => {
          document.querySelector('#theme-toggle').click();
          return {theme: document.documentElement.dataset.theme,
                  stored: localStorage.getItem('theme')};
        })()''')
        if theme.get('theme') != 'light' or theme.get('stored') != 'light':
            failures.append('زنش دکمهٔ نمایش، حالت روشن را فعال/ذخیره نکرد')

        cdp.call('Page.reload', ignoreCache=True)
        cdp.wait_complete(args.timeout)
        reloaded = cdp.evaluate('''({
          fallback: window.__rchepCriticalControls === true,
          theme: document.documentElement.dataset.theme,
          lang: document.documentElement.lang,
          dir: document.documentElement.dir,
          themeStored: localStorage.getItem('theme'),
          langStored: localStorage.getItem('rchep_lang')
        })''')
        if reloaded.get('theme') != 'light' or reloaded.get('lang') != 'en' or reloaded.get('dir') != 'ltr':
            failures.append('زبان/نمایش پس از بازخوانی صفحه ماندگار نماند')

        if failures:
            for failure in failures:
                print(f'!! آزمون رفتاری: {failure}')
            return 1
        print('رفتار زبان و شب/روز سالم است؛ حتی با قطع همهٔ JavaScriptهای بیرونی، و پس از بازخوانی')
        return 0
    except Exception as error:  # noqa: BLE001
        print(f'!! آزمون رفتاری اجرا نشد: {type(error).__name__}: {error}')
        return 1
    finally:
        if cdp:
            try:
                cdp.ws.close()
            except Exception:
                pass
        process.terminate()
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            process.kill()
        shutil.rmtree(profile, ignore_errors=True)


if __name__ == '__main__':
    sys.exit(main())
