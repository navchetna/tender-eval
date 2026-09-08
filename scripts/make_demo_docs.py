"""
Generates synthetic merchant compliance self-certification PDFs for the merchant-eval demo,
keyed to the clauses of the real reference document
(merchant-eval-docs/NPCI-UPI-Procedural-Guidelines-Circular.pdf — payment side: Annexure I
Settlement & Reports obligations; service side: Annexure XIV App Checklist items and the
Customer Complaints section).

Two merchants are authored with deliberately different compliance postures so the compliance
matrix and the risk-triage ranking show visible signal:
  - QuickKart: substantially compliant, with evidence/attestation references.
  - PayZippy:  material gaps (expired PCI-DSS AOC, T+2 settlement, complaint TAT breaches,
               missing mandatory app functions).

Usage:  python3 scripts/make_demo_docs.py
Output: merchant-eval-docs/<Merchant>-merchant-self-certification.pdf
(filenames contain "merchant"/"certification" so ingestion's classify() marks them SUBMISSION)

Requires: pip install fpdf2
"""
from __future__ import annotations

from pathlib import Path

from fpdf import FPDF

OUT_DIR = Path(__file__).resolve().parent.parent / 'merchant-eval-docs'

PAYMENT_COLUMNS = ['Clause Ref', 'Requirement', 'Compliance Status', 'Merchant Response / Evidence']
SERVICE_COLUMNS = ['Item Ref', 'Requirement', 'Mandatory/Optional', 'Compliance Status', 'Merchant Response / Evidence']

# Payment-compliance clauses drawn from the circular's settlement/security obligations
# (Annexure I Settlement & Reports, Authorization, Broad Security Considerations).
PAYMENT_CLAUSES = [
    ('PAY-01', 'Settlement of UPI transactions credited to merchant account within T+1 of the settlement cycle'),
    ('PAY-02', 'Daily reconciliation of raw transaction files against NPCI settlement reports'),
    ('PAY-03', 'PCI-DSS attestation of compliance (AOC) valid and on file for card-adjacent data handling'),
    ('PAY-04', 'Two-factor authentication enforced for every payment transaction as per UPI authorization rules'),
    ('PAY-05', 'Failed/declined transaction reversals processed within the prescribed TAT'),
    ('PAY-06', 'Dispute (chargeback/UDIR) responses filed within the prescribed dispute-resolution TAT'),
]

# Service-compliance items mirroring Annexure XIV (App Checklist) + Customer Complaints.
SERVICE_ITEMS = [
    ('SRV-01', 'Log a complaint function available to the customer in the payment journey', 'M'),
    ('SRV-02', 'Transaction history visible to the customer', 'M'),
    ('SRV-03', 'Customer grievances resolved within T+5 working days', 'M'),
    ('SRV-04', 'Deregistration and deletion of customer account/VPA supported on request', 'M'),
    ('SRV-05', 'Charges/fees disclosed to the customer before payment confirmation', 'M'),
    ('SRV-06', 'Refunds to customers processed within 7 days of approval', 'M'),
    ('SRV-07', 'Whitelisting of frequent payees offered to customers', 'O'),
]

