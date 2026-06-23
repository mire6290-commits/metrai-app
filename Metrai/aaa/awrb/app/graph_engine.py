import base64
import io
import json
import numpy as np
import matplotlib
# Set backend to Agg for non-interactive rendering in web applications
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import plotly.graph_objects as go
import plotly.io as pio
import sympy as sp
from typing import Dict, Any, List, Optional, Tuple

class GraphEngine:
    @staticmethod
    def get_dark_theme_layout() -> Dict[str, Any]:
        """Returns standard Plotly layout parameters for dark glassmorphic styling."""
        return {
            "paper_bgcolor": "rgba(30, 41, 59, 0.4)",
            "plot_bgcolor": "rgba(30, 41, 59, 0.6)",
            "font": {"color": "#f1f5f9", "family": "Inter, sans-serif"},
            "xaxis": {
                "gridcolor": "#334155",
                "zerolinecolor": "#64748b",
                "linecolor": "#475569"
            },
            "yaxis": {
                "gridcolor": "#334155",
                "zerolinecolor": "#64748b",
                "linecolor": "#475569"
            },
            "margin": {"l": 40, "r": 40, "t": 60, "b": 40},
            "legend": {"bgcolor": "rgba(15, 23, 42, 0.8)", "bordercolor": "#334155"}
        }

    @classmethod
    def plot_2d_expression(
        cls, 
        expr_str: str, 
        var_str: str = "x", 
        x_min: float = -10.0, 
        x_max: float = 10.0,
        num_points: int = 400
    ) -> Dict[str, Any]:
        """
        Plots an explicit equation y = f(x) over a range.
        Returns a dictionary containing Plotly JSON structure and a Matplotlib base64 image.
        """
        try:
            var = sp.Symbol(var_str)
            # Replace caret with double asterisk
            cleaned = expr_str.replace("^", "**")
            expr = sp.parse_expr(cleaned, transformations=sp.parsing.sympy_parser.standard_transformations + 
                                 (sp.parsing.sympy_parser.implicit_multiplication_application,))
            
            # Create numpy vectorized function
            f_np = sp.lambdify(var, expr, modules=["numpy", {"sin": np.sin, "cos": np.cos, "tan": np.tan, "exp": np.exp, "log": np.log, "sqrt": np.sqrt}])
            
            x_vals = np.linspace(x_min, x_max, num_points)
            y_vals = f_np(x_vals)
            
            # Handle float arrays with infinities, complex values, or divide-by-zero anomalies
            if np.iscomplexobj(y_vals):
                y_vals = np.real(y_vals)
            
            y_vals = np.where(np.isinf(y_vals), np.nan, y_vals)
            y_vals = np.where(np.abs(y_vals) > 1e4, np.nan, y_vals)

            # --- 1. GENERATE DYNAMIC PLOTLY GRAPH ---
            fig = go.Figure()
            fig.add_trace(go.Scatter(
                x=x_vals, 
                y=y_vals, 
                mode="lines", 
                name=f"y = {expr_str}",
                line=dict(color="#10b981", width=3)  # Vibrant emerald line
            ))
            
            fig.update_layout(
                title=f"Graph of y = {sp.pretty(expr)}",
                xaxis_title=var_str,
                yaxis_title="y",
                **cls.get_dark_theme_layout()
            )
            plotly_json = json.loads(pio.to_json(fig))

            # --- 2. GENERATE STATIC MATPLOTLIB IMAGE (FALLBACK / PRINT) ---
            plt.style.use('dark_background')
            fig_plt, ax = plt.subplots(figsize=(6, 4.5), dpi=100)
            fig_plt.patch.set_alpha(0.0)  # Transparent surrounding
            ax.set_alpha(0.0)
            ax.patch.set_facecolor('#1e293b')
            ax.grid(True, color="#334155", linestyle="--")
            
            ax.plot(x_vals, y_vals, color="#10b981", linewidth=2.5, label=f"y = {expr_str}")
            ax.axhline(0, color='#64748b', linewidth=1.2)
            ax.axvline(0, color='#64748b', linewidth=1.2)
            ax.set_title(f"y = {expr_str}", color="#f1f5f9", fontsize=12, fontweight='bold')
            ax.set_xlabel(var_str, color="#cbd5e1")
            ax.set_ylabel("y", color="#cbd5e1")
            ax.tick_params(colors="#cbd5e1")
            
            # Output base64 encoding
            buf = io.BytesIO()
            fig_plt.savefig(buf, format="png", bbox_inches='tight', transparent=True)
            plt.close(fig_plt)
            buf.seek(0)
            base64_image = base64.b64encode(buf.read()).decode("utf-8")

            return {
                "success": True,
                "plotly_data": plotly_json,
                "base64_img": f"data:image/png;base64,{base64_image}"
            }
        except Exception as e:
            return {"success": False, "error": str(e)}

    @classmethod
    def plot_3d_surface(
        cls, 
        expr_str: str, 
        var_x: str = "x", 
        var_y: str = "y", 
        x_min: float = -5.0, 
        x_max: float = 5.0, 
        y_min: float = -5.0, 
        y_max: float = 5.0,
        num_points: int = 100
    ) -> Dict[str, Any]:
        """Plots a 3D Surface z = f(x, y) over a defined boundary box."""
        try:
            vx = sp.Symbol(var_x)
            vy = sp.Symbol(var_y)
            cleaned = expr_str.replace("^", "**")
            expr = sp.parse_expr(cleaned, transformations=sp.parsing.sympy_parser.standard_transformations + 
                                 (sp.parsing.sympy_parser.implicit_multiplication_application,))
            
            f_np = sp.lambdify((vx, vy), expr, modules=["numpy", {"sin": np.sin, "cos": np.cos, "tan": np.tan, "exp": np.exp, "log": np.log, "sqrt": np.sqrt}])
            
            x_vals = np.linspace(x_min, x_max, num_points)
            y_vals = np.linspace(y_min, y_max, num_points)
            x_grid, y_grid = np.meshgrid(x_vals, y_vals)
            
            z_vals = f_np(x_grid, y_grid)
            
            if np.iscomplexobj(z_vals):
                z_vals = np.real(z_vals)
            
            z_vals = np.where(np.isinf(z_vals), np.nan, z_vals)
            z_vals = np.where(np.abs(z_vals) > 1e4, np.nan, z_vals)

            # Generate Plotly 3D Surface
            fig = go.Figure()
            fig.add_trace(go.Surface(
                x=x_vals, 
                y=y_vals, 
                z=z_vals, 
                colorscale="Viridis",
                showscale=True
            ))
            
            fig.update_layout(
                title=f"3D Surface: z = {sp.pretty(expr)}",
                scene={
                    "xaxis": {"title": var_x, "gridcolor": "#334155", "zerolinecolor": "#64748b", "backgroundcolor": "#1e293b"},
                    "yaxis": {"title": var_y, "gridcolor": "#334155", "zerolinecolor": "#64748b", "backgroundcolor": "#1e293b"},
                    "zaxis": {"title": "z", "gridcolor": "#334155", "zerolinecolor": "#64748b", "backgroundcolor": "#1e293b"},
                    "xaxis_backgroundcolor": "rgba(30, 41, 59, 0.5)",
                    "yaxis_backgroundcolor": "rgba(30, 41, 59, 0.5)",
                    "zaxis_backgroundcolor": "rgba(30, 41, 59, 0.5)"
                },
                **cls.get_dark_theme_layout()
            )
            
            plotly_json = json.loads(pio.to_json(fig))

            # Matplotlib static fallback (3D projection)
            plt.style.use('dark_background')
            fig_plt = plt.figure(figsize=(6, 5), dpi=100)
            fig_plt.patch.set_alpha(0.0)
            ax = fig_plt.add_subplot(111, projection='3d')
            ax.patch.set_facecolor('#1e293b')
            ax.set_alpha(0.0)
            
            surf = ax.plot_surface(x_grid, y_grid, z_vals, cmap='viridis', edgecolor='none', alpha=0.9)
            ax.set_title(f"z = {expr_str}", color="#f1f5f9", fontsize=12, fontweight='bold')
            ax.set_xlabel(var_x, color="#cbd5e1")
            ax.set_ylabel(var_y, color="#cbd5e1")
            ax.set_zlabel("z", color="#cbd5e1")
            ax.tick_params(colors="#cbd5e1")
            
            buf = io.BytesIO()
            fig_plt.savefig(buf, format="png", bbox_inches='tight', transparent=True)
            plt.close(fig_plt)
            buf.seek(0)
            base64_image = base64.b64encode(buf.read()).decode("utf-8")

            return {
                "success": True,
                "plotly_data": plotly_json,
                "base64_img": f"data:image/png;base64,{base64_image}"
            }
        except Exception as e:
            return {"success": False, "error": str(e)}
