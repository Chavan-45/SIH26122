import logging
from datetime import datetime, date, timedelta, timezone
from typing import List, Optional, Dict, Any, Tuple
from fastapi import HTTPException, status
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import func, or_, and_, desc, asc

from app.models.user import User
from app.models.project import Project
from app.models.activity import Activity
from app.models.activity_execution import ActivityExecution
from app.models.progress_update import ProgressUpdate
from app.models.planner_review_case import PlannerReviewCase
from app.models.progress_report_item import ProgressReportItem
from app.models.progress_report_import import ProgressReportImport
from app.core.datetime_utils import get_today_date
from app.core.activity_code_utils import normalize_activity_code, extract_and_normalize_activity_code
from app.schemas.project_memory import (
    MemoryEvent,
    MemoryUserRef,
    MemoryProvenance,
    MemorySummary,
    ActivityScheduleContext,
    ActivityDelayAnalysis,
    ActivityTimelineResponse,
    MemoryEventListResponse,
)

logger = logging.getLogger(__name__)


class ProjectMemoryService:
    """
    Single source of truth service for Institutional Project Memory & Historical Intelligence.
    Aggregates, normalizes, searches, and explains real historical records across UI and AI tools.
    """

    @staticmethod
    def _resolve_activity(
        db: Session,
        project_id: int,
        activity_id_or_code: Any,
    ) -> Optional[Activity]:
        """Resolves an activity by integer ID, exact code, normalized code, or fuzzy code match."""
        # 1. If integer or digit string ID
        if isinstance(activity_id_or_code, int) or (isinstance(activity_id_or_code, str) and activity_id_or_code.isdigit()):
            act = db.query(Activity).filter(
                Activity.project_id == project_id,
                Activity.id == int(activity_id_or_code)
            ).first()
            if act:
                return act

        if not isinstance(activity_id_or_code, str) or not activity_id_or_code.strip():
            return None

        raw_str = activity_id_or_code.strip()
        norm_code = normalize_activity_code(raw_str)

        # 2. Exact match on raw uppercase
        act = db.query(Activity).filter(
            Activity.project_id == project_id,
            func.upper(Activity.activity_code) == raw_str.upper()
        ).first()
        if act:
            return act

        # 3. Exact match on normalized code
        if norm_code:
            act = db.query(Activity).filter(
                Activity.project_id == project_id,
                func.upper(Activity.activity_code) == norm_code.upper()
            ).first()
            if act:
                return act

        # 4. ILIKE match
        act = db.query(Activity).filter(
            Activity.project_id == project_id,
            Activity.activity_code.ilike(f"%{raw_str}%")
        ).first()
        if act:
            return act

        # 5. Extract and normalize
        extracted = extract_and_normalize_activity_code(raw_str)
        if extracted:
            act = db.query(Activity).filter(
                Activity.project_id == project_id,
                func.upper(Activity.activity_code) == extracted.upper()
            ).first()
            if act:
                return act

        # 6. Name match fallback
        act = db.query(Activity).filter(
            Activity.project_id == project_id,
            Activity.activity_name.ilike(f"%{raw_str}%")
        ).first()

        return act

    @staticmethod
    def _verify_discipline_access(
        activity_discipline: Optional[str],
        user_role: str,
        user_discipline: Optional[str],
    ) -> None:
        """Enforces backend RBAC: Supervisors cannot access records outside their assigned discipline."""
        if user_role == "SUPERVISOR":
            sup_disc = (user_discipline or "").strip().upper()
            act_disc = (activity_discipline or "UNASSIGNED").strip().upper()
            if not sup_disc or act_disc == "UNASSIGNED" or sup_disc != act_disc:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=f"Access forbidden: As a {sup_disc or 'restricted'} supervisor, you can only access {sup_disc} activity historical memory.",
                )

    @classmethod
    def get_memory_summary(
        cls,
        db: Session,
        project_id: int,
        user_role: str = "PLANNER",
        user_discipline: Optional[str] = None,
    ) -> MemorySummary:
        """
        Computes deterministic historical memory summary metrics.
        Guarantees supervisor numbers are strictly discipline-scoped.
        """
        # Progress updates query
        q_updates = (
            db.query(ProgressUpdate)
            .join(Activity, ProgressUpdate.activity_id == Activity.id)
            .filter(ProgressUpdate.project_id == project_id)
        )

        # Review decisions query
        q_reviews = (
            db.query(PlannerReviewCase)
            .outerjoin(Activity, PlannerReviewCase.selected_activity_id == Activity.id)
            .filter(
                PlannerReviewCase.project_id == project_id,
                PlannerReviewCase.decision.in_(["RESOLVED", "REJECTED", "UNPLANNED", "APPLIED"]),
            )
        )

        effective_disc = None
        if user_role == "SUPERVISOR" and user_discipline:
            effective_disc = user_discipline.strip().upper()
            q_updates = q_updates.filter(func.upper(Activity.discipline) == effective_disc)
            q_reviews = q_reviews.filter(func.upper(Activity.discipline) == effective_disc)

        total_updates = q_updates.count()
        total_reviews = q_reviews.count()

        # Activities with history
        activities_count = (
            db.query(func.count(func.distinct(ProgressUpdate.activity_id)))
            .join(Activity, ProgressUpdate.activity_id == Activity.id)
            .filter(ProgressUpdate.project_id == project_id)
        )
        if effective_disc:
            activities_count = activities_count.filter(func.upper(Activity.discipline) == effective_disc)
        act_hist_count = activities_count.scalar() or 0

        # Date range
        date_stats = (
            db.query(
                func.min(ProgressUpdate.reported_date),
                func.max(ProgressUpdate.reported_date),
            )
            .join(Activity, ProgressUpdate.activity_id == Activity.id)
            .filter(ProgressUpdate.project_id == project_id)
        )
        if effective_disc:
            date_stats = date_stats.filter(func.upper(Activity.discipline) == effective_disc)

        min_date, max_date = date_stats.first() or (None, None)

        return MemorySummary(
            total_execution_updates=total_updates,
            activities_with_history=act_hist_count,
            total_review_decisions=total_reviews,
            earliest_date=str(min_date) if min_date else None,
            latest_date=str(max_date) if max_date else None,
            scope=f"Discipline: {effective_disc}" if effective_disc else "Project-wide",
        )

    @classmethod
    def get_project_events(
        cls,
        db: Session,
        project_id: int,
        user_role: str = "PLANNER",
        user_discipline: Optional[str] = None,
        q: Optional[str] = None,
        activity_id: Optional[int] = None,
        activity_code: Optional[str] = None,
        discipline: Optional[str] = None,
        event_type: Optional[str] = None,
        source: Optional[str] = None,
        date_from: Optional[date] = None,
        date_to: Optional[date] = None,
        page: int = 1,
        page_size: int = 20,
    ) -> MemoryEventListResponse:
        """
        Retrieves paginated, filtered historical memory events with RBAC discipline scoping.
        """
        if page < 1:
            page = 1
        if page_size < 1 or page_size > 100:
            page_size = 20

        # Determine effective discipline filter
        effective_disc = None
        if user_role == "SUPERVISOR":
            effective_disc = (user_discipline or "").strip().upper()
        elif discipline and discipline.upper() != "ALL":
            effective_disc = discipline.strip().upper()

        # Handle exact activity target if provided
        target_act_id = None
        if activity_id:
            target_act_id = activity_id
        elif activity_code:
            act_obj = cls._resolve_activity(db, project_id, activity_code)
            if act_obj:
                target_act_id = act_obj.id

        # 1. Fetch Execution Updates (ProgressUpdate)
        query_updates = (
            db.query(ProgressUpdate, Activity, User)
            .join(Activity, ProgressUpdate.activity_id == Activity.id)
            .outerjoin(User, ProgressUpdate.reported_by_id == User.id)
            .filter(ProgressUpdate.project_id == project_id)
        )

        if effective_disc:
            query_updates = query_updates.filter(func.upper(Activity.discipline) == effective_disc)

        if target_act_id:
            query_updates = query_updates.filter(ProgressUpdate.activity_id == target_act_id)

        if source and source.upper() != "ALL":
            query_updates = query_updates.filter(func.upper(ProgressUpdate.source_type) == source.strip().upper())

        if date_from:
            query_updates = query_updates.filter(ProgressUpdate.reported_date >= date_from)
        if date_to:
            query_updates = query_updates.filter(ProgressUpdate.reported_date <= date_to)

        if q and q.strip():
            search_str = q.strip()
            norm = normalize_activity_code(search_str)
            search_filter = or_(
                Activity.activity_code.ilike(f"%{search_str}%"),
                Activity.activity_name.ilike(f"%{search_str}%"),
                ProgressUpdate.remarks.ilike(f"%{search_str}%"),
            )
            if norm:
                search_filter = or_(
                    search_filter,
                    func.upper(Activity.activity_code) == norm.upper(),
                )
            query_updates = query_updates.filter(search_filter)

        raw_events: List[MemoryEvent] = []

        # If event_type is not filtered to REVIEW_DECISION only, gather execution updates
        if not event_type or event_type.upper() in ["ALL", "EXECUTION_UPDATE"]:
            update_rows = query_updates.order_by(
                desc(ProgressUpdate.reported_date),
                desc(ProgressUpdate.created_at),
            ).all()

            # Preload report item provenance for these updates if available
            report_items_by_act = {}
            if update_rows:
                act_ids = list({u.activity_id for u, _, _ in update_rows})
                rep_items = (
                    db.query(ProgressReportItem, ProgressReportImport)
                    .join(ProgressReportImport, ProgressReportItem.report_id == ProgressReportImport.id)
                    .filter(
                        ProgressReportItem.project_id == project_id,
                        ProgressReportItem.matched_activity_id.in_(act_ids),
                    )
                    .all()
                )
                for r_item, r_imp in rep_items:
                    key = (r_item.matched_activity_id, str(r_item.reported_date) if r_item.reported_date else None)
                    report_items_by_act[key] = (r_item, r_imp)

            for u_obj, act_obj, user_obj in update_rows:
                u_type = u_obj.update_type.value if hasattr(u_obj.update_type, "value") else str(u_obj.update_type)
                prog_val = float(u_obj.progress_percentage) if u_obj.progress_percentage is not None else None

                # Build event title
                if u_type == "START":
                    title = f"Activity started ({prog_val or 0:.0f}%)"
                elif u_type == "COMPLETE":
                    title = "Activity completed (100%)"
                elif u_type == "PROGRESS":
                    title = f"Progress updated to {prog_val or 0:.0f}%"
                elif u_type == "ON_HOLD":
                    title = f"Activity placed ON_HOLD ({prog_val or 0:.0f}%)"
                elif u_type == "RESUME":
                    title = f"Activity resumed ({prog_val or 0:.0f}%)"
                else:
                    title = f"{u_type} update ({prog_val or 0:.0f}%)"

                # Check provenance
                prov = None
                r_key = (act_obj.id, str(u_obj.reported_date))
                if r_key in report_items_by_act:
                    r_item, r_imp = report_items_by_act[r_key]
                    prov = MemoryProvenance(
                        filename=r_imp.original_filename,
                        page=getattr(r_item, "source_page", None),
                        report_import_id=r_imp.id,
                        source_type=r_imp.source_type,
                    )

                src_str = u_obj.source_type.value if hasattr(u_obj.source_type, "value") else str(u_obj.source_type)

                user_ref = None
                if user_obj:
                    user_ref = MemoryUserRef(
                        id=user_obj.id,
                        name=user_obj.full_name,
                        role=user_obj.role.value if hasattr(user_obj.role, "value") else str(user_obj.role),
                    )

                raw_events.append(
                    MemoryEvent(
                        event_id=f"PU-{u_obj.id}",
                        event_type="EXECUTION_UPDATE",
                        project_id=project_id,
                        activity_id=act_obj.id,
                        activity_code=act_obj.activity_code,
                        activity_name=act_obj.activity_name,
                        discipline=act_obj.discipline or "UNASSIGNED",
                        event_date=str(u_obj.reported_date),
                        created_at=u_obj.created_at.isoformat() if u_obj.created_at else datetime.now(timezone.utc).isoformat(),
                        title=title,
                        description=f"Execution state updated to {u_type} with recorded progress {prog_val or 0:.0f}%.",
                        update_type=u_type,
                        progress_percentage=prog_val,
                        reported_by=user_ref,
                        source=src_str,
                        remarks=u_obj.remarks,
                        provenance=prov,
                    )
                )

        # 2. Fetch Review Decisions (PlannerReviewCase)
        if not event_type or event_type.upper() in ["ALL", "REVIEW_DECISION"]:
            query_reviews = (
                db.query(PlannerReviewCase, Activity, User)
                .outerjoin(Activity, PlannerReviewCase.selected_activity_id == Activity.id)
                .outerjoin(User, PlannerReviewCase.reviewed_by_id == User.id)
                .filter(
                    PlannerReviewCase.project_id == project_id,
                    PlannerReviewCase.decision.in_(["RESOLVED", "REJECTED", "UNPLANNED", "APPLIED"]),
                )
            )

            if effective_disc:
                query_reviews = query_reviews.filter(
                    or_(
                        func.upper(Activity.discipline) == effective_disc,
                        PlannerReviewCase.selected_activity_id == None,
                    )
                )

            if target_act_id:
                query_reviews = query_reviews.filter(
                    or_(
                        PlannerReviewCase.selected_activity_id == target_act_id,
                        PlannerReviewCase.original_activity_id == target_act_id,
                    )
                )

            if date_from:
                query_reviews = query_reviews.filter(PlannerReviewCase.reviewed_at >= datetime.combine(date_from, datetime.min.time()))
            if date_to:
                query_reviews = query_reviews.filter(PlannerReviewCase.reviewed_at <= datetime.combine(date_to, datetime.max.time()))

            if q and q.strip():
                search_str = q.strip()
                query_reviews = query_reviews.filter(
                    or_(
                        Activity.activity_code.ilike(f"%{search_str}%"),
                        Activity.activity_name.ilike(f"%{search_str}%"),
                        PlannerReviewCase.review_reason.ilike(f"%{search_str}%"),
                    )
                )

            review_rows = query_reviews.order_by(
                desc(PlannerReviewCase.reviewed_at),
                desc(PlannerReviewCase.created_at),
            ).all()

            for r_case, act_obj, user_obj in review_rows:
                rev_date_str = str(r_case.reviewed_at.date()) if r_case.reviewed_at else str(r_case.created_at.date())

                user_ref = None
                if user_obj:
                    user_ref = MemoryUserRef(
                        id=user_obj.id,
                        name=user_obj.full_name,
                        role=user_obj.role.value if hasattr(user_obj.role, "value") else str(user_obj.role),
                    )

                prov = MemoryProvenance(
                    review_case_id=r_case.id,
                    source_type=r_case.source_type,
                )

                raw_events.append(
                    MemoryEvent(
                        event_id=f"RC-{r_case.id}",
                        event_type="REVIEW_DECISION",
                        project_id=project_id,
                        activity_id=act_obj.id if act_obj else None,
                        activity_code=act_obj.activity_code if act_obj else "UNPLANNED/N/A",
                        activity_name=act_obj.activity_name if act_obj else "Review Case Resolution",
                        discipline=act_obj.discipline if act_obj else "UNASSIGNED",
                        event_date=rev_date_str,
                        created_at=r_case.created_at.isoformat() if r_case.created_at else datetime.now(timezone.utc).isoformat(),
                        title=f"Review Decision: {r_case.decision}",
                        description=f"Planner resolved case #{r_case.id} as {r_case.decision}.",
                        update_type=r_case.decision,
                        progress_percentage=None,
                        reported_by=user_ref,
                        source="REVIEW_CENTER",
                        remarks=r_case.review_reason,
                        provenance=prov,
                    )
                )

        # Sort all raw events: newest first
        raw_events.sort(key=lambda x: (x.event_date or "1970-01-01", x.created_at), reverse=True)

        total_count = len(raw_events)
        total_pages = max(1, (total_count + page_size - 1) // page_size)
        start_idx = (page - 1) * page_size
        paged_events = raw_events[start_idx : start_idx + page_size]

        return MemoryEventListResponse(
            total=total_count,
            page=page,
            page_size=page_size,
            total_pages=total_pages,
            events=paged_events,
        )

    @classmethod
    def get_activity_timeline(
        cls,
        db: Session,
        project_id: int,
        activity_id_or_code: Any,
        user_role: str = "PLANNER",
        user_discipline: Optional[str] = None,
    ) -> ActivityTimelineResponse:
        """
        Retrieves complete chronological historical timeline for a specific activity.
        Sorted OLDEST -> NEWEST. Includes schedule context and deterministic delay analysis.
        """
        activity = cls._resolve_activity(db, project_id, activity_id_or_code)
        if not activity:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Activity '{activity_id_or_code}' not found in project ID {project_id}.",
            )

        # Verify RBAC discipline access
        cls._verify_discipline_access(activity.discipline, user_role, user_discipline)

        # Fetch execution record
        exec_obj = db.query(ActivityExecution).filter(ActivityExecution.activity_id == activity.id).first()

        # Build Schedule Context
        act_context = ActivityScheduleContext(
            activity_id=activity.id,
            activity_code=activity.activity_code,
            activity_name=activity.activity_name,
            discipline=activity.discipline or "UNASSIGNED",
            wbs_code=activity.wbs_code,
            planned_start=str(activity.planned_start) if activity.planned_start else None,
            planned_finish=str(activity.planned_finish) if activity.planned_finish else None,
            planned_duration=activity.planned_duration,
            actual_start=str(exec_obj.actual_start) if exec_obj and exec_obj.actual_start else None,
            actual_finish=str(exec_obj.actual_finish) if exec_obj and exec_obj.actual_finish else None,
            current_progress=float(exec_obj.progress_percentage) if exec_obj and exec_obj.progress_percentage is not None else 0.0,
            current_status=exec_obj.execution_status.value if exec_obj and hasattr(exec_obj.execution_status, "value") else (str(exec_obj.execution_status) if exec_obj else "NOT_STARTED"),
        )

        # Fetch ProgressUpdates sorted OLDEST -> NEWEST
        updates = (
            db.query(ProgressUpdate, User)
            .outerjoin(User, ProgressUpdate.reported_by_id == User.id)
            .filter(ProgressUpdate.activity_id == activity.id)
            .order_by(asc(ProgressUpdate.reported_date), asc(ProgressUpdate.created_at))
            .all()
        )

        # Preload report provenance
        rep_items = (
            db.query(ProgressReportItem, ProgressReportImport)
            .join(ProgressReportImport, ProgressReportItem.report_id == ProgressReportImport.id)
            .filter(
                ProgressReportItem.project_id == project_id,
                ProgressReportItem.matched_activity_id == activity.id,
            )
            .all()
        )
        report_items_map = {}
        for r_item, r_imp in rep_items:
            key = str(r_item.reported_date) if r_item.reported_date else None
            report_items_map[key] = (r_item, r_imp)

        events: List[MemoryEvent] = []
        for u_obj, user_obj in updates:
            u_type = u_obj.update_type.value if hasattr(u_obj.update_type, "value") else str(u_obj.update_type)
            prog_val = float(u_obj.progress_percentage) if u_obj.progress_percentage is not None else None

            if u_type == "START":
                title = f"Activity started ({prog_val or 0:.0f}%)"
            elif u_type == "COMPLETE":
                title = "Activity completed (100%)"
            elif u_type == "PROGRESS":
                title = f"Progress updated to {prog_val or 0:.0f}%"
            elif u_type == "ON_HOLD":
                title = f"Activity placed ON_HOLD ({prog_val or 0:.0f}%)"
            elif u_type == "RESUME":
                title = f"Activity resumed ({prog_val or 0:.0f}%)"
            else:
                title = f"{u_type} update ({prog_val or 0:.0f}%)"

            prov = None
            r_key = str(u_obj.reported_date)
            if r_key in report_items_map:
                r_item, r_imp = report_items_map[r_key]
                prov = MemoryProvenance(
                    filename=r_imp.original_filename,
                    page=getattr(r_item, "source_page", None),
                    report_import_id=r_imp.id,
                    source_type=r_imp.source_type,
                )

            src_str = u_obj.source_type.value if hasattr(u_obj.source_type, "value") else str(u_obj.source_type)

            user_ref = None
            if user_obj:
                user_ref = MemoryUserRef(
                    id=user_obj.id,
                    name=user_obj.full_name,
                    role=user_obj.role.value if hasattr(user_obj.role, "value") else str(user_obj.role),
                )

            events.append(
                MemoryEvent(
                    event_id=f"PU-{u_obj.id}",
                    event_type="EXECUTION_UPDATE",
                    project_id=project_id,
                    activity_id=activity.id,
                    activity_code=activity.activity_code,
                    activity_name=activity.activity_name,
                    discipline=activity.discipline or "UNASSIGNED",
                    event_date=str(u_obj.reported_date),
                    created_at=u_obj.created_at.isoformat() if u_obj.created_at else datetime.now(timezone.utc).isoformat(),
                    title=title,
                    description=f"{u_type} reported with {prog_val or 0:.0f}% progress.",
                    update_type=u_type,
                    progress_percentage=prog_val,
                    reported_by=user_ref,
                    source=src_str,
                    remarks=u_obj.remarks,
                    provenance=prov,
                )
            )

        # Also fetch review decisions for this activity
        reviews = (
            db.query(PlannerReviewCase, User)
            .outerjoin(User, PlannerReviewCase.reviewed_by_id == User.id)
            .filter(
                PlannerReviewCase.project_id == project_id,
                or_(
                    PlannerReviewCase.selected_activity_id == activity.id,
                    PlannerReviewCase.original_activity_id == activity.id,
                ),
                PlannerReviewCase.decision.in_(["RESOLVED", "REJECTED", "UNPLANNED", "APPLIED"]),
            )
            .all()
        )
        for r_case, user_obj in reviews:
            rev_date_str = str(r_case.reviewed_at.date()) if r_case.reviewed_at else str(r_case.created_at.date())
            user_ref = None
            if user_obj:
                user_ref = MemoryUserRef(
                    id=user_obj.id,
                    name=user_obj.full_name,
                    role=user_obj.role.value if hasattr(user_obj.role, "value") else str(user_obj.role),
                )

            events.append(
                MemoryEvent(
                    event_id=f"RC-{r_case.id}",
                    event_type="REVIEW_DECISION",
                    project_id=project_id,
                    activity_id=activity.id,
                    activity_code=activity.activity_code,
                    activity_name=activity.activity_name,
                    discipline=activity.discipline or "UNASSIGNED",
                    event_date=rev_date_str,
                    created_at=r_case.created_at.isoformat() if r_case.created_at else datetime.now(timezone.utc).isoformat(),
                    title=f"Review Decision: {r_case.decision}",
                    description=f"Planner resolved case #{r_case.id} as {r_case.decision}.",
                    update_type=r_case.decision,
                    progress_percentage=None,
                    reported_by=user_ref,
                    source="REVIEW_CENTER",
                    remarks=r_case.review_reason,
                    provenance=MemoryProvenance(review_case_id=r_case.id, source_type=r_case.source_type),
                )
            )

        # Sort chronologically OLDEST -> NEWEST
        events.sort(key=lambda x: (x.event_date or "1970-01-01", x.created_at), reverse=False)

        # Compute deterministic delay analysis
        delay_analysis = cls._compute_deterministic_delay_analysis(activity, exec_obj, events)

        return ActivityTimelineResponse(
            activity=act_context,
            delay_analysis=delay_analysis,
            events=events,
            total_events=len(events),
        )

    @classmethod
    def get_activity_delay_analysis(
        cls,
        db: Session,
        project_id: int,
        activity_id_or_code: Any,
        user_role: str = "PLANNER",
        user_discipline: Optional[str] = None,
    ) -> ActivityDelayAnalysis:
        """
        Calculates and returns deterministic delay analysis facts for an activity.
        Guarantees: Zero invented delay causes. Cites real recorded notes or states lack thereof.
        """
        activity = cls._resolve_activity(db, project_id, activity_id_or_code)
        if not activity:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Activity '{activity_id_or_code}' not found in project ID {project_id}.",
            )

        cls._verify_discipline_access(activity.discipline, user_role, user_discipline)

        exec_obj = db.query(ActivityExecution).filter(ActivityExecution.activity_id == activity.id).first()

        # Fetch events to gather real recorded notes
        timeline_res = cls.get_activity_timeline(db, project_id, activity.id, user_role, user_discipline)
        return timeline_res.delay_analysis

    @staticmethod
    def _compute_deterministic_delay_analysis(
        activity: Activity,
        exec_obj: Optional[ActivityExecution],
        events: List[MemoryEvent],
    ) -> ActivityDelayAnalysis:
        """
        Pure deterministic computation of delay status and evidence notes.
        """
        planned_finish = activity.planned_finish
        actual_finish = exec_obj.actual_finish if exec_obj else None
        current_status = exec_obj.execution_status.value if exec_obj and hasattr(exec_obj.execution_status, "value") else (str(exec_obj.execution_status) if exec_obj else "NOT_STARTED")
        current_progress = float(exec_obj.progress_percentage) if exec_obj and exec_obj.progress_percentage is not None else 0.0

        today = get_today_date()

        # Gather recorded notes from events
        recorded_notes = []
        relevant_events = []

        for ev in events:
            if ev.update_type in ["ON_HOLD", "RESUME", "COMPLETE", "START"] or ev.remarks:
                relevant_events.append(ev)
            if ev.remarks and ev.remarks.strip() and ev.remarks.strip() not in recorded_notes:
                recorded_notes.append(ev.remarks.strip())

        # No planned finish date
        if not planned_finish:
            return ActivityDelayAnalysis(
                state="NO_PLANNED_FINISH",
                late_days=0,
                planned_finish=None,
                actual_finish=str(actual_finish) if actual_finish else None,
                current_status=current_status,
                current_progress=current_progress,
                summary="Activity does not have a baseline planned finish date recorded.",
                relevant_events=relevant_events,
                recorded_notes=recorded_notes,
            )

        is_completed = current_status == "COMPLETED" or current_progress >= 100.0

        if is_completed:
            # Check completion finish date
            effective_finish = actual_finish
            if not effective_finish:
                # If actual_finish date missing, check last complete event date
                for ev in reversed(events):
                    if ev.update_type == "COMPLETE" and ev.event_date:
                        try:
                            effective_finish = date.fromisoformat(ev.event_date)
                            break
                        except Exception:
                            pass
            if not effective_finish:
                effective_finish = planned_finish

            if effective_finish > planned_finish:
                late_days = (effective_finish - planned_finish).days
                state = "COMPLETED_LATE"
                if recorded_notes:
                    summary = f"{activity.activity_code} finished {late_days} day(s) after its planned finish date ({planned_finish}). Recorded project notes: {'; '.join(recorded_notes)}."
                else:
                    summary = f"{activity.activity_code} finished {late_days} day(s) after its planned finish date ({planned_finish}). The project records show the delay, but no explicit reason for the delay was recorded."
            else:
                late_days = 0
                state = "ON_TIME"
                summary = f"{activity.activity_code} was completed on time (finished on {effective_finish}, planned for {planned_finish})."

            return ActivityDelayAnalysis(
                state=state,
                late_days=late_days,
                planned_finish=str(planned_finish),
                actual_finish=str(effective_finish),
                current_status=current_status,
                current_progress=current_progress,
                summary=summary,
                relevant_events=relevant_events,
                recorded_notes=recorded_notes,
            )

        # Incomplete activity
        if today > planned_finish:
            late_days = (today - planned_finish).days
            state = "CURRENTLY_OVERDUE"
            if recorded_notes:
                summary = f"{activity.activity_code} is currently {late_days} day(s) overdue (planned finish was {planned_finish}). Recorded project notes: {'; '.join(recorded_notes)}."
            else:
                summary = f"{activity.activity_code} is currently {late_days} day(s) overdue (planned finish was {planned_finish}). The project records show the delay, but no explicit reason for the delay was recorded."
        else:
            late_days = 0
            state = "ON_TIME"
            summary = f"{activity.activity_code} is progressing on schedule (due {planned_finish}, current progress {current_progress:.0f}%)."

        return ActivityDelayAnalysis(
            state=state,
            late_days=late_days,
            planned_finish=str(planned_finish),
            actual_finish=str(actual_finish) if actual_finish else None,
            current_status=current_status,
            current_progress=current_progress,
            summary=summary,
            relevant_events=relevant_events,
            recorded_notes=recorded_notes,
        )

    @classmethod
    def search_events(
        cls,
        db: Session,
        project_id: int,
        query: str,
        user_role: str = "PLANNER",
        user_discipline: Optional[str] = None,
        limit: int = 50,
    ) -> List[MemoryEvent]:
        """
        Searches historical memory events for Project AI tools and UI.
        """
        res = cls.get_project_events(
            db=db,
            project_id=project_id,
            user_role=user_role,
            user_discipline=user_discipline,
            q=query,
            page=1,
            page_size=limit,
        )
        return res.events
