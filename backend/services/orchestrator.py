"""
Master Orchestrator — Manages the full pipeline with proper dependency ordering.

Consolidates scattered pipeline logic from server.py and ingestion.py.

5-stage dependency ordering:
  1. Deck extraction + Website DD (parallel)
  2. LinkedIn + Company Profile + Social Signals + Glassdoor (parallel)
  3. Market Sizing + GTM + Competitive Landscape + Milestones (parallel, depends on step 2)
  4. All scoring agents (parallel, depends on steps 1-3)
  5. Memo generation (sequential, depends on all)

Handles partial failures gracefully.
Emits progress events for real-time UI updates.
"""
import asyncio
import logging
from datetime import datetime, timezone
from typing import Optional, Callable

import db as database

logger = logging.getLogger(__name__)


class PipelineStage:
    """Tracks a single pipeline stage."""

    def __init__(self, name: str, order: int):
        self.name = name
        self.order = order
        self.status = "pending"  # pending → running → completed → failed
        self.started_at = None
        self.completed_at = None
        self.error = None
        self.result = None

    def start(self):
        self.status = "running"
        self.started_at = datetime.now(timezone.utc).isoformat()

    def complete(self, result=None):
        self.status = "completed"
        self.completed_at = datetime.now(timezone.utc).isoformat()
        self.result = result

    def fail(self, error: str):
        self.status = "failed"
        self.completed_at = datetime.now(timezone.utc).isoformat()
        self.error = error

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "order": self.order,
            "status": self.status,
            "started_at": self.started_at,
            "completed_at": self.completed_at,
            "error": self.error,
        }


