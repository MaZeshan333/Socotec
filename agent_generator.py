# agent_generator.py
import concurrent.futures

class SQLGeneratorAgent:
    def __init__(self, chat, engine):
        self.chat = chat
        self.engine = engine

    def generate_candidates(self, question, snapshot, k=1):
        print(f"\n{'='*20} Starting Generation of {k} Candidate Queries {'='*20}")
        candidates = []
        
        def _generate_task(idx):
            print(f">>> Branch {idx+1} starting work...")
            prompt = f"""You are a top-tier PostgreSQL database expert.
Database Schema:
{snapshot}

Task: {question}

[Absolute Mandatory Rules]:
1. You can generate executable SELECT queries. If the task explicitly asks to update parameters or generate a global status summary layout, you are permitted to output standard UPDATE or CREATE VIEW statements matching the exact command intent.
2. Alias & Aggregates Constraints: When generating aggregate computations (like COUNT(*), AVG(), SUM()), do NOT assign fancy descriptive custom aliases (e.g., avoid 'AS total_count'). Let PostgreSQL apply its default column naming behavior ('count', 'avg'), or mirror standard implicit outputs to pass rigid evaluation schemas.
3. Handle Duplicate Join Columns Literally: If you are joining multiple relations containing identical attribute names that the user requests (e.g., project name, site name), do NOT override them with descriptive aliases (like 'AS project_name'). Output them literally as `table_alias.name` to match row matrices.
4. Strict Relational Entity Tracking: Carefully look at the entities specified in the text. Ensure you extract every required filtering layer or output column requested by the prompt without dropping contextual key identifiers or names.
5. If the query involves JSONB fields, you must use standard PostgreSQL operators (e.g., `->>` to extract text, `->` to extract objects).
6. Output ONLY the final SQL wrapped inside a single ```sql block, without any explanation."""
            
            sql = self.chat.get_sql(prompt, temperature=0.2 if k==1 else 0.7)
            print(f"[Branch {idx+1}] SQL string returned from model. Testing execution stability...")
            res = self.engine.execute_and_print(sql)
            
            return {"sql": sql, "status": res["status"], "data": res.get("df"), "message": res.get("message")}

        # Adaptively run sequentially or in concurrent threads depending on k parameters
        if k == 1:
            try:
                task_result = _generate_task(0)
                if task_result["status"] == "success":
                    candidates.append(task_result)
                else:
                    print(f"[Generation Warning] Initial syntax check failed: {task_result['message']}")
                    candidates.append(task_result) # pass down payload to allow explorer recovery
            except Exception as e:
                print(f"[Fatal Branch Error] Run collapsed: {str(e)}")
        else:
            with concurrent.futures.ThreadPoolExecutor(max_workers=k) as executor:
                futures = {executor.submit(_generate_task, i): i for i in range(k)}
                for future in concurrent.futures.as_completed(futures):
                    try:
                        res = future.result()
                        if res["status"] == "success":
                            candidates.append(res)
                    except Exception as e:
                        print(f"[Thread Error] Branch processing failed: {str(e)}")
                        
        return candidates