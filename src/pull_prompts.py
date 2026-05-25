"""
Script para fazer pull de prompts do LangSmith Prompt Hub.

Este script:
1. Conecta ao LangSmith usando credenciais do .env
2. Faz pull dos prompts do Hub
3. Salva localmente em prompts/bug_to_user_story_v1.yml

SIMPLIFICADO: Usa serialização nativa do LangChain para extrair prompts.
"""

import os
import sys
from pathlib import Path
from dotenv import load_dotenv
from langsmith import Client
from langchain_core.prompts import ChatPromptTemplate
from utils import save_yaml, check_env_vars, print_section_header

load_dotenv()


def pull_prompts_from_langsmith():
    """
    Pull prompt leonanluppi/bug_to_user_story_v1 from LangSmith Hub
    and save it locally as prompts/bug_to_user_story_v1.yml
    
    Returns:
        bool: True if successful, False otherwise
    """
    print_section_header("PULLING PROMPT FROM LANGSMITH HUB")
    
    # Check required environment variables
    required_vars = ["LANGSMITH_API_KEY"]
    if not check_env_vars(required_vars):
        return False
    
    try:
        client = Client()
        prompt_obj = client.pull_prompt("leonanluppi/bug_to_user_story_v1")
        #print(prompt_obj)

        system_prompt = ""
        user_prompt = ""

        # Extract prompt values
        if hasattr(prompt_obj, 'messages'):
            for message in prompt_obj.messages:
                if hasattr(message, 'prompt') and hasattr(message.prompt, 'template'):
                    if message.__class__.__name__ == 'SystemMessagePromptTemplate':
                        system_prompt = message.prompt.template
                    elif message.__class__.__name__ == 'HumanMessagePromptTemplate':
                        user_prompt = message.prompt.template
                
        # Create the YAML structure
        prompt_data = {
            "bug_to_user_story_v1": {
                "description": "Prompt original para converter bug reports em User Stories",
                "system_prompt": system_prompt,
                "user_prompt": user_prompt,
                "version": "v1",
                "tags": ["bug-report", "user-story", "original"]
            }
        }
        
        # Save to file
        output_path = "prompts/bug_to_user_story_v1.yml"
        if save_yaml(prompt_data, output_path):
            print(f"✓ Prompt salvo com sucesso em: {output_path}")
            return True
        else:
            print(f"❌ Falha ao salvar prompt em: {output_path}")
            return False
            
    except Exception as e:
        print(f"❌ Erro ao fazer pull do prompt: {e}")
        print("Verifique:")
        print("- LANGSMITH_API_KEY está configurada corretamente no .env")
        print("- O prompt 'leonanluppi/bug_to_user_story_v1' existe no LangSmith Hub")
        print("- Sua conexão com a internet está funcionando")
        return False


def main():
    """Função principal"""
    try:
        success = pull_prompts_from_langsmith()
        return 0 if success else 1
    except Exception as e:
        print(f"❌ Erro inesperado: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())