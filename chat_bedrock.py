# chat_bedrock.py
import re
from langchain_aws import ChatBedrock

class MultiModelChat:
    def __init__(self):
        # Using Claude 3.5/4.5 Sonnet on AWS Bedrock
        self.llm = ChatBedrock(
            model_id="us.anthropic.claude-sonnet-4-5-20250929-v1:0",
            region_name="us-west-2" 
        )

    def ask(self, prompt, role="coder", temperature=0.3):
        """
        Send a request to Claude. 
        The role parameter is kept for backward compatibility with components like snapshot_manager.
        """
        print(f"\n[AWS Bedrock Request] Invoking Claude (Role: {role})...")
        
        # Invoke automatically processes AWS authentication and message transformation
        response = self.llm.invoke(prompt, config={"temperature": temperature})
        return response.content

    def get_sql(self, prompt, temperature=0.3):
        """
        Specialized method to retrieve SQL.
        Extracts the ```sql block using regular expressions.
        """
        full_content = self.ask(prompt, role="coder", temperature=temperature)
        sql_match = re.search(r"```sql\n(.*?)\n```", full_content, re.DOTALL | re.IGNORECASE)
        
        if sql_match:
            return sql_match.group(1).strip()
        else:
            return full_content.strip()