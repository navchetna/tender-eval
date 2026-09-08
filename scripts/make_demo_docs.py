"""
Generates synthetic merchant compliance self-certification PDFs for the merchant-eval demo,
keyed to the ACTUAL rows of the reference document's approved sections
(merchant-eval-docs/NPCI-UPI-Procedural-Guidelines-Circular.pdf):

  - Payment side  = Annexure I (Settlement & Reports): the 3-row settlement-scenario table
    plus the settlement/reconciliation/report obligations from its Note/Please-note bullets.
  - Service side  = Annexure XIV (APP CHECKLIST): the Level 1-13 checklist items, referenced
    by level+row (L2.d, L9.c, ...) with the item text mirrored so the alignment model can
    match each self-certified row to the corresponding checklist row.

This row-for-row mirroring matters: the normalization view's rows come from the circular
section's own tables, and a merchant response only shows up in the compliance matrix (and
therefore in scoring and risk triage) when the alignment model can pair the merchant's row
with a circular row. Free-floating clause ids that don't exist in the circular align to
nothing and produce an empty matrix.

Two merchants are authored with deliberately different compliance postures so the matrix and
the risk-triage ranking show visible signal:
  - QuickKart: substantially compliant, evidence references throughout, two Partial items.
  - PayZippy:  material gaps on mandatory checklist items (no in-app complaint, no
               self-service deregistration/deletion, VPA moratorium not enforced, ...) and on
               settlement obligations (weekly reconciliation, missed settlement obligations,
               no dedicated recon team).

Usage:  python3 scripts/make_demo_docs.py
Output: merchant-eval-docs/<Merchant>-merchant-self-certification.pdf
(filenames contain "merchant"/"certification" so ingestion's classify() marks them SUBMISSION)

Requires: pip install fpdf2
NOTE: core Helvetica is latin-1 — keep the content plain ASCII (no bullets/en-dashes).
"""
from __future__ import annotations

from pathlib import Path

from fpdf import FPDF

OUT_DIR = Path(__file__).resolve().parent.parent / 'merchant-eval-docs'

# --- Payment side: Annexure I (Settlement & Reports) -----------------------------------

# The circular's settlement-scenario table, mirrored verbatim — these three rows ARE the
# payment compliance matrix's rows.
SETTLEMENT_SCENARIOS = [
    ('1', 'Sending Bank live in UPI & Recipient Bank live in IMPS only (Debit in UPI, Credit in IMPS; Settlement in IMPS)'),
    ('2', 'Both the Sending & receiving Bank live in IMPS (Credit in IMPS; Settlement in IMPS)'),
    ('3', 'Both Banks live in UPI (Debit in UPI, Credit in UPI; Settlement in IMPS)'),
]

# Obligations drawn from Annexure I's Note / Please-note bullets and reports list.
SETTLEMENT_OBLIGATIONS = [
    ('OB-1', 'Download all settlement files (Raw data file, NTSL/DSR, STL) daily from DMS/RGCS'),
    ('OB-2', 'Perform reconciliation as per the guidelines issued by NPCI from time to time'),
    ('OB-3', 'Maintain a separate operations and reconciliation team for day-to-day settlement activities'),
    ('OB-4', 'Verify accuracy of the Daily Settlement Reports against own transaction data'),
    ('OB-5', 'Meet the daily settlement obligation (no more than two failures in a month)'),
    ('OB-6', 'Letter of authority to RBI for net debit/credit of the settlement account, via sponsor bank'),
    ('OB-7', 'Consume the separate UPI DSR for transactions where the credit request is processed through UPI'),
]

PAYMENT_SCENARIO_COLUMNS = ['Sr', 'Settlement scenario (Annexure I)', 'Compliance Status', 'Merchant Response / Evidence']
PAYMENT_OBLIGATION_COLUMNS = ['Ref', 'Obligation (Annexure I - Settlement & Reports)', 'Compliance Status', 'Merchant Response / Evidence']

# --- Service side: Annexure XIV (APP CHECKLIST) -----------------------------------------

