from mcp.server.fastmcp import FastMCP
from patient_data import (
    fetch_patient_summary, 
    detect_anomalous_glucose_events,
    find_last_hypoglycemic_event,
    analyze_glucose_patterns,
    get_available_patients
)

import logging
import sys

logging.basicConfig(level=logging.INFO, handlers=[logging.StreamHandler(sys.stderr)])
logger = logging.getLogger(__name__)

# Initialize the MCP server
mcp = FastMCP(name="DiabetesMonitoringServer")

@mcp.tool()
def get_patient_summary(patient_id: str, start_date: str = None, end_date: str = None) -> dict:
    """
    Retrieve patient summary with optional date filtering.
    
    Args:
        patient_id (str): Patient identifier (can be string or numeric)
        start_date (str): Optional start date (YYYY-MM-DD format)
        end_date (str): Optional end date (YYYY-MM-DD format)
    """
    try:
        logger.info(f"Received patient_id: {patient_id}, dates: {start_date} to {end_date}")
        result = fetch_patient_summary(patient_id, start_date, end_date)
        return result
    except Exception as e:
        logger.error(f"Error processing patient {patient_id}: {e}")
        return {"error": str(e), "patient_id": patient_id}

@mcp.tool()
def get_anomalous_events(patient_id: str, days_back: int = 30, threshold_factor: float = 2.5) -> dict:
    """
    Detect anomalous glucose events based on statistical analysis.
    
    Args:
        patient_id (str): Patient identifier
        days_back (int): Number of days to analyze (default: 30)
        threshold_factor (float): Standard deviation multiplier for anomaly detection (default: 2.5)
    """
    try:
        logger.info(f"Analyzing anomalies for patient {patient_id}, last {days_back} days")
        result = detect_anomalous_glucose_events(patient_id, days_back, threshold_factor)
        return result
    except Exception as e:
        logger.error(f"Error detecting anomalies for patient {patient_id}: {e}")
        return {"error": str(e), "patient_id": patient_id}

@mcp.tool()
def get_last_hypo_event(patient_id: str, glucose_threshold: float = 70) -> dict:
    """
    Find the most recent hypoglycemic event and recovery information.
    
    Args:
        patient_id (str): Patient identifier
        glucose_threshold (float): Glucose level considered hypoglycemic (default: 70 mg/dL)
    """
    try:
        logger.info(f"Finding last hypo event for patient {patient_id}, threshold: {glucose_threshold}")
        result = find_last_hypoglycemic_event(patient_id, glucose_threshold)
        return result
    except Exception as e:
        logger.error(f"Error finding hypo event for patient {patient_id}: {e}")
        return {"error": str(e), "patient_id": patient_id}

@mcp.tool()
def get_glucose_patterns(patient_id: str, analysis_days: int = 14) -> dict:
    """
    Analyze daily glucose patterns to identify when sugar typically rises and falls.
    
    Args:
        patient_id (str): Patient identifier
        analysis_days (int): Number of days to analyze (default: 14)
    """
    try:
        logger.info(f"Analyzing glucose patterns for patient {patient_id}, last {analysis_days} days")
        result = analyze_glucose_patterns(patient_id, analysis_days)
        return result
    except Exception as e:
        logger.error(f"Error analyzing patterns for patient {patient_id}: {e}")
        return {"error": str(e), "patient_id": patient_id}

@mcp.tool()
def list_available_patients() -> dict:
    """
    Get a list of all available patient/device IDs in the dataset.
    """
    try:
        logger.info("Getting list of available patients")
        patients = get_available_patients()
        return {
            "available_patients": patients,
            "total_count": len(patients),
            "message": f"Found {len(patients)} patients/devices in the dataset"
        }
    except Exception as e:
        logger.error(f"Error getting patient list: {e}")
        return {"error": str(e)}

