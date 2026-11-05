#!/usr/bin/env python3
"""Build a deterministic, local full-page PSM review gallery without adjudicating it."""
from __future__ import annotations

import argparse
import html
import random
import shutil
import sys
from collections import defaultdict
from pathlib import Path

from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT))
from docucheck.evaluation.metrics import align_word_predictions_to_lines, normalize_text
from docucheck.ocr.inference import load_manifest
from scripts.run_psm_comparison import PSMS, SPLIT, read, save, sha


def select_cases(image_metrics, region_metrics):
    ids = sorted(image_metrics[6])
    unmatched = {p: {i: sum(not r["matched"] for r in region_metrics[p][i]) for i in ids} for p in PSMS}
    selected = []
    used = set()

    def take(group, candidates, count, question):
        for image_id in candidates:
            if image_id in used:
                continue
            selected.append({"image_id": image_id, "selection_group": group, "question": question,
                             "review_status": "pending", "reviewer": None, "decision": None, "notes": None})
            used.add(image_id)
            count -= 1
            if count == 0:
                break

    for p in (4, 11):
        delta = lambda i: image_metrics[p][i]["cer"] - image_metrics[6][i]["cer"]
        take(f"psm{p}_largest_cer_improvement", sorted((i for i in ids if delta(i) < 0), key=lambda i: (delta(i), i)), 3,
             "CER giảm có phản ánh chữ đọc đúng hơn, hay chủ yếu do mất/gộp box hoặc cách ghép GT? Chỉ rõ vùng.")
        take(f"psm{p}_largest_cer_regression", sorted((i for i in ids if delta(i) > 0), key=lambda i: (-delta(i), i)), 3,
             "CER tăng do nhận dạng sai, thứ tự đọc/ghép vùng hay annotation? Chỉ rõ vùng và PSM.")
    tradeoffs = sorted(ids, key=lambda i: (-max(unmatched[p][i] - unmatched[6][i] for p in (4, 11)), i))
    tradeoffs = [i for i in tradeoffs if any(image_metrics[p][i]["cer"] < image_metrics[6][i]["cer"]
                 and unmatched[p][i] > unmatched[6][i] for p in (4, 11))]
    take("lower_cer_but_more_unmatched_gt", tradeoffs, 3,
         "Candidate có bỏ mất chữ thực sự khi CER giảm không? Các vùng không nhận box có GT hợp lý không?")
    take("successful_empty_ocr", [i for i in ids if any(image_metrics[p][i].get("prediction_word_box_count") == 0 for p in PSMS)], 1,
         "Ảnh có chữ đọc được nhưng PSM trả rỗng không? Kiểm tra hướng ảnh và vùng chữ bị bỏ sót.")
    take("high_error_all_modes", sorted(ids, key=lambda i: (-min(image_metrics[p][i]["cer"] for p in PSMS), i)), 2,
         "Đọc ảnh gốc: GT có khớp vùng chữ không? Lỗi chung có thể do ảnh khó, annotation hay alignment?")
    shuffled = list(ids)
    random.Random(42).shuffle(shuffled)
    take("fixed_seed_sample", shuffled, 20 - len(selected),
         "PSM nào giữ được nội dung và vùng chữ tốt nhất? Ghi điểm mạnh/yếu, hoặc chưa thể kết luận.")
    return selected


