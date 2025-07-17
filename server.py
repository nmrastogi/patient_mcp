from mcp.server.fastmcp import FastMCP
from patient_data import fetch_patient_summary

import logging
import sys

logging.basicConfig(level=logging.INFO, handlers=[logging.StreamHandler(sys.stderr)])
logger = logging.getLogger(__name__)

# Initialize the MCP server
mcp = FastMCP(name="PatientSummaryServer")

@mcp.tool()
def get_patient_summary(patient_id: int) -> dict:
    try:
        logger.info(f"Received patient_id: {patient_id}")
        result = fetch_patient_summary(patient_id)
        if "error" not in result:
            logger.info(f"Successfully processed patient {patient_id}")
        return result
    except Exception as e:
        logger.error(f"Error processing patient {patient_id}: {e}")
        return {"error": str(e), "patient_id": patient_id}

if __name__ == "__main__":
    mcp.run(transport='stdio')
