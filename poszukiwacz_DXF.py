#!/usr/bin/env python3
"""
Zbiera pliki DXF o nazwie zaczynającej się od maski AIxxx-xxxx-xxx
z dysku sieciowego do jednego folderu lokalnego.

Maska (case-sensitive na "AI", spójnie z walidacją aplikacji Estymatora):
    ^AI\\d{3}-\\d{4}-\\d{3}.*\\.dxf$

Zachowanie:
    - rekurencyjne skanowanie źródła (Windows long paths obsłużone),
    - kopiowanie płaskie do jednego folderu (kolizje nazw: ostatni wygrywa),
    - log postępu + pełny log w pliku obok skopiowanych plików,
    - odporność na błędy dostępu do pojedynczych katalogów (loguje i idzie dalej).

Uruchomienie:
    python collect_ai_files.py

Opcjonalnie:
    python collect_ai_files.py --source "\\\\qnap\\Z" --dest "C:\\...\\dxf"
    python collect_ai_files.py --dry-run   # tylko lista, bez kopiowania

Wymagania: Python 3.8+.
"""
from __future__ import annotations

import argparse
import os
import re
import shutil
import sys
import time
from collections import Counter, defaultdict
from datetime import datetime


PATTERN = re.compile(r"^AI\d{3}-\d{4}-\d{3}")
NEAR_MISS_PATTERN = re.compile(r"^ai\d{3}-\d{4}-\d{3}")
EXT = ".dxf"
DEFAULT_SOURCE = r"\\qnap\Z"
DEFAULT_DEST = r"C:\Users\K.Piaskowski\Desktop\dxf"
LOG_FILENAME = "log_zbierania.txt"


def win_long_path(p: str) -> str:
    """
    Dodaje prefiks \\\\?\\ dla ścieżek >260 znaków (Windows long path).
    Na innych systemach zwraca ścieżkę bez zmian.
    """
    if sys.platform != "win32":
        return str(p)
    p = str(p)
    if p.startswith("\\\\?\\"):
        return p
    if p.startswith("\\\\"):
        return "\\\\?\\UNC\\" + p[2:]
    return "\\\\?\\" + p


def is_ai_dxf(filename: str) -> bool:
    """Czy nazwa pasuje do maski AIxxx-xxxx-xxx + .dxf (prefix 'AI' case-sensitive)."""
    if not filename.lower().endswith(EXT):
        return False
    return PATTERN.match(filename) is not None


def base_code(filename: str) -> str:
    """Zwraca rdzeń kodu (AIxxx-xxxx-xxx) z nazwy pliku, lub '' gdy brak."""
    m = PATTERN.match(filename)
    return m.group(0) if m else ""


def format_size(n: int) -> str:
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if n < 1024:
            return f"{n:.1f} {unit}"
        n /= 1024
    return f"{n:.1f} PB"


def scan(source: str, log_fn) -> tuple[list[str], Counter, list[tuple[str, str]]]:
    """
    Rekurencyjnie skanuje źródło, zwraca (lista_pasujących, statystyki, błędy).
    """
    results: list[str] = []
    stats = Counter()
    errors: list[tuple[str, str]] = []

    def onerror(e):
        errors.append((e.filename or "?", str(e)))
        stats["errors"] += 1

    dirs_visited = 0
    last_log = time.time()

    for root, _dirs, files in os.walk(win_long_path(source), onerror=onerror):
        dirs_visited += 1
        for f in files:
            stats["files_seen"] += 1
            if is_ai_dxf(f):
                results.append(os.path.join(root, f))
                stats["matched"] += 1
            elif f.lower().endswith(EXT) and NEAR_MISS_PATTERN.match(f):
                # Np. "ai029-0421-013.dxf" — pominięte, ale zgłoszone w podsumowaniu.
                stats["near_miss"] += 1

        if dirs_visited % 100 == 0 and (time.time() - last_log) >= 5:
            log_fn(f"  ... skanuję: {dirs_visited:>5} katalogów | "
                   f"{stats['files_seen']:>7} plików | "
                   f"{stats['matched']:>4} dopasowań")
            last_log = time.time()

    return results, stats, errors


def copy_files(files: list[str], dest: str, log_fn) -> tuple[Counter, list[tuple[str, str]], dict[str, list[str]]]:
    """
    Kopiuje pliki do dest (płasko, nadpisując kolizje).
    Zwraca (statystyki, błędy, kolizje {nazwa: [src1, src2, ...]}).
    """
    stats = Counter()
    errors: list[tuple[str, str]] = []
    by_name: dict[str, list[str]] = defaultdict(list)

    dest_real = os.path.abspath(dest)
    os.makedirs(win_long_path(dest_real), exist_ok=True)

    for i, src in enumerate(files, 1):
        name = os.path.basename(src)
        by_name[name].append(src)
        target = os.path.join(dest_real, name)
        try:
            if os.path.exists(target):
                stats["overwritten"] += 1
            shutil.copy2(win_long_path(src), win_long_path(target))
            stats["copied"] += 1
        except OSError as ex:
            errors.append((src, str(ex)))
            stats["copy_errors"] += 1

        if i % 50 == 0:
            log_fn(f"  ... skopiowano {i}/{len(files)}")

    collisions = {n: srcs for n, srcs in by_name.items() if len(srcs) > 1}
    return stats, errors, collisions


