# agent_voter.py
import pandas as pd
import hashlib

class SQLVoterAgent:
    def vote(self, candidates):
        if not candidates:
            return {"confidence": "failed", "winner": None}
        if len(candidates) == 1:
            return {"confidence": "high", "winner": candidates[0]}

        print("\n[Majority Voting] Comparing multiple execution results...")
        vote_counts = {}
        result_map = {}
        
        for cand in candidates:
            df = cand["data"]
            fingerprint = self._generate_fingerprint(df)
            
            if fingerprint not in vote_counts:
                vote_counts[fingerprint] = 0
                # Store the first candidate that generated this fingerprint as the representative
                result_map[fingerprint] = cand 
                
            vote_counts[fingerprint] += 1
            
        # Find the highest vote
        sorted_votes = sorted(vote_counts.items(), key=lambda item: item[1], reverse=True)
        top_fingerprint, top_votes = sorted_votes[0]
        
        # Check for ties
        if len(sorted_votes) > 1 and sorted_votes[0][1] == sorted_votes[1][1]:
            print(f"[Majority Voting] Tie detected for highest vote ({top_votes} votes). Confidence: LOW.")
            return {"confidence": "low", "winner": result_map[top_fingerprint]}
        else:
            print(f"[Majority Voting] Consensus reached (Highest: {top_votes} votes). Confidence: HIGH.")
            return {"confidence": "high", "winner": result_map[top_fingerprint]}

    def _generate_fingerprint(self, df):
        """
        Generates a lightweight data fingerprint to prevent memory explosion from full CSV conversions.
        """
        if df.empty:
            return "empty_dataframe"
            
        # 1. Extract basic metadata (rows, columns, column names)
        meta_info = f"shape:{df.shape}_cols:{list(df.columns)}"
        
        # 2. Extract local data sample (at most top 50 and bottom 50 rows)
        if len(df) > 100:
            sample_df = pd.concat([df.head(50), df.tail(50)])
        else:
            sample_df = df
            
        # 3. Convert sample to string
        sample_str = sample_df.to_csv(index=False)
        
        # 4. Compute MD5 hash
        # Whether the data has 10 rows or 1 million rows, it maps to a fixed 32-character string
        hash_obj = hashlib.md5((meta_info + sample_str).encode('utf-8'))
        return hash_obj.hexdigest()