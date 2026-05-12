"""
Pre-descarga todas las imágenes referenciadas en los CSVs a la carpeta `images/`.
Cada imagen se guarda con un nombre derivado del hash de su URL.
También genera `url_map.json` con la correspondencia URL -> archivo local.
"""
import csv
import hashlib
import json
import os
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import requests

ROOT = Path(__file__).parent
PARENT = ROOT.parent
IMG_DIR = ROOT / "images"
URL_MAP_PATH = ROOT / "url_map.json"

SINGLE_CSV = PARENT / "SingleLabelStudioGPT_JorgeDavidBustamantePino.csv"
MULTI_CSV = PARENT / "MultiLabelStudioGEMINI_JorgeDavidBustamantePino.csv"


def url_to_filename(url: str) -> str:
    h = hashlib.sha1(url.encode("utf-8")).hexdigest()[:16]
    ext = ".png"
    if "." in url.rsplit("/", 1)[-1]:
        ext_candidate = "." + url.rsplit(".", 1)[-1].split("?")[0].lower()
        if ext_candidate in {".png", ".jpg", ".jpeg", ".webp", ".gif"}:
            ext = ext_candidate
    return f"{h}{ext}"


def collect_urls():
    urls = set()
    if SINGLE_CSV.exists():
        with SINGLE_CSV.open(encoding="utf-8-sig", newline="") as f:
            for row in csv.DictReader(f):
                if row.get("image"):
                    urls.add(row["image"].strip())
    if MULTI_CSV.exists():
        with MULTI_CSV.open(encoding="utf-8-sig", newline="") as f:
            for row in csv.DictReader(f):
                for col in ("img_1", "img_2", "img_3", "img_4"):
                    if row.get(col):
                        urls.add(row[col].strip())
    return sorted(urls)


def download_one(url: str, dest: Path) -> tuple[str, str | None]:
    if dest.exists() and dest.stat().st_size > 0:
        return url, None
    try:
        r = requests.get(url, timeout=30)
        r.raise_for_status()
        dest.write_bytes(r.content)
        return url, None
    except Exception as e:
        return url, f"{type(e).__name__}: {e}"


def main():
    IMG_DIR.mkdir(exist_ok=True)
    urls = collect_urls()
    print(f"Total URLs únicas a descargar: {len(urls)}")

    url_map: dict[str, str] = {}
    for url in urls:
        url_map[url] = url_to_filename(url)
    URL_MAP_PATH.write_text(json.dumps(url_map, ensure_ascii=False, indent=2), encoding="utf-8")

    to_download = [(url, IMG_DIR / url_map[url]) for url in urls]
    pending = [(u, d) for u, d in to_download if not (d.exists() and d.stat().st_size > 0)]
    print(f"Ya descargadas: {len(to_download) - len(pending)}. Pendientes: {len(pending)}.")

    if not pending:
        print("Listo, no hay nada que descargar.")
        return

    errors: list[tuple[str, str]] = []
    done = 0
    with ThreadPoolExecutor(max_workers=16) as ex:
        futs = {ex.submit(download_one, u, d): u for u, d in pending}
        for fut in as_completed(futs):
            url, err = fut.result()
            done += 1
            if err:
                errors.append((url, err))
            if done % 50 == 0 or done == len(pending):
                print(f"  {done}/{len(pending)} descargadas ({len(errors)} errores)")

    if errors:
        err_path = ROOT / "download_errors.txt"
        err_path.write_text("\n".join(f"{u}\t{e}" for u, e in errors), encoding="utf-8")
        print(f"\nHubo {len(errors)} errores. Ver {err_path}")
        sys.exit(1)
    print("\nDescarga completada sin errores.")


if __name__ == "__main__":
    main()
