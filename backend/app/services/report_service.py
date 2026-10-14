import csv
from io import StringIO


def safe_cell(value):
    if isinstance(value, (int, float)):
        return value
    text = "" if value is None else str(value)
    # Keep exported free text from being interpreted as a spreadsheet formula.
    return "'" + text if text.lstrip().startswith(("=", "+", "-", "@")) else text


def flaws_csv(result):
    output = StringIO(newline="")
    writer = csv.writer(output)
    writer.writerow(
        [
            "analysis_id",
            "execution_mode",
            "type",
            "start_seconds",
            "end_seconds",
            "severity",
            "confidence",
            "baseline_value",
            "participant_value",
            "difference_percent",
            "units",
            "evidence_source",
            "explanation",
            "recommendation",
        ]
    )
    for flaw in result.flaws:
        writer.writerow(
            [
                safe_cell(v)
                for v in [
                    result.analysis_id,
                    result.execution_mode,
                    flaw.type,
                    flaw.start_seconds,
                    flaw.end_seconds,
                    flaw.severity,
                    flaw.confidence,
                    flaw.evidence.baseline_value,
                    flaw.evidence.participant_value,
                    flaw.evidence.difference_percent,
                    flaw.evidence.units,
                    flaw.evidence.source,
                    flaw.explanation,
                    flaw.recommendation,
                ]
            ]
        )
    return output.getvalue()


