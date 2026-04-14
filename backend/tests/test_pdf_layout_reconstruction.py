from app.services.extraction.pdf_extractor import PDFExtractor


def _page_dict(lines):
    """Helper to build a minimal PyMuPDF-like page dict."""
    return {
        "blocks": [
            {
                "type": 0,
                "lines": [
                    {
                        "bbox": ln["bbox"],
                        "spans": [{"text": ln["text"]}],
                    }
                    for ln in lines
                ],
            }
        ]
    }


def test_reconstruct_two_columns_reads_left_then_right():
    # Two columns: left x0=50, right x0=360 on a 600px page.
    lines = [
        {"bbox": [50, 10, 200, 20], "text": "LEFT 1"},
        {"bbox": [50, 30, 200, 40], "text": "LEFT 2"},
        {"bbox": [360, 15, 520, 25], "text": "RIGHT 1"},
        {"bbox": [360, 40, 520, 50], "text": "RIGHT 2"},
    ]

    text = PDFExtractor._reconstruct_text_from_pymupdf_page(_page_dict(lines), page_width=600)

    # Left column should come entirely before right column.
    assert text.index("LEFT 1") < text.index("LEFT 2")
    assert text.index("LEFT 2") < text.index("RIGHT 1")
    assert text.index("RIGHT 1") < text.index("RIGHT 2")


def test_reconstruct_single_column_keeps_vertical_order():
    lines = [
        {"bbox": [60, 10, 400, 20], "text": "A"},
        {"bbox": [65, 25, 420, 35], "text": "B"},
        {"bbox": [62, 40, 410, 50], "text": "C"},
    ]

    text = PDFExtractor._reconstruct_text_from_pymupdf_page(_page_dict(lines), page_width=600)
    assert text.splitlines()[:3] == ["A", "B", "C"]
