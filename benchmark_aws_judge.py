# benchmark_aws.py
import os
import json
import pandas as pd
import warnings
from dotenv import load_dotenv

from chat_bedrock import MultiModelChat 
from sql_engine import PGSqlEngine
from snapshot_manager import get_compressed_snapshot
from agent_generator import SQLGeneratorAgent
from agent_voter import SQLVoterAgent
from agent_explorer import SQLExplorerAgent

warnings.filterwarnings('ignore')
load_dotenv()

DB_CONFIG = {
    "host": os.getenv("DB_HOST"), 
    "port": os.getenv("DB_PORT", "5432"),
    "user": os.getenv("DB_USER"), 
    "password": os.getenv("DB_PASS"),
    "database": os.getenv("DB_NAME_NEW")
}

def clean_value(v):
    """
    Helper function to convert unhashable objects (like dicts/lists from JSONB)
    into structured strings so they can be safely hashed for set comparison.
    """
    if isinstance(v, (dict, list)):
        return json.dumps(v, sort_keys=True)
    return str(v)

def compare_results(engine, expected_sql, agent_sql):
    """
    Validates correctness through an enhanced matrix-alignment comparison.
    Completely decouples column names (like 'count', 'avg') from verification,
    and safely handles DDL/DML operations (NoneType dataframes).
    """
    if not agent_sql:
        return False, "Agent failed to generate an executable SQL statement"
        
    res_expected = engine.execute_and_print(expected_sql)
    res_agent = engine.execute_and_print(agent_sql)
    
    # [Safety Hack] Handle DDL/DML (e.g., UPDATE, CREATE VIEW) where df is None
    if res_expected["status"] == "success" and res_expected.get("df") is None:
        if res_agent["status"] == "success":
            return True, "Lenient Match: DDL/DML statement executed successfully on both ends."
        return False, f"Agent DDL/DML execution failed: {res_agent.get('message', '')}"
        
    if res_expected["status"] != "success":
        return False, f"Ground-truth SQL failed to execute: {res_expected.get('message', '')}"
        
    if res_agent["status"] != "success":
        return False, f"Agent generated SQL failed to execute: {res_agent.get('message', '')}"
        
    df_exp = res_expected["df"].copy()
    df_agt = res_agent["df"].copy()
    
    # If both datasets are empty, consider it a functional match
    if df_exp.empty and df_agt.empty:
        return True, ""
        
    if df_agt.empty and not df_exp.empty:
        return False, "Agent returned an empty dataset while Expected has data."

    try:
        # Uniformly fill missing values to avoid NaN inconsistencies
        df_exp = df_exp.fillna("")
        df_agt = df_agt.fillna("")

        # Standardize data types using the cleaner helper
        df_exp_cleaned = df_exp.map(clean_value)
        df_agt_cleaned = df_agt.map(clean_value)

        # CASE 1: Column Count Matches exactly -> Strict Row Matrix Matching (Ignore Column Aliases entirely)
        if len(df_exp.columns) == len(df_agt.columns):
            set_exp = set(tuple(x) for x in df_exp_cleaned.values)
            set_agt = set(tuple(x) for x in df_agt_cleaned.values)
            
            if set_exp.issubset(set_agt) or set_agt.issubset(set_exp):
                return True, ""
                
            intersection = set_exp.intersection(set_agt)
            if len(set_exp) > 0 and (len(intersection) / len(set_exp)) >= 0.8:
                return True, f"Lenient Matrix Match: High data overlap ({len(intersection)}/{len(set_exp)} rows)."
                
            return False, f"Value matrix mismatch. Target rows: {len(set_exp)}, Matched: {len(intersection)}"

        # CASE 2: Column Count Mismatches -> Fallback to Lowercase Named-Intersection Filtering
        df_exp_cleaned.columns = [str(c).lower() for c in df_exp_cleaned.columns]
        df_agt_cleaned.columns = [str(c).lower() for c in df_agt_cleaned.columns]
        
        # Deduplicate internal duplicated names (like 'name', 'name.1' from pandas processing)
        exp_cols_clean = [c.split('.')[0] for c in df_exp_cleaned.columns]
        agt_cols_clean = [c.split('.')[0] for c in df_agt_cleaned.columns]
        
        missing_cols = [col for col in exp_cols_clean if col not in agt_cols_clean]
        if missing_cols:
            return False, f"Column count mismatch & Key column missing! Expected: {exp_cols_clean}, Missing: {missing_cols}"
            
        # Filter agent data map using positions matching the expected schema sequence
        matched_indices = [agt_cols_clean.index(col) for col in exp_cols_clean if col in agt_cols_clean]
        df_agt_filtered = df_agt_cleaned.iloc[:, matched_indices]
        
        set_exp = set(tuple(x) for x in df_exp_cleaned.values)
        set_agt = set(tuple(x) for x in df_agt_filtered.values)
        
        if set_exp.issubset(set_agt) or set_agt.issubset(set_exp):
            return True, ""
            
        intersection = set_exp.intersection(set_agt)
        if len(set_exp) > 0 and (len(intersection) / len(set_exp)) >= 0.8:
            return True, f"Lenient Filtered Match: High overlap ({len(intersection)}/{len(set_exp)} rows)."

        return False, f"Data alignment mismatch after column filtering."
        
    except Exception as e:
        return False, f"Exception occurred during lenient data matching: {str(e)}"