def report_pdf(result, job):
    """Printable evidence report from the exact persisted analysis result."""
    from io import BytesIO
    from xml.sax.saxutils import escape
    from reportlab.lib import colors
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.enums import TA_LEFT
    from reportlab.lib.pagesizes import A4
    from reportlab.platypus import (
        SimpleDocTemplate,
        Paragraph,
        Spacer,
        Table,
        TableStyle,
        KeepTogether,
    )
    from reportlab.graphics.shapes import Drawing, Line, String, Rect

    output = BytesIO()
    doc = SimpleDocTemplate(
        output,
        pagesize=A4,
        rightMargin=42,
        leftMargin=42,
        topMargin=48,
        bottomMargin=44,
        title="Vocalis Speech Delivery Report",
        author="Vocalis",
    )
    styles = getSampleStyleSheet()
    styles.add(
        ParagraphStyle(
            name="ReportText",
            fontName="Helvetica",
            fontSize=9,
            leading=12,
            spaceAfter=6,
        )
    )
    styles.add(
        ParagraphStyle(
            name="ReportSmall",
            fontName="Helvetica",
            fontSize=8,
            leading=11,
            textColor=colors.HexColor("#546176"),
        )
    )

    def paragraph(text, style="ReportText"):
        return Paragraph(escape(str(text)), styles[style])

    def value(number):
        return "Unavailable" if number is None else f"{number:.1f}"

    story = [
        Paragraph("VOCALIS", styles["Title"]),
        paragraph("Speech delivery and contrastive acoustic evidence", "ReportSmall"),
        Spacer(1, 12),
        paragraph(job.participant_filename, "Heading2"),
        paragraph(
            f"Analysis: {result.analysis_id} | {job.created_at[:19]} UTC", "ReportSmall"
        ),
        paragraph(
            f"Provider: {result.provider_name} / {result.provider_version} | {result.execution_mode.upper()}",
            "ReportSmall",
        ),
        paragraph(
            f"Rubric: {job.rubric_snapshot.get('name','')} / version {job.rubric_snapshot.get('version','')}",
            "ReportSmall",
        ),
        Spacer(1, 14),
        paragraph(
            f"Overall delivery score: {value(result.scores.overall)} / 100", "Heading2"
        ),
    ]
    if result.execution_mode == "mock":
        story.append(
            paragraph(
                "DEMONSTRATION: These values are illustrative fixtures, not measured speech analysis."
            )
        )
    rows = [["Dimension", "Score / 100"]] + [
        [name.replace("_", " ").capitalize(), value(score)]
        for name, score in result.scores.dimensions.items()
    ]
    table = Table(rows, colWidths=[340, 160], hAlign="LEFT")
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#203447")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("FONTSIZE", (0, 0), (-1, -1), 9),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
                ("TOPPADDING", (0, 0), (-1, -1), 8),
                (
                    "ROWBACKGROUNDS",
                    (0, 1),
                    (-1, -1),
                    [colors.HexColor("#f0f5f7"), colors.white],
                ),
            ]
        )
    )
    story += [table, Spacer(1, 14)]
    if result.clarity:
        clarity = result.clarity
        story.append(paragraph("Clarity evidence", "Heading2"))
        story.append(
            paragraph(
                "Clarity is reference-relative ASR word recoverability. It is not a calibrated human intelligibility or accent score; recording conditions and model bias can affect it."
            )
        )
        if clarity.available:
            story.append(
                paragraph(
                    f"Reference word errors: {clarity.reference.word_error_rate * 100:.1f}%. "
                    f"Participant word errors: {clarity.participant.word_error_rate * 100:.1f}%. "
                    f"Additional errors: {clarity.excess_word_error_rate * 100:.1f} percentage points. "
                    "Score = 100 x (1 - additional error rate), bounded to 0-100.",
                    "ReportSmall",
                )
            )
        else:
            story.append(
                paragraph(clarity.reason or "Clarity unavailable.", "ReportSmall")
            )
        story.append(
            paragraph(
                f"Independently recognized participant words: {clarity.participant_text or 'No words recognized'}",
                "ReportSmall",
            )
        )
        story.append(Spacer(1, 10))
    for name in ["pitch", "energy", "pacing"]:
        series = result.feature_series.get(name)
        if not series:
            continue
        points = [
            p for p in [*series.reference, *series.participant] if p.value is not None
        ]
        if not points:
            continue
        drawing = Drawing(500, 116)
        xmin, xmax = 0, max(p.time_seconds for p in points)
        ymin, ymax = min(p.value for p in points), max(p.value for p in points)
        span = max(1e-6, ymax - ymin)
        drawing.add(String(0, 104, f"{name.capitalize()} ({series.unit})", fontSize=9))
        if series.time_axis == "participant_aligned":
            for flaw in result.flaws:
                if flaw.category == name:
                    left = 22 + flaw.start_seconds / max(0.01, xmax) * 465
                    width = (
                        (flaw.end_seconds - flaw.start_seconds) / max(0.01, xmax) * 465
                    )
                    drawing.add(
                        Rect(
                            left,
                            18,
                            width,
                            70,
                            fillColor=colors.HexColor("#fae7ec"),
                            strokeColor=None,
                        )
                    )
        for role, color in [
            ("reference", colors.HexColor("#158575")),
            ("participant", colors.HexColor("#6657b2")),
        ]:
            previous = None
            for p in getattr(series, role):
                if p.value is None:
                    previous = None
                    continue
                current = (
                    22 + p.time_seconds / max(0.01, xmax) * 465,
                    18 + (p.value - ymin) / span * 70,
                )
                if previous:
                    drawing.add(
                        Line(*previous, *current, strokeColor=color, strokeWidth=0.8)
                    )
                previous = current
        drawing.add(String(22, 2, "0s", fontSize=7))
        drawing.add(String(465, 2, f"{xmax:.1f}s", fontSize=7))
        drawing.add(
            String(
                300, 104, "Reference", fontSize=7, fillColor=colors.HexColor("#158575")
            )
        )
        drawing.add(
            String(
                390,
                104,
                "Participant",
                fontSize=7,
                fillColor=colors.HexColor("#6657b2"),
            )
        )
        drawing.add(String(0, 18, f"{ymin:.0f}", fontSize=6))
        drawing.add(String(0, 85, f"{ymax:.0f}", fontSize=6))
        story += [drawing, Spacer(1, 16)]
    story += [paragraph(f"Flagged delivery regions ({len(result.flaws)})", "Heading2")]
    if not result.flaws:
        story.append(
            paragraph(
                "No supported delivery deviations crossed the configured thresholds. This is not a guarantee of flawless delivery."
            )
        )
    for index, flaw in enumerate(result.flaws, 1):
        evidence = flaw.evidence
        block = [
            paragraph(
                f"{index}. {flaw.type.replace('_',' ').capitalize()} | {flaw.start_seconds:.2f}-{flaw.end_seconds:.2f}s | severity {flaw.severity}/5",
                "Heading3",
            ),
            paragraph(flaw.explanation),
            paragraph("Practice: " + flaw.recommendation),
        ]
        if flaw.transcript_text:
            block.append(paragraph("Passage: " + flaw.transcript_text, "ReportSmall"))
        block.append(
            paragraph(
                f"{evidence.measurement_name}: reference {value(evidence.baseline_value)}, participant {value(evidence.participant_value)}, difference {value(evidence.absolute_deviation)} {evidence.units}. Evidence: {evidence.source}.",
                "ReportSmall",
            )
        )
        story += block + [Spacer(1, 8)]
    story += [paragraph("Measurement notes", "Heading2")]
    story.extend(paragraph(warning, "ReportSmall") for warning in result.warnings)

    def footer(canvas, document):
        canvas.setStrokeColor(colors.HexColor("#cad6df"))
        canvas.line(42, 32, A4[0] - 42, 32)
        canvas.setFont("Helvetica", 7)
        canvas.setFillColor(colors.HexColor("#546176"))
        canvas.drawString(
            42, 21, "Vocalis | Saved acoustic evidence and rubric snapshot"
        )
        canvas.drawRightString(A4[0] - 42, 21, str(document.page))

    doc.build(story, onFirstPage=footer, onLaterPages=footer)
    return output.getvalue()
