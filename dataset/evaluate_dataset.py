"""Independent acoustic inference against controlled-edit interval ground truth."""

from pathlib import Path
import argparse
import json
import sys
import time
from dataclasses import asdict
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import evaluator


def iou(a, b):
    overlap = max(0, min(a[1], b[1]) - max(a[0], b[0]))
    union = max(a[1], b[1]) - min(a[0], b[0])
    return overlap / union if union else 0


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--only", nargs="+", help="Source/excerpt IDs")
    args = ap.parse_args()
    corpus = ROOT / "dataset/contrastive"
    manifest = json.loads((corpus / "manifest.json").read_text())
    output = ROOT / "docs/benchmarks"
    output.mkdir(parents=True, exist_ok=True)
    rows = []
    for group in manifest["groups"]:
        if (
            args.only
            and group["id"] not in args.only
            and group["source_id"] not in args.only
        ):
            continue
        for variant in group["variants"]:
            started = time.monotonic()
            try:
                report = evaluator.evaluate(
                    str(corpus / group["reference"]["audio_file"]),
                    str(corpus / variant["audio_file"]),
                    group["transcript"],
                    config=evaluator.EvaluatorConfig(enable_clarity=False),
                )
                labels = variant["annotations"]
                flaws = report["flaw_regions"]
                matches = []
                used = set()
                for label in labels:
                    expected = [label["start_seconds"], label["end_seconds"]]
                    candidates = [
                        (iou(expected, [f["start_time"], f["end_time"]]), i, f)
                        for i, f in enumerate(flaws)
                        if f["flaw_type"] == label["flaw_type"] and i not in used
                    ]
                    best = max(candidates, default=(0, None, None), key=lambda x: x[0])
                    if best[0] >= 0.25:
                        used.add(best[1])
                    matches.append(
                        dict(
                            type=label["flaw_type"],
                            best_iou=round(best[0], 4),
                            matched=best[0] >= 0.25,
                            boundary_error_seconds=(
                                round(
                                    (
                                        abs(best[2]["start_time"] - expected[0])
                                        + abs(best[2]["end_time"] - expected[1])
                                    )
                                    / 2,
                                    4,
                                )
                                if best[2]
                                else None
                            ),
                        )
                    )
                row = dict(
                    group_id=group["id"],
                    variant_id=variant["id"],
                    split=group["split"],
                    level=variant["level"],
                    scores=report["scores"],
                    label_count=len(labels),
                    detected_count=len(flaws),
                    true_positives=sum(m["matched"] for m in matches),
                    false_positives=len(flaws) - len(used),
                    matches=matches,
                    elapsed_seconds=round(time.monotonic() - started, 2),
                    error=None,
                )
                # Preserve model-generated variant alignment separately from exact edit labels.
                path = corpus / variant["audio_file"]
                alignment = path.with_suffix(".alignment.json")
                alignment.write_text(
                    json.dumps(report["word_alignments"]["candidate"], indent=2)
                )
                variant["alignment_file"] = str(alignment.relative_to(corpus)).replace(
                    "\\", "/"
                )
                (output / (variant["id"] + ".json")).write_text(
                    json.dumps(report, indent=2)
                )
            except Exception as exc:
                row = dict(
                    group_id=group["id"],
                    variant_id=variant["id"],
                    split=group["split"],
                    error=str(exc),
                    elapsed_seconds=round(time.monotonic() - started, 2),
                )
            rows.append(row)
            print(
                variant["id"],
                row.get("true_positives"),
                row.get("false_positives"),
                row.get("error"),
                flush=True,
            )
            (output / "results.json").write_text(json.dumps(rows, indent=2))
    summaries = {}
    for split in ["training", "validation", "testing", "all"]:
        subset = [
            r
            for r in rows
            if (split == "all" or r["split"] == split) and not r["error"]
        ]
        tp = sum(r["true_positives"] for r in subset)
        fp = sum(r["false_positives"] for r in subset)
        labels = sum(r["label_count"] for r in subset)
        precision = tp / (tp + fp) if tp + fp else None
        recall = tp / labels if labels else None
        errors = [
            m["boundary_error_seconds"]
            for r in subset
            for m in r["matches"]
            if m["matched"]
        ]
        summaries[split] = dict(
            recordings=len(subset),
            true_positives=tp,
            false_positives=fp,
            labels=labels,
            precision=precision,
            recall=recall,
            f1=(
                2 * precision * recall / (precision + recall)
                if precision is not None and recall is not None and precision + recall
                else None
            ),
            mean_boundary_error_seconds=float(np.mean(errors)) if errors else None,
        )
    summary = dict(
        version="1.0",
        matching_iou_threshold=0.25,
        results=summaries,
        failed_recordings=[r for r in rows if r["error"]],
        limitations="Controlled same-speaker edits, not human-rated accuracy on natural delivery. Do not tune thresholds on the testing split.",
    )
    (output / "summary.json").write_text(json.dumps(summary, indent=2))
    (corpus / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    print(json.dumps(summary, indent=2), flush=True)
    return 1 if summary["failed_recordings"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
