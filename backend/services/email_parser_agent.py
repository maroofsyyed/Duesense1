"""
Email Parser Agent — Parses forwarded deal flow emails.

Extracts company name, founder contacts, pitch summary from forwarded emails.
Triggers the pipeline automatically on email ingestion.

Gmail IMAP connection for: youareconnectingtomaroof@gmail.com
"""
import os
import re
import email
import imaplib
import asyncio
import logging
from datetime import datetime, timezone
from typing import Optional
from email.header import decode_header

import db as database
from services.llm_provider import llm

logger = logging.getLogger(__name__)

GMAIL_IMAP = "imap.gmail.com"
GMAIL_USER = os.getenv("GMAIL_USER", "youareconnectingtomaroof@gmail.com")
GMAIL_APP_PASSWORD = os.getenv("GMAIL_APP_PASSWORD", "")


class EmailParserAgent:
    """Parses forwarded deal flow emails and extracts structured deal data."""

    def __init__(self):
        self.user = GMAIL_USER
        self.password = GMAIL_APP_PASSWORD

    # ─── Fetch Unread Deal Emails ─────────────────────────────────────

    def fetch_unread_emails(self, folder: str = "INBOX", label: str = "DealFlow", max_emails: int = 10) -> list[dict]:
        """Connect to Gmail IMAP, fetch unread emails from a label/folder."""
        if not self.password:
            logger.warning("[EmailParser] GMAIL_APP_PASSWORD not set — email ingestion disabled")
            return []

        results = []
        try:
            mail = imaplib.IMAP4_SSL(GMAIL_IMAP)
            mail.login(self.user, self.password)
            mail.select(folder)

            # Search for unread emails (or use label)
            status, messages = mail.search(None, "UNSEEN")
            if status != "OK":
                logger.warning("[EmailParser] No unread emails found")
                return []

            msg_ids = messages[0].split()[-max_emails:]  # Latest N

            for msg_id in msg_ids:
                status, msg_data = mail.fetch(msg_id, "(RFC822)")
                if status != "OK":
                    continue

                raw_email = msg_data[0][1]
                msg = email.message_from_bytes(raw_email)

                parsed = self._parse_email(msg)
                if parsed:
                    results.append(parsed)

                # Mark as read
                mail.store(msg_id, "+FLAGS", "\\Seen")

            mail.logout()
        except Exception as e:
            logger.error(f"[EmailParser] IMAP error: {e}")

        return results

    # ─── Parse Single Email ───────────────────────────────────────────

    def _parse_email(self, msg) -> Optional[dict]:
        """Extract structured data from a single email message."""
        subject = self._decode_header(msg.get("Subject", ""))
        sender = self._decode_header(msg.get("From", ""))
        date_str = msg.get("Date", "")
        body = self._get_body(msg)

        if not body or len(body.strip()) < 50:
            return None

        return {
            "subject": subject,
            "sender": sender,
            "date": date_str,
            "body": body[:10000],  # Cap body
            "has_attachments": self._has_attachments(msg),
            "attachments": self._list_attachments(msg),
        }

    # ─── LLM Extraction ──────────────────────────────────────────────

    async def extract_deal_info(self, email_data: dict) -> dict:
        """Use LLM to extract structured deal information from email body."""
        prompt = f"""You are a VC analyst parsing a forwarded deal flow email.
Extract structured information from this email.

SUBJECT: {email_data.get('subject', '')}
FROM: {email_data.get('sender', '')}
BODY:
{email_data.get('body', '')[:6000]}

Extract the following (use "not_mentioned" if not found):

Respond with JSON only:
{{
    "company_name": "string",
    "company_website": "string or not_mentioned",
    "company_description": "string - 2-3 sentence summary of what the company does",
    "industry": "string",
    "stage": "string - Pre-Seed/Seed/Series A/etc or not_mentioned",
    "funding_ask": "string - amount being raised or not_mentioned",
    "founders": [
        {{
            "name": "string",
            "role": "string",
            "email": "string or not_mentioned",
            "linkedin": "string or not_mentioned",
            "background": "string - brief background"
        }}
    ],
    "pitch_summary": "string - 3-5 sentence pitch summary",
    "key_metrics": {{
        "revenue": "string or not_mentioned",
        "users": "string or not_mentioned",
        "growth": "string or not_mentioned"
    }},
    "referral_source": "string - who forwarded/referred this deal",
    "urgency": "HIGH/MEDIUM/LOW - based on timeline mentions",
    "has_deck_attached": {str(email_data.get('has_attachments', False)).lower()},
    "confidence": "HIGH/MEDIUM/LOW - confidence in extraction quality"
}}"""

        result = await llm.generate_json(
            prompt,
            "You are a VC deal flow email parser. Extract ONLY explicitly stated facts. Use 'not_mentioned' for anything not found."
        )
        result["source_email"] = {
            "subject": email_data.get("subject"),
            "sender": email_data.get("sender"),
            "date": email_data.get("date"),
        }
        return result

    # ─── Auto-Trigger Pipeline ────────────────────────────────────────

    async def process_email_deals(self) -> list[dict]:
        """Fetch emails, extract deals, and trigger pipeline for each."""
        emails = self.fetch_unread_emails()
        if not emails:
            logger.info("[EmailParser] No new deal emails found")
            return []

        processed = []
        for email_data in emails:
            try:
                deal_info = await self.extract_deal_info(email_data)
                company_name = deal_info.get("company_name", "Unknown")

                if company_name == "not_mentioned" or company_name == "Unknown":
                    logger.info(f"[EmailParser] Skipped email — no company found: {email_data.get('subject')}")
                    continue

                # Store in DB
                enrichment_tbl = database.enrichment_collection()
                enrichment_tbl.insert({
                    "company_id": None,  # Will be linked when pipeline creates company
                    "source_type": "email_deal_flow",
                    "source_url": f"email://{email_data.get('sender', 'unknown')}",
                    "data": deal_info,
                    "fetched_at": datetime.now(timezone.utc).isoformat(),
                    "is_valid": True,
                })

                # Create company + trigger pipeline
                company_id = await self._create_company_from_email(deal_info)
                if company_id:
                    deal_info["company_id"] = company_id
                    # Trigger orchestrator (non-blocking)
                    asyncio.create_task(self._trigger_pipeline(company_id, deal_info))

                processed.append(deal_info)
                logger.info(f"[EmailParser] Processed deal: {company_name}")

            except Exception as e:
                logger.error(f"[EmailParser] Failed to process email: {e}")

        return processed

    # ─── Create Company from Email Data ───────────────────────────────

    async def _create_company_from_email(self, deal_info: dict) -> Optional[str]:
        """Create a company record from extracted email data."""
        companies_tbl = database.companies_collection()
        founders_tbl = database.founders_collection()

        now = datetime.now(timezone.utc).isoformat()
        company_name = deal_info.get("company_name", "Unknown")
        website = deal_info.get("company_website")
        if website == "not_mentioned":
            website = None

        try:
            company_row = companies_tbl.insert({
                "name": company_name,
                "status": "processing",
                "website": website,
                "website_source": "email_extraction",
                "industry": deal_info.get("industry"),
                "stage": deal_info.get("stage"),
                "input_source": "email",
                "created_at": now,
                "updated_at": now,
            })
            company_id = company_row["id"]

            # Save founders
            for f in deal_info.get("founders", []):
                if f.get("name") and f["name"] != "not_mentioned":
                    founders_tbl.insert({
                        "company_id": company_id,
                        "name": f["name"],
                        "role": f.get("role"),
                        "email": f.get("email") if f.get("email") != "not_mentioned" else None,
                        "linkedin_url": f.get("linkedin") if f.get("linkedin") != "not_mentioned" else None,
                        "created_at": now,
                    })

            return company_id
        except Exception as e:
            logger.error(f"[EmailParser] Failed to create company: {e}")
            return None

    async def _trigger_pipeline(self, company_id: str, deal_info: dict):
        """Trigger the main orchestrator pipeline for this company."""
        try:
            from services.orchestrator import MasterOrchestrator
            orchestrator = MasterOrchestrator()
            await orchestrator.run_pipeline(
                company_id=company_id,
                extracted_data={
                    "company": {
                        "name": deal_info.get("company_name"),
                        "website": deal_info.get("company_website"),
                        "industry": deal_info.get("industry"),
                        "stage": deal_info.get("stage"),
                    },
                    "founders": deal_info.get("founders", []),
                    "solution": {"product_description": deal_info.get("company_description", "")},
                    "traction": deal_info.get("key_metrics", {}),
                    "funding": {"raising": deal_info.get("funding_ask")},
                },
                source="email",
            )
        except Exception as e:
            logger.error(f"[EmailParser] Pipeline trigger failed: {e}")

    # ─── Helpers ──────────────────────────────────────────────────────

    def _decode_header(self, header_val: str) -> str:
        """Decode email header value."""
        if not header_val:
            return ""
        decoded = decode_header(header_val)
        parts = []
        for part, encoding in decoded:
            if isinstance(part, bytes):
                parts.append(part.decode(encoding or "utf-8", errors="replace"))
            else:
                parts.append(str(part))
        return " ".join(parts)

    def _get_body(self, msg) -> str:
        """Extract email body text."""
        body = ""
        if msg.is_multipart():
            for part in msg.walk():
                content_type = part.get_content_type()
                if content_type == "text/plain":
                    payload = part.get_payload(decode=True)
                    if payload:
                        body += payload.decode("utf-8", errors="replace")
                elif content_type == "text/html" and not body:
                    payload = part.get_payload(decode=True)
                    if payload:
                        # Strip HTML tags for plain text
                        html = payload.decode("utf-8", errors="replace")
                        body = re.sub(r"<[^>]+>", " ", html)
                        body = re.sub(r"\s+", " ", body).strip()
        else:
            payload = msg.get_payload(decode=True)
            if payload:
                body = payload.decode("utf-8", errors="replace")
        return body.strip()

    def _has_attachments(self, msg) -> bool:
        """Check if email has attachments."""
        if msg.is_multipart():
            for part in msg.walk():
                if part.get_content_disposition() == "attachment":
                    return True
        return False

    def _list_attachments(self, msg) -> list[dict]:
        """List attachment names and types."""
        attachments = []
        if msg.is_multipart():
            for part in msg.walk():
                if part.get_content_disposition() == "attachment":
                    filename = part.get_filename()
                    if filename:
                        attachments.append({
                            "filename": self._decode_header(filename),
                            "content_type": part.get_content_type(),
                            "size": len(part.get_payload(decode=True) or b""),
                        })
        return attachments
