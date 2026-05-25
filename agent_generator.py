# agent_generator.py
import concurrent.futures

class SQLGeneratorAgent:
    def __init__(self, chat, engine):
        self.chat = chat
        self.engine = engine

    def generate_candidates(self, question, snapshot, k=3):
        print(f"\n{'='*20} Starting Concurrent Generation of {k} Candidate Queries {'='*20}")
        candidates = []
        
        def _generate_task(idx):
            print(f">>> Branch {idx+1} starting work...")
            prompt = f"""You are a top-tier PostgreSQL database expert.
Database Schema:
{snapshot}

Task: {question}

[Absolute Mandatory Rules]:
1. You can ONLY generate executable SELECT queries! It is strictly forbidden to generate any INSERT/UPDATE/DELETE/DROP statements that modify or destroy data.
2. Never fabricate non-existent tables or columns. You must strictly perform JOINs based on the provided Schema (e.g., via site_id, gateway_id, project_id).
3. If the query involves JSONB fields, you must use standard PostgreSQL operators (e.g., `->>` to extract text, `->` to extract objects).
4. To prevent returning excessively large amounts of data, if a specific count is not explicitly defined, please append a default LIMIT 100 at the end.
5. Output ONLY the final SQL wrapped inside a single ```sql block, without any explanation."""
            
            # Use a slightly higher temperature to achieve diversity
            sql = self.chat.get_sql(prompt, temperature=0.7)
            # Self-optimization loop (execution feedback)
            return self._self_correct_loop(sql, snapshot)

        # Use a thread pool to execute k generation tasks concurrently
        with concurrent.futures.ThreadPoolExecutor(max_workers=k) as executor:
            results = executor.map(_generate_task, range(k))
            for res in results:
                if res:
                    candidates.append(res)
                
        return candidates

    def _self_correct_loop(self, initial_sql, snapshot, max_retry=3):
        current_sql = initial_sql
        # List to track the historical attempts and prevent the model from getting stuck in a loop
        error_history = [] 

        for i in range(max_retry):
            result = self.engine.execute_and_print(current_sql)
            if result["status"] == "success":
                return {"sql": current_sql, "data": result["df"]}
            
            error_msg = result['message']
            # Extract a brief error message for clean terminal logging
            short_error = error_msg.split('\n')[0][:100] 
            print(f"  [Self-Correction] Attempt {i+1} to fix SQL... Error: {short_error}")
            
            # Store current failure into history
            error_history.append(f"[Attempted SQL]:\n{current_sql}\n[Resulting Error]:\n{error_msg}")
            history_context = "\n---\n".join(error_history)
            
            prompt = f"""You are a senior PostgreSQL troubleshooting expert. You need to fix a query error.
Database Schema:
{snapshot}

[Your Past Failed Attempts and Error Records] (Learn from this, DO NOT generate the same incorrect SQL again!):
{history_context}

[Troubleshooting Mandatory Requirements]:
1. Analyze the failure history above and find the root cause of the error (Table misspelling? Missing JOIN? Type mismatch?).
2. If the error involves JSONB fields, check if you used the correct operators (->> for text, -> for object), and verify if explicit type casting is needed (e.g., ::numeric or ::text).
3. If the error is "column does not exist", carefully check the actual column names in the schema. Do not fabricate them.
4. You must output a BRAND NEW, corrected SQL statement to resolve this issue.
5. Output ONLY the final SQL wrapped inside a single ```sql block, without any explanation."""
            
            # Slightly elevated temperature (0.3) to encourage creative troubleshooting
            current_sql = self.chat.get_sql(prompt, temperature=0.3)
            
        return None