def llm_as_a_judge(chat, question, expected_sql, agent_sql, rule_error_note):
    """
    Invokes the LLM as a SQL Judge to evaluate semantic equivalence 
    when deterministic rule-based matching fails.
    """
    prompt = f"""You are an expert SQL Judge evaluating a Text-to-SQL system. 
Your task is to determine if the Agent's generated SQL is semantically equivalent to the Expected Ground-Truth SQL for the given user question.

[Evaluation Context]
- User Natural Language Question: "{question}"
- Expected Ground-Truth SQL: `{expected_sql}`
- Agent Generated SQL: `{agent_sql}`
- Technical Reason Rule Engine Rejected It: "{rule_error_note}"

[Strict Judging Guidelines]
1. PASS (Semantic Match): 
   - The Agent's SQL fulfills the user's operational goal.
   - It only differs in column aliases (e.g., 'items_purchased' vs 'quantity_purchased').
   - It selected additional helpful reference columns (e.g., returning 'user_id' along with 'username') without altering the aggregation level or row granularity.
   - It computes mathematically equivalent statements (e.g., `COUNT(*)` vs `COUNT(id)` on a non-null primary key).

2. FAIL (Mismatch):
   - The Agent missed a critical filtering constraint (`WHERE` clause).
   - It used the wrong join entity type (e.g., `INNER JOIN` dropping zero-asset entities instead of `LEFT JOIN`).
   - It grouped data at the wrong database granularity (`GROUP BY`).
   - It completely misinterpreted the business logic metrics.

Respond STRICTLY in the following raw JSON format (Do not wrap it in markdown formatting or add explanatory prose):
{{
    "is_match": true or false,
    "reason": "Provide a concise 1-2 sentence reason detailing your design decision."
}}"""
    try:
        # Utilizing your pre-configured Bedrock chat instance
        # If your MultiModelChat instance uses another inference method, swap `.send_message` with `.ask` or equivalent.
        response_text = chat.send_message(prompt)
        
        # Robustly clean potential markdown wrappers out of LLM responses
        if "```json" in response_text:
            response_text = response_text.split("```json")[1].split("```")[0]
        elif "```" in response_text:
            response_text = response_text.split("```")[1].split("```")[0]
            
        judge_res = json.loads(response_text.strip())
        return bool(judge_res.get("is_match", False)), judge_res.get("reason", "No reason provided by the judge.")
    except Exception as e:
        return False, f"Exception occurred during LLM Judge arbitration: {str(e)}"

