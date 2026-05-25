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
    "host": os.getenv("DB_HOST"), "port": os.getenv("DB_PORT", "5432"),
    "user": os.getenv("DB_USER"), "password": os.getenv("DB_PASS"),
    "database": os.getenv("DB_NAME_NEW")
}

def compare_results(engine, expected_sql, agent_sql):
    """
    Validates correctness through real runtime output comparisons (Execution Match).
    """
    if not agent_sql:
        return False, "Agent failed to generate an executable SQL statement"
        
    res_expected = engine.execute_and_print(expected_sql)
    res_agent = engine.execute_and_print(agent_sql)
    
    if res_expected["status"] != "success":
        return False, f"Ground-truth SQL failed to execute: {res_expected.get('message', '')}"
        
    if res_agent["status"] != "success":
        return False, f"Agent generated SQL failed to execute: {res_agent.get('message', '')}"
        
    df_exp = res_expected["df"]
    df_agt = res_agent["df"]
    
    if df_exp.shape != df_agt.shape:
        return False, f"Dimension mismatch! Expected: {df_exp.shape}, Got: {df_agt.shape}"
        
    try:
        val_exp = df_exp.fillna("").values.tolist()
        val_agt = df_agt.fillna("").values.tolist()
        is_match = (val_exp == val_agt)
        return is_match, ""
    except Exception as e:
        return False, f"Exception occurred during data matching: {str(e)}"

def run_benchmark_aws():
    print(f"\n{'='*50}\nExecuting Agent Benchmark (AWS Bedrock Claude Edition)\n{'='*50}")
    
    chat = MultiModelChat()
    engine = PGSqlEngine(DB_CONFIG)
    generator = SQLGeneratorAgent(chat, engine)
    voter = SQLVoterAgent()
    explorer = SQLExplorerAgent(chat, engine)

    try:
        with open("new_benchmark_sql.json", "r", encoding="utf-8") as f:
            benchmark_data = json.load(f)
    except Exception as e:
        print(f"Failed to read JSON: {str(e)}")
        return
        
    # Intercept top 20 questions for verification
    # benchmark_data = benchmark_data[:20]
        
    results = []
    correct_count = 0
    total_count = len(benchmark_data)
    
    for idx, item in enumerate(benchmark_data):
        question = item.get("question", "")
        expected_sql = item.get("sql", "")
        
        print(f"\n" + "-"*50)
        print(f"▶ [Test Case {idx+1}/{total_count}]")
        print(f"▶ Question: {question}")
        
        agent_sql = None
        is_match = False
        note = ""
        
        try:
            snapshot = get_compressed_snapshot(DB_CONFIG, chat, question)
            # AWS Claude 4.5 offers premium accuracy; k=1 balances speed. Increase if needed.
            candidates = generator.generate_candidates(question, snapshot, k=1)
            vote_result = voter.vote(candidates)
            final_result = vote_result["winner"]
            agent_sql = final_result["sql"] if final_result else None
            
            is_match, note = compare_results(engine, expected_sql, agent_sql)
            
        except Exception as e:
            note = f"Agent Exception: {str(e)}"
            is_match = False
            
        if is_match:
            correct_count += 1
            print(f"✅ Result: [PASS]")
        else:
            print(f"❌ Result: [FAIL] | Reason: {note}")
            
        results.append({
            "ID": idx + 1,
            "Question": question,
            "Expected SQL": expected_sql,
            "Agent SQL": agent_sql if agent_sql else "N/A",
            "Is Match": is_match,
            "Error Note": note
        })

    accuracy = correct_count / total_count if total_count > 0 else 0
    print(f"\n{'='*50}")
    print(f" 🎉 AWS Benchmark Performance Report (Top {total_count} Questions)")
    print(f"{'='*50}")
    print(f"Matched Queries: {correct_count} | Accuracy: {accuracy:.2%}")
    
    output_df = pd.DataFrame(results)
    output_file = "AWS_Benchmark_Report_Top20.csv"
    output_df.to_csv(output_file, index=False, encoding="utf-8-sig")
    print(f"Detailed evaluation file saved as: {output_file}")

if __name__ == "__main__":
    run_benchmark_aws()