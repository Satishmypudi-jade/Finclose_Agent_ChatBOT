# agent_backend.py
import os
import pandas as pd
import json
from dotenv import load_dotenv

# Import necessary langchain and snowflake components
from langchain.prompts import PromptTemplate
from langchain_community.embeddings.openai import OpenAIEmbeddings
from langchain.prompts.few_shot import FewShotPromptTemplate
from langchain_community.chat_models import ChatOpenAI
from langchain_community.vectorstores import FAISS
from langchain.prompts.example_selector import SemanticSimilarityExampleSelector
import snowflake.connector
from langchain.chains import RetrievalQA
from FewShotSettings import few_shot_settings

# It's good practice to load environment variables
load_dotenv()

def get_sql_and_data(user_question: str, secrets: dict) -> str:
    """
    This single function takes a user question and a dictionary of secrets,
    generates SQL, runs it, and returns the result as a JSON string.
    """
    try:
        # --- 1. Generate SQL ---
        api_key = secrets["OpenAI_Secret_Key"]
        llm = ChatOpenAI(model_name="gpt-4", temperature=0, max_tokens=2000, openai_api_key=api_key)
        
        prefix = few_shot_settings.get_prefix()
        suffix, input_variable = few_shot_settings.get_suffix()
        examples = few_shot_settings.get_examples()
        example_template, example_variables = few_shot_settings.get_example_template()

        example_prompt = PromptTemplate(input_variables=example_variables, template=example_template)
        embeddings = OpenAIEmbeddings(openai_api_key=api_key)
        
        # This requires the 'db_faiss_index' folder to be in the same directory as the script
        # when the robot runs it.
        docsearch = FAISS.load_local("db_faiss_index", embeddings, allow_dangerous_deserialization=True)
        
        prompt_template = FewShotPromptTemplate(
            example_selector=SemanticSimilarityExampleSelector.from_examples(examples, embeddings, FAISS, k=3),
            example_prompt=example_prompt,
            prefix=prefix,
            suffix=suffix,
            input_variables=input_variable
        )
        
        qa_chain = RetrievalQA.from_chain_type(llm, retriever=docsearch.as_retriever(), chain_type_kwargs={"prompt": prompt_template})
        sql_query = qa_chain({"query": user_question})['result']

        if "Error" in str(sql_query):
            raise Exception(f"Failed to generate SQL: {sql_query}")

        # --- 2. Run SQL Query ---
        snow_con = snowflake.connector.connect(
            account=secrets["Snowflake_Account_Name"],
            user=secrets["Snowflake_User_Name"],
            password=secrets["Snowflake_User_Credential"],
            role=secrets["Snowflake_User_Role"],
            warehouse=secrets["Snowflake_Warehouse_Name"],
            database=secrets["Snowflake_Database_Name"],
            schema=secrets["Snowflake_Schema_Name"]
        )
        sql_result = pd.read_sql(sql_query, snow_con)
        
        # --- 3. Format and Return Result ---
        result_json = sql_result.to_json(orient='split')
        # We wrap the data in another JSON object for consistency
        final_payload = json.dumps({"data": result_json})
        return final_payload

    except Exception as e:
        return json.dumps({"error": str(e)})