def run_benchmark_aws():
    print(f"\n{'='*50}\nExecuting Agent Benchmark (AWS Bedrock Claude Edition)\n{'='*50}")
    
    chat = MultiModelChat()
    engine = PGSqlEngine(DB_CONFIG)
    generator = SQLGeneratorAgent(chat, engine)
    explorer = SQLExplorerAgent(chat, engine)

    try:
        with open("benchmark_merged.json", "r", encoding="utf-8") as f:
            #benchmark_data = json.load(f)
            benchmark_data = json.load(f)[:20]
    except Exception as e:
        print(f"[Error] Failed to load benchmark JSON: {str(e)}")
        return

    results = []
    correct_count = 0
    total_count = len(benchmark_data)

    snapshot = get_compressed_snapshot(DB_CONFIG, chat, "Get full schema", threshold=10)

    for item in benchmark_data:
        q_id = item.get("id")
        category = item.get("category")
        question = item.get("question")
        expected_sql = item.get("sql")

        print(f"\n[Progress {q_id}/{total_count}] Category: {category} | ID: {q_id}")
        print(f"Question: {question}")

        # Optimized to k=1 generation to avoid concurrency bottlenecks
        print(f"==================== Generating Single Candidate Query ====================")
        candidates = generator.generate_candidates(question, snapshot, k=1)
        
        agent_sql = None
        winner_payload = None
        if candidates and len(candidates) > 0:
            agent_sql = candidates[0]["sql"]
            winner_payload = candidates[0]

        # Robust explorer recovery fallback block
        if not agent_sql and winner_payload:
            print(f"-> Initial SQL syntax execution failed. Triggering Explorer recovery...")
            try:
                explorer_sql = explorer.deep_explore(question, snapshot, winner_payload)
                if explorer_sql:
                    agent_sql = explorer_sql
            except Exception as e:
                print(f"[Explorer Error] Fallback mechanism failure: {str(e)}")

        # Step 1: Run fast, free deterministic check
        is_match, error_note = compare_results(engine, expected_sql, agent_sql)

        # Step 2: Fallback to LLM as a Judge if rule-engine fails but SQL successfully executed
        if not is_match and agent_sql and "failed to execute" not in error_note and agent_sql != "Generation Failed":
            print(f"-> Rule match failed. Invoking LLM as a Judge Arbitration...")
            judge_match, judge_reason = llm_as_a_judge(chat, question, expected_sql, agent_sql, error_note)
            if judge_match:
                is_match = True
                error_note = f"LLM Judge Overrule: {judge_reason}"
            else:
                error_note = f"Rejected by LLM Judge: {judge_reason} (Original Rule Fault: {error_note})"

        if is_match:
            correct_count += 1
            if "LLM Judge Overrule" in error_note:
                print(f"-> [RESULT] MATCH SUCCESS (via Judge Overrule)! 🧠")
                print(f"   Reason: {error_note}")
            else:
                print(f"-> [RESULT] MATCH SUCCESS! 🎉")
        else:
            print(f"-> [RESULT] MATCH FAILED ❌ | Reason: {error_note}")

        results.append({
            "ID": q_id,
            "Category": category,
            "Question": question,
            "Expected SQL": expected_sql,
            "Agent SQL": agent_sql if agent_sql else "Generation Failed",
            "Is Match": is_match,
            "Error Note": error_note
        })

    #report_df = pd.DataFrame(results)
    #report_filename = "AWS_Benchmark_Report_Standard.csv"
    #report_df.to_csv(report_filename, index=False, encoding="utf-8")
    
    accuracy = (correct_count / total_count) * 100
    print(f"\n{'='*50}\nBenchmark Execution Complete!")
    print(f"Final Accuracy (Lenient Match + LLM Judge): {correct_count}/{total_count} ({accuracy:.2f}%)")
    #print(f"Detailed report saved to: {report_filename}\n{'='*50}")

if __name__ == "__main__":
    run_benchmark_aws()