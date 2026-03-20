import json
import logging
from app.services.graph_service import GraphService

logger = logging.getLogger(__name__)

class SchemaToolServer:
    """
    Pseudo-MCP Server implementation.
    Exposes graph schema discovery tools to the LLM via OpenAI function calling.
    """
    
    @staticmethod
    def get_tools_definition():
        """Returns the OpenAI functions definitions for schema discovery."""
        return [
            {
                "type": "function",
                "function": {
                    "name": "get_graph_schema",
                    "description": "Get the current graph schema including active node labels and edge types. MUST be called first to understand the DB structure before generating Cypher queries.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "graph_path": {
                                "type": "string",
                                "description": "The name of the graph to get schema for, usually provided in the context."
                            }
                        },
                        "required": ["graph_path"]
                    }
                }
            }
        ]

    @staticmethod
    def execute_tool(tool_call, graph_path):
        """Execute the requested tool call and return the stringified result."""
        tool_name = tool_call.function.name
        
        if tool_name == "get_graph_schema":
            try:
                args = json.loads(tool_call.function.arguments)
                target_graph_path = args.get("graph_path", graph_path)
                schema = GraphService.get_current_schema(target_graph_path)
                return json.dumps({
                    "node_labels": schema.get("node_labels", []),
                    "edge_types": schema.get("edge_types", []),
                    "message": "Use these exact labels and relationship types when constructing Cypher MATCH patterns."
                }, ensure_ascii=False)
            except Exception as e:
                logger.error(f"Error executing get_graph_schema tool: {e}")
                return json.dumps({"error": str(e)})
        
        return json.dumps({"error": f"Unknown tool: {tool_name}"})