def _save_log(dest: str, lines: list[str]) -> None:
    """Zapisuje log do pliku w katalogu docelowym."""
    log_path = os.path.join(dest, LOG_FILENAME)
    try:
        with open(win_long_path(log_path), "w", encoding="utf-8") as f:
            f.write("\n".join(lines) + "\n")
    except OSError as ex:
        print(f"⚠️ Nie udało się zapisać logu: {ex}", file=sys.stderr)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Zbiera pliki DXF o masce AIxxx-xxxx-xxx do jednego folderu."
    )
    parser.add_argument("--source", default=DEFAULT_SOURCE,
                        help=f"Katalog źródłowy (domyślnie: {DEFAULT_SOURCE})")
    parser.add_argument("--dest", default=DEFAULT_DEST,
                        help=f"Katalog docelowy (domyślnie: {DEFAULT_DEST})")
    parser.add_argument("--dry-run", action="store_true",
                        help="Tylko pokaż listę, nie kopiuj.")
    args = parser.parse_args()

    start = time.time()
    log_lines: list[str] = []

    def log(msg: str) -> None:
        print(msg, flush=True)
        log_lines.append(msg)

    try:
        log("=" * 72)
        log(f"Start:   {datetime.now().isoformat(timespec='seconds')}")
        log(f"Źródło:  {args.source}")
        log(f"Cel:     {args.dest}")
        log(f"Maska:   ^{PATTERN.pattern}.*\\.dxf$  (prefiks 'AI' case-sensitive)")
        log(f"Tryb:    {'DRY-RUN (bez kopiowania)' if args.dry_run else 'kopiowanie'}")
        log("=" * 72)

        if not os.path.isdir(win_long_path(args.source)):
            log(f"❌ Katalog źródłowy nie istnieje lub niedostępny: {args.source}")
            return 1

        log("\n📡 Skanowanie źródła...")
        files, scan_stats, scan_errors = scan(args.source, log)

        codes = {base_code(os.path.basename(f)) for f in files}
        log(f"\n✅ Znaleziono {scan_stats['matched']} pasujących plików "
            f"(unikalnych kodów: {len(codes)}).")
        log(f"   Przeskanowano: {scan_stats['files_seen']} plików razem.")
        if scan_stats["near_miss"]:
            log(f"   ⚠️  {scan_stats['near_miss']} plików 'prawie pasuje' "
                f"(np. 'ai...' zamiast 'AI...') — pominięte, aplikacja wymaga 'AI'.")
        if scan_errors:
            log(f"   ⚠️  {len(scan_errors)} błędów dostępu (szczegóły w podsumowaniu).")

        if not files:
            log("\n⚠️ Brak plików do skopiowania.")
            return 0

        if args.dry_run:
            log("\nDRY-RUN — lista znalezionych plików:")
            for f in files:
                log(f"   {f}")
            log("\n(Nie kopiuję — tryb dry-run.)")
            return 0

        log(f"\n📥 Kopiowanie {len(files)} plików do: {args.dest}")
        copy_stats, copy_errors, collisions = copy_files(files, args.dest, log)

        elapsed = time.time() - start
        log("\n" + "=" * 72)
        log("PODSUMOWANIE")
        log("=" * 72)
        log(f"Czas:                 {elapsed:.1f} s")
        log(f"Znaleziono plików:    {scan_stats['matched']}")
        log(f"Unikalnych kodów:     {len(codes)}")
        log(f"Skopiowano:           {copy_stats['copied']}")
        if copy_stats["overwritten"]:
            log(f"Nadpisano (kolizje):  {copy_stats['overwritten']}")
        if copy_errors:
            log(f"Błędów kopiowania:    {len(copy_errors)}")

        if collisions:
            log(f"\n⚠️  {len(collisions)} nazw wystąpiło wielokrotnie (ostatni wygrał):")
            for name, srcs in sorted(collisions.items())[:20]:
                log(f"   • {name}: {len(srcs)} źródeł")
            if len(collisions) > 20:
                log(f"   ... i {len(collisions) - 20} więcej (pełna lista w logu niżej).")

        if scan_errors or copy_errors:
            log("\n⚠️  Błędy:")
            all_errors = scan_errors + copy_errors
            for path, err in all_errors[:20]:
                log(f"   • {path}: {err}")
            if len(all_errors) > 20:
                log(f"   ... i {len(all_errors) - 20} więcej.")

        return 2 if copy_errors else 0
    finally:
        try:
            _save_log(args.dest, log_lines)
        except Exception as ex:
            print(f"⚠️ Nie udało się zapisać logu: {ex}", file=sys.stderr)
        print(f"\n📄 Log: {os.path.join(args.dest, LOG_FILENAME)}", flush=True)


if __name__ == "__main__":
    try:
        sys.exit(main() or 0)
    except KeyboardInterrupt:
        print("\n\n⛔ Przerwano przez użytkownika (Ctrl+C).", file=sys.stderr)
        sys.exit(130)