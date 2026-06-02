import json
from fastapi import APIRouter, Depends, HTTPException, status, Request
from sqlalchemy.orm import Session
from app.database import get_db
from app.models import CalculationHistory, ActivityLog
from app.schemas import MathSolveRequest, MatrixRequest, UnitConversionRequest
from app.auth import get_optional_user
from app.math_engine import MathEngine
from app.graph_engine import GraphEngine

router = APIRouter(prefix="/api/math", tags=["Math Engine"])

def save_calculation(db: Session, user_id: Optional[int], calc_type: str, input_val: str, output_dict: dict):
    """Saves mathematical execution history if a user session is active."""
    if not user_id:
        return
    history = CalculationHistory(
        user_id=user_id,
        calculation_type=calc_type,
        expression_input=input_val,
        expression_output=json.dumps(output_dict),
        is_saved=False
    )
    db.add(history)
    db.commit()

@router.post("/scientific")
def scientific_calculator(
    request: Request,
    body: MathSolveRequest,
    db: Session = Depends(get_db),
    user: Optional[Any] = Depends(get_optional_user)
):
    """Evaluates general scientific expressions, supporting decimals, trig, log, and constants."""
    result = MathEngine.evaluate_scientific(body.expression)
    if not result["success"]:
        raise HTTPException(status_code=400, detail=result.get("error", "Failed to evaluate expression."))
    
    user_id = user.id if user else None
    save_calculation(db, user_id, "scientific", body.expression, result)
    return result

@router.post("/algebra")
def algebra_solver(
    request: Request,
    body: MathSolveRequest,
    db: Session = Depends(get_db),
    user: Optional[Any] = Depends(get_optional_user)
):
    """
    Performs algebraic solvers.
    Options: 'simplify', 'factor', 'expand', 'cancel', or 'solve'.
    """
    operation = body.options.get("operation", "simplify") if body.options else "simplify"
    variable = body.options.get("variable", "x") if body.options else "x"
    
    if operation == "solve":
        result = MathEngine.solve_equation(body.expression, variable)
    else:
        result = MathEngine.simplify_algebra(body.expression, operation)
        
    if not result["success"]:
        raise HTTPException(status_code=400, detail=result.get("error", "Algebra operation failed."))
        
    user_id = user.id if user else None
    save_calculation(db, user_id, f"algebra_{operation}", body.expression, result)
    return result

@router.post("/calculus")
def calculus_solver(
    request: Request,
    body: MathSolveRequest,
    db: Session = Depends(get_db),
    user: Optional[Any] = Depends(get_optional_user)
):
    """
    Performs calculus operations.
    Options: 'derivative', 'integral', 'limit'.
    Supports: variables, bounds, directions.
    """
    if not body.options or "operation" not in body.options:
        raise HTTPException(status_code=400, detail="Calculus 'operation' option is required (derivative, integral, limit).")
        
    operation = body.options.get("operation")
    variable = body.options.get("variable", "x")
    
    # Optional parameters for definite integration / limits
    lower_bound = body.options.get("lower_bound")
    upper_bound = body.options.get("upper_bound")
    limit_point = body.options.get("limit_point", "0")
    limit_dir = body.options.get("direction", "+-")
    
    result = MathEngine.solve_calculus(
        op_type=operation,
        expr_str=body.expression,
        var_str=variable,
        limit_point=limit_point,
        limit_dir=limit_dir,
        lower_bound=lower_bound,
        upper_bound=upper_bound
    )
    
    if not result["success"]:
        raise HTTPException(status_code=400, detail=result.get("error", "Calculus operation failed."))
        
    user_id = user.id if user else None
    save_calculation(db, user_id, f"calculus_{operation}", body.expression, result)
    return result

@router.post("/matrix")
def matrix_solver(
    request: Request,
    body: MatrixRequest,
    db: Session = Depends(get_db),
    user: Optional[Any] = Depends(get_optional_user)
):
    """Executes matrix addition, subtraction, multiplication, inverse, determinant, transpose, or eigenvalues."""
    result = MathEngine.solve_matrix(
        matrix_a=body.matrix_a,
        matrix_b=body.matrix_b,
        operation=body.operation,
        scalar=body.scalar
    )
    
    if not result["success"]:
        raise HTTPException(status_code=400, detail=result.get("error", "Matrix calculation failed."))
        
    user_id = user.id if user else None
    save_calculation(db, user_id, f"matrix_{body.operation}", f"Matrix A size {len(body.matrix_a)}x{len(body.matrix_a[0])}", result)
    return result

