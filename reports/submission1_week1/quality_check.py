"""Check the delivered PDF against its source/evidence and render contact sheets.

Requires the outputs of build.ps1 -Render and pdftotext -bbox-layout.
Manual visual review of the rendered pages remains necessary.
"""
import csv
import hashlib
import json
from pathlib import Path
import re
import shutil
import xml.etree.ElementTree as ET

from PIL import Image, ImageDraw

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
QA = HERE / "qa"


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    text = (QA / "extracted.txt").read_text(encoding="utf-8")
    pages = [p for p in text.split("\f") if p.strip()]
    log = (HERE / "main.log").read_text(encoding="utf-8", errors="replace")
    assert not re.search(r"Overfull \\[hv]box|Missing character:|undefined references|Citation .+ undefined|Reference .+ undefined|ignored error:|LaTeX Warning:|Package .+ Warning:", log)
    assert "?" not in text and "\ufffd" not in text, "Unexpected question mark or replacement glyph; inspect Unicode plot labels"
    main_start = next(i for i, page in enumerate(pages) if re.search(r"^I\.\s+Mục tiêu và phạm vi tuần 1", page, re.M))
    references_start = next(i for i, page in enumerate(pages) if "Tài liệu tham khảo" in {line.strip() for line in page.splitlines()})
    main_pages = references_start - main_start + 1  # References may share the last content page.
    assert main_start == 1  # Compact reader report: abstract shares the first content page.
    assert "AI-VIETNAM" in pages[0] and "AIO2026" in pages[0]
    for token in ("1.546", "8.131", "26.859", "1,8725", "2,1448", "1.886", "10.488", "106", "8.304", "104", "Tóm tắt"):
        assert token in text, repr(token)
    for name in ("Nguyễn Văn Minh", "Nguyễn Thành Trung", "Winner Winner Chicken Dinner"):
        assert name in pages[0]
    for goal in range(1, 4):
        assert f"Kết quả {goal}:" in text
    assert not re.search(r"\b(?:data|outputs|notebooks|scripts|tests)/|\bE\d{2}\b|PHỤ LỤC", text)
    assert not re.search(r"\b[\w.-]+\.(?:jsonl?|csv|ipynb|py|tex|pdf|ya?ml|ps1|md)\b", text, re.I), "Internal filename in reader report"
    assert not re.search(r"\b[a-f0-9]{40,64}\b", text), "Commit/checksum in reader report"
    for i, page in enumerate(pages[1:], 2):
        assert len(page.split()) > 50, f"Unexpected nearly empty page {i}"
    source = (HERE / "main.tex").read_text(encoding="utf-8")
    labels = re.findall(r"\\label\{([^}]+)\}", source)
    assert len(labels) == len(set(labels))
    assert set(re.findall(r"\\(?:ref|pageref|eqref)\{([^}]+)\}", source)) <= set(labels)
    bibliography = set(re.findall(r"\\bibitem\{([^}]+)\}", source))
    for citation in re.findall(r"\\cite\{([^}]+)\}", source):
        assert set(citation.split(",")) <= bibliography

    ns = {"h": "http://www.w3.org/1999/xhtml"}
    tree = ET.parse(QA / "bbox.html")
    pdf_pages = tree.findall(".//h:page", ns)
    assert len(pdf_pages) == len(pages)
    out_of_page = []
    for i, page in enumerate(pdf_pages, 1):
        width, height = float(page.attrib["width"]), float(page.attrib["height"])
        for word in page.findall(".//h:word", ns):
            a = word.attrib
            if float(a["xMin"]) < 0 or float(a["yMin"]) < 0 or float(a["xMax"]) > width or float(a["yMax"]) > height:
                out_of_page.append(i)
    assert not out_of_page

    with (HERE / "evidence/artifact_manifest.csv").open(encoding="utf-8", newline="") as stream:
        source_inventory = list(csv.DictReader(stream))
    for item in source_inventory:
        path = ROOT / item["path"]
        assert path.is_file(), item["path"]
        assert sha(path) == item["sha256"], item["path"]
    assert all((HERE / p).is_file() for p in ("main.tex", "main.pdf", "EVIDENCE_INDEX.md", "BUILD.md", "SUBMISSION_CHECKLIST.md", "build.ps1"))
    summary = json.loads((HERE / "evidence/verified_summary.json").read_text(encoding="utf-8"))
    assert summary["ocr_word_boxes"] == 26859
    assert summary["train_images_with_all_four_fields"] == 947
    assert summary["train_exact_duplicate_groups"] == 31
    assert summary["train_records_in_exact_duplicate_groups"] == 64
    assert summary["images"]["decoded_and_hash_matched"] == 8131
    expected_field_counts = {
        "seller_name": (1171, 1071, 84),
        "seller_address": (1952, 1077, 78),
        "transaction_datetime": (1347, 1088, 67),
        "total_amount": (2114, 1081, 74),
    }
    assert all(row["bytes_equal"] for row in summary["existing_repeat_bundles"].values())
    with (ROOT / "data/processed/manifest.jsonl").open(encoding="utf-8") as stream:
        receipts = [json.loads(line) for line in stream]
    assert sum(bool(r.get("validation_issues")) for r in receipts) == 115
    train = [row for row in receipts if row["source_subset"] == "kie_train"]
    for field, (regions, annotated, missing) in expected_field_counts.items():
        assert sum(sum(region.get("canonical_field") == field for region in row["regions"]) for row in train) == regions
        assert sum(any(region.get("canonical_field") == field for region in row["regions"]) for row in train) == annotated
        assert len(train) - annotated == missing

    rendered = sorted(QA.glob("review-page-*.png"), key=lambda path: int(path.stem.rsplit("-", 1)[1]))
    # Ignore stale render files beyond the length of the current PDF.
    rendered = rendered[:len(pages)]
    assert len(rendered) == len(pages)
    for offset in range(0, len(rendered), 6):
        sheet = Image.new("RGB", (1240, 1740), "#d4dbe0")
        draw = ImageDraw.Draw(sheet)
        for j, path in enumerate(rendered[offset:offset + 6]):
            image = Image.open(path).convert("RGB")
            image.thumbnail((595, 540))
            x, y = 10 + (j % 2) * 620, 27 + (j // 2) * 575
            sheet.paste(image, (x, y))
            draw.text((x, y - 17), f"PDF page {offset + j + 1}", fill="black")
        sheet.save(QA / f"final-contact-{offset // 6 + 1}.png")

    shutil.copyfile(HERE / "main.log", HERE / "evidence/latex-final.log")
    result = {
        "date_local": "2026-10-29", "timezone": "Asia/Saigon",
        "scope": "Reader-facing report: technical accuracy and independent readability across all three Week 1 goals",
        "compiler": "XeLaTeX / MiKTeX 25.12", "build_command": "powershell -NoProfile -ExecutionPolicy Bypass -File build.ps1 -Render",
        "physical_pages": len(pages), "substantive_pages": main_pages,
        "composition": {"cover": 1, "content_including_abstract_and_references": len(pages) - 1, "separate_contents_or_appendix": 0},
        "paper": "A4", "pdf_sha256": sha(HERE / "main.pdf"), "tex_sha256": sha(HERE / "main.tex"),
        "latex_log_has_warning_or_overflow_or_missing_glyph": False,
        "undefined_references_or_citations": False, "unexpected_empty_pages": False,
        "all_word_bounds_within_pages": True, "source_artifact_hashes_unchanged": True,
        "source_inventory_entries_verified": len(source_inventory),
        "reader_report_has_no_internal_evidence_paths": True,
        "reader_report_has_no_internal_filenames_or_hashes": True,
        "cover_identity_verified": True,
        "new_test_suite_execution": False,
        "visual_review_status": "pending final image inspection",
        "qa_note": "Programmatic checks do not substitute for inspecting rendered pages. MiKTeX update advisory is external to the LaTeX document log.",
    }
    (HERE / "evidence/pdf_qa.json").write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps({"pages": len(pages), "source_hashes_verified": len(source_inventory), "log_checks": "passed", "bbox_checks": "passed"}))


if __name__ == "__main__":
    main()
