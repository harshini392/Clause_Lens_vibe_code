"""Generate realistic sample contracts and edge cases for ClauseLens testing and demonstration.
Creates all required sample files in sample_contracts/ using ReportLab, python-docx, and PyMuPDF.
"""
import os
from pathlib import Path
import docx
import pymupdf
from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, PageBreak
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle

SAMPLE_DIR = Path(__file__).resolve().parent
SAMPLE_DIR.mkdir(parents=True, exist_ok=True)


def build_pdf_document(filepath: Path, pages_content: list, title: str):
    """Build a multi-page PDF document with ReportLab."""
    doc = SimpleDocTemplate(
        str(filepath),
        pagesize=letter,
        leftMargin=54,
        rightMargin=54,
        topMargin=54,
        bottomMargin=54
    )
    styles = getSampleStyleSheet()

    title_style = ParagraphStyle(
        "DocTitle",
        parent=styles["Heading1"],
        fontName="Helvetica-Bold",
        fontSize=16,
        leading=20,
        textColor=colors.HexColor("#0B1F3A"),
        spaceAfter=12
    )
    heading_style = ParagraphStyle(
        "DocHeading",
        parent=styles["Heading2"],
        fontName="Helvetica-Bold",
        fontSize=12,
        leading=16,
        textColor=colors.HexColor("#1E3A8A"),
        spaceBefore=10,
        spaceAfter=6
    )
    body_style = ParagraphStyle(
        "DocBody",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=10,
        leading=14,
        textColor=colors.HexColor("#1A202C"),
        spaceAfter=8
    )

    story = [Paragraph(title, title_style), Spacer(1, 12)]

    for p_idx, page_sections in enumerate(pages_content):
        if p_idx > 0:
            story.append(PageBreak())
        for heading, body in page_sections:
            if heading:
                story.append(Paragraph(heading, heading_style))
            story.append(Paragraph(body, body_style))

    doc.build(story)


def generate_risky_pdf():
    """Generate 4+ page risky agreement PDF with payment 60 days, auto-renewal 1-year with 60-day notice,
    unlimited liability, NY jurisdiction, one-sided termination.
    """
    path = SAMPLE_DIR / "risky_services_agreement.pdf"
    pages = [
        # Page 1: Preamble & Scope
        [
            ("MASTER PROFESSIONAL SERVICES AGREEMENT",
             "This Master Professional Services Agreement (the 'Agreement') is entered into as of January 15, 2026, "
             "by and between Global Enterprise Solutions Inc. ('Client') and Premier Consulting Services LLC ('Contractor')."),
            ("Section 1. Engagement and Scope of Work",
             "Contractor shall perform strategic technical advisory, cloud infrastructure architecture, and custom software development "
             "as detailed in applicable Statements of Work executed by the parties from time to time. Contractor agrees to devote reasonable "
             "commercial efforts and industry standard expertise to the deliverables described herein.")
        ],
        # Page 2: Payment Terms (60 days)
        [
            ("Section 2. Compensation and Invoicing",
             "Client shall pay Contractor fees in accordance with the fee schedule specified in Exhibit A. Invoices shall be rendered on a monthly basis. "
             "Client shall remit payment for all undisputed invoice amounts within sixty (60) days of invoice date. Any overdue payments shall accrue interest "
             "at the rate of 1.5% per month or the maximum rate permitted by law, whichever is less."),
            ("Section 3. Taxes and Expenses",
             "All quoted fees are exclusive of applicable federal, state, and local value-added, sales, or withholding taxes. Client shall reimburse Contractor for "
             "pre-approved travel and out-of-pocket expenses incurred in the direct performance of services under this Agreement.")
        ],
        # Page 3: Term & Automatic Renewal (1 year, 60-day notice) & Termination
        [
            ("Section 4. Term and Automatic Renewal",
             "The initial term of this Agreement shall commence on the Effective Date and continue for one (1) year. "
             "Thereafter, this Agreement shall automatically renew for successive one-year periods unless either party provides at least sixty (60) days advance written notice "
             "of non-renewal prior to the expiration of the then-current term."),
            ("Section 5. Termination Provisions",
             "Client may terminate this Agreement or any Statement of Work at any time for convenience upon thirty (30) days written notice to Contractor. "
             "Contractor has no right of termination for convenience and may terminate only in the event of an uncured material breach by Client that remains unremedied "
             "for forty-five (45) days after written notice.")
        ],
        # Page 4: Liability (Unlimited) & Jurisdiction (New York)
        [
            ("Section 6. Limitation of Liability",
             "Notwithstanding anything to the contrary contained herein, Company's liability shall be unlimited and not subject to any monetary cap "
             "for any claims, damages, liabilities, or losses arising out of or related to performance under this Agreement."),
            ("Section 7. Governing Law and Exclusive Jurisdiction",
             "This Agreement shall be governed by, and construed in accordance with, the laws of the State of New York, without regard to its conflict of law rules. "
             "The parties irrevocably agree that any dispute or proceeding shall be subject to the exclusive jurisdiction of the state and federal courts located in New York County, New York."),
            ("Section 8. Signatures",
             "IN WITNESS WHEREOF, authorized representatives of Client and Contractor have executed this Agreement as of the date first above written.")
        ]
    ]
    build_pdf_document(path, pages, "MASTER PROFESSIONAL SERVICES AGREEMENT")


