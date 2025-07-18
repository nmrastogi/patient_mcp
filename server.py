from mcp.server.fastmcp import FastMCP
from patient_data import fetch_patient_summary

import logging
import sys

logging.basicConfig(level=logging.INFO, handlers=[logging.StreamHandler(sys.stderr)])
logger = logging.getLogger(__name__)

# Initialize the MCP server
mcp = FastMCP(name="PatientSummaryServer")

@mcp.tool()
def get_patient_summary(patient_id: int, start_date: str = None, end_date: str = None) -> dict:
    """
    Retrieve patient summary with optional date filtering.
    
    Args:
        patient_id (int): Patient identifier 
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

if __name__ == "__main__":
    mcp.run(transport='stdio')