def overlay(image, regions, color, scale):
    draw = ImageDraw.Draw(image)
    for index, region in enumerate(regions):
        pts = [(float(x) * scale, float(y) * scale) for x, y in region.get("polygon", [])]
        if len(pts) < 3:
            continue
        c = region.get("display_color", color)
        draw.line(pts + [pts[0]], fill=c, width=2)
        draw.text(pts[0], str(index), fill="black", stroke_width=1, stroke_fill="white")


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-dir", type=Path, required=True)
    args = parser.parse_args(argv)
    run = args.run_dir.resolve()
    folder = run / "error_review"
    if folder.exists():
        parser.error("Review directory exists; preserve review decisions and choose a new run")
    lock = read(run / "locked_config.json")
    root = Path(lock["dataset_root"])
    manifest = {r["image_id"]: r for r in load_manifest(run / "manifest.jsonl") if r.get("split") == SPLIT}
    images, regions, predictions = {}, {}, {}
    for p in PSMS:
        sub = run / f"psm{p}"
        images[p] = {r["image_id"]: r for r in load_manifest(sub / "per_image_metrics.jsonl")}
        predictions[p] = {r["image_id"]: r["predictions"] for r in load_manifest(sub / "predictions.jsonl")}
        regions[p] = defaultdict(list)
        for r in load_manifest(sub / "per_region_alignment.jsonl"):
            regions[p][r["image_id"]].append(r)
    cases = select_cases(images, regions)
    folder.mkdir()
    (folder / "images").mkdir()
    escape = lambda value: html.escape(str(value))
    style = "body{font:16px Arial;margin:24px;line-height:1.5;background:#fafafa}table{border-collapse:collapse;width:100%;margin:12px 0}td,th{border:1px solid #ccc;padding:6px;vertical-align:top}th{background:#eee}img{max-width:100%;height:auto}a{color:#0759a2}.grid{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:8px}.grid img{width:100%}details{margin:16px 0}.pending{color:#984900}"
    page = [f"<!doctype html><html lang='vi'><meta charset='utf-8'><title>PSM comparison review</title><style>{style}</style>",
            "<h1>So sánh PSM trên cùng ảnh biên lai</h1><p>20 ảnh chẩn đoán, chọn có chủ đích và seed 42; không dùng để ước lượng tỷ lệ lỗi toàn tập.</p>",
            "<p class='pending'>Trạng thái: chờ người review. Số liệu đo được không tự xác nhận nguyên nhân lỗi.</p>",
            "<p>GT có transcript hợp lệ: xanh lá; GT thiếu transcript hoặc hình học lỗi: cam. Box OCR được gán vào GT có transcript: xanh dương; không được gán: đỏ. "
            "Số trên hình là index trong bảng. Bấm ảnh để mở kích thước lớn; mở ảnh gốc để đọc chữ.</p><ol>"]
    page.extend(f"<li><a href='#{i:02d}'>{escape(c['image_id'])}</a> — {escape(c['selection_group'])}</li>" for i, c in enumerate(cases, 1))
    page.append("</ol>")
    for index, case in enumerate(cases, 1):
        image_id = case["image_id"]
        record = manifest[image_id]
        original_path = root / record["image_path"]
        original_name = f"{index:02d}_original{original_path.suffix}"
        shutil.copyfile(original_path, folder / "images" / original_name)
        original = Image.open(original_path).convert("RGB")
        scale = min(1, 1000 / original.width)
        base = original.resize((round(original.width * scale), round(original.height * scale)))
        valid_gt, display_gt = [], []
        for r in record["ocr_regions"]:
            valid = not r.get("validation_issues") and r.get("polygon") and r.get("text_raw") is not None and normalize_text(r["text_raw"])
            if valid:
                valid_gt.append(r)
            display_gt.append({**r, "display_color": "#008000" if valid else "#ee9900"})
        panels = []
        gt_image = base.copy()
        overlay(gt_image, display_gt, "#008000", scale)
        gt_name = f"{index:02d}_gt.png"
        gt_image.save(folder / "images" / gt_name)
        panels.append(("GT (source index)", gt_name, gt_image))
        case["measurements"] = {}
        unassigned_by_psm = {}
        for p in PSMS:
            pred = predictions[p][image_id]
            _, unassigned = align_word_predictions_to_lines(pred, valid_gt)
            unassigned_by_psm[p] = set(unassigned)
            shown = [{**r, "display_color": "#e00000" if j in unassigned else "#0055ff"} for j, r in enumerate(pred)]
            panel = base.copy()
            overlay(panel, shown, "#0055ff", scale)
            name = f"{index:02d}_psm{p}.png"
            panel.save(folder / "images" / name)
            panels.append((f"PSM {p}", name, panel))
            case["measurements"][str(p)] = {**images[p][image_id], "unmatched_gt": sum(not r["matched"] for r in regions[p][image_id])}
        thumb_width = 300
        thumb_height = round(base.height / base.width * thumb_width)
        contact = Image.new("RGB", (thumb_width * 4, thumb_height + 30), "white")
        d = ImageDraw.Draw(contact)
        for j, (label, name, panel) in enumerate(panels):
            d.text((j * thumb_width + 5, 5), label, fill="black")
            contact.paste(panel.resize((thumb_width, thumb_height)), (j * thumb_width, 30))
        contact.save(folder / "images" / f"{index:02d}_comparison.png")
        case.update(index=index, original_image=f"images/{original_name}", contact_sheet=f"images/{index:02d}_comparison.png")
        page.append(f"<hr><h2 id='{index:02d}'>{index:02d}. {escape(image_id)}</h2><p>{escape(case['selection_group'])}</p>"
                    f"<p><b>Cần xác minh:</b> {escape(case['question'])}</p><p><a href='images/{original_name}'>Mở ảnh gốc</a></p><div class='grid'>")
        page.extend(f"<div><b>{label}</b><a href='images/{name}'><img loading='lazy' src='images/{name}' alt='{label}'></a></div>" for label, name, _ in panels)
        page.append("</div><table><tr><th>PSM</th><th>CER</th><th>WER</th><th>Boxes</th><th>Unassigned (text GT)</th><th>Unmatched text GT</th><th>Unassigned (all geometry)</th><th>Unmatched geometry</th></tr>")
        for p in PSMS:
            m = case["measurements"][str(p)]
            page.append(f"<tr><td>{p}</td><td>{m['cer']:.4f}</td><td>{m['wer']:.4f}</td><td>{m['prediction_word_box_count']}</td>"
                        f"<td>{m['unassigned_prediction_count']}</td><td>{m['unmatched_gt']}/{m['evaluated_region_count']}</td>"
                        f"<td>{m.get('geometry_unassigned_word_count', 'n/a')}</td><td>{m.get('geometry_unmatched_region_count', 'n/a')}/{m.get('geometry_valid_region_count', 'n/a')}</td></tr>")
        page.append("</table><details><summary>GT và transcript được ghép của ba PSM</summary><table><tr><th>GT source index</th><th>GT</th><th>PSM 6</th><th>PSM 4</th><th>PSM 11</th></tr>")
        valid_index = 0
        for source_index, r in enumerate(record["ocr_regions"]):
            valid = not r.get("validation_issues") and r.get("polygon") and r.get("text_raw") is not None and normalize_text(r["text_raw"])
            if not valid:
                page.append(f"<tr><td>{source_index}</td><td>{escape(r.get('text_raw'))}</td><td colspan='3'>Loại khỏi phép đo: {escape(r.get('validation_issues') or 'missing geometry/empty transcript')}</td></tr>")
                continue
            page.append(f"<tr><td>{source_index}</td><td>{escape(r['text_raw'])}</td>" + "".join(
                f"<td>{escape(regions[p][image_id][valid_index]['text_pred'])}</td>" for p in PSMS) + "</tr>")
            valid_index += 1
        page.append("</table></details>")
        for p in PSMS:
            page.append(f"<details><summary>PSM {p}: tất cả word boxes, text, confidence</summary><table><tr><th>Index</th><th>Text</th><th>Confidence</th><th>Assignment</th></tr>")
            for j, pred in enumerate(predictions[p][image_id]):
                page.append(f"<tr><td>{j}</td><td>{escape(pred['text'])}</td><td>{escape(pred.get('confidence'))}</td><td>{'unassigned' if j in unassigned_by_psm[p] else 'assigned'}</td></tr>")
            page.append("</table></details>")
    page.append("</html>")
    (folder / "index.html").write_text("\n".join(page), encoding="utf-8")
    save(folder / "review_cases.json", cases)
    save(folder / "review_summary.json", {"case_count": len(cases), "confirmed": 0, "pending": len(cases),
         "selection": "Up to 3 largest CER improvements and 3 regressions per candidate, 3 CER/coverage tradeoffs, 1 successful empty OCR, 2 high-error images, fill to 20 with seed 42; IDs unique, earlier groups take precedence",
         "selection_code_sha256": sha(__file__)})
    (folder / "REVIEW_WORKSHEET.md").write_text("# Visual review worksheet\n\nRecord observations; leave uncertain cases pending. Do not infer prevalence from this selected sample.\n\n" +
        "\n".join(f"## {c['index']:02d}. {c['image_id']}\n\n- Group: {c['selection_group']}\n- Question: {c['question']}\n- Status: pending\n- Reviewer: \n- Observation and region index: \n- Decision: \n" for c in cases), encoding="utf-8")
    shutil.copyfile(__file__, folder / "review_generator.py")
    print(f"Created {len(cases)} pending review cases: {folder / 'index.html'}")


if __name__ == "__main__":
    main()