def generate_risky_docx():
    """Generate risky agreement in DOCX format matching the PDF contents."""
    path = SAMPLE_DIR / "risky_services_agreement.docx"
    doc = docx.Document()

    doc.add_heading("MASTER PROFESSIONAL SERVICES AGREEMENT", level=1)
    doc.add_paragraph("This Master Professional Services Agreement is entered into as of January 15, 2026, by and between Global Enterprise Solutions Inc. ('Client') and Premier Consulting Services LLC ('Contractor').")
    
    doc.add_heading("Section 1. Scope of Services", level=2)
    doc.add_paragraph("Contractor shall perform software architecture and technical advisory services as agreed in subsequent Statements of Work.")

    doc.add_heading("Section 2. Payment Terms", level=2)
    doc.add_paragraph("Client shall remit payment for all undisputed invoice amounts within sixty (60) days of invoice date. Overdue amounts shall accrue late fees of 1.5% per month.")

    doc.add_heading("Section 3. Term and Renewal", level=2)
    doc.add_paragraph("This Agreement shall automatically renew for successive one-year periods unless either party provides at least sixty (60) days advance written notice of non-renewal prior to term end.")

    doc.add_heading("Section 4. Termination", level=2)
    doc.add_paragraph("Client may terminate this Agreement at any time for convenience upon written notice. Contractor has no right of termination for convenience.")

    doc.add_heading("Section 5. Limitation of Liability", level=2)
    doc.add_paragraph("Company's liability shall be unlimited and not subject to any monetary cap for any claims, damages, liabilities, or losses arising under this Agreement.")

    doc.add_heading("Section 6. Governing Law and Venue", level=2)
    doc.add_paragraph("This Agreement shall be governed by the laws of the State of New York, and disputes shall be subject to the exclusive jurisdiction of the state and federal courts in New York.")

    doc.save(str(path))


def generate_compliant_pdf():
    """Generate compliant agreement PDF with payment 30 days, no auto-renewal,
    liability capped at fees paid, and approved jurisdiction (India/Chennai).
    """
    path = SAMPLE_DIR / "compliant_services_agreement.pdf"
    pages = [
        [
            ("STANDARD SERVICES AGREEMENT",
             "This Standard Services Agreement is made between Apex Systems Pvt Ltd ('Company') and Technocraft Solutions ('Provider')."),
            ("Section 1. Services and Obligations",
             "Provider shall render enterprise consulting, testing, and system integration services under the direction of Company."),
            ("Section 2. Invoicing and Payment Terms",
             "Invoices shall be rendered upon completion of each monthly milestone. Client shall remit payment within thirty (30) days following receipt of invoice. "
             "No late payment interest shall apply unless agreed in writing."),
            ("Section 3. Term and Expiration",
             "The initial term of this Agreement shall be twelve (12) months. This Agreement shall not automatically renew and shall expire at the end of the Initial Term "
             "unless extended by mutual written agreement signed by both parties."),
            ("Section 4. Limitation of Liability",
             "Neither party's aggregate liability arising out of or related to this Agreement shall exceed the total fees paid under this Agreement in the preceding twelve months. "
             "In no event shall either party be liable for indirect, punitive, or consequential damages."),
            ("Section 5. Governing Law and Dispute Resolution",
             "This Agreement shall be governed by and construed in accordance with the laws of India. The courts in Chennai shall have exclusive jurisdiction over any disputes arising hereunder.")
        ]
    ]
    build_pdf_document(path, pages, "STANDARD SERVICES AGREEMENT")


