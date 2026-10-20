import argparse
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import (
    PageBreak,
    Paragraph,
    Preformatted,
    SimpleDocTemplate,
    Spacer,
)


ET = ZoneInfo("America/New_York")


def get_slate(run_id: int) -> str:
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "reports.nfl_slate",
            "--run",
            str(run_id),
        ],
        text=True,
        capture_output=True,
    )

    if result.returncode != 0:
        if result.stdout:
            print(result.stdout, end="")
        if result.stderr:
            print(result.stderr, end="", file=sys.stderr)
        raise SystemExit(result.returncode)

    return result.stdout


def add_page_number(canvas, doc):
    canvas.saveState()

    canvas.setFont("Helvetica", 8)
    canvas.setFillColor(colors.HexColor("#666666"))

    canvas.drawString(
        0.55 * inch,
        0.35 * inch,
        "MarketEdge Lab • NFL Research",
    )

    canvas.drawRightString(
        8.0 * inch,
        0.35 * inch,
        f"Page {doc.page}",
    )

    canvas.restoreState()


def split_report(text: str):
    sections = []
    current = []

    for line in text.splitlines():
        if line.startswith("=" * 10) and current:
            sections.append("\n".join(current).rstrip())
            current = [line]
        else:
            current.append(line)

    if current:
        sections.append("\n".join(current).rstrip())

    return [section for section in sections if section.strip()]


def main():
    parser = argparse.ArgumentParser(
        description="Export a MarketEdge NFL slate report to PDF."
    )
    parser.add_argument(
        "--run",
        type=int,
        required=True,
        help="NFL collection run ID",
    )
    parser.add_argument(
        "--output",
        help="Optional output PDF path",
    )
    args = parser.parse_args()

    print(f"Building NFL slate for run {args.run}...")

    slate = get_slate(args.run)

    output_dir = Path("reports/output")
    output_dir.mkdir(parents=True, exist_ok=True)

    if args.output:
        output_path = Path(args.output)
    else:
        output_path = (
            output_dir
            / f"MarketEdge_NFL_Run{args.run}.pdf"
        )

    generated = datetime.now(ET)

    doc = SimpleDocTemplate(
        str(output_path),
        pagesize=letter,
        rightMargin=0.45 * inch,
        leftMargin=0.45 * inch,
        topMargin=0.55 * inch,
        bottomMargin=0.55 * inch,
        title=f"MarketEdge NFL Run {args.run}",
        author="MarketEdge Lab",
        subject="NFL market and model research slate",
    )

    styles = getSampleStyleSheet()

    title_style = ParagraphStyle(
        "MarketEdgeTitle",
        parent=styles["Title"],
        fontName="Helvetica-Bold",
        fontSize=22,
        leading=26,
        alignment=TA_CENTER,
        spaceAfter=8,
        textColor=colors.HexColor("#111111"),
    )

    subtitle_style = ParagraphStyle(
        "MarketEdgeSubtitle",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=10,
        leading=14,
        alignment=TA_CENTER,
        textColor=colors.HexColor("#555555"),
        spaceAfter=16,
    )

    section_style = ParagraphStyle(
        "SectionHeader",
        parent=styles["Heading2"],
        fontName="Helvetica-Bold",
        fontSize=12,
        leading=15,
        spaceBefore=6,
        spaceAfter=6,
        textColor=colors.HexColor("#111111"),
    )

    mono_style = ParagraphStyle(
        "SlateMono",
        fontName="Courier",
        fontSize=6.8,
        leading=8.3,
        leftIndent=0,
        rightIndent=0,
        spaceBefore=3,
        spaceAfter=7,
        textColor=colors.HexColor("#111111"),
    )

    story = []

    story.append(
        Paragraph(
            "MarketEdge Lab",
            title_style,
        )
    )

    story.append(
        Paragraph(
            f"NFL Research Slate • Collection Run {args.run}",
            subtitle_style,
        )
    )

    story.append(
        Paragraph(
            (
                f"Generated {generated.strftime('%A, %B %d, %Y at %I:%M:%S %p %Z')}"
                "<br/>"
                "Prospective market/model research • Not a prediction guarantee"
            ),
            subtitle_style,
        )
    )

    story.append(Spacer(1, 0.08 * inch))

    sections = split_report(slate)

    if not sections:
        story.append(
            Preformatted(
                slate,
                mono_style,
                maxLineLength=115,
            )
        )
    else:
        for index, section in enumerate(sections):
            lines = section.splitlines()

            heading = None
            for line in lines[:6]:
                stripped = line.strip(" =-")
                if stripped and len(stripped) <= 90:
                    heading = stripped
                    break

            if heading:
                story.append(
                    Paragraph(
                        heading.replace("&", "&amp;"),
                        section_style,
                    )
                )

            story.append(
                Preformatted(
                    section,
                    mono_style,
                    maxLineLength=115,
                )
            )

            if index < len(sections) - 1:
                story.append(Spacer(1, 0.05 * inch))

    doc.build(
        story,
        onFirstPage=add_page_number,
        onLaterPages=add_page_number,
    )

    txt_path = output_path.with_suffix(".txt")
    txt_path.write_text(slate)

    print()
    print("MarketEdge export complete.")
    print(f"PDF : {output_path}")
    print(f"Text: {txt_path}")


if __name__ == "__main__":
    main()
