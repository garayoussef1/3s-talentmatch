"""Test rapide extraction OCR — diagnostic."""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.services.extraction.cv_extractor import CVExtractor

DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "data", "cvs_raw", "scanned")
ext = CVExtractor()

# Test PDF scanné
print("=== PDF SCANNE ===")
r1 = ext.extract(os.path.join(DATA_DIR, "cv_scanne_test.pdf"))
print(f"  success:   {r1['success']}")
print(f"  method:    {r1['method']}")
print(f"  needs_ocr: {r1.get('needs_ocr')}")
print(f"  text_len:  {len(r1['text'])}")
print(f"  preview:   {r1['text'][:200]}")
print(f"  error:     {r1.get('error')}")

# Test image PNG
print("\n=== IMAGE PNG ===")
r2 = ext.extract(os.path.join(DATA_DIR, "cv_scanne_test.png"))
print(f"  success:   {r2['success']}")
print(f"  method:    {r2['method']}")
print(f"  text_len:  {len(r2['text'])}")
print(f"  preview:   {r2['text'][:200]}")
print(f"  error:     {r2.get('error')}")
