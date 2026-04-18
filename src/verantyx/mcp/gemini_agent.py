import os
from typing import List, Dict
from google import genai
from google.genai import types
from src.verantyx.mcp.tools import JCrossMCPTools

# Setup Gemini Config from User Rules
GEMINI_API_KEY = "AIzaSyBxkFg8k95WLa2M3XrX0_b8pcbmLhg24Zo"
MODEL_ID = "gemini-2.5-flash"

class GeminiVerantyxAgent:
    """
    Central Nervous System for Verantyx in Agent-Mode.
    Uses LLM as a highly-pure nuance interpreter that defers factual recall 
    to the deterministic `query_jcross_memory` tool.
    """
    def __init__(self, fragments: List[Dict]):
        self.client = genai.Client(api_key=GEMINI_API_KEY)
        self.mcp_tools = JCrossMCPTools(fragments)
        
        # Expose the tool functionally
        self.callable_tools = [self.mcp_tools.query_jcross_memory]

    def solve(self, question: str) -> str:
        """
        Executes a Tool-Calling chat session to solve the user's Long-Context question.
        """
        system_instruction = (
            "You are a master analytical agent operating over a vast JCross Symbolic Engine.\n"
            "You do NOT trust your own memory for specific factual details. You MUST use the `query_jcross_memory` tool.\n"
            "If the tool returns 'No direct topological connection found', you should rephrase your search terms with synonyms and try again.\n"
            "Once you find the absolute truth from JCross, output the exact final answer confidently without conversational filler."
        )

        config = types.GenerateContentConfig(
            system_instruction=system_instruction,
            tools=self.callable_tools,
            temperature=0.0,
            automatic_function_calling=types.AutomaticFunctionCallingConfig(disable=False, maximum_remote_calls=5)
        )

        print(f"🤖 [Gemini Agent] Pondering: '{question}'")
        
        try:
            # Create a chat session with the tools
            chat = self.client.chats.create(model=MODEL_ID, config=config)
            
            # Send message and let GenAI automatically handle the loop (Call -> Tool -> Send Result -> Respond)
            response = chat.send_message(question)
            
            return response.text.replace('**', '').strip()
            
        except Exception as e:
            print(f"❌ [Gemini Agent Exception]: {type(e).__name__} - {e}")
            return "Execution Failed."