@router.post("/statistics")
def statistics_calculator(
    request: Request,
    body: MathSolveRequest,
    db: Session = Depends(get_db),
    user: Optional[Any] = Depends(get_optional_user)
):
    """
    Computes dataset statistics from a comma-separated string of data values.
    Example Input: '1.2, 3.4, 5.6, 7.8, 9.0'
    """
    try:
        data_points = [float(val.strip()) for val in body.expression.split(",") if val.strip() != ""]
    except ValueError:
        raise HTTPException(status_code=400, detail="Data points must be a list of numerical values separated by commas.")
        
    result = MathEngine.solve_statistics(data_points)
    if not result["success"]:
        raise HTTPException(status_code=400, detail=result.get("error", "Statistics computation failed."))
        
    user_id = user.id if user else None
    save_calculation(db, user_id, "statistics", f"N={len(data_points)}", result)
    return result

@router.post("/convert")
def unit_converter(
    request: Request,
    body: UnitConversionRequest,
    db: Session = Depends(get_db),
    user: Optional[Any] = Depends(get_optional_user)
):
    """Executes length, mass, temperature, area, volume, and speed conversions."""
    result = MathEngine.convert_units(
        value=body.value,
        from_unit=body.from_unit,
        to_unit=body.to_unit,
        category=body.category
    )
    
    if not result["success"]:
        raise HTTPException(status_code=400, detail=result.get("error", "Unit conversion failed."))
        
    user_id = user.id if user else None
    save_calculation(db, user_id, "conversion", f"{body.value} {body.from_unit} to {body.to_unit}", result)
    return result

@router.post("/plot/2d")
def plot_2d_graph(
    request: Request,
    body: MathSolveRequest,
    db: Session = Depends(get_db),
    user: Optional[Any] = Depends(get_optional_user)
):
    """Plots a 2D equation y = f(x) and returns Plotly configs alongside a base64 print static fallback."""
    x_min = body.options.get("x_min", -10.0) if body.options else -10.0
    x_max = body.options.get("x_max", 10.0) if body.options else 10.0
    variable = body.options.get("variable", "x") if body.options else "x"
    
    result = GraphEngine.plot_2d_expression(
        expr_str=body.expression,
        var_str=variable,
        x_min=float(x_min),
        x_max=float(x_max)
    )
    
    if not result["success"]:
        raise HTTPException(status_code=400, detail=result.get("error", "Plotting failed."))
        
    user_id = user.id if user else None
    save_calculation(db, user_id, "plot_2d", f"y = {body.expression}", {"plotted": True})
    return result

@router.post("/plot/3d")
def plot_3d_graph(
    request: Request,
    body: MathSolveRequest,
    db: Session = Depends(get_db),
    user: Optional[Any] = Depends(get_optional_user)
):
    """Plots a 3D surface z = f(x, y) over defined boundaries."""
    x_min = body.options.get("x_min", -5.0) if body.options else -5.0
    x_max = body.options.get("x_max", 5.0) if body.options else 5.0
    y_min = body.options.get("y_min", -5.0) if body.options else -5.0
    y_max = body.options.get("y_max", 5.0) if body.options else 5.0
    var_x = body.options.get("var_x", "x") if body.options else "x"
    var_y = body.options.get("var_y", "y") if body.options else "y"
    
    result = GraphEngine.plot_3d_surface(
        expr_str=body.expression,
        var_x=var_x,
        var_y=var_y,
        x_min=float(x_min),
        x_max=float(x_max),
        y_min=float(y_min),
        y_max=float(y_max)
    )
    
    if not result["success"]:
        raise HTTPException(status_code=400, detail=result.get("error", "Plotting failed."))
        
    user_id = user.id if user else None
    save_calculation(db, user_id, "plot_3d", f"z = {body.expression}", {"plotted": True})
    return result