@mcp.tool()
def get_comprehensive_diabetes_report(patient_id: str, analysis_days: int = 30) -> dict:
    """
    Generate a comprehensive diabetes management report including all key metrics.
    
    Args:
        patient_id (str): Patient identifier
        analysis_days (int): Number of days to analyze (default: 30)
    """
    try:
        logger.info(f"Generating comprehensive report for patient {patient_id}")
        
        # Gather all analyses
        summary = fetch_patient_summary(patient_id)
        anomalies = detect_anomalous_glucose_events(patient_id, analysis_days)
        last_hypo = find_last_hypoglycemic_event(patient_id)
        patterns = analyze_glucose_patterns(patient_id, analysis_days)
        
        # Compile comprehensive report
        report = {
            "patient_id": patient_id,
            "report_generated": "2025-07-22",
            "analysis_period": f"Last {analysis_days} days",
            "summary": {
                "total_readings": summary.get("total_readings", 0),
                "data_quality": "Good" if summary.get("total_readings", 0) > 100 else "Limited",
                "data_sources": summary.get("data_sources", {})
            },
            "glucose_control": {
                "time_in_ranges": patterns.get("time_in_ranges", {}),
                "glucose_variability": patterns.get("glucose_variability", {}),
                "peak_time": patterns.get("peak_glucose_time", "Unknown"),
                "lowest_time": patterns.get("lowest_glucose_time", "Unknown")
            },
            "safety_events": {
                "last_hypoglycemic_event": last_hypo.get("last_hypo_event"),
                "total_anomalies": anomalies.get("total_anomalies", 0),
                "severe_anomalies": len([a for a in anomalies.get("anomalous_events", []) if a.get("severity") == "severe"])
            },
            "patterns": {
                "dawn_phenomenon": patterns.get("dawn_phenomenon", {}),
                "hourly_averages": patterns.get("hourly_patterns", {})
            },
            "recommendations": generate_recommendations(patterns, anomalies, last_hypo)
        }
        
        return report
        
    except Exception as e:
        logger.error(f"Error generating comprehensive report for patient {patient_id}: {e}")
        return {"error": str(e), "patient_id": patient_id}

def generate_recommendations(patterns: dict, anomalies: dict, hypo_data: dict) -> list:
    """Generate actionable recommendations based on analysis."""
    recommendations = []
    
    # Time in range recommendations
    time_in_range = patterns.get("time_in_ranges", {})
    target_percentage = float(time_in_range.get("target_70_to_180", "0%").rstrip("%"))
    
    if target_percentage < 70:
        recommendations.append({
            "category": "Glucose Control",
            "priority": "High",
            "recommendation": f"Time in range is {target_percentage}%. Target is >70%. Consider discussing treatment adjustments with healthcare provider."
        })
    
    # Dawn phenomenon
    dawn_phenomenon = patterns.get("dawn_phenomenon", {})
    if dawn_phenomenon.get("detected"):
        recommendations.append({
            "category": "Dawn Phenomenon",
            "priority": "Medium", 
            "recommendation": f"Dawn phenomenon detected with {dawn_phenomenon.get('rise_amount', 0)} mg/dL rise. Consider discussing morning insulin timing with healthcare provider."
        })
    
    # Hypoglycemia
    last_hypo = hypo_data.get("last_hypo_event")
    if last_hypo and last_hypo.get("days_ago", 999) < 7:
        recommendations.append({
            "category": "Hypoglycemia Prevention",
            "priority": "High",
            "recommendation": f"Recent hypoglycemic event {last_hypo.get('days_ago')} days ago. Review patterns and consider glucose monitoring frequency."
        })
    
    # Anomalies
    total_anomalies = anomalies.get("total_anomalies", 0)
    if total_anomalies > 5:
        recommendations.append({
            "category": "Glucose Stability",
            "priority": "Medium",
            "recommendation": f"{total_anomalies} anomalous glucose events detected. Consider reviewing food, exercise, and medication timing patterns."
        })
    
    # Variability
    variability = patterns.get("glucose_variability", {})
    cv = variability.get("coefficient_of_variation", 0)
    if cv > 36:  # High glucose variability
        recommendations.append({
            "category": "Glucose Variability",
            "priority": "Medium",
            "recommendation": f"High glucose variability detected (CV: {cv}%). Focus on consistent meal timing and carbohydrate counting."
        })
    
    return recommendations

if __name__ == "__main__":
    mcp.run(transport='stdio')