# (ref, checklist item mirrored from Annexure XIV, M/O)
SERVICE_ITEMS = [
    ('L1.a', 'App available for download on Play Store', 'M'),
    ('L1.b', 'App available for download on App Store', 'M'),
    ('L2.a', 'Send (Push) from home screen using Virtual Address (VPA) and Account/IFSC', 'M'),
    ('L2.b', 'Collect from home screen using Virtual Address', 'M'),
    ('L2.c', 'Add/Link a Bank A/C from home screen', 'M'),
    ('L2.d', 'Transaction history available from home screen', 'M'),
    ('L2.e', 'Mobile Banking registration with manual card number & expiry entry', 'M'),
    ('L2.f', 'Generate MPIN / Set MPIN from home screen', 'M'),
    ('L2.g', 'Change MPIN with old and new MPIN entered manually', 'M'),
    ('L2.i', 'Log a complaint from home screen', 'M'),
    ('L3.a', 'Registration via encrypted SMS from the app without user typing (PKI, dual-SIM selection)', 'M'),
    ('L3.b', 'Profile creation on registration', 'M'),
    ('L3.c', 'VPA creation on registration', 'M'),
    ('L3.f', 'Deregistration from PSP supported in-app', 'M'),
    ('L3.g', 'Deletion of Account linked to VPA supported', 'M'),
    ('L3.h', 'Deletion of VPA supported', 'M'),
    ('L4.i', 'Restoring of VPA by PSP in case of deletion by user (at least 2 years moratorium)', 'M'),
    ('L5.a', 'List of banks displayed as Issuer in a drop-down menu', 'M'),
    ('L5.c', 'Set-MPIN flow via debit card last 6 digits & expiry + OTP, or "Continue with Existing MPIN"', 'M'),
    ('L5.G', 'One PSP app can register multiple bank accounts with multiple VPAs', 'M'),
    ('L6.a', 'Pay using VPA', 'M'),
    ('L6.b', 'Pay using a/c & IFSC', 'M'),
    ('L6.e', 'MPIN pre-approved pay transaction', 'M'),
    ('L6.g', 'Online transaction confirmation shown to the customer', 'M'),
    ('L7.a', 'Collect using VPA', 'M'),
    ('L7.e', 'Display of VPA and Name for incoming collect request', 'M'),
    ('L7.f', 'Display of expiry time for incoming collect request', 'M'),
    ('L7.g', 'Default validity of 30 minutes when customer does not specify collect expiry', 'M'),
    ('L8.a', 'Balance enquiry with account selection', 'M'),
    ('L9.b', 'Raise a query / dispute, date-wise', 'M'),
    ('L9.c', 'Query/dispute screen displays Transaction ID, beneficiary & remitter VPA, date & time, amount', 'M'),
    ('L9.d', 'Option to raise a query / log a complaint against each transaction in status view', 'M'),
    ('L9.e', 'Last 5 transactions visible', 'M'),
    ('L10.a', 'Hot-listed or deleted VPA not re-allocated (2 years moratorium)', 'M'),
    ('L11.a', 'Pay by UPI entry point', 'M'),
    ('L11.b', 'Collect by UPI entry point', 'M'),
    ('L11.c', 'Reject collect request option', 'M'),
    ('L12.c', 'QR-based payment displays at least VPA, amount and name to the customer', 'M'),
    ('L13.a1', 'Intent call from merchant apps supported on Android', 'M'),
    ('L13.a2', 'Intent call from merchant apps supported on iOS', 'M'),
]

SERVICE_COLUMNS = ['Ref', 'Checklist item (Annexure XIV)', 'M/O', 'Compliance Status', 'Merchant Response / Evidence']

# --- Merchant postures -------------------------------------------------------------------

_QK_SERVICE_DEFAULT = ('Compliant', 'Verified in release 5.2 regression pack; UI evidence ref QK-APP-2026-Q2.')
_PZ_SERVICE_DEFAULT = ('Compliant', 'Verified in current production build 3.9; screenshots ref PZ-APP-2026-Q2.')