MERCHANTS: dict[str, dict] = {
    'QuickKart': {
        'profile': (
            'QuickKart Retail Pvt. Ltd. is an online marketplace merchant accepting UPI payments '
            'through its acquiring bank. This self-certification covers the quarter ending 30 June 2026.'
        ),
        'payment': {
            'PAY-01': ('Compliant', 'Settlement received T+1 across the full quarter; bank settlement advice refs QK-SET-2026-Q2-001..091 on file.'),
            'PAY-02': ('Compliant', 'Automated daily reconciliation via recon tool v3.2; zero unresolved breaks older than 2 days; recon logs ref QK-REC-2026-Q2.'),
            'PAY-03': ('Compliant', 'PCI-DSS v4.0 AOC dated 12 Jan 2026, valid to 11 Jan 2027; QSA: SecureAssess India; certificate ref QK-PCI-2026-014.'),
            'PAY-04': ('Compliant', 'All transactions routed through UPI 2FA (device binding + UPI PIN); no bypass paths; last security audit ref QK-SEC-2026-03.'),
            'PAY-05': ('Compliant', 'Auto-reversal within 24 hours for failed debits; quarterly average reversal time 6.2 hours; report ref QK-REV-2026-Q2.'),
            'PAY-06': ('Partial', 'UDIR responses averaged 4.1 days against the 3-day TAT in peak weeks of May 2026; remediation: dispute-desk staffing increased from 2 to 4 FTE in July.'),
        },
        'service': {
            'SRV-01': ('Compliant', 'In-app "Raise an issue" available on every order and payment screen; ticket ids issued instantly.'),
            'SRV-02': ('Compliant', 'Full transaction history with UPI transaction reference numbers available under Account > Payments.'),
            'SRV-03': ('Compliant', 'Quarterly average grievance resolution 2.8 working days; 97.4% within T+5; CRM report ref QK-GRV-2026-Q2.'),
            'SRV-04': ('Compliant', 'Self-service account deletion live since Feb 2026; VPA mappings removed within 24 hours of request.'),
            'SRV-05': ('Compliant', 'No customer-borne charges on UPI; zero-fee disclosure shown on the payment confirmation screen.'),
            'SRV-06': ('Compliant', 'Refunds auto-initiated on approval; quarterly average 2.1 days to customer account; report ref QK-RFD-2026-Q2.'),
            'SRV-07': ('Compliant', 'Saved payees with nicknames supported for VPA and account+IFSC.'),
        },
    },
    'PayZippy': {
        'profile': (
            'PayZippy Commerce Ltd. is a customer-facing bill-payments and recharge merchant on UPI. '
            'This self-certification covers the quarter ending 30 June 2026.'
        ),
        'payment': {
            'PAY-01': ('Non-compliant', 'Settlement currently received on T+2 due to a legacy nodal-account arrangement; migration to T+1 settlement planned for Q4 2026.'),
            'PAY-02': ('Partial', 'Reconciliation performed weekly, not daily; 41 unresolved breaks older than 7 days at quarter end.'),
            'PAY-03': ('Non-compliant', 'PCI-DSS AOC expired 28 Feb 2026; re-assessment engagement not yet signed with a QSA.'),
            'PAY-04': ('Compliant', 'UPI PIN + device binding enforced on all flows; no card-on-file bypass.'),
            'PAY-05': ('Partial', 'Failed-transaction reversals average 3.5 days against the 24-hour norm; manual reversal queue is the bottleneck.'),
            'PAY-06': ('Partial', 'Dispute responses tracked in a shared mailbox without TAT reporting; average response time not measured this quarter.'),
        },
        'service': {
            'SRV-01': ('Non-compliant', 'No in-app complaint function; customers are directed to an email address with no ticket id issued.'),
            'SRV-02': ('Compliant', 'Transaction history with UPI reference numbers available in the app.'),
            'SRV-03': ('Non-compliant', 'Quarterly average grievance resolution 11 working days; 52% resolved within T+5.'),
            'SRV-04': ('Partial', 'Account deletion possible only via support request; average completion 12 days; no self-service option.'),
            'SRV-05': ('Partial', 'Convenience fee on some bill categories shown only on the final receipt, not before confirmation; fix scheduled for the next app release.'),
            'SRV-06': ('Partial', 'Refunds average 9 days against the 7-day norm during high-volume weeks.'),
            'SRV-07': ('Compliant', 'Saved billers and payee whitelisting supported.'),
        },
    },
}


class CertificationPdf(FPDF):
    def header(self) -> None:  # noqa: D102 — fpdf2 hook
        if self.page_no() > 1:
            self.set_font('helvetica', 'I', 8)
            self.set_text_color(120)
            self.cell(0, 6, self._header_text, align='R', new_x='LMARGIN', new_y='NEXT')
            self.set_text_color(0)
            self.ln(2)

    _header_text = ''


