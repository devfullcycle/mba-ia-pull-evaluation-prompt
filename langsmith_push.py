import yaml
from dotenv import load_dotenv
from langchain_core.prompts import PromptTemplate
from langsmith import Client

from prompt_registry import registry

load_dotenv()

prompt = registry.get_prompt("agent-pull-request-creator")
with open(prompt.path, "r", encoding="utf-8") as f:
    data = yaml.safe_load(f)
prompt_template = PromptTemplate(
    template=data["template"],
    input_variables=data["input_variables"],
)

client = Client()
url = client.push_prompt(
    "agent-pull-request-creator", 
    object=prompt_template, 
    tags=[
        f"v{prompt.version}",
        f"model: {prompt.model}",
    ], 
    description=prompt.description,
)
print(url)