MERCHANTS: dict[str, dict] = {
    'QuickKart': {
        'profile': (
            'QuickKart Retail Pvt. Ltd. is an online marketplace merchant accepting UPI payments '
            'through its acquiring bank. This self-certification covers the quarter ending 30 June 2026 '
            'and certifies compliance against the NPCI UPI Procedural Guidelines: the settlement and '
            'reports obligations of Annexure I on the payment side, and the Annexure XIV app checklist '
            'on the service side.'
        ),
        'summary': (
            'QuickKart certifies full compliance with all three Annexure I settlement scenarios and '
            'with 38 of the 40 mandatory Annexure XIV checklist items covered by this certification. '
            'Two items are certified Partial with committed remediation dates. Independent evidence '
            'references are maintained in the evidence register (section 5) and are available to the '
            'regulator on request.'
        ),
        'scenarios': {
            '1': ('Compliant', 'IMPS credit-leg raw files ingested daily; scenario-1 transactions reconciled T+1 against bank IMPS raw file; zero unresolved breaks at quarter end; ref QK-REC-2026-Q2-S1.'),
            '2': ('Compliant', 'IMPS-to-IMPS flows reconciled inside the existing IMPS recon stream, matched to acquirer MIS daily; ref QK-REC-2026-Q2-S2.'),
            '3': ('Compliant', 'Separate UPI DSR consumed daily for UPI-credit transactions; auto-matching of UPI raw file vs DSR vs ledger; ref QK-REC-2026-Q2-S3.'),
        },
        'obligations': {
            'OB-1': ('Compliant', 'Automated SFTP pull of Raw, NTSL/DSR and STL files at each cutover; job logs ref QK-SET-2026-Q2-001..091.'),
            'OB-2': ('Compliant', 'Reconciliation SOP v4 aligned to NPCI RGCS circulars; recon tool v3.2; zero breaks older than 2 days.'),
            'OB-3': ('Compliant', 'Dedicated 6-member settlement operations & reconciliation team, separate from finance; org chart ref QK-ORG-2026.'),
            'OB-4': ('Compliant', 'DSR figures verified daily against internal switch data; variance report auto-generated; ref QK-DSR-2026-Q2.'),
            'OB-5': ('Compliant', 'Zero settlement-obligation failures in the quarter; funding buffer maintained at 1.4x average net debit.'),
            'OB-6': ('Compliant', 'Board-approved letter of authority on file with sponsor bank; ref QK-LOA-2024-11.'),
            'OB-7': ('Partial', 'UPI-credit DSR consumed daily, but STL automation falls back to manual download on RTGS holidays; full automation scheduled Aug 2026; ref QK-STL-2026-07.'),
        },
        'service': {
            'L9.b': ('Partial', 'Query/dispute can be raised per transaction reference; date-wise search ships in release 5.3 (Aug 2026); ref QK-CRM-2026-Q2.'),
            'L13.a2': ('Partial', 'iOS intent-call support in beta with two merchant apps; production rollout scheduled Sep 2026; ref QK-IOS-2026-08.'),
        },
        'service_default': _QK_SERVICE_DEFAULT,
        'evidence': [
            ('QK-SET-2026-Q2-001..091', 'Daily settlement file download job logs, full quarter', 'Settlement Ops'),
            ('QK-REC-2026-Q2-S1..S3', 'Per-scenario reconciliation packs (IMPS credit, IMPS-IMPS, UPI credit)', 'Recon Team'),
            ('QK-DSR-2026-Q2', 'Daily Settlement Report verification and variance reports', 'Recon Team'),
            ('QK-PCI-2026-014', 'PCI-DSS v4.0 AOC valid to 11 Jan 2027 (QSA: SecureAssess India)', 'InfoSec'),
            ('QK-APP-2026-Q2', 'Annexure XIV checklist regression pack, release 5.2, all screens', 'QA'),
            ('QK-CRM-2026-Q2', 'Complaint/grievance CRM extract: 97.4% resolved within T+5', 'Customer Service'),
            ('QK-LOA-2024-11', 'Letter of authority lodged with sponsor bank for RBI settlement account', 'Finance'),
            ('QK-IOS-2026-08', 'iOS intent-call beta test report', 'Engineering'),
        ],
    },
    'PayZippy': {
        'profile': (
            'PayZippy Commerce Ltd. is a customer-facing bill-payments and recharge merchant on UPI. '
            'This self-certification covers the quarter ending 30 June 2026 and certifies compliance '
            'against the NPCI UPI Procedural Guidelines: the settlement and reports obligations of '
            'Annexure I on the payment side, and the Annexure XIV app checklist on the service side.'
        ),
        'summary': (
            'PayZippy certifies compliance with the majority of checklist items but reports material '
            'gaps this quarter: settlement reconciliation is performed weekly rather than daily, two '
            'daily settlement obligations were missed in June 2026, the separate UPI DSR is not yet '
            'consumed, and several mandatory Annexure XIV items (in-app complaint logging, in-app '
            'deregistration and deletion, collect-request expiry display, VPA re-allocation moratorium, '
            'iOS intent calls) are not yet implemented. Remediation positions are stated per item.'
        ),
        'scenarios': {
            '1': ('Compliant', 'IMPS credit-leg transactions reconciled against bank statement weekly; no unresolved breaks over 30 days; ref PZ-REC-2026-Q2.'),
            '2': ('Partial', 'IMPS-to-IMPS flows are not segregated from other IMPS traffic in recon; 41 unresolved breaks older than 7 days at quarter end.'),
            '3': ('Non-compliant', 'Separate UPI DSR for UPI-credit transactions is not consumed; these transactions are reconciled only against the bank statement, not the DSR.'),
        },
        'obligations': {
            'OB-1': ('Partial', 'Raw data file and DSR downloaded manually each morning; STL not downloaded on 9 occasions in the quarter.'),
            'OB-2': ('Non-compliant', 'Reconciliation performed weekly, not daily as per NPCI guidelines; migration to daily recon planned Q4 2026.'),
            'OB-3': ('Non-compliant', 'No separate operations and reconciliation team; recon handled part-time by two finance staff.'),
            'OB-4': ('Non-compliant', 'Daily Settlement Report figures are not verified against internal transaction data; verification control planned with the daily-recon project.'),
            'OB-5': ('Non-compliant', 'Two daily settlement obligations missed in June 2026 due to funding shortfall on the nodal account; funding buffer under review.'),
            'OB-6': ('Compliant', 'Letter of authority on file with sponsor bank since onboarding; ref PZ-LOA-2023-04.'),
            'OB-7': ('Non-compliant', 'UPI DSR feed not integrated; dependent on OB-2 daily-recon migration.'),
        },
        'service': {
            'L2.i': ('Non-compliant', 'No in-app complaint function; customers are directed to a support email address and no ticket id is issued.'),
            'L3.f': ('Non-compliant', 'Deregistration only via a support request; average completion 12 days; no in-app option.'),
            'L3.g': ('Non-compliant', 'Account unlinking requires a support request; not available in-app.'),
            'L3.h': ('Non-compliant', 'VPA deletion not available to the customer in-app or via support self-service.'),
            'L4.i': ('Partial', 'Deleted VPAs are blocked for 90 days only; the 2-year moratorium is not enforced in the current identity store.'),
            'L7.f': ('Non-compliant', 'Expiry time of an incoming collect request is not displayed to the customer.'),
            'L7.g': ('Partial', 'Default collect validity is set to 60 minutes instead of the prescribed 30 minutes.'),
            'L8.a': ('Partial', 'Balance enquiry available but fails intermittently for one sponsor bank (approx. 6% of attempts in June 2026).'),
            'L9.c': ('Partial', 'Dispute screen shows amount and date but not the beneficiary/remitter VPA or transaction ID.'),
            'L9.d': ('Non-compliant', 'No per-transaction "raise a query / log a complaint" option in the transaction status view.'),
            'L10.a': ('Non-compliant', 'Deleted VPAs can be re-allocated to a new customer after 90 days; moratorium control not implemented.'),
            'L11.c': ('Partial', 'Collect requests can be rejected, but the option is nested two screens deep and not shown on the request itself.'),
            'L13.a2': ('Non-compliant', 'Intent calls from merchant apps are not supported on iOS.'),
        },
        'service_default': _PZ_SERVICE_DEFAULT,
        'evidence': [
            ('PZ-REC-2026-Q2', 'Weekly reconciliation workpapers for the quarter', 'Finance'),
            ('PZ-LOA-2023-04', 'Letter of authority lodged with sponsor bank', 'Finance'),
            ('PZ-APP-2026-Q2', 'App checklist walkthrough screenshots, production build 3.9', 'QA'),
            ('PZ-RMD-2026-Q3', 'Remediation plan: daily reconciliation, UPI DSR integration, in-app servicing', 'Compliance'),
        ],
    },
}


