#!/usr/bin/env bash
# One-time setup per session: fonts (via npm), qrcode + playwright (pip), a Chromium binary.
# Safe to run repeatedly; it skips anything already present.
set -e
HERE="$(cd "$(dirname "$0")/.." && pwd)"
FONTS="$HERE/fonts"
mkdir -p "$FONTS"
cd "$FONTS"
for pkg in fraunces instrument-serif inter; do
  if [ ! -d "$pkg" ]; then
    npm pack "@fontsource/$pkg" >/dev/null 2>&1
    tar xzf fontsource-$pkg-*.tgz && mv package "$pkg" && rm -f fontsource-$pkg-*.tgz
  fi
done
python3 -c "import qrcode" 2>/dev/null || pip install qrcode --break-system-packages -q 2>/dev/null || pip install qrcode -q
python3 -c "import playwright" 2>/dev/null || pip install playwright --break-system-packages -q 2>/dev/null || pip install playwright -q
python3 -c "import PIL" 2>/dev/null || pip install pillow --break-system-packages -q 2>/dev/null || pip install pillow -q
# Chromium: prefer a preinstalled one, otherwise let Playwright fetch it.
if ! ls /opt/pw-browsers/*/chrome-linux*/chrome >/dev/null 2>&1 && ! ls ~/.cache/ms-playwright/chromium-*/chrome-linux*/chrome >/dev/null 2>&1; then
  python3 -m playwright install chromium >/dev/null 2>&1 || true
fi
echo "setup ok"
