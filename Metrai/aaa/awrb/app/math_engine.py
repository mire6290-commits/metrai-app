import math
import numpy as np
import scipy.stats as stats
import pandas as pd
import sympy as sp
from typing import List, Dict, Any, Optional, Union

# Define standard math symbols
x, y, z, t = sp.symbols('x y z t')

class MathEngine:
    @staticmethod
    def parse_expression(expr_str: str):
        """Safely parses a string expression into a SymPy object."""
        # Replace caret with double asterisk for power operations
        cleaned = expr_str.replace('^', '**')
        # Handle implied multiplication (e.g. 2x -> 2*x)
        # Note: SymPy sympify can parse standard expressions, but cleaning beforehand helps robustness.
        try:
            return sp.parse_expr(cleaned, transformations=sp.parsing.sympy_parser.standard_transformations + 
                                 (sp.parsing.sympy_parser.implicit_multiplication_application,))
        except Exception as e:
            raise ValueError(f"Invalid math expression syntax: {str(e)}")

    @classmethod
    def evaluate_scientific(cls, expr_str: str) -> Dict[str, Any]:
        """Evaluates general scientific expressions, supporting decimals, constants, and complex forms."""
        try:
            expr = cls.parse_expression(expr_str)
            numeric_val = float(expr.evalf())
            exact_val = sp.pretty(expr)
            latex_val = sp.latex(expr)
            
            # Build steps explanation
            steps = [
                f"Parsed the input expression: $${sp.latex(expr)}$$",
                f"Evaluated the exact symbolic representation: $${sp.latex(expr.simplify())}$$",
                f"Calculated the numerical decimal approximation: $${numeric_val:.10g}$$"
            ]
            
            return {
                "success": True,
                "input": expr_str,
                "numeric_result": numeric_val,
                "exact_result": str(expr),
                "latex": latex_val,
                "steps": steps
            }
        except Exception as e:
            return {"success": False, "error": str(e)}

    @classmethod
    def solve_equation(cls, eq_str: str, var_str: str = "x") -> Dict[str, Any]:
        """
        Solves algebraic equations (e.g., f(x) = g(x) or f(x) = 0).
        Supports quadratic, polynomial, systems, trigonometric, and transcendental.
        """
        try:
            var = sp.Symbol(var_str)
            # Parse equation
            if "=" in eq_str:
                lhs_str, rhs_str = eq_str.split("=")
                lhs = cls.parse_expression(lhs_str)
                rhs = cls.parse_expression(rhs_str)
                eq = sp.Eq(lhs, rhs)
                expr_to_solve = lhs - rhs
            else:
                expr_to_solve = cls.parse_expression(eq_str)
                eq = sp.Eq(expr_to_solve, 0)
            
            solutions = sp.solve(expr_to_solve, var)
            latex_solutions = [sp.latex(sol) for sol in solutions]
            
            steps = [
                f"Set up the equation to solve for variable ${var_str}$:",
                f"$${sp.latex(eq)}$$",
                f"Rearranged equation into standard form $f({var_str}) = 0$:",
                f"$${sp.latex(expr_to_solve)} = 0$$"
            ]

            # Detailed solver steps
            if expr_to_solve.is_polynomial(var):
                deg = sp.degree(expr_to_solve, var)
                steps.append(f"Detected a polynomial equation of degree {deg}.")
                if deg == 1:
                    steps.append("Solved directly using linear isolating steps:")
                    steps.append(f"$${var_str} = {sp.latex(solutions[0])}$$")
                elif deg == 2:
                    steps.append("Used the quadratic formula $x = \\frac{-b \\pm \\sqrt{b^2 - 4ac}}{2a}$ to obtain roots:")
                    for idx, sol in enumerate(solutions):
                        steps.append(f"Root {idx+1}: $${var_str} = {sp.latex(sol)}$$")
                else:
                    steps.append("Factored the higher-degree polynomial and solved for roots:")
                    for sol in solutions:
                        steps.append(f"Root: $${var_str} = {sp.latex(sol)}$$")
            else:
                steps.append("Applied non-linear solver heuristics to find exact symbolic solutions:")
                for sol in solutions:
                    steps.append(f"Symbolic Solution: $${var_str} = {sp.latex(sol)}$$")

            # Fallback if symbolic yields nothing, try numerical
            if not solutions:
                steps.append("Symbolic solver could not find exact roots. Attempting numerical root-finding (SciPy/NumPy):")
                try:
                    f_numeric = sp.lambdify(var, expr_to_solve, "numpy")
                    # Find roots starting around -10 to 10
                    import scipy.optimize as opt
                    num_sols = []
                    for guess in [-5.0, -1.0, 0.0, 1.0, 5.0]:
                        try:
                            sol = float(opt.fsolve(f_numeric, guess)[0])
                            if not any(math.isclose(sol, s, abs_tol=1e-5) for s in num_sols):
                                num_sols.append(sol)
                        except Exception:
                            continue
                    if num_sols:
                        solutions = num_sols
                        latex_solutions = [f"{sol:.6f}" for sol in num_sols]
                        steps.append(f"Numerical approximations found: {', '.join([f'${s:.6f}$' for s in num_sols])}")
                    else:
                        steps.append("No real roots found.")
                except Exception as ne:
                    steps.append(f"Numerical solver failed: {str(ne)}")

            return {
                "success": True,
                "equation": str(eq),
                "variable": var_str,
                "solutions": [str(s) for s in solutions],
                "latex_solutions": latex_solutions,
                "steps": steps
            }
        except Exception as e:
            return {"success": False, "error": str(e)}

    @classmethod
    def simplify_algebra(cls, expr_str: str, operation: str = "simplify") -> Dict[str, Any]:
        """Performs algebraic simplifications: simplify, factor, expand, or simplify fractions."""
        try:
            expr = cls.parse_expression(expr_str)
            steps = [f"Initial expression: $${sp.latex(expr)}$$"]
            
            if operation == "simplify":
                res = sp.simplify(expr)
                steps.append("Applied SymPy standard simplification algorithm to combine terms, reduce quotients, and clear trig forms:")
            elif operation == "factor":
                res = sp.factor(expr)
                steps.append("Factored the expression into products of irreducible polynomials:")
            elif operation == "expand":
                res = sp.expand(expr)
                steps.append("Expanded the terms, distributing factors and exponents across additions:")
            elif operation == "cancel":
                res = sp.cancel(expr)
                steps.append("Cancelled common factors in the numerator and denominator of rational fractions:")
            else:
                res = sp.simplify(expr)
            
            steps.append(f"Final output: $${sp.latex(res)}$$")
            
            return {
                "success": True,
                "input": expr_str,
                "operation": operation,
                "result": str(res),
                "latex": sp.latex(res),
                "steps": steps
            }
        except Exception as e:
            return {"success": False, "error": str(e)}

    @classmethod
    def solve_calculus(
        cls, 
        op_type: str, 
        expr_str: str, 
        var_str: str = "x", 
        limit_point: str = "0", 
        limit_dir: str = "+-", 
        lower_bound: str = None, 
        upper_bound: str = None
    ) -> Dict[str, Any]:
        """
        Executes calculus operations: derivative, integral (definite/indefinite), or limit.
        Includes full educational derivations.
        """
        try:
            var = sp.Symbol(var_str)
            expr = cls.parse_expression(expr_str)
            steps = []
            
            if op_type == "derivative":
                steps.append(f"Given function to differentiate: $$f({var_str}) = {sp.latex(expr)}$$")
                res = sp.diff(expr, var)
                steps.append(f"Differentiated with respect to ${var_str}$ using power rule, product/chain rules:")
                
                # Dynamic derivative step breakdown
                if expr.is_Add:
                    steps.append("Applying the Sum/Difference Rule: Differentiate each term independently:")
                    for term in expr.args:
                        steps.append(f"$$\\frac{{d}}{{d{var_str}}}\\left({sp.latex(term)}\\right) = {sp.latex(sp.diff(term, var))}$$")
                elif expr.is_Mul:
                    steps.append("Applying Product / Quotient rules for multiplication:")
                
                steps.append(f"Combining and simplifying terms:")
                steps.append(f"$$\\frac{{d}}{{d{var_str}}}\\left[{sp.latex(expr)}\\right] = {sp.latex(res)}$$")
                
                return {
                    "success": True,
                    "operation": "derivative",
                    "input": expr_str,
                    "result": str(res),
                    "latex": sp.latex(res),
                    "steps": steps
                }
                
            elif op_type == "integral":
                if lower_bound is not None and upper_bound is not None and lower_bound != "" and upper_bound != "":
                    # Definite Integral
                    lb = cls.parse_expression(lower_bound)
                    ub = cls.parse_expression(upper_bound)
                    steps.append(f"Setting up the definite integral of $f({var_str})$ from ${lower_bound}$ to ${upper_bound}$:")
                    steps.append(f"$$\\int_{{{sp.latex(lb)}}}^{{{sp.latex(ub)}}} {sp.latex(expr)} \\, d{var_str}$$")
                    
                    indef_res = sp.integrate(expr, var)
                    def_res = sp.integrate(expr, (var, lb, ub))
                    
                    steps.append("Step 1: Compute the antiderivative (indefinite integral) first:")
                    steps.append(f"$$F({var_str}) = \\int {sp.latex(expr)} \\, d{var_str} = {sp.latex(indef_res)}$$")
                    steps.append("Step 2: Apply the Fundamental Theorem of Calculus: $F(b) - F(a)$:")
                    
                    fb = indef_res.subs(var, ub)
                    fa = indef_res.subs(var, lb)
                    steps.append(f"Evaluate at upper limit $F({sp.latex(ub)}) = {sp.latex(fb)}$")
                    steps.append(f"Evaluate at lower limit $F({sp.latex(lb)}) = {sp.latex(fa)}$")
                    steps.append(f"Evaluate difference: $${sp.latex(fb)} - \\left({sp.latex(fa)}\\right) = {sp.latex(def_res)}$$")
                    
                    return {
                        "success": True,
                        "operation": "definite_integral",
                        "input": expr_str,
                        "lower_bound": lower_bound,
                        "upper_bound": upper_bound,
                        "result": str(def_res),
                        "latex": sp.latex(def_res),
                        "steps": steps
                    }
                else:
                    # Indefinite Integral
                    steps.append(f"Given function to integrate: $$f({var_str}) = {sp.latex(expr)}$$")
                    res = sp.integrate(expr, var)
                    steps.append(f"Found the anti-derivative using integration methods:")
                    steps.append(f"$$\\int {sp.latex(expr)} \\, d{var_str} = {sp.latex(res)} + C$$")
                    
                    return {
                        "success": True,
                        "operation": "indefinite_integral",
                        "input": expr_str,
                        "result": f"{res} + C",
                        "latex": f"{sp.latex(res)} + C",
                        "steps": steps
                    }
                    
            elif op_type == "limit":
                pt = cls.parse_expression(limit_point)
                steps.append(f"Evaluating the limit of $f({var_str}) = {sp.latex(expr)}$ as ${var_str}$ approaches ${limit_point}$:")
                
                if limit_dir == "+":
                    res = sp.limit(expr, var, pt, dir="+")
                    steps.append(f"Evaluating right-handed limit ($x \\to {limit_point}^+$):")
                elif limit_dir == "-":
                    res = sp.limit(expr, var, pt, dir="-")
                    steps.append(f"Evaluating left-handed limit ($x \\to {limit_point}^-$):")
                else:
                    res = sp.limit(expr, var, pt)
                    steps.append(f"Evaluating two-sided limit ($x \\to {limit_point}$):")
                
                steps.append(f"$$\\lim_{{{var_str} \\to {sp.latex(pt)}}} {sp.latex(expr)} = {sp.latex(res)}$$")
                
                return {
                    "success": True,
                    "operation": "limit",
                    "input": expr_str,
                    "limit_point": limit_point,
                    "direction": limit_dir,
                    "result": str(res),
                    "latex": sp.latex(res),
                    "steps": steps
                }
            else:
                return {"success": False, "error": f"Invalid calculus operation: {op_type}"}
                
        except Exception as e:
            return {"success": False, "error": str(e)}

    @classmethod
    def solve_matrix(cls, matrix_a: List[List[float]], matrix_b: Optional[List[List[float]]] = None, operation: str = "determinant", scalar: Optional[float] = None) -> Dict[str, Any]:
        """Performs robust matrix operations (addition, subtraction, multiplication, inverse, determinant, transpose, eigenvalues)."""
        try:
            mA = sp.Matrix(matrix_a)
            steps = [f"Matrix A set up: $${sp.latex(mA)}$$"]
            
            if operation == "add":
                if not matrix_b:
                    return {"success": False, "error": "Matrix B is required for addition"}
                mB = sp.Matrix(matrix_b)
                if mA.shape != mB.shape:
                    return {"success": False, "error": f"Matrices must have the same size (A is {mA.shape}, B is {mB.shape})"}
                res = mA + mB
                steps.append(f"Adding Matrix A and Matrix B: $${sp.latex(mA)} + {sp.latex(mB)}$$")
                steps.append(f"Resulting sum: $${sp.latex(res)}$$")
                
            elif operation == "subtract":
                if not matrix_b:
                    return {"success": False, "error": "Matrix B is required for subtraction"}
                mB = sp.Matrix(matrix_b)
                if mA.shape != mB.shape:
                    return {"success": False, "error": f"Matrices must have the same size (A is {mA.shape}, B is {mB.shape})"}
                res = mA - mB
                steps.append(f"Subtracting Matrix B from Matrix A: $${sp.latex(mA)} - {sp.latex(mB)}$$")
                steps.append(f"Resulting difference: $${sp.latex(res)}$$")
                
            elif operation == "multiply":
                if not matrix_b:
                    return {"success": False, "error": "Matrix B is required for multiplication"}
                mB = sp.Matrix(matrix_b)
                if mA.shape[1] != mB.shape[0]:
                    return {"success": False, "error": f"Inner dimensions must match for multiplication: A columns ({mA.shape[1]}) must equal B rows ({mB.shape[0]})"}
                res = mA * mB
                steps.append(f"Multiplied Matrix A ({mA.shape[0]}x{mA.shape[1]}) by Matrix B ({mB.shape[0]}x{mB.shape[1]}):")
                steps.append(f"$${sp.latex(mA)} \\times {sp.latex(mB)}$$")
                steps.append(f"Resulting product: $${sp.latex(res)}$$")
                
            elif operation == "scalar_multiply":
                if scalar is None:
                    return {"success": False, "error": "Scalar value is required"}
                res = mA * scalar
                steps.append(f"Multiplying Matrix A by scalar factor {scalar}:")
                steps.append(f"{scalar} \\times {sp.latex(mA)}")
                steps.append(f"Resulting scaled matrix: $${sp.latex(res)}$$")
                
            elif operation == "determinant":
                if not mA.is_square:
                    return {"success": False, "error": "Determinant is only defined for square matrices"}
                res = mA.det()
                steps.append(f"Calculating the determinant of square matrix A:")
                steps.append(f"$$\\det(A) = {sp.latex(res)}$$")
                
            elif operation == "inverse":
                if not mA.is_square:
                    return {"success": False, "error": "Inverse is only defined for square matrices"}
                if mA.det() == 0:
                    return {"success": False, "error": "Matrix is singular (determinant = 0) and does not have an inverse"}
                res = mA.inv()
                steps.append(f"Inverting square matrix A (since $\\det(A) \\neq 0$):")
                steps.append(f"$$A^{{-1}} = {sp.latex(res)}$$")
                
            elif operation == "transpose":
                res = mA.T
                steps.append(f"Transposing Matrix A (swapping rows with columns):")
                steps.append(f"$$A^T = {sp.latex(res)}$$")
                
            elif operation == "eigenvalues":
                if not mA.is_square:
                    return {"success": False, "error": "Eigenvalues are only defined for square matrices"}
                res_dict = mA.eigenvals()
                res = str(res_dict)
                steps.append("Solving the characteristic equation $\\det(A - \\lambda I) = 0$:")
                for eigenval, multiplicity in res_dict.items():
                    steps.append(f"Eigenvalue $\\lambda = {sp.latex(eigenval)}$ with algebraic multiplicity {multiplicity}")
            else:
                return {"success": False, "error": f"Invalid matrix operation: {operation}"}
                
            # Formatting results
            res_str = str(res)
            latex_res = sp.latex(res) if not isinstance(res, str) else res
            
            return {
                "success": True,
                "operation": operation,
                "result": res_str,
                "latex": latex_res,
                "steps": steps
            }
        except Exception as e:
            return {"success": False, "error": str(e)}

    @classmethod
    def solve_statistics(cls, data_points: List[float]) -> Dict[str, Any]:
        """Calculates advanced descriptive and inferential statistics using SciPy/NumPy/Pandas."""
        try:
            if not data_points:
                return {"success": False, "error": "Data points list cannot be empty"}
            
            df = pd.Series(data_points)
            arr = np.array(data_points)
            
            mean = float(np.mean(arr))
            median = float(np.median(arr))
            variance = float(np.var(arr, ddof=1)) if len(arr) > 1 else 0.0
            std_dev = float(np.std(arr, ddof=1)) if len(arr) > 1 else 0.0
            min_val = float(np.min(arr))
            max_val = float(np.max(arr))
            skewness = float(stats.skew(arr)) if len(arr) > 2 else 0.0
            kurtosis = float(stats.kurtosis(arr)) if len(arr) > 2 else 0.0
            
            # Formulate mathematical explanation
            steps = [
                f"Ingested dataset of size $N = {len(data_points)}$: $[{', '.join([str(x) for x in data_points])}]$",
                f"Sorted Dataset: $[{', '.join([str(x) for x in sorted(data_points)])}]$",
                f"Calculated Mean (average) $\\mu = \\frac{{\\sum x_i}}{{N}} = {mean:.6g}$",
                f"Calculated Median (middle value) $M = {median:.6g}$",
                f"Calculated Sample Variance $s^2 = \\frac{{\\sum (x_i - \\mu)^2}}{{N-1}} = {variance:.6g}$",
                f"Calculated Standard Deviation $s = \\sqrt{{s^2}} = {std_dev:.6g}$",
                f"Range: $[{min_val:.6g}, {max_val:.6g}]$ (Width: {max_val - min_val:.6g})"
            ]
            
            return {
                "success": True,
                "stats": {
                    "count": len(data_points),
                    "mean": mean,
                    "median": median,
                    "variance": variance,
                    "std_dev": std_dev,
                    "min": min_val,
                    "max": max_val,
                    "skewness": skewness,
                    "kurtosis": kurtosis
                },
                "steps": steps
            }
        except Exception as e:
            return {"success": False, "error": str(e)}

    @classmethod
    def convert_units(cls, value: float, from_unit: str, to_unit: str, category: str) -> Dict[str, Any]:
        """Provides unit conversions for length, mass, temperature, area, volume, and speed."""
        try:
            conversions = {
                "length": {
                    "m": 1.0, "km": 0.001, "cm": 100.0, "mm": 1000.0, 
                    "in": 39.3701, "ft": 3.28084, "yd": 1.09361, "mi": 0.000621371
                },
                "mass": {
                    "kg": 1.0, "g": 1000.0, "mg": 1000000.0, "lb": 2.20462, "oz": 35.274
                },
                "area": {
                    "m2": 1.0, "km2": 0.000001, "cm2": 10000.0, "mm2": 1000000.0,
                    "hec": 0.0001, "acre": 0.000247105, "ft2": 10.7639, "in2": 1550.0
                },
                "volume": {
                    "l": 1.0, "ml": 1000.0, "m3": 0.001, "gal": 0.264172, "qt": 1.05669, "cup": 4.22675
                },
                "speed": {
                    "m_s": 1.0, "km_h": 3.6, "mph": 2.23694, "knot": 1.94384
                }
            }

            if category == "temperature":
                # Temperature has non-multiplicative conversions
                from_u = from_unit.lower()
                to_u = to_unit.lower()
                res = value
                
                # Convert to Celsius first
                if from_u == "f":
                    c = (value - 32) * 5/9
                elif from_u == "k":
                    c = value - 273.15
                else:
                    c = value
                
                # Convert from Celsius to target
                if to_u == "f":
                    res = (c * 9/5) + 32
                elif to_u == "k":
                    res = c + 273.15
                else:
                    res = c
                
                steps = [
                    f"Converting temperature from {from_unit.upper()} to {to_unit.upper()}:",
                    f"Input: {value}°{from_unit.upper()} = {res:.6g}°{to_unit.upper()}"
                ]
                return {"success": True, "result": res, "steps": steps}

            if category not in conversions:
                return {"success": False, "error": f"Invalid unit category: {category}"}

            cat_map = conversions[category]
            if from_unit not in cat_map or to_unit not in cat_map:
                return {"success": False, "error": f"Unsupported conversion from {from_unit} to {to_unit} in category {category}"}

            # Convert to base unit then to target unit
            base_val = value / cat_map[from_unit]
            res = base_val * cat_map[to_unit]
            
            steps = [
                f"Selected Category: {category.capitalize()}",
                f"Converting from {from_unit} to base unit: {value} / {cat_map[from_unit]} = {base_val:.6g}",
                f"Converting from base unit to {to_unit}: {base_val:.6g} * {cat_map[to_unit]} = {res:.6g}"
            ]

            return {
                "success": True,
                "result": res,
                "steps": steps
            }
        except Exception as e:
            return {"success": False, "error": str(e)}
