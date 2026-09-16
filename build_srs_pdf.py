import os
import re
import markdown
from xhtml2pdf import pisa

def build_pdf():
    srs_md_path = os.path.join(os.getcwd(), 'SRS.md')
    pdf_out_path = os.path.join(os.getcwd(), 'Aarogyam_SRS_v2.1.pdf')
    
    with open(srs_md_path, 'r', encoding='utf-8') as f:
        md_text = f.read()

    # Preprocess markdown to clean any LaTeX formulas if needed for clean display
    # E.g. replace $\Delta W$ with &Delta;W or ΔW
    md_text = md_text.replace(r'$\Delta W = W_{\text{before}} - W_{\text{after}}$', '<b>&Delta;W = W<sub>before</sub> - W<sub>after</sub></b>')
    md_text = md_text.replace(r'$\Delta W$', '&Delta;W')
    md_text = md_text.replace(r'$W_{\text{before}}$', 'W<sub>before</sub>')
    md_text = md_text.replace(r'$W_{\text{after}}$', 'W<sub>after</sub>')
    md_text = md_text.replace(r'$\pm 0.05\text{ g}$', '&plusmn;0.05 g')
    md_text = md_text.replace(r'$\le 15\text{ cm}$', '&le; 15 cm')
    md_text = md_text.replace(r'$>15\text{ cm}$', '&gt; 15 cm')
    md_text = md_text.replace(r'$\le 3.0\text{ seconds}$', '&le; 3.0 s')
    md_text = md_text.replace(r'$<100\text{ ms}$', '&lt; 100 ms')
    md_text = md_text.replace(r'$<200\text{ ms}$', '&lt; 200 ms')
    md_text = md_text.replace(r'$<1.0\text{ second}$', '&lt; 1.0 s')
    md_text = md_text.replace(r'$<1.0\text{ s}$', '&lt; 1.0 s')
    md_text = md_text.replace(r'$<2.5\text{ seconds}$', '&lt; 2.5 s')
    md_text = md_text.replace(r'$50\text{ Hz}$', '50 Hz')
    md_text = md_text.replace(r'$0^\circ$', '0&deg;')
    md_text = md_text.replace(r'$90^\circ$', '90&deg;')
    md_text = md_text.replace(r'$20\text{ ms}$', '20 ms')
    md_text = md_text.replace(r'$1.0\text{ ms}$', '1.0 ms')
    md_text = md_text.replace(r'$2.0\text{ ms}$', '2.0 ms')
    md_text = md_text.replace(r'$0.1\,\mu\text{s}$', '0.1 &mu;s')
    md_text = md_text.replace(r'$10\,\mu\text{s}$', '10 &mu;s')
    md_text = md_text.replace(r'$400\,\text{kHz}$', '400 kHz')
    md_text = md_text.replace(r'$>100\,\text{kHz}$', '&gt; 100 kHz')
    md_text = md_text.replace(r'$9600\,\text{bps}$', '9600 bps')
    md_text = md_text.replace(r'$8\,\Omega / 3\,\text{W}$', '8 &Omega; / 3W')
    md_text = md_text.replace(r'$5\,\text{V} / 2\,\text{A}$', '5V / 2A')
    md_text = md_text.replace(r'$0-3.3\,\text{V}$', '0-3.3V')
    md_text = md_text.replace(r'$500\text{ ms}$', '500 ms')
    md_text = md_text.replace(r'$1.0\text{ s}$', '1.0 s')
    md_text = md_text.replace(r'$3.0\text{ s}$', '3.0 s')
    md_text = md_text.replace(r'$3.0\text{ seconds}$', '3.0 s')
    md_text = md_text.replace(r'$15\text{ s}$', '15 s')
    md_text = md_text.replace(r'$5\text{ min}$', '5 min')
    md_text = md_text.replace(r'$60\text{ s}$', '60 s')
    md_text = md_text.replace(r'$10\text{ s}$', '10 s')
    md_text = md_text.replace(r'$500\text{ m}$', '500 m')
    md_text = md_text.replace(r'$60 - 85\,\text{dB}$', '60 - 85 dB')
    md_text = md_text.replace(r'$>4.5:1$', '&gt; 4.5:1')
    md_text = md_text.replace(r'$>48 \times 48\,\text{px}$', '&gt; 48x48 px')
    md_text = md_text.replace(r'$\ge 99.9\%$', '&ge; 99.9%')
    md_text = md_text.replace(r'$\ge \pm 0.05\text{ g}$', '&ge; &plusmn;0.05 g')
    md_text = md_text.replace(r'$\le \pm 0.05\text{ g}$', '&le; &plusmn;0.05 g')
    md_text = md_text.replace(r'$\le \pm 2^\circ$', '&le; &plusmn;2&deg;')
    md_text = md_text.replace(r'$0.25\text{ g}$', '0.25 g')
    md_text = md_text.replace(r'$0.50\text{ g}$', '0.50 g')
    md_text = md_text.replace(r'$1.00\text{ g}$', '1.00 g')
    md_text = md_text.replace(r'$5.00\text{ g}$', '5.00 g')
    md_text = md_text.replace(r'$0 - 100$', '0 - 100')
    md_text = md_text.replace(r'$0 - 35$', '0 - 35')
    md_text = md_text.replace(r'$36 - 65$', '36 - 65')
    md_text = md_text.replace(r'$66 - 100$', '66 - 100')
    md_text = md_text.replace(r'$0 - 1000$', '0 - 1000')
    md_text = md_text.replace(r'$>160\,\text{mmHg}$', '&gt; 160 mmHg')
    md_text = md_text.replace(r'$<70\,\text{mg/dL}$', '&lt; 70 mg/dL')
    md_text = md_text.replace(r'$<2\text{ s}$', '&lt; 2 s')

    # Convert markdown to html
    html_content = markdown.markdown(
        md_text,
        extensions=['tables', 'fenced_code', 'nl2br']
    )

    # Wrap in executive styling
    full_html = f'''<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<title>Aarogyam (MedAdhere v2.1) - Software Requirements Specification</title>
<style>
@page {{
    size: a4 portrait;
    margin-top: 2.5cm;
    margin-bottom: 2.2cm;
    margin-left: 1.8cm;
    margin-right: 1.8cm;
    @frame header_frame {{
        -pdf-frame-content: page_header;
        left: 1.8cm; width: 17.4cm; top: 1.0cm; height: 1.0cm;
    }}
    @frame footer_frame {{
        -pdf-frame-content: page_footer;
        left: 1.8cm; width: 17.4cm; top: 27.7cm; height: 1.0cm;
    }}
}}

body {{
    font-family: Helvetica, Arial, sans-serif;
    font-size: 8.5pt;
    line-height: 1.4;
    color: #1E293B;
}}

/* Header & Footer */
.header-bar {{
    font-size: 7.5pt;
    color: #64748B;
    border-bottom: 1px solid #CBD5E1;
    padding-bottom: 4px;
}}
.header-bar table {{
    width: 100%;
    margin: 0;
}}
.header-bar td {{
    padding: 0;
    border: none;
}}
.footer-bar {{
    font-size: 7.5pt;
    color: #64748B;
    border-top: 1px solid #CBD5E1;
    padding-top: 4px;
}}
.footer-bar table {{
    width: 100%;
    margin: 0;
}}
.footer-bar td {{
    padding: 0;
    border: none;
}}

/* Cover Page */
.cover-container {{
    padding-top: 2.5cm;
    text-align: center;
    page-break-after: always;
}}
.cover-badge {{
    display: inline-block;
    background-color: #EFF6FF;
    color: #1D4ED8;
    border: 1px solid #BFDBFE;
    border-radius: 4px;
    padding: 4px 12px;
    font-size: 9pt;
    font-weight: bold;
    letter-spacing: 1px;
    margin-bottom: 20px;
}}
.cover-title {{
    font-size: 24pt;
    font-weight: bold;
    color: #0F172A;
    line-height: 1.2;
    margin-bottom: 12px;
}}
.cover-subtitle {{
    font-size: 13pt;
    color: #0369A1;
    line-height: 1.4;
    margin-bottom: 30px;
}}
.cover-divider {{
    height: 3px;
    background-color: #0284C7;
    width: 120px;
    margin: 0 auto 35px auto;
}}
.cover-meta-table {{
    width: 80%;
    margin: 0 auto;
    border-collapse: collapse;
    text-align: left;
    font-size: 9pt;
}}
.cover-meta-table td {{
    padding: 7px 12px;
    border-bottom: 1px solid #E2E8F0;
}}
.cover-meta-table td.label {{
    font-weight: bold;
    color: #475569;
    width: 38%;
}}
.cover-meta-table td.val {{
    color: #0F172A;
}}
.cover-footer-note {{
    margin-top: 60px;
    font-size: 8pt;
    color: #94A3B8;
}}

/* Headings */
h1 {{
    font-size: 15pt;
    color: #0F172A;
    border-bottom: 1.5px solid #0284C7;
    padding-bottom: 4px;
    margin-top: 22px;
    margin-bottom: 10px;
    page-break-after: avoid;
}}
h2 {{
    font-size: 12pt;
    color: #0369A1;
    margin-top: 16px;
    margin-bottom: 8px;
    page-break-after: avoid;
}}
h3 {{
    font-size: 10pt;
    color: #1E293B;
    margin-top: 12px;
    margin-bottom: 6px;
    page-break-after: avoid;
}}
h4 {{
    font-size: 9pt;
    color: #334155;
    margin-top: 10px;
    margin-bottom: 4px;
    page-break-after: avoid;
}}

p {{
    margin-top: 0;
    margin-bottom: 8px;
    text-align: justify;
}}

ul, ol {{
    margin-top: 2px;
    margin-bottom: 8px;
    padding-left: 18px;
}}
li {{
    margin-bottom: 3px;
}}

/* Tables */
table {{
    width: 100%;
    border-collapse: collapse;
    margin-top: 8px;
    margin-bottom: 12px;
    font-size: 7.8pt;
}}
th {{
    background-color: #0F172A;
    color: #FFFFFF;
    font-weight: bold;
    padding: 5px 6px;
    border: 0.5px solid #334155;
    text-align: left;
}}
td {{
    padding: 4px 6px;
    border: 0.5px solid #CBD5E1;
    vertical-align: top;
}}
tr:nth-child(even) {{
    background-color: #F8FAFC;
}}

/* Code & Preformatted Blocks */
pre {{
    background-color: #F1F5F9;
    border: 0.5px solid #CBD5E1;
    border-radius: 3px;
    padding: 6px 8px;
    font-family: Courier, monospace;
    font-size: 7pt;
    line-height: 1.25;
    margin-top: 6px;
    margin-bottom: 10px;
    color: #0F172A;
}}
code {{
    font-family: Courier, monospace;
    font-size: 7.5pt;
    background-color: #F1F5F9;
    padding: 1px 3px;
    border-radius: 2px;
    color: #0F172A;
}}

/* Blockquotes / Alerts */
blockquote {{
    border-left: 3px solid #0284C7;
    background-color: #F0F9FF;
    padding: 6px 10px;
    margin-left: 0;
    margin-right: 0;
    margin-top: 6px;
    margin-bottom: 8px;
    font-style: italic;
    color: #0369A1;
}}

hr {{
    border: none;
    border-top: 1px solid #E2E8F0;
    margin-top: 14px;
    margin-bottom: 14px;
}}

strong, b {{
    color: #0F172A;
}}
</style>
</head>
<body>

<!-- Header Frame Content -->
<div id="page_header">
    <div class="header-bar">
        <table>
            <tr>
                <td style="text-align: left;"><strong>Aarogyam (MedAdhere v2.1)</strong> &bull; Technical Product Specification</td>
                <td style="text-align: right; color: #0284C7;"><strong>IEEE 830-1998 / ISO 29148</strong></td>
            </tr>
        </table>
    </div>
</div>

<!-- Footer Frame Content -->
<div id="page_footer">
    <div class="footer-bar">
        <table>
            <tr>
                <td style="text-align: left;">Confidential &amp; Proprietary &bull; MedAdhere Healthcare Technologies</td>
                <td style="text-align: right;">Page <pdf:pageNumber/> of <pdf:pageCount/></td>
            </tr>
        </table>
    </div>
</div>

<!-- Cover Page -->
<div class="cover-container">
    <div class="cover-badge">OFFICIAL TECHNICAL SPECIFICATION</div>
    <div class="cover-title">SOFTWARE REQUIREMENTS<br/>SPECIFICATION (SRS)</div>
    <div class="cover-subtitle">Aarogyam (MedAdhere v2.1)<br/>Intelligent Medication Adherence Monitoring &amp; Autonomous Intervention System</div>
    <div class="cover-divider"></div>
    
    <table class="cover-meta-table">
        <tr>
            <td class="label">Document Identifier</td>
            <td class="val"><strong>SRS-AAROGYAM-2026-V2.1</strong></td>
        </tr>
        <tr>
            <td class="label">Document Version</td>
            <td class="val">Version 2.1.0</td>
        </tr>
        <tr>
            <td class="label">Standard Compliance</td>
            <td class="val">IEEE Std 830-1998 / ISO/IEC/IEEE 29148:2018</td>
        </tr>
        <tr>
            <td class="label">Classification / Status</td>
            <td class="val">Technical Product Specification / Production Baseline</td>
        </tr>
        <tr>
            <td class="label">Release Date</td>
            <td class="val">September 2026</td>
        </tr>
        <tr>
            <td class="label">Authoring Team</td>
            <td class="val">Aarogyam Architecture &amp; Engineering Team</td>
        </tr>
        <tr>
            <td class="label">Core Architecture</td>
            <td class="val">ESP32 Dual-Core FreeRTOS &bull; Django 5 ASGI &bull; React 19 &bull; Groq LLM &bull; XGBoost v1.9.0</td>
        </tr>
    </table>

    <div class="cover-footer-note">
        This document contains proprietary information regarding the cyber-physical design, firmware architecture, agent handover protocols, and machine learning inference pipelines of Aarogyam.
    </div>
</div>

<!-- Main Body -->
<div class="main-body">
{html_content}
</div>

</body>
</html>'''

    print('Converting to PDF...')
    with open(pdf_out_path, 'wb') as pdf_file:
        pisa_status = pisa.CreatePDF(full_html, dest=pdf_file)

    if pisa_status.err:
        print(f'Error occurred: {pisa_status.err}')
        return False
    else:
        print(f'Successfully generated PDF at: {pdf_out_path}')
        return True

if __name__ == '__main__':
    build_pdf()
