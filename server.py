from mcp.server.fastmcp import FastMCP
from patient_data import fetch_patient_summary

# Initialize the MCP server
mcp = FastMCP(name="PatientSummaryServer")

@mcp.tool()
def get_patient_summary(patient_id: int) -> dict:
    print(f"Received patient_id: {patient_id}")
    return fetch_patient_summary(patient_id)

if __name__ == "__main__":
    mcp.run(transport='stdio')
