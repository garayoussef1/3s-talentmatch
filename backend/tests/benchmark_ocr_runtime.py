import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from app.services.extraction.cv_extractor import CVExtractor


def benchmark(paths):
    extractor = CVExtractor()
    results = []

    for path in paths:
        start = time.perf_counter()
        result = extractor.extract(str(path))
        elapsed = time.perf_counter() - start
        pages = result.get("pages", 1) or 1
        results.append({
            "file": path.name,
            "success": result.get("success", False),
            "method": result.get("method", ""),
            "engine": result.get("engine", ""),
            "pages": pages,
            "seconds": elapsed,
            "seconds_per_page": elapsed / pages,
            "chars": len(result.get("text", "") or ""),
            "error": result.get("error"),
        })

    return results


def print_report(results):
    total = len(results)
    success = sum(1 for r in results if r["success"])
    success_rate = (success / total * 100) if total else 0
    avg_seconds_per_page = (
        sum(r["seconds_per_page"] for r in results) / total if total else 0
    )

    print("\n" + "=" * 90)
    print("BENCHMARK OCR - TALENTMATCH")
    print("=" * 90)
    print(f"Fichiers testés        : {total}")
    print(f"Succès extraction      : {success}/{total} ({success_rate:.1f}%)")
    print(f"Temps moyen / page     : {avg_seconds_per_page:.2f}s")
    print("=" * 90)

    for r in results:
        status = "OK" if r["success"] else "FAIL"
        print(
            f"[{status}] {r['file']:<24} | method={r['method']:<10} | "
            f"engine={str(r['engine']):<9} | pages={r['pages']} | "
            f"sec/page={r['seconds_per_page']:.2f} | chars={r['chars']}"
        )
        if r["error"]:
            print(f"       error: {r['error']}")

    print("=" * 90)
    print("CRITÈRES")
    print("- Taux succès > 85%     :", "OK" if success_rate > 85 else "NOK")
    print("- Temps < 10s / page    :", "OK" if avg_seconds_per_page < 10 else "NOK")
    print("=" * 90)


def main():
    repo = Path(__file__).resolve().parents[2]
    raw = repo / "data" / "cvs_raw"
    scanned = raw / "scanned"

    files = []
    # Datasets réels disponibles
    for name in ["test_pdf_text.pdf", "test_word.docx"]:
        path = raw / name
        if path.exists():
            files.append(path)

    for name in ["cv_scanne_test.pdf", "cv_scanne_test.png", "asma_scanned.png"]:
        path = scanned / name
        if path.exists():
            files.append(path)

    if not files:
        print("Aucun fichier de benchmark trouvé.")
        return

    # Pour approcher un batch plus large, on réplique les fichiers dispo jusqu'à 10
    if len(files) < 10:
        base = list(files)
        idx = 0
        while len(files) < 10:
            files.append(base[idx % len(base)])
            idx += 1

    results = benchmark(files[:10])
    print_report(results)


if __name__ == "__main__":
    main()
