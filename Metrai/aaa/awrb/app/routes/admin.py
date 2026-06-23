from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session
from app.database import get_db
from app.models import User, CalculationHistory, ActivityLog, AdminReport
from app.schemas import UserResponse, UserUpdate, AdminReportResponse, AdminReportUpdate, ActivityLogResponse
from app.auth import get_current_admin
from typing import List, Dict, Any
import datetime

router = APIRouter(prefix="/api/admin", tags=["Admin Control Panel"])

@router.get("/users", response_model=List[UserResponse])
def admin_get_users(
    db: Session = Depends(get_db),
    admin: User = Depends(get_current_admin)
):
    """Admin-only: Retrieve lists of all registered users in the database."""
    users = db.query(User).order_by(User.created_at.desc()).all()
    return users

@router.put("/users/{user_id}", response_model=UserResponse)
def admin_update_user(
    user_id: int,
    body: UserUpdate,
    db: Session = Depends(get_db),
    admin: User = Depends(get_current_admin)
):
    """Admin-only: Modify account states, deactivate users, or elevate roles."""
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User account not found.")
        
    if user.id == admin.id and body.role == "user":
        raise HTTPException(status_code=400, detail="Administrators cannot demote themselves.")

    if body.full_name is not None:
        user.full_name = body.full_name
    if body.is_active is not None:
        user.is_active = body.is_active
    if body.role is not None:
        if body.role not in ["user", "admin"]:
            raise HTTPException(status_code=400, detail="Invalid system role classification.")
        user.role = body.role
        
    db.commit()
    db.refresh(user)
    return user

@router.get("/reports", response_model=List[AdminReportResponse])
def admin_get_reports(
    db: Session = Depends(get_db),
    admin: User = Depends(get_current_admin)
):
    """Admin-only: Retrieve all system support tickets, bug alerts, or feature inquiries."""
    reports = db.query(AdminReport).order_by(AdminReport.created_at.desc()).all()
    return reports

@router.put("/reports/{report_id}", response_model=AdminReportResponse)
def admin_update_report(
    report_id: int,
    body: AdminReportUpdate,
    db: Session = Depends(get_db),
    admin: User = Depends(get_current_admin)
):
    """Admin-only: Update tickets to open, in_progress, or resolved states."""
    report = db.query(AdminReport).filter(AdminReport.id == report_id).first()
    if not report:
        raise HTTPException(status_code=404, detail="System report not found.")
        
    if body.status not in ["open", "in_progress", "resolved"]:
        raise HTTPException(status_code=400, detail="Invalid ticket status category.")
        
    report.status = body.status
    db.commit()
    db.refresh(report)
    return report

@router.get("/logs", response_model=List[ActivityLogResponse])
def admin_get_activity_logs(
    limit: int = 100,
    db: Session = Depends(get_db),
    admin: User = Depends(get_current_admin)
):
    """Admin-only: Fetch raw chronological activity log files for security audit checks."""
    logs = db.query(ActivityLog).order_by(ActivityLog.created_at.desc()).limit(limit).all()
    return logs

@router.get("/stats")
def admin_get_telemetry(
    db: Session = Depends(get_db),
    admin: User = Depends(get_current_admin)
):
    """Admin-only: Pull comprehensive system-wide performance and engagement metrics."""
    total_users = db.query(User).count()
    total_calcs = db.query(CalculationHistory).count()
    open_reports = db.query(AdminReport).filter(AdminReport.status == "open").count()
    
    # Mathematical requests by category breakdown
    category_counts = {}
    calcs = db.query(CalculationHistory.calculation_type).all()
    for c in calcs:
        category_counts[c[0]] = category_counts.get(c[0], 0) + 1

    # Ingestion rate (calculations in past 24h)
    twenty_four_hours_ago = datetime.datetime.utcnow() - datetime.timedelta(hours=24)
    calcs_24h = db.query(CalculationHistory)\
        .filter(CalculationHistory.created_at >= twenty_four_hours_ago)\
        .count()
        
    # Active logins in past 24h
    logins_24h = db.query(ActivityLog)\
        .filter(ActivityLog.action == "login", ActivityLog.created_at >= twenty_four_hours_ago)\
        .count()

    return {
        "total_users": total_users,
        "total_calculations": total_calcs,
        "open_reports": open_reports,
        "calculations_24h": calcs_24h,
        "active_logins_24h": logins_24h,
        "category_breakdown": category_counts
    }
