# chat_local.py
from openai import OpenAI
import re

class MultiModelChat:
    def __init__(self):
        self.client = OpenAI(base_url='http://localhost:11434/v1', api_key='ollama')
        # Dual-model setup
        self.coder_model = "deepseek-r1:8b" 
        self.judge_model = "llama3.1"      

    def ask(self, prompt, role="coder", temperature=0.3):
        model = self.coder_model if role == "coder" else self.judge_model
        print(f"\n[AI Request] Invoking {model}...")
        response = self.client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": prompt}],
            temperature=temperature
        )
        return response.choices[0].message.content

    def get_sql(self, prompt, temperature=0.3):
        full_content = self.ask(prompt, role="coder", temperature=temperature)
        sql_match = re.search(r"```sql\n(.*?)\n```", full_content, re.DOTALL | re.IGNORECASE)
        return sql_match.group(1).strip() if sql_match else full_content.strip()