def _title_page(pdf: CertificationPdf, merchant: str, profile: str) -> None:
    pdf.add_page()
    pdf.ln(30)
    pdf.set_font('helvetica', 'B', 22)
    pdf.multi_cell(0, 12, f'{merchant}\nMerchant Compliance Self-Certification', align='C', new_x='LMARGIN', new_y='NEXT')
    pdf.ln(6)
    pdf.set_font('helvetica', '', 12)
    pdf.multi_cell(0, 8, 'Periodic self-certification against the NPCI UPI Procedural Guidelines', align='C', new_x='LMARGIN', new_y='NEXT')
    pdf.multi_cell(0, 8, 'Reporting period: Q2 FY 2026-27 (quarter ending 30 June 2026)', align='C', new_x='LMARGIN', new_y='NEXT')
    pdf.ln(14)
    pdf.set_font('helvetica', '', 11)
    pdf.multi_cell(0, 7, profile, new_x='LMARGIN', new_y='NEXT')
    pdf.ln(6)
    pdf.multi_cell(
        0, 7,
        'This document certifies the merchant\'s compliance status against the payment and service '
        'obligations applicable to customer-facing merchants on the Unified Payments Interface, as '
        'set out in the NPCI UPI Procedural Guidelines and associated circulars. Statuses are '
        'self-attested; evidence references are available to the regulator on request.',
    )


def _section_heading(pdf: CertificationPdf, number: int, title: str) -> None:
    pdf.add_page()
    pdf.set_font('helvetica', 'B', 16)
    pdf.cell(0, 10, f'{number}. {title}', new_x='LMARGIN', new_y='NEXT')
    pdf.ln(2)


def _table(pdf: CertificationPdf, columns: list[str], rows: list[list[str]], widths: list[int]) -> None:
    pdf.set_font('helvetica', '', 9)
    with pdf.table(col_widths=widths, text_align='LEFT', line_height=5.5) as table:
        header = table.row()
        pdf.set_font('helvetica', 'B', 9)
        for col in columns:
            header.cell(col)
        pdf.set_font('helvetica', '', 9)
        for row in rows:
            r = table.row()
            for value in row:
                r.cell(value)


def build_pdf(merchant: str, spec: dict) -> Path:
    pdf = CertificationPdf(format='A4')
    pdf._header_text = f'{merchant} - Merchant Compliance Self-Certification - Q2 FY 2026-27'
    pdf.set_auto_page_break(auto=True, margin=18)
    pdf.set_title(f'{merchant} Merchant Compliance Self-Certification')

    _title_page(pdf, merchant, spec['profile'])

    _section_heading(pdf, 2, 'Payment Compliance Self-Certification')
    pdf.set_font('helvetica', '', 10)
    pdf.multi_cell(
        0, 6,
        'Self-certified status against the settlement, reconciliation, security and dispute '
        'obligations of the NPCI UPI Procedural Guidelines (ref. Settlement of UPI Transactions; '
        'Annexure I - Settlement & Reports; Annexure XIII - Broad Security Considerations).',
    )
    pdf.ln(3)
    payment_rows = [
        [ref, requirement, *spec['payment'][ref]]
        for ref, requirement in PAYMENT_CLAUSES
    ]
    _table(pdf, PAYMENT_COLUMNS, payment_rows, [16, 46, 22, 66])

    _section_heading(pdf, 3, 'Service Compliance Self-Certification')
    pdf.set_font('helvetica', '', 10)
    pdf.multi_cell(
        0, 6,
        'Self-certified status against the customer-facing service obligations of the NPCI UPI '
        'Procedural Guidelines (ref. Customer Complaints; Customer Registration; Annexure XIV - '
        'App Checklist).',
    )
    pdf.ln(3)
    service_rows = [
        [ref, requirement, mo, *spec['service'][ref]]
        for ref, requirement, mo in SERVICE_ITEMS
    ]
    _table(pdf, SERVICE_COLUMNS, service_rows, [14, 42, 18, 22, 54])

    pdf.add_page()
    pdf.set_font('helvetica', 'B', 16)
    pdf.cell(0, 10, '4. Declaration', new_x='LMARGIN', new_y='NEXT')
    pdf.ln(2)
    pdf.set_font('helvetica', '', 10)
    pdf.multi_cell(
        0, 6,
        f'The undersigned certifies on behalf of {merchant} that the statuses above are true and '
        'complete as of the reporting date, and that any clause marked Partial or Non-compliant '
        'is accompanied by the current remediation position stated in the response column.\n\n'
        'Authorised signatory: Chief Compliance Officer\n'
        'Date: 15 July 2026',
    )

    out = OUT_DIR / f'{merchant}-merchant-self-certification.pdf'
    pdf.output(str(out))
    return out


def main() -> None:
    OUT_DIR.mkdir(exist_ok=True)
    for merchant, spec in MERCHANTS.items():
        path = build_pdf(merchant, spec)
        print(f'wrote {path}')


if __name__ == '__main__':
    main()
