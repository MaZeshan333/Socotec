# run.py
import os
import pandas as pd
from dotenv import load_dotenv
from chat_local import MultiModelChat
from sql_engine import PGSqlEngine
from snapshot_manager import get_compressed_snapshot
from agent_generator import SQLGeneratorAgent
from agent_voter import SQLVoterAgent
from agent_explorer import SQLExplorerAgent

load_dotenv()
DB_CONFIG = {
    "host": os.getenv("DB_HOST"), "port": os.getenv("DB_PORT", "5432"),
    "user": os.getenv("DB_USER"), "password": os.getenv("DB_PASS"),
    "database": os.getenv("DB_NAME_NEW")
}

def main():
    print(f"\n{'='*50}\nAdvanced Multi-Agent SQL-Agent Pipeline Online\n{'='*50}")

    chat = MultiModelChat()
    engine = PGSqlEngine(DB_CONFIG)
    generator = SQLGeneratorAgent(chat, engine)
    voter = SQLVoterAgent()
    explorer = SQLExplorerAgent(chat, engine)
    
    question = "Query the 10 most recently collected raw measurements (raw_measurements), displaying their values (value) and timestamps (timestamp), sorted in reverse chronological order."
    print(f"\n[Target Mission]: {question}")

    # Phase 1: Context Truncation / Schema Linking
    snapshot = get_compressed_snapshot(DB_CONFIG, chat, question)

    # Phase 2: Multi-path generation & self-correction loop
    candidates = generator.generate_candidates(question, snapshot, k=3)

    # Phase 3: Consensus Verification / Voting
    vote_result = voter.vote(candidates)
    final_result = None

    # Phase 4: Low-confidence runtime rollback & exploratory execution
    if vote_result["confidence"] == "low" and vote_result["winner"] is not None:
        final_result = explorer.deep_explore(question, snapshot, vote_result["winner"])
    else:
        final_result = vote_result["winner"]

    # Phase 5: Present final outcome
    if final_result:
        pd.set_option('display.max_colwidth', None)
        pd.set_option('display.expand_frame_repr', False)
        
        print("\n" + "#" * 45)
        print(" Mission Accomplished Successfully! ".center(45, '#'))
        print("#" * 45)
        print(f"\n【Final Selected SQL】:\n{final_result['sql']}")
        print(f"\n【Retrieved Output Dataset】:\n{final_result['data'].to_string(index=False)}")
    else:
        print("\n[System Failure] All generation and alignment correction loops failed.")

if __name__ == "__main__":
    main()