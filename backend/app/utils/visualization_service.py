# backend/app/utils/visualization_service.py
import json
import logging
from typing import Dict, List, Any, Optional
import io
import base64
import re

logger = logging.getLogger(__name__)

try:
    import pandas as pd
    import matplotlib.pyplot as plt
    VISUALIZATION_AVAILABLE = True
    logger.info("⭐ Visualization libraries (pandas, matplotlib) successfully imported")
except ImportError as e:
    logger.warning(f"⭐ Visualization libraries not available: {e}")
    VISUALIZATION_AVAILABLE = False
    # Create dummy classes for type checking
    pd = None
    plt = None

class VisualizationService:
    """Service for generating charts and graphs from query results"""
    
    def __init__(self):
        logger.info("⭐ ENTER: VisualizationService.__init__()")
        if VISUALIZATION_AVAILABLE:
            plt.style.use('default')
            logger.info("⭐ Matplotlib style set to default")
        else:
            logger.warning("⭐ Visualization disabled - required libraries not installed")
        logger.info("⭐ EXIT: VisualizationService.__init__() - Service initialized")
    
    def _detect_chart_type_from_query(self, query: str, data: List[Dict]) -> str:
        """Detect the appropriate chart type based on query and data"""
        logger.info(f"⭐ ENTER: _detect_chart_type_from_query(query='{query[:50]}...', data_rows={len(data)})")
        
        if not VISUALIZATION_AVAILABLE:
            logger.info("⭐ DECISION: Visualization not available, defaulting to bar chart")
            logger.info("⭐ EXIT: _detect_chart_type_from_query() -> 'bar'")
            return "bar"
            
        query_lower = query.lower()
        logger.info(f"⭐ Query lowercased: '{query_lower[:50]}...'")

        # Keyword-based detection
        logger.info("⭐ START: Keyword-based chart type detection")
        
        trend_keywords = ["trend", "over time", "history", "timeline", "growth"]
        trend_matches = [word for word in trend_keywords if word in query_lower]
        if trend_matches:
            logger.info(f"⭐ DECISION: Identified trend keywords: {trend_matches}")
            logger.info("⭐ EXIT: _detect_chart_type_from_query() -> 'bar' (trend)")
            return "bar" 
        
        distribution_keywords = ["distribution", "percentage", "ratio", "share", "breakdown"]
        distribution_matches = [word for word in distribution_keywords if word in query_lower]
        if distribution_matches:
            logger.info(f"⭐ DECISION: Identified distribution keywords: {distribution_matches}")
            logger.info("⭐ EXIT: _detect_chart_type_from_query() -> 'pie'")
            return "pie"
        
        comparison_keywords = ["compare", "ranking", "top", "best", "worst", "comparison", "graph", "chart", "visualize"]
        comparison_matches = [word for word in comparison_keywords if word in query_lower]
        if comparison_matches:
            logger.info(f"⭐ DECISION: Identified comparison keywords: {comparison_matches}")
            logger.info("⭐ EXIT: _detect_chart_type_from_query() -> 'bar' (comparison)")
            return "bar"
        
        scatter_keywords = ["relationship", "correlation", "scatter"]
        scatter_matches = [word for word in scatter_keywords if word in query_lower]
        if scatter_matches:
            logger.info(f"⭐ DECISION: Identified scatter keywords: {scatter_matches}")
            logger.info("⭐ EXIT: _detect_chart_type_from_query() -> 'scatter'")
            return "scatter"
        
        # Default to bar chart if no specific type is detected but data is present
        if data and len(data) > 0:
            logger.info("⭐ DECISION: No specific keywords found, defaulting to bar chart due to data presence")
            logger.info("⭐ EXIT: _detect_chart_type_from_query() -> 'bar' (default)")
            return "bar"
        
        # Data-based detection
        logger.info("⭐ START: Data-based chart type detection")
        if data and len(data) > 0:
            logger.info(f"⭐ Analyzing {len(data)} data rows for chart type detection")
            try:
                df = pd.DataFrame(data)
                numeric_columns = df.select_dtypes(include=['number']).columns.tolist()
                date_columns = [col for col in df.columns if any(keyword in col.lower() for keyword in ['date', 'time', 'year', 'month', 'day'])]
                
                logger.info(f"⭐ Found {len(numeric_columns)} numeric columns: {numeric_columns}")
                logger.info(f"⭐ Found {len(date_columns)} date columns: {date_columns}")
                
                if date_columns and numeric_columns:
                    logger.info("⭐ DECISION: Chart type detected: line (date + numeric columns)")
                    logger.info("⭐ EXIT: _detect_chart_type_from_query() -> 'line'")
                    return "line"
                elif len(numeric_columns) >= 2:
                    logger.info("⭐ DECISION: Chart type detected: scatter (multiple numeric columns)")
                    logger.info("⭐ EXIT: _detect_chart_type_from_query() -> 'scatter'")
                    return "scatter"
                elif len(data) <= 10:  # Small number of categories
                    logger.info(f"⭐ DECISION: Small dataset ({len(data)} rows), checking for pie chart suitability")
                    chart_type = "pie" if len(numeric_columns) == 1 else "bar"
                    logger.info(f"⭐ EXIT: _detect_chart_type_from_query() -> '{chart_type}'")
                    return chart_type
            except Exception as e:
                logger.error(f"⭐ ERROR during data-based detection: {str(e)}")
        
        logger.info("⭐ DECISION: Final fallback - defaulting to bar chart")
        logger.info("⭐ EXIT: _detect_chart_type_from_query() -> 'bar' (fallback)")
        return "bar"
    
    def generate_chart(self, data: List[Dict], query: str, title: str = "") -> Optional[Dict]:
        """Generate chart from data and return base64 encoded image"""
        logger.info(f"⭐ ENTER: generate_chart(data_rows={len(data)}, query='{query[:30]}...', title='{title}')")
        
        if not data:
            logger.warning("⭐ DECISION: No data provided for chart generation - returning None")
            logger.info("⭐ EXIT: generate_chart() -> None (no data)")
            return None
        
        if not VISUALIZATION_AVAILABLE:
            logger.warning("⭐ DECISION: Visualization libraries not available - returning None")
            logger.info("⭐ EXIT: generate_chart() -> None (libraries not available)")
            return None
        
        try:
            logger.info("⭐ Converting data to DataFrame")
            df = pd.DataFrame(data)
            logger.info(f"⭐ DataFrame created with shape: {df.shape}")
            
            # Clean column names and data
            logger.info("⭐ Cleaning column names")
            df.columns = [col.strip().lower() for col in df.columns]
            logger.info(f"⭐ Cleaned columns: {list(df.columns)}")
            
            # Convert numeric columns
            logger.info("⭐ Converting numeric columns")
            for col in df.columns:
                if df[col].dtype == 'object':
                    try:
                        df[col] = pd.to_numeric(df[col], errors='ignore')
                        logger.info(f"⭐ Converted column '{col}' to numeric")
                    except Exception as e:
                        logger.debug(f"⭐ Could not convert column '{col}' to numeric: {e}")
                        pass
            
            logger.info("⭐ Detecting chart type")
            chart_type = self._detect_chart_type_from_query(query, data)
            logger.info(f"⭐ DECISION: Selected chart type: {chart_type}")
            
            logger.info("⭐ Creating matplotlib figure")
            fig, ax = plt.subplots(figsize=(10, 6))
            
            logger.info(f"⭐ Creating {chart_type} chart")
            if chart_type == "bar":
                self._create_bar_chart(df, ax, query)
            elif chart_type == "line":
                self._create_line_chart(df, ax, query)
            elif chart_type == "pie":
                self._create_pie_chart(df, ax, query)
            elif chart_type == "scatter":
                self._create_scatter_chart(df, ax, query)
            else:
                logger.warning(f"⭐ DECISION: Unknown chart type: {chart_type}, defaulting to bar")
                self._create_bar_chart(df, ax, query)
                chart_type = "bar"
            
            if not title:
                logger.info("⭐ Generating chart title")
                title = self._generate_chart_title(query, chart_type)
            logger.info(f"⭐ Chart title: '{title}'")
            
            ax.set_title(title, fontsize=14, fontweight='bold')
            
            # Rotate x-axis labels if needed
            if len(df) > 5:
                logger.info("⭐ DECISION: Rotating x-axis labels for better readability")
                ax.tick_params(axis='x', rotation=45)
            
            plt.tight_layout()
            
            # Convert to base64
            logger.info("⭐ Converting chart to base64 image")
            buffer = io.BytesIO()
            plt.savefig(buffer, format='png', dpi=100, bbox_inches='tight')
            buffer.seek(0)
            img_base64 = base64.b64encode(buffer.read()).decode('utf-8')
            plt.close(fig)
            logger.info("⭐ Chart successfully converted to base64")
            
            result = {
                "type": chart_type,
                "data": img_base64,
                "title": title,
                "raw_data": data[:10]  # Include sample data for reference
            }
            logger.info(f"⭐ SUCCESS: Chart generation complete, type: {chart_type}, title: '{title}'")
            logger.info("⭐ EXIT: generate_chart() -> result")
            return result
            
        except Exception as e:
            logger.error(f"⭐ ERROR generating chart: {str(e)}")
            logger.error(f"⭐ FAILED: Chart generation for query: '{query}'")
            logger.info("⭐ EXIT: generate_chart() -> None (error)")
            return None
    
    def _create_bar_chart(self, df: pd.DataFrame, ax: plt.Axes, query: str):
        """Create bar chart optimized for trading data"""
        logger.info(f"⭐ ENTER: _create_bar_chart(df_shape={df.shape}, query='{query[:20]}...')")
        
        numeric_cols = df.select_dtypes(include=['number']).columns.tolist()
        logger.info(f"⭐ Numeric columns found: {numeric_cols}")
        
        if not numeric_cols:
            logger.warning("⭐ DECISION: No numeric columns found for bar chart - returning")
            logger.info("⭐ EXIT: _create_bar_chart()")
            return
        
        # Try to find appropriate columns for trading data
        value_col = None
        label_col = None
        
        # Common trading column patterns
        trading_value_cols = ['price', 'amount', 'volume', 'value', 'quantity']
        trading_label_cols = ['deal', 'tran', 'trade', 'currency', 'instrument']
        
        logger.info("⭐ Looking for trading value columns")
        for col in trading_value_cols:
            if col in df.columns:
                value_col = col
                logger.info(f"⭐ DECISION: Found value column: {value_col}")
                break
        
        if not value_col and numeric_cols:
            value_col = numeric_cols[0]
            logger.info(f"⭐ DECISION: Using first numeric column as value: {value_col}")
        
        logger.info("⭐ Looking for trading label columns")
        for col in trading_label_cols:
            if col in df.columns:
                label_col = col
                logger.info(f"⭐ DECISION: Found label column: {label_col}")
                break
        
        if not label_col:
            # Use index as labels
            labels = [f"Item {i+1}" for i in range(len(df))]
            values = df[value_col] if value_col else df[numeric_cols[0]]
            logger.info("⭐ DECISION: No label column found, using index-based labels")
        else:
            labels = df[label_col].astype(str)
            values = df[value_col] if value_col else df[numeric_cols[0]]
            logger.info(f"⭐ DECISION: Using '{label_col}' as labels and '{value_col}' as values")
        
        logger.info("⭐ Creating bar chart")
        ax.bar(labels, values)
        ax.set_ylabel(value_col.replace('_', ' ').title() if value_col else 'Value')
        ax.set_xlabel(label_col.replace('_', ' ').title() if label_col else 'Category')
        logger.info("⭐ EXIT: _create_bar_chart() - Bar chart created successfully")
    
    def _create_line_chart(self, df: pd.DataFrame, ax: plt.Axes, query: str):
        """Create line chart optimized for trading data"""
        logger.info(f"⭐ ENTER: _create_line_chart(df_shape={df.shape}, query='{query[:20]}...')")
        
        numeric_cols = df.select_dtypes(include=['number']).columns.tolist()
        logger.info(f"⭐ Numeric columns found: {numeric_cols}")
        
        if not numeric_cols:
            logger.warning("⭐ DECISION: No numeric columns found for line chart - returning")
            logger.info("⭐ EXIT: _create_line_chart()")
            return
        
        value_col = numeric_cols[0]
        logger.info(f"⭐ DECISION: Using value column: {value_col}")
        
        date_cols = [col for col in df.columns if any(keyword in col.lower() for keyword in ['date', 'time'])]
        logger.info(f"⭐ Date columns found: {date_cols}")
        
        x_values = None
        
        if date_cols:
            # Try to use date column
            date_col = date_cols[0]
            logger.info(f"⭐ DECISION: Using date column: {date_col}")
            try:
                x_values = pd.to_datetime(df[date_col])
                logger.info("⭐ Successfully converted date column to datetime")
            except Exception as e:
                logger.warning(f"⭐ Could not convert date column: {e}, using index instead")
                x_values = range(len(df))
        else:
            logger.info("⭐ DECISION: No date columns found, using index as x-values")
            x_values = range(len(df))
        
        logger.info("⭐ Creating line chart")
        ax.plot(x_values, df[value_col], marker='o', linewidth=2)
        ax.set_ylabel(value_col.replace('_', ' ').title())
        ax.set_xlabel(date_cols[0].replace('_', ' ').title() if date_cols else 'Index')
        logger.info("⭐ EXIT: _create_line_chart() - Line chart created successfully")
    
    def _create_pie_chart(self, df: pd.DataFrame, ax: plt.Axes, query: str):
        """Create pie chart"""
        logger.info(f"⭐ ENTER: _create_pie_chart(df_shape={df.shape}, query='{query[:20]}...')")
        
        numeric_cols = df.select_dtypes(include=['number']).columns.tolist()
        categorical_cols = df.select_dtypes(exclude=['number']).columns.tolist()
        
        logger.info(f"⭐ Numeric columns: {numeric_cols}")
        logger.info(f"⭐ Categorical columns: {categorical_cols}")
        
        if numeric_cols and categorical_cols:
            value_col = numeric_cols[0]
            label_col = categorical_cols[0]
            logger.info(f"⭐ DECISION: Using value column: {value_col}, label column: {label_col}")
            
            # Take top 8 categories for readability
            df_sorted = df.sort_values(by=value_col, ascending=False).head(8)
            logger.info(f"⭐ DECISION: Using top {len(df_sorted)} categories for pie chart")
            
            logger.info("⭐ Creating pie chart")
            ax.pie(df_sorted[value_col], labels=df_sorted[label_col].astype(str), autopct='%1.1f%%')
            ax.axis('equal')
            logger.info("⭐ EXIT: _create_pie_chart() - Pie chart created successfully")
        else:
            logger.warning("⭐ DECISION: Insufficient data for pie chart - need both numeric and categorical columns")
            logger.info("⭐ EXIT: _create_pie_chart()")
    
    def _create_scatter_chart(self, df: pd.DataFrame, ax: plt.Axes, query: str):
        """Create scatter chart"""
        logger.info(f"⭐ ENTER: _create_scatter_chart(df_shape={df.shape}, query='{query[:20]}...')")
        
        numeric_cols = df.select_dtypes(include=['number']).columns.tolist()
        logger.info(f"⭐ Numeric columns found: {numeric_cols}")
        
        if len(numeric_cols) >= 2:
            x_col, y_col = numeric_cols[0], numeric_cols[1]
            logger.info(f"⭐ DECISION: Using x-column: {x_col}, y-column: {y_col}")
            
            logger.info("⭐ Creating scatter chart")
            ax.scatter(df[x_col], df[y_col], alpha=0.6)
            ax.set_xlabel(x_col.replace('_', ' ').title())
            ax.set_ylabel(y_col.replace('_', ' ').title())
            logger.info("⭐ EXIT: _create_scatter_chart() - Scatter chart created successfully")
        else:
            logger.warning("⭐ DECISION: Insufficient numeric columns for scatter chart (need at least 2)")
            logger.info("⭐ EXIT: _create_scatter_chart()")
    
    def _generate_chart_title(self, query: str, chart_type: str) -> str:
        """Generate appropriate chart title from query"""
        logger.info(f"⭐ ENTER: _generate_chart_title(query='{query[:30]}...', chart_type={chart_type})")
        
        query_lower = query.lower()
        
        if "top" in query_lower or "best" in query_lower:
            title = f"Top Results: {query}"
            logger.info(f"⭐ DECISION: Generated top/best title: '{title}'")
            logger.info(f"⭐ EXIT: _generate_chart_title() -> '{title}'")
            return title
        elif "trend" in query_lower:
            title = f"Trend Analysis: {query}"
            logger.info(f"⭐ DECISION: Generated trend title: '{title}'")
            logger.info(f"⭐ EXIT: _generate_chart_title() -> '{title}'")
            return title
        elif "distribution" in query_lower:
            title = f"Distribution: {query}"
            logger.info(f"⭐ DECISION: Generated distribution title: '{title}'")
            logger.info(f"⭐ EXIT: _generate_chart_title() -> '{title}'")
            return title
        else:
            title = f"Visualization: {query}"
            logger.info(f"⭐ DECISION: Generated default title: '{title}'")
            logger.info(f"⭐ EXIT: _generate_chart_title() -> '{title}'")
            return title

    def _extract_data_from_result(self, result_text: str) -> List[Dict]:
        """Extract structured data from the result text"""
        logger.info(f"⭐ ENTER: _extract_data_from_result(text_length={len(result_text)})")
        
        try:
            lines = result_text.split('\n')
            data = []
            current_row = {}
            logger.info(f"⭐ Processing {len(lines)} lines")
            
            for i, line in enumerate(lines):
                if ':' in line and '|' not in line:  # Simple key:value format
                    parts = line.split(':', 1)
                    if len(parts) == 2:
                        key = parts[0].strip()
                        value = parts[1].strip()
                        if key and value:
                            current_row[key] = value
                            logger.debug(f"⭐ Line {i}: Added key-value pair - {key}: {value}")
                
                # If we have a complete row or end of section
                if not line.strip() and current_row:
                    data.append(current_row)
                    logger.debug(f"⭐ Line {i}: Completed row with {len(current_row)} fields")
                    current_row = {}
            
            if current_row:
                data.append(current_row)
                logger.debug(f"⭐ Added final row with {len(current_row)} fields")
            
            logger.info(f"⭐ SUCCESS: Extracted {len(data)} data rows from result text")
            logger.info(f"⭐ EXIT: _extract_data_from_result() -> {len(data)} rows")
            return data
            
        except Exception as e:
            logger.error(f"⭐ ERROR extracting data from result: {str(e)}")
            logger.info("⭐ EXIT: _extract_data_from_result() -> [] (error)")
            return []

# Singleton instance
logger.info("⭐ Creating VisualizationService singleton instance")
visualization_service = VisualizationService()
logger.info("⭐ VisualizationService singleton created")