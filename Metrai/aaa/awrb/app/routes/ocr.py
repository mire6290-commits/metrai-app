from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Request, status
from sqlalchemy.orm import Session
from app.database import get_db
from app.models import CalculationHistory, ActivityLog
from app.auth import get_optional_user
from app.ocr_engine import OCREngine
from app.math_engine import MathEngine
import json
from typing import Optional, Any

router = APIRouter(prefix="/api/ocr", tags=["OCR Image Recognition"])

def save_ocr_history(db: Session, user_id: Optional[int], input_img_name: str, result_dict: dict):
    if not user_id:
        return
    history = CalculationHistory(
        user_id=user_id,
        calculation_type="ocr_extraction",
        expression_input=f"Uploaded Image: {input_img_name}",
        expression_output=json.dumps(result_dict),
        is_saved=False
    )
    db.add(history)
    db.commit()

@router.post("/upload")
async def upload_math_image(
    request: Request,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    user: Optional[Any] = Depends(get_optional_user)
):
    """
    Ingests an image containing hand-written or printed math equations,
    preprocesses it locally using OpenCV, and runs Tesseract to extract the formula.
    """
    # Verify file is an image
    if not file.content_type.startswith("image/"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="File uploaded is not a valid image format."
        )
        
    try:
        image_bytes = await file.read()
        ocr_result = OCREngine.extract_expression(image_bytes)
        
        user_id = user.id if user else None
        save_ocr_history(db, user_id, file.filename, ocr_result)
        
        return ocr_result
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Image parsing error: {str(e)}")

@router.post("/solve")
async def upload_and_solve(
    request: Request,
    file: UploadFile = File(...),
    operation: str = "solve",  # "solve", "simplify", "derivative", "integral"
    db: Session = Depends(get_db),
    user: Optional[Any] = Depends(get_optional_user)
):
    """
    An ultra-premium endpoint: Upload an image, extract the mathematical equation, 
    and automatically solve/integrate/differentiate the extracted expression in a single step.
    """
    if not file.content_type.startswith("image/"):
        raise HTTPException(status_code=400, detail="Uploaded file is not a valid image.")
        
    try:
        image_bytes = await file.read()
        ocr_result = OCREngine.extract_expression(image_bytes)
        
        if not ocr_result["success"]:
            return ocr_result

        expr = ocr_result["cleaned_expression"]
        solve_result = None

        # Determine math solving route
        if operation == "solve":
            # Check if it looks like an equation
            solve_result = MathEngine.solve_equation(expr)
        elif operation == "simplify":
            solve_result = MathEngine.simplify_algebra(expr, "simplify")
        elif operation == "derivative":
            solve_result = MathEngine.solve_calculus("derivative", expr)
        elif operation == "integral":
            solve_result = MathEngine.solve_calculus("integral", expr)
        else:
            solve_result = MathEngine.evaluate_scientific(expr)

        response_data = {
            "ocr": ocr_result,
            "solution": solve_result
        }
        
        user_id = user.id if user else None
        if user_id and solve_result:
            history = CalculationHistory(
                user_id=user_id,
                calculation_type=f"ocr_and_{operation}",
                expression_input=f"Image Solve ({file.filename}): {expr}",
                expression_output=json.dumps(response_data),
                is_saved=False
            )
            db.add(history)
            db.commit()

        return response_data
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"OCR solve automation failed: {str(e)}")
