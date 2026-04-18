import ollama
from typing import List, Dict
from src.verantyx.mcp.tools import JCrossMCPTools

# Note: gemma4:e2b might not be explicitly optimized for Tool Calling JSON schema.
# But we adhere exactly to the official Ollama Tool format. If the model hallucinates
# the JSON, upgrading to a 'Coder' model or `llama-3.1` is the permanent fix.
MODEL_ID = "gemma4:e2b"

class OllamaVerantyxAgent:
    """
    Completely Local Ecosystem.
    Wraps the JCross Spatial memory to be dynamically queried by `gemma4:e2b`.
    Zero cloud connection or API usage. Highest security posture. 
    """
    def __init__(self, fragments: List[Dict]):
        self.mcp_tools = JCrossMCPTools(fragments)
        self.available_functions = {
            'query_jcross_memory': self.mcp_tools.query_jcross_memory
        }

    def solve(self, question: str) -> str:
        """
        Runs the Ollama Chat interaction with the explicit JCross Tool Schema.
        """
        system_instruction = (
            "You are an analytical agent connected to the JCross Symbolic Engine.\n"
            "You do not possess factual memory. You MUST ALWAYS use the `query_jcross_memory` tool to find truth.\n"
            "Only answer after you receive the tool's result."
        )

        messages = [
            {'role': 'system', 'content': system_instruction},
            {'role': 'user', 'content': question}
        ]

        print(f"🤖 [Local Agent] Pondering: '{question}'")
        
        try:
            # 1. First Pass: The Model decides if it needs a tool
            response = ollama.chat(
                model=MODEL_ID,
                messages=messages,
                tools=[
                    {
                        'type': 'function',
                        'function': {
                            'name': 'query_jcross_memory',
                            'description': 'Queries the deterministic JCross Spatial Engine for absolute facts.',
                            'parameters': {
                                'type': 'object',
                                'properties': {
                                    'search_text': {
                                        'type': 'string',
                                        'description': 'The precise noun or concept to search for in memory. Ex: "Admon shift" or "John purchase".'
                                    }
                                },
                                'required': ['search_text']
                            }
                        }
                    }
                ],
                options={"temperature": 0.0} # Maximum strictness for JSON tool structure
            )

            messages.append(response['message'])
            
            # 2. Check if the model attempted a tool call
            if not response['message'].get('tool_calls'):
                return response['message']['content'].strip()

            print("  [Local Agent] 🛠️ Tool Action Initiated by Model!")
            
            # 3. Execute the Python Native Engine Tools requested by the Model
            for tool in response['message']['tool_calls']:
                function_to_call = self.available_functions.get(tool['function']['name'])
                if function_to_call:
                    args = tool['function']['arguments']
                    print(f"  [Local Agent] Executing Tool: {tool['function']['name']} with args {args}")
                    tool_result = function_to_call(**args)
                    print(f"  [Local Agent] Tool Result: {tool_result}")
                    
                    # Push the result back into the chat history for the final synthesis
                    messages.append(
                        {
                            'role': 'tool', 
                            'content': str(tool_result),
                            'name': tool['function']['name']
                        }
                    )
            
            # 4. Final Pass: The model synthesizes the answer reading the tool content
            final_response = ollama.chat(model=MODEL_ID, messages=messages, options={"temperature": 0.0})
            return final_response['message']['content'].strip()

        except Exception as e:
            print(f"❌ [Local Agent Exception]: {type(e).__name__} - {e}")
            return "Execution Failed."
