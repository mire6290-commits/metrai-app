from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session
from app.database import get_db
from app.models import User, CalculationHistory, ActivityLog, AdminReport
from app.schemas import CalculationResponse, AdminReportCreate, AdminReportResponse, DashboardStats
from app.auth import get_current_active_user
import json
from typing import List, Dict

router = APIRouter(prefix="/api/dashboard", tags=["User Dashboard"])

@router.get("/history", response_model=List[CalculationResponse])
def get_user_history(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """Retrieves all mathematical computations executed by the authenticated user."""
    history = db.query(CalculationHistory)\
        .filter(CalculationHistory.user_id == current_user.id)\
        .order_by(CalculationHistory.created_at.desc())\
        .all()
    return history

@router.post("/save/{calc_id}")
def toggle_save_calculation(
    calc_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """Toggles the 'saved' bookmark state of a history item for persistent dash reference."""
    calc = db.query(CalculationHistory)\
        .filter(CalculationHistory.id == calc_id, CalculationHistory.user_id == current_user.id)\
        .first()
        
    if not calc:
        raise HTTPException(status_code=404, detail="Calculation record not found.")
        
    calc.is_saved = not calc.is_saved
    db.commit()
    
    status_label = "pinned" if calc.is_saved else "unpinned"
    return {"detail": f"Calculation successfully {status_label}.", "is_saved": calc.is_saved}

@router.delete("/history/{calc_id}", status_code=status.HTTP_200_OK)
def delete_history_item(
    calc_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """Deletes a record from the user's calculation history."""
    calc = db.query(CalculationHistory)\
        .filter(CalculationHistory.id == calc_id, CalculationHistory.user_id == current_user.id)\
        .first()
        
    if not calc:
        raise HTTPException(status_code=404, detail="Calculation record not found.")
        
    db.delete(calc)
    db.commit()
    return {"detail": "Calculation removed from history."}

@router.get("/stats", response_model=DashboardStats)
def get_dashboard_statistics(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """Computes usage statistics and category breakdowns for the user dashboard."""
    calcs = db.query(CalculationHistory).filter(CalculationHistory.user_id == current_user.id).all()
    
    total = len(calcs)
    saved = sum(1 for c in calcs if c.is_saved)
    
    # Calculate type count distribution
    categories = {}
    for c in calcs:
        categories[c.calculation_type] = categories.get(c.calculation_type, 0) + 1
        
    recent_activity = db.query(ActivityLog)\
        .filter(ActivityLog.user_id == current_user.id)\
        .count()

    return {
        "total_calculations": total,
        "saved_calculations": saved,
        "recent_activity_count": recent_activity,
        "categories_breakdown": categories
    }

@router.post("/report", response_model=AdminReportResponse)
def submit_admin_report(
    body: AdminReportCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """Submits a bug report, mathematical inaccuracy flag, or feature request to the system Admin."""
    report = AdminReport(
        reporter_id=current_user.id,
        title=body.title,
        content=body.content,
        status="open"
    )
    db.add(report)
    db.commit()
    db.refresh(report)
    return report
