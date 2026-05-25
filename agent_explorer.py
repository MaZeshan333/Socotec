# agent_explorer.py

class SQLExplorerAgent:
    def __init__(self, chat, engine):
        self.chat = chat
        self.engine = engine

    def deep_explore(self, question, snapshot, ambiguous_result):
        print("\n!!! Triggered [Iterative Column Exploration] (Handling low-confidence complex samples) !!!")
        
        # Probe 1: Let the model evaluate where the complexity/difficulty lies
        prompt = f"""Task: "{question}". The previously generated SQL was: {ambiguous_result['sql']}, but confidence in the result is low.
Possible reasons include complex nested columns (like JSONB), ambiguous fields, or lacking data distribution insights.
Based on the current Schema:
{snapshot}
Please write an exploratory SQL query (e.g., LIMIT 5 to check specific column contents, or extract JSONB keys) to help us understand the data distribution. Output ONLY the ```sql block."""
        
        probe_sql = self.chat.get_sql(prompt, temperature=0.2)
        probe_result = self.engine.execute_and_print(probe_sql)
        
        probe_info = ""
        if probe_result["status"] == "success":
            probe_info = f"Exploratory Query Result:\n{probe_result['df'].head(5).to_string()}"
            print(f"[Exploration Feedback] Gained deeper insights into data structures...")
        
        # Probe 2: Combine findings to generate the final high-certainty SQL
        final_prompt = f"""You now possess deep exploratory knowledge of the actual data.
Task: "{question}"
Initial Schema: {snapshot}
Additional Exploratory Insights: {probe_info}

Please combine the information above to write the most accurate final SQL to solve this problem. Wrap it in ```sql."""
        
        final_sql = self.chat.get_sql(final_prompt, temperature=0.1)
        final_result = self.engine.execute_and_print(final_sql)
        
        if final_result["status"] == "success":
            return {"sql": final_sql, "data": final_result["df"]}
        return ambiguous_result # Fall back to the previous surviving version if exploration still fails