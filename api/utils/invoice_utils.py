import os
from datetime import datetime
from io import BytesIO
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT, TA_RIGHT, TA_CENTER


def generate_invoice_pdf(
    invoice_id: str,
    candidate_name: str,
    jd_title: str,
    client_email: str,
    placement_date: datetime,
    fee_amount: float,
) -> bytes:
    """Generate a PDF invoice using reportlab. Returns PDF bytes."""
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter, topMargin=0.5*inch, bottomMargin=0.5*inch)

    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        'CustomTitle',
        parent=styles['Heading1'],
        fontSize=24,
        textColor=colors.HexColor('#0f172a'),
        spaceAfter=30,
        alignment=TA_CENTER,
    )
    heading_style = ParagraphStyle(
        'CustomHeading',
        parent=styles['Heading2'],
        fontSize=12,
        textColor=colors.HexColor('#1e293b'),
        spaceAfter=10,
        spaceBefore=10,
    )

    elements = []

    elements.append(Paragraph("INVOICE", title_style))
    elements.append(Spacer(1, 0.2*inch))

    invoice_info = [
        ["Invoice ID:", invoice_id],
        ["Date:", placement_date.strftime('%Y-%m-%d')],
        ["Bill To:", client_email],
    ]
    invoice_table = Table(invoice_info, colWidths=[2*inch, 4*inch])
    invoice_table.setStyle(TableStyle([
        ('FONT', (0, 0), (0, -1), 'Helvetica-Bold', 10),
        ('FONT', (1, 0), (1, -1), 'Helvetica', 10),
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
    ]))
    elements.append(invoice_table)
    elements.append(Spacer(1, 0.3*inch))

    elements.append(Paragraph("Placement Details", heading_style))

    placement_data = [
        ["Candidate Name:", candidate_name],
        ["Position:", jd_title],
        ["Placement Date:", placement_date.strftime('%Y-%m-%d')],
    ]
    placement_table = Table(placement_data, colWidths=[2*inch, 4*inch])
    placement_table.setStyle(TableStyle([
        ('FONT', (0, 0), (0, -1), 'Helvetica-Bold', 10),
        ('FONT', (1, 0), (1, -1), 'Helvetica', 10),
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
    ]))
    elements.append(placement_table)
    elements.append(Spacer(1, 0.3*inch))

    elements.append(Paragraph("Fee Summary", heading_style))

    fee_data = [
        ["Description", "Amount"],
        ["Placement Fee (15%)", f"${fee_amount:,.2f}"],
    ]
    fee_table = Table(fee_data, colWidths=[3*inch, 3*inch])
    fee_table.setStyle(TableStyle([
        ('FONT', (0, 0), (-1, 0), 'Helvetica-Bold', 11),
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#f1f5f9')),
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('ALIGN', (1, 0), (1, -1), 'RIGHT'),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
        ('TOPPADDING', (0, 0), (-1, -1), 8),
        ('GRID', (0, 0), (-1, -1), 1, colors.HexColor('#e2e8f0')),
        ('FONT', (0, 1), (-1, -1), 'Helvetica', 10),
    ]))
    elements.append(fee_table)
    elements.append(Spacer(1, 0.3*inch))

    total_data = [
        ["TOTAL DUE", f"${fee_amount:,.2f}"],
    ]
    total_table = Table(total_data, colWidths=[3*inch, 3*inch])
    total_table.setStyle(TableStyle([
        ('FONT', (0, 0), (-1, 0), 'Helvetica-Bold', 12),
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#0f172a')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.HexColor('#f1f5f9')),
        ('ALIGN', (0, 0), (0, 0), 'LEFT'),
        ('ALIGN', (1, 0), (1, 0), 'RIGHT'),
        ('VALIGN', (0, 0), (-1, 0), 'MIDDLE'),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
        ('TOPPADDING', (0, 0), (-1, 0), 12),
    ]))
    elements.append(total_table)

    doc.build(elements)
    pdf_bytes = buffer.getvalue()
    buffer.close()
    return pdf_bytes


def save_invoice_pdf(jd_id: str, candidate_id: str, pdf_bytes: bytes) -> str:
    """Save PDF to /data/invoices/{jd_id}/ and return file path."""
    invoice_dir = os.path.join("/data", "invoices", jd_id)
    os.makedirs(invoice_dir, exist_ok=True)

    filename = f"{candidate_id}_invoice.pdf"
    file_path = os.path.join(invoice_dir, filename)

    with open(file_path, "wb") as f:
        f.write(pdf_bytes)

    return file_path
