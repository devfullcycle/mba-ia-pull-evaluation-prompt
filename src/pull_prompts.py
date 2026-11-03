"""
Script para fazer pull de prompts do LangSmith Prompt Hub.

Este script:
1. Conecta ao LangSmith usando credenciais do .env
2. Faz pull do prompt semente do desafio
3. Salva localmente em prompts/bug_to_user_story_v1.yml

DICAS DE IMPLEMENTAÇÃO:

- O pull é feito pelo cliente do LangSmith:

      from langsmith import Client
      client = Client()
      prompt = client.pull_prompt(
          "leonanluppi/bug_to_user_story_v1",
          dangerously_pull_public_prompt=True,
      )

- O parâmetro `dangerously_pull_public_prompt=True` é obrigatório sempre que o
  identificador tem dono explícito ("owner/nome"). O LangSmith bloqueia esse pull
  por padrão porque um prompt do Hub é um objeto LangChain serializado, que pode
  vir de terceiros. Aqui o prompt é o do desafio, então o risco é conhecido.

- O retorno é um ChatPromptTemplate. Para extrair o conteúdo das mensagens,
  use a serialização nativa do LangChain (`prompt.messages`, e o atributo
  `.prompt.template` de cada mensagem).

- Use `save_yaml` de utils.py para gravar o resultado no arquivo .yml.
"""


import sys
from dotenv import load_dotenv
from langsmith import Client
from utils import save_yaml, check_env_vars, print_section_header

load_dotenv()

PROMPT_REPO = "leonanluppi/bug_to_user_story_v1"
OUTPUT_PATH = "prompts/bug_to_user_story_v1.yml"

def pull_prompts_from_langsmith():
    """
    Faz o pull do prompt do LangSmith e salva em arquivo YAML local.
    """
    print(f"   ⬇️  Fazendo pull de: {PROMPT_REPO}")
    
    try:
        # Faz o pull do objeto ChatPromptTemplate
        prompt_template = hub.pull(PROMPT_REPO)
        
        # Extrai o conteúdo das mensagens (System e User)
        # Nota: A estrutura depende de como o prompt foi salvo. 
        # Assumindo ChatPromptTemplate com SystemMessage e HumanMessage.
        system_prompt = ""
        user_prompt = ""
        
        for msg in prompt_template.messages:
            # Verifica o tipo de mensagem para extrair o template correto
            content = getattr(msg, 'prompt', None)
            text = content.template if content else str(msg)
            
            if "System" in msg.__class__.__name__:
                system_prompt = text
            elif "Human" in msg.__class__.__name__:
                user_prompt = text

        # Monta o dicionário no formato esperado pelo projeto
        data = {
            "bug_to_user_story_v1": {
                "description": "Prompt original extraído do LangSmith Hub",
                "system_prompt": system_prompt,
                "user_prompt": user_prompt,
                "version": "v1",
                "created_at": "2025-01-15",
                "tags": ["bug-analysis", "user-story", "original"]
            }
        }

        # Salva o arquivo
        if save_yaml(data, OUTPUT_PATH):
            print(f"   ✅ Prompt salvo com sucesso em: {OUTPUT_PATH}")
        
    except Exception as e:
        print(f"   ❌ Erro ao fazer pull do prompt: {e}")
        sys.exit(1)


def main():
    """Função principal"""
    print_section_header("PULL PROMPTS DO LANGSMITH")
    
    # Verifica variáveis necessárias
    if not check_env_vars(["LANGSMITH_API_KEY"]):
        return

    pull_prompts_from_langsmith()


if __name__ == "__main__":
    sys.exit(main())