class CertificationPdf(FPDF):
    _header_text = ''

    def header(self) -> None:  # noqa: D102 — fpdf2 hook
        if self.page_no() > 1:
            self.set_font('helvetica', 'I', 8)
            self.set_text_color(120)
            self.cell(0, 6, self._header_text, align='R', new_x='LMARGIN', new_y='NEXT')
            self.set_text_color(0)
            self.ln(2)

    def footer(self) -> None:  # noqa: D102 — fpdf2 hook
        self.set_y(-14)
        self.set_font('helvetica', 'I', 8)
        self.set_text_color(120)
        self.cell(0, 6, f'Page {self.page_no()}', align='C')
        self.set_text_color(0)


def _title_page(pdf: CertificationPdf, merchant: str, spec: dict) -> None:
    pdf.add_page()
    pdf.ln(26)
    pdf.set_font('helvetica', 'B', 22)
    pdf.multi_cell(0, 12, f'{merchant}\nMerchant Compliance Self-Certification', align='C', new_x='LMARGIN', new_y='NEXT')
    pdf.ln(4)
    pdf.set_font('helvetica', '', 12)
    pdf.multi_cell(0, 8, 'Periodic self-certification against the NPCI UPI Procedural Guidelines', align='C', new_x='LMARGIN', new_y='NEXT')
    pdf.multi_cell(0, 8, 'Reporting period: Q2 FY 2026-27 (quarter ending 30 June 2026)', align='C', new_x='LMARGIN', new_y='NEXT')
    pdf.ln(12)
    pdf.set_font('helvetica', 'B', 13)
    pdf.cell(0, 8, '1. Merchant profile and certification scope', new_x='LMARGIN', new_y='NEXT')
    pdf.set_font('helvetica', '', 11)
    pdf.multi_cell(0, 7, spec['profile'], new_x='LMARGIN', new_y='NEXT')
    pdf.ln(4)
    pdf.set_font('helvetica', 'B', 11)
    pdf.cell(0, 7, 'Executive summary', new_x='LMARGIN', new_y='NEXT')
    pdf.set_font('helvetica', '', 11)
    pdf.multi_cell(0, 7, spec['summary'], new_x='LMARGIN', new_y='NEXT')
    pdf.ln(4)
    pdf.set_font('helvetica', '', 10)
    pdf.multi_cell(
        0, 6,
        'Statuses in this document are self-attested by the merchant. "Compliant" means the control '
        'or app function is live and evidenced; "Partial" means it is live with stated limitations or '
        'in remediation; "Non-compliant" means it is not implemented as of the reporting date. '
        'Evidence references resolve through the evidence register in section 5.',
    )