class MasterOrchestrator:
    """
    Orchestrates the full VC deal intelligence pipeline.
    
    Manages 5 stages with proper dependency ordering,
    handles partial failures, and emits progress events.
    """

    def __init__(self, progress_callback: Optional[Callable] = None):
        self.progress_callback = progress_callback
        self.stages: dict[str, PipelineStage] = {}

    async def run_pipeline(
        self,
        company_id: str,
        deck_id: Optional[str] = None,
        file_path: Optional[str] = None,
        file_ext: Optional[str] = None,
        company_website: Optional[str] = None,
        extracted_data: Optional[dict] = None,
        source: str = "deck",
    ) -> dict:
        """
        Run the full pipeline with 6-stage dependency ordering.
        
        Can start from:
        - file_path + file_ext: full deck processing
        - extracted_data: skip extraction (e.g. from email)
        """
        companies_tbl = database.companies_collection()
        pitch_decks_tbl = database.pitch_decks_collection() if deck_id else None

        pipeline_result = {
            "company_id": company_id,
            "deck_id": deck_id,
            "source": source,
            "started_at": datetime.now(timezone.utc).isoformat(),
            "stages": {},
        }

        try:
            # ━━━ STAGE 1: Extraction + Website DD (parallel) ━━━
            await self._emit_progress(company_id, "stage_1_extraction", 1, 6)
            self._update_status(companies_tbl, company_id, "extracting")
            if pitch_decks_tbl and deck_id:
                pitch_decks_tbl.update({"id": deck_id}, {"processing_status": "extracting"})

            extracted, website_dd = await self._stage_1_extraction(
                company_id, deck_id, file_path, file_ext, company_website, extracted_data
            )
            pipeline_result["stages"]["extraction"] = "completed"

            # Update company with extracted info
            company_info = extracted.get("company", {})
            final_website = company_website or company_info.get("website")
            companies_tbl.update({"id": company_id}, {
                "name": company_info.get("name", "Unknown Company"),
                "tagline": company_info.get("tagline"),
                "website": final_website,
                "stage": company_info.get("stage"),
                "founded_year": company_info.get("founded"),
                "hq_location": company_info.get("hq_location"),
                "status": "enriching",
                "updated_at": datetime.now(timezone.utc).isoformat(),
            })

            # Save founders
            founders_tbl = database.founders_collection()
            for f in extracted.get("founders", []):
                founders_tbl.insert({
                    "company_id": company_id,
                    "name": f.get("name", "Unknown"),
                    "role": f.get("role"),
                    "linkedin_url": f.get("linkedin"),
                    "github_url": f.get("github"),
                    "previous_companies": f.get("previous_companies", []),
                    "years_in_industry": f.get("years_in_industry"),
                    "created_at": datetime.now(timezone.utc).isoformat(),
                })

            # ━━━ STAGE 2: Core Enrichment + Funding + Traffic (parallel) ━━━
            await self._emit_progress(company_id, "stage_2_enrichment", 2, 6)
            self._update_status(companies_tbl, company_id, "enriching")
            if pitch_decks_tbl and deck_id:
                pitch_decks_tbl.update({"id": deck_id}, {"processing_status": "enriching"})

            enrichment = await self._stage_2_enrichment(company_id, extracted)
            pipeline_result["stages"]["enrichment"] = "completed"

            # ━━━ STAGE 3: Deep Analysis (parallel, depends on stage 2) ━━━
            await self._emit_progress(company_id, "stage_3_analysis", 3, 6)
            self._update_status(companies_tbl, company_id, "analyzing")

            analysis = await self._stage_3_analysis(
                company_id, extracted, enrichment
            )
            # Merge analysis into enrichment for downstream use
            enrichment.update(analysis)
            pipeline_result["stages"]["analysis"] = "completed"

            # ━━━ STAGE 4: Scoring (parallel, depends on 1-3) ━━━
            await self._emit_progress(company_id, "stage_4_scoring", 4, 6)
            self._update_status(companies_tbl, company_id, "scoring")
            if pitch_decks_tbl and deck_id:
                pitch_decks_tbl.update({"id": deck_id}, {"processing_status": "scoring"})

            score = await self._stage_4_scoring(company_id, extracted, enrichment)
            pipeline_result["stages"]["scoring"] = "completed"

            # ━━━ STAGE 5: Memo Generation (sequential, depends on all) ━━━
            await self._emit_progress(company_id, "stage_5_memo", 5, 6)
            self._update_status(companies_tbl, company_id, "generating_memo")
            if pitch_decks_tbl and deck_id:
                pitch_decks_tbl.update({"id": deck_id}, {"processing_status": "generating_memo"})

            memo = await self._stage_5_memo(company_id, extracted, enrichment, score)
            pipeline_result["stages"]["memo"] = "completed"

            # ━━━ STAGE 6: Kruncher Insights (depends on all + score) ━━━
            await self._emit_progress(company_id, "stage_6_kruncher_insights", 6, 6)
            self._update_status(companies_tbl, company_id, "generating_insights")

            kruncher = await self._stage_6_kruncher_insights(
                company_id, extracted, enrichment, score
            )
            pipeline_result["stages"]["kruncher_insights"] = "completed"

            # ━━━ COMPLETE ━━━
            pipeline_result["status"] = "completed"
            pipeline_result["completed_at"] = datetime.now(timezone.utc).isoformat()
            pipeline_result["score"] = score.get("total_score")
            pipeline_result["tier"] = score.get("tier")

            self._update_status(companies_tbl, company_id, "completed")
            if pitch_decks_tbl and deck_id:
                pitch_decks_tbl.update({"id": deck_id}, {"processing_status": "completed"})

            logger.info(f"✅ Pipeline completed for {company_id}: {score.get('tier')} ({score.get('total_score')}/100)")

        except Exception as e:
            pipeline_result["status"] = "failed"
            pipeline_result["error"] = str(e)
            pipeline_result["failed_at"] = datetime.now(timezone.utc).isoformat()

            logger.error(f"❌ Pipeline failed for {company_id}: {e}")
            companies_tbl.update({"id": company_id}, {
                "status": "failed",
                "updated_at": datetime.now(timezone.utc).isoformat(),
            })
            if pitch_decks_tbl and deck_id:
                pitch_decks_tbl.update({"id": deck_id}, {
                    "processing_status": "failed",
                    "error_message": str(e),
                })

        finally:
            # Cleanup temp file
            if file_path:
                try:
                    import os
                    if os.path.exists(file_path):
                        os.remove(file_path)
                except Exception:
                    pass

        return pipeline_result

    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    # Stage Implementations
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

    async def _stage_1_extraction(
        self, company_id, deck_id, file_path, file_ext,
        company_website, extracted_data
    ) -> tuple[dict, dict]:
        """Stage 1: Deck extraction + Website DD in parallel."""
        if extracted_data:
            # Skip extraction (e.g. from email source)
            website_dd = {}
            if company_website:
                try:
                    from services.website_due_diligence import run_website_due_diligence
                    website_dd = await run_website_due_diligence(company_id, company_website)
                except Exception as e:
                    logger.warning(f"Website DD failed: {e}")
            return extracted_data, website_dd

        tasks = []

        # Deck extraction
        from services.deck_processor import extract_deck
        tasks.append(extract_deck(file_path, file_ext))

        # Website DD (parallel)
        if company_website:
            from services.website_due_diligence import run_website_due_diligence
            tasks.append(run_website_due_diligence(company_id, company_website))

        results = await asyncio.gather(*tasks, return_exceptions=True)

        extracted = results[0] if not isinstance(results[0], Exception) else {}
        if isinstance(results[0], Exception):
            raise results[0]

        website_dd = {}
        if len(results) > 1 and not isinstance(results[1], Exception):
            website_dd = results[1]

        # Store extracted data
        if deck_id:
            pitch_decks_tbl = database.pitch_decks_collection()
            pitch_decks_tbl.update(
                {"id": deck_id},
                {"extracted_data": extracted, "processing_status": "extracted"}
            )

        return extracted, website_dd

    async def _stage_2_enrichment(self, company_id: str, extracted: dict) -> dict:
        """Stage 2: Core enrichment + funding + web traffic — all sources in parallel."""
        company_info = extracted.get("company", {})
        company_name = company_info.get("name", "")
        website = company_info.get("website", "")
        deck_funding = extracted.get("funding", extracted.get("financials", {}))

        tasks = {}

        # Core enrichment (LinkedIn, GitHub, News, etc.)
        try:
            from services.enrichment_engine import enrich_company
            tasks["core"] = enrich_company(company_id, extracted)
        except Exception as e:
            logger.warning(f"Core enrichment import failed: {e}")

        # Funding History Agent (parallel)
        try:
            from services.funding_agent import run_funding_agent
            tasks["funding_history"] = run_funding_agent(
                company_id, company_name, website, deck_funding
            )
        except Exception as e:
            logger.warning(f"FundingAgent import failed: {e}")

        # Web Traffic Agent (parallel)
        if website:
            try:
                from services.web_traffic_agent import run_web_traffic_agent
                tasks["web_traffic"] = run_web_traffic_agent(company_id, website)
            except Exception as e:
                logger.warning(f"WebTrafficAgent import failed: {e}")

        if not tasks:
            return {}

        names = list(tasks.keys())
        coros = list(tasks.values())
        gathered = await asyncio.gather(*coros, return_exceptions=True)

        # Core enrichment returns the main dict; others are merged in
        enrichment = {}
        for name, result in zip(names, gathered):
            if isinstance(result, Exception):
                logger.warning(f"Stage 2 {name} failed: {result}")
            elif name == "core":
                enrichment = result if isinstance(result, dict) else {}
            else:
                enrichment[name] = result if isinstance(result, dict) else {}

        return enrichment

    async def _stage_3_analysis(
        self, company_id: str, extracted: dict, enrichment: dict
    ) -> dict:
        """Stage 3: Deep analysis — market sizing, GTM, competitive, milestones."""
        company_info = extracted.get("company", {})
        company_name = company_info.get("name", "")
        industry = company_info.get("industry", "")
        product_desc = extracted.get("solution", {}).get("product_description", "")
        market_claims = extracted.get("market", {})
        website = company_info.get("website")

        tasks = {}

        # Market Sizing
        try:
            from services.market_sizing_agent import MarketSizingAgent
            market_agent = MarketSizingAgent()
            tasks["market_sizing"] = market_agent.analyze(
                company_id, industry, product_desc, market_claims
            )
        except Exception as e:
            logger.warning(f"MarketSizing import failed: {e}")

        # GTM Analysis
        try:
            from services.gtm_agent import GTMAnalysisAgent
            gtm_agent = GTMAnalysisAgent()
            tasks["gtm_analysis"] = gtm_agent.analyze(
                company_id, extracted, enrichment
            )
        except Exception as e:
            logger.warning(f"GTM import failed: {e}")

        # Competitive Landscape
        try:
            from services.competitive_landscape_agent import CompetitiveLandscapeAgent
            comp_agent = CompetitiveLandscapeAgent()
            tasks["competitive_landscape"] = comp_agent.analyze(
                company_id, company_name, product_desc, industry, website
            )
        except Exception as e:
            logger.warning(f"CompLandscape import failed: {e}")

        # Milestones
        try:
            from services.milestone_agent import MilestoneTrackerAgent
            milestone_agent = MilestoneTrackerAgent()
            tasks["milestones"] = milestone_agent.analyze(
                company_id, company_name, extracted, enrichment
            )
        except Exception as e:
            logger.warning(f"Milestones import failed: {e}")

        if not tasks:
            return {}

        names = list(tasks.keys())
        coros = list(tasks.values())
        gathered = await asyncio.gather(*coros, return_exceptions=True)

        results = {}
        for name, result in zip(names, gathered):
            if isinstance(result, Exception):
                logger.warning(f"Stage 3 {name} failed: {result}")
                results[name] = {"error": str(result)}
            else:
                results[name] = result

        return results

    async def _stage_4_scoring(
        self, company_id: str, extracted: dict, enrichment: dict
    ) -> dict:
        """Stage 4: Run all scoring agents in parallel."""
        from services.scorer import calculate_investment_score
        return await calculate_investment_score(company_id, extracted, enrichment)

    async def _stage_5_memo(
        self, company_id: str, extracted: dict, enrichment: dict, score: dict
    ) -> dict:
        """Stage 5: Generate comprehensive investment memo."""
        from services.memo_generator import generate_memo
        return await generate_memo(company_id, extracted, enrichment, score)

    async def _stage_6_kruncher_insights(
        self, company_id: str, extracted: dict, enrichment: dict, score: dict
    ) -> dict:
        """Stage 6: Generate Kruncher Insights (strengths, risks, questions, ice breakers)."""
        try:
            from services.kruncher_insights_agent import run_kruncher_insights_agent
            return await run_kruncher_insights_agent(
                company_id, extracted, enrichment, score
            )
        except Exception as e:
            logger.warning(f"KruncherInsights failed (non-fatal): {e}")
            return {}

    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    # Helpers
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

    def _update_status(self, tbl, company_id: str, status: str):
        """Update company status in DB."""
        try:
            tbl.update({"id": company_id}, {
                "status": status,
                "updated_at": datetime.now(timezone.utc).isoformat(),
            })
        except Exception as e:
            logger.warning(f"Status update failed: {e}")

    async def _emit_progress(self, company_id: str, stage: str, current: int, total: int):
        """Emit progress event for real-time UI updates."""
        event = {
            "company_id": company_id,
            "stage": stage,
            "progress": current,
            "total": total,
            "percentage": round(current / total * 100),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        logger.info(f"📊 Pipeline progress: {stage} ({current}/{total})")
        if self.progress_callback:
            try:
                await self.progress_callback(event)
            except Exception:
                pass
