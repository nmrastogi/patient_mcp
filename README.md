# Patient Summary MCP Server
- Getting summary of patients 
- Main file: 
    * server.py: main server which has the function which MCP calls. Requests data from patient_data.py 
    * patient_data.py: Processes and gives structured data to MCP. 
    * manifest.json: Defines the structure of Claude to connect. 
- Tools and other filea:
    * tools_schema.json: Expected input for the tool. 
    * mcp_alter.py: Tests the full server/claude workflow manually. 
    * test_server.py: Test individual functions. 
    * start_server.sh: TO specify correct working folders. 
            