def _section_heading(pdf: CertificationPdf, number: int, title: str) -> None:
    pdf.add_page()
    pdf.set_font('helvetica', 'B', 16)
    pdf.cell(0, 10, f'{number}. {title}', new_x='LMARGIN', new_y='NEXT')
    pdf.ln(2)


def _subheading(pdf: CertificationPdf, title: str) -> None:
    pdf.ln(3)
    pdf.set_font('helvetica', 'B', 12)
    pdf.cell(0, 8, title, new_x='LMARGIN', new_y='NEXT')
    pdf.ln(1)


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

    _title_page(pdf, merchant, spec)

    _section_heading(pdf, 2, 'Payment Compliance Self-Certification')
    pdf.set_font('helvetica', '', 10)
    pdf.multi_cell(
        0, 6,
        'Self-certified status against Annexure I (Settlement & Reports) of the NPCI UPI Procedural '
        'Guidelines: first the three settlement scenarios of the Annexure I settlement table, then '
        'the settlement, reconciliation and reports obligations stated in the same annexure.',
    )

    _subheading(pdf, '2.1 Settlement scenario readiness (Annexure I settlement table)')
    scenario_rows = [[sr, text, *spec['scenarios'][sr]] for sr, text in SETTLEMENT_SCENARIOS]
    _table(pdf, PAYMENT_SCENARIO_COLUMNS, scenario_rows, [10, 52, 22, 66])

    _subheading(pdf, '2.2 Settlement and reports obligations (Annexure I notes and reports availability)')
    obligation_rows = [[ref, text, *spec['obligations'][ref]] for ref, text in SETTLEMENT_OBLIGATIONS]
    _table(pdf, PAYMENT_OBLIGATION_COLUMNS, obligation_rows, [12, 50, 22, 66])

    _section_heading(pdf, 3, 'Service Compliance Self-Certification')
    pdf.set_font('helvetica', '', 10)
    pdf.multi_cell(
        0, 6,
        'Self-certified status against the mandatory items of Annexure XIV (APP CHECKLIST) of the '
        'NPCI UPI Procedural Guidelines. The Ref column cites the checklist level and row (for '
        'example L2.d = Level 2, row d) and the item text mirrors the checklist wording.',
    )
    pdf.ln(3)
    default_status = spec['service_default']
    service_rows = [
        [ref, item, mo, *spec['service'].get(ref, default_status)]
        for ref, item, mo in SERVICE_ITEMS
    ]
    _table(pdf, SERVICE_COLUMNS, service_rows, [13, 52, 9, 21, 55])

    _section_heading(pdf, 4, 'Declaration')
    pdf.set_font('helvetica', '', 10)
    pdf.multi_cell(
        0, 6,
        f'The undersigned certifies on behalf of {merchant} that the statuses above are true and '
        'complete as of the reporting date, and that every item marked Partial or Non-compliant is '
        'accompanied by its current remediation position in the response column.\n\n'
        'Authorised signatory: Chief Compliance Officer\n'
        'Date: 15 July 2026',
    )

    _section_heading(pdf, 5, 'Evidence register')
    pdf.set_font('helvetica', '', 10)
    pdf.multi_cell(0, 6, 'Evidence packs referenced in sections 2 and 3, available to the regulator on request.')
    pdf.ln(3)
    _table(pdf, ['Evidence ref', 'Description', 'Custodian'], [list(e) for e in spec['evidence']], [34, 84, 32])

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