def generate_ambiguous_docx():
    """Generate ambiguous agreement in DOCX format with vague payment, renewal, liability, and jurisdiction."""
    path = SAMPLE_DIR / "ambiguous_agreement.docx"
    doc = docx.Document()

    doc.add_heading("COLLABORATION FRAMEWORK AGREEMENT", level=1)
    doc.add_paragraph("This Collaboration Framework Agreement outlines general business principles between Alpha Ventures and Beta Innovators.")

    doc.add_heading("Section 1. Commercial Remuneration", level=2)
    doc.add_paragraph("Compensation for provided contributions shall be payable within a reasonable time after submission of milestones, taking into account general processing cadence.")

    doc.add_heading("Section 2. Duration and Extensions", level=2)
    doc.add_paragraph("The term may be continued from time to time as the parties may deem appropriate upon ongoing collaboration and mutual review.")

    doc.add_heading("Section 3. Responsibility and Legal Recourse", level=2)
    doc.add_paragraph("Liability shall be determined in accordance with applicable general law principles and equitable restitution.")

    doc.add_heading("Section 4. Jurisdiction and Resolution", level=2)
    doc.add_paragraph("Any controversies shall be brought before a competent court having jurisdiction over commercial matters in the relevant territory.")

    doc.save(str(path))


def generate_india_pdf():
    """Generate India-flavored freelance agreement PDF with Indian law, courts in Chennai, 45-day payment, renewal."""
    path = SAMPLE_DIR / "india_freelance_agreement.pdf"
    pages = [
        [
            ("FREELANCE CONSULTING AGREEMENT (INDIA)",
             "This Freelance Agreement is entered into between Bangalore Digital Technologies and Independent Consultant, residing in Chennai, India."),
            ("Clause 1. Professional Scope",
             "Consultant shall deliver design and architecture assets according to the agreed work plan."),
            ("Clause 2. Remuneration and Payment",
             "Professional fees shall be remitted within forty-five (45) days of invoice date directly to Consultant's designated bank account in India."),
            ("Clause 3. Term and Successive Renewal",
             "This Agreement shall automatically renew for additional six-month terms unless terminated with thirty (30) days notice prior to the end of the term."),
            ("Clause 4. Governing Law and Legal Venue",
             "This Agreement shall be governed by Indian law, with exclusive jurisdiction in the courts of Chennai, India.")
        ]
    ]
    build_pdf_document(path, pages, "FREELANCE CONSULTING AGREEMENT (INDIA)")


def generate_test_edge_cases():
    """Generate edge cases: empty.pdf, scanned_like.pdf, corrupted.pdf, fake.pdf, password_protected.pdf."""
    # 1. empty.pdf (0 bytes)
    empty_path = SAMPLE_DIR / "empty.pdf"
    empty_path.write_bytes(b"")

    # 2. scanned_like.pdf (Image/vector drawing with zero extractable text)
    scanned_path = SAMPLE_DIR / "scanned_like.pdf"
    doc_scanned = pymupdf.open()
    for _ in range(3):
        page = doc_scanned.new_page(width=595, height=842)
        # Draw some rectangles simulating scanned image blocks, no text
        page.draw_rect(pymupdf.Rect(50, 50, 545, 792), color=(0.7, 0.7, 0.7), fill=(0.95, 0.95, 0.95))
    doc_scanned.save(str(scanned_path))
    doc_scanned.close()

    # 3. corrupted.pdf
    corrupt_path = SAMPLE_DIR / "corrupted.pdf"
    corrupt_path.write_bytes(b"%PDF-1.4\n%Corrupted Byte Stream \x00\xff\xee\xdd\xcc Broken Header without xref or catalog")

    # 4. fake.pdf (Plain text file renamed to .pdf)
    fake_path = SAMPLE_DIR / "fake.pdf"
    fake_path.write_bytes(b"This is just a text file renamed to have a .pdf extension. It lacks PDF magic bytes.")

    # 5. password_protected.pdf
    pw_path = SAMPLE_DIR / "password_protected.pdf"
    doc_pw = pymupdf.open()
    page = doc_pw.new_page(width=595, height=842)
    page.insert_text(pymupdf.Point(72, 72), "Confidential Protected Contract Text", fontsize=12)
    # Save with user password
    doc_pw.save(
        str(pw_path),
        encryption=pymupdf.PDF_ENCRYPT_AES_256,
        user_pw="secret123",
        owner_pw="master123"
    )
    doc_pw.close()

    # 6. XSS named file content
    xss_content_path = SAMPLE_DIR / "xss_contract.pdf"
    doc_xss = pymupdf.open()
    p_xss = doc_xss.new_page(width=595, height=842)
    p_xss.insert_text(pymupdf.Point(72, 72), "Payment within 60 days. <script>alert('contract_xss')</script>", fontsize=12)
    doc_xss.save(str(xss_content_path))
    doc_xss.close()


def generate_all():
    """Generate all sample contracts and test fixtures."""
    generate_risky_pdf()
    generate_risky_docx()
    generate_compliant_pdf()
    generate_ambiguous_docx()
    generate_india_pdf()
    generate_test_edge_cases()
    print("All sample contracts and test fixtures generated successfully in:", SAMPLE_DIR)


if __name__ == "__main__":
    generate_all()
