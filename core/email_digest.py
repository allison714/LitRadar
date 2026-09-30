"""
Weekly Email Digest Generator and SMTP Dispatcher.
LitRadar Suite.
"""

import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path
from typing import List, Dict, Any
from datetime import datetime

from config import (
    SMTP_SERVER, SMTP_PORT, SMTP_USER, SMTP_PASSWORD, EMAIL_RECIPIENT,
    EXCEL_PATH, PODCAST_DIR, OUTPUT_DIR
)


class EmailDigestNotifier:
    def __init__(self):
        self.recipient = EMAIL_RECIPIENT
        self.sender = SMTP_USER or "literature-bot@research.org"

    def render_html_digest(self, harvest_results: Dict[str, List[Dict[str, Any]]], podcast_files: List[Path]) -> str:
        today_str = datetime.now().strftime("%B %d, %Y")
        week_num = datetime.now().strftime("%U")
        total_papers = sum(len(papers) for papers in harvest_results.values())

        podcast_cards_html = ""
        for p_file in podcast_files:
            track_name = p_file.stem.replace("Track_", "Track ").replace("_", " ")
            podcast_cards_html += f"""
            <div style="background-color: #f7f9fc; border-left: 4px solid #1f4e79; padding: 14px 18px; margin-bottom: 14px; border-radius: 4px;">
                <h4 style="margin: 0 0 6px 0; color: #1f4e79; font-size: 15px;">🎧 {track_name}</h4>
                <p style="margin: 0; color: #444; font-size: 13px;">
                    <strong>NotebookLM Briefing:</strong> <code style="background: #e2e8f0; padding: 2px 6px; border-radius: 3px;">{p_file.name}</code><br/>
                    <em>Ready to copy or sync directly to NotebookLM for 2-host audio generation.</em>
                </p>
            </div>
            """

        table_rows_html = ""
        for track_key, papers in harvest_results.items():
            for p in papers:
                tags_badge = " ".join([f"<span style='background: #e2e8f0; color: #1e293b; padding: 2px 6px; border-radius: 4px; font-size: 11px; margin-right: 4px;'>{t}</span>" for t in p.get("tags", [])[:5]])
                table_rows_html += f"""
                <tr style="border-bottom: 1px solid #e2e8f0;">
                    <td style="padding: 10px 12px; font-size: 12px; font-weight: bold; color: #1f4e79;">{p.get('track_name', '')}</td>
                    <td style="padding: 10px 12px; font-size: 13px;">
                        <a href="{p.get('url', '#')}" style="color: #0d6efd; text-decoration: none; font-weight: 600;">{p.get('title', '')}</a>
                        <div style="font-size: 12px; color: #64748b; margin-top: 4px;">{p.get('journal', '')} • {p.get('authors', '')}</div>
                        <div style="font-size: 12px; color: #334155; margin-top: 6px; line-height: 1.4;">{p.get('tldr', '')}</div>
                        <div style="margin-top: 6px;">{tags_badge}</div>
                    </td>
                    <td style="padding: 10px 12px; font-size: 12px; text-align: center; color: #475569;">{p.get('citations', 0)}</td>
                </tr>
                """

        if not table_rows_html:
            table_rows_html = "<tr><td colspan='3' style='padding: 16px; text-align: center; color: #64748b;'>No newly indexed papers this week. Historical knowledge base remains up to date.</td></tr>"

        excel_uri = str(EXCEL_PATH).replace("\\", "/")

        html = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="utf-8">
            <style>
                body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif; background-color: #f1f5f9; margin: 0; padding: 24px; color: #1e293b; }}
                .container {{ max-width: 800px; margin: 0 auto; background: #ffffff; border-radius: 8px; overflow: hidden; box-shadow: 0 4px 6px rgba(0,0,0,0.05); }}
                .header {{ background-color: #0f2c59; color: #ffffff; padding: 28px 32px; }}
                .content {{ padding: 32px; }}
                h2 {{ color: #0f2c59; border-bottom: 2px solid #e2e8f0; padding-bottom: 8px; margin-top: 28px; font-size: 18px; }}
                table {{ width: 100%; border-collapse: collapse; margin-top: 12px; }}
                th {{ background-color: #f8fafc; color: #475569; text-align: left; padding: 10px 12px; font-size: 12px; text-transform: uppercase; letter-spacing: 0.5px; border-bottom: 2px solid #cbd5e1; }}
            </style>
        </head>
        <body>
            <div class="container">
                <div class="header">
                    <h1 style="margin: 0 0 6px 0; font-size: 22px;">LitRadar — Weekly Science Digest</h1>
                    <p style="margin: 0; opacity: 0.85; font-size: 14px;">Week {week_num} • {today_str} • {total_papers} New Publications Harvested</p>
                </div>

                    <div style="display: flex; gap: 12px; margin-bottom: 24px;">
                        <div style="flex: 1; background-color: #e0f2fe; border: 1px solid #bae6fd; padding: 14px 18px; border-radius: 6px;">
                            <span style="font-weight: bold; color: #0369a1;">📊 Weekly Slide Deck Ready:</span><br/>
                            <a href="file:///{excel_uri.replace(EXCEL_PATH.name, 'Weekly_Slide_Deck.html')}" style="color: #0284c7; font-weight: bold; text-decoration: none; font-size: 14px;">🖥️ Open Interactive Slide Deck ↗</a><br/>
                            <span style="font-size: 11px; color: #0369a1;">Formatted with academic citations & mechanistic models.</span>
                        </div>
                        <div style="flex: 1; background-color: #fef3c7; border: 1px solid #fde68a; padding: 14px 18px; border-radius: 6px;">
                            <span style="font-weight: bold; color: #92400e;">🎧 Listen in NotebookLM:</span><br/>
                            <a href="https://notebooklm.google.com" target="_blank" style="color: #b45309; font-weight: bold; text-decoration: none; font-size: 14px;">🎙️ Launch Google NotebookLM ↗</a><br/>
                            <span style="font-size: 11px; color: #92400e;">Drop in briefing files from <code>podcast_briefings/</code>.</span>
                        </div>
                    </div>

                    <h2>1. The 5 Curated Weekly Podcasts & Slide Decks</h2>
                    <p style="font-size: 13px; color: #64748b; margin-bottom: 16px;">
                        The top paper from each research dimension has been converted into an intellectually rigorous briefing dossier and slide deck in <code>{PODCAST_DIR.name}</code>:
                    </p>
                    {podcast_cards_html}

                    <h2>2. Complete Harvest & Tagged Discoveries</h2>
                    <table>
                        <thead>
                            <tr>
                                <th style="width: 25%;">Track</th>
                                <th style="width: 65%;">Publication & Synthesis</th>
                                <th style="width: 10%; text-align: center;">Cites</th>
                            </tr>
                        </thead>
                        <tbody>
                            {table_rows_html}
                        </tbody>
                    </table>

                    <div style="margin-top: 36px; padding-top: 18px; border-top: 1px solid #e2e8f0; font-size: 12px; color: #94a3b8; text-align: center;">
                        LitRadar • Automated Literature Surveillance System
                    </div>
                </div>
            </div>
        </body>
        </html>
        """
        return html

    def dispatch_email(self, html_content: str) -> bool:
        preview_path = OUTPUT_DIR / "weekly_digest_latest.html"
        with open(preview_path, "w", encoding="utf-8") as f:
            f.write(html_content)
        print(f"[Email Digest] Saved local preview at: {preview_path}")

        if SMTP_USER and SMTP_PASSWORD:
            try:
                msg = MIMEMultipart("alternative")
                msg["Subject"] = f"🔬 Weekly Science Digest: SHANK2, Pan-ExM & Synaptic Biology ({datetime.now().strftime('%b %d')})"
                msg["From"] = self.sender
                msg["To"] = self.recipient
                msg.attach(MIMEText(html_content, "html"))

                with smtplib.SMTP(SMTP_SERVER, SMTP_PORT) as server:
                    server.starttls()
                    server.login(SMTP_USER, SMTP_PASSWORD.replace(" ", ""))
                    server.sendmail(self.sender, self.recipient, msg.as_string())

                print(f"[Email Digest] Successfully sent email to {self.recipient}.")
                return True
            except Exception as e:
                print(f"[Email Digest] SMTP send failed: {e}")
                return False
        else:
            print("[Email Digest] SMTP credentials not set in config.py. Preview saved to output/weekly_digest_latest.html.")
            return True
