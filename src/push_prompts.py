"""
Script para fazer push de prompts otimizados ao LangSmith Prompt Hub.

Este script:
1. Lê os prompts otimizados de prompts/bug_to_user_story_v2.yml
2. Valida os prompts
3. Faz push PÚBLICO para o LangSmith Hub
4. Adiciona metadados (tags, descrição, técnicas utilizadas)

SIMPLIFICADO: Código mais limpo e direto ao ponto.
"""

import os
import sys
from dotenv import load_dotenv
from langchain import hub
from langchain_core.prompts import ChatPromptTemplate
from utils import load_yaml, check_env_vars, print_section_header, validate_prompt_structure

load_dotenv()


def validate_prompt(prompt_data: dict) -> tuple[bool, list]:
    """
    Validate prompt structure and content requirements.
    
    Args:
        prompt_data: Dados do prompt
        
    Returns:
        (is_valid, errors) - Tupla com status e lista de erros
    """
    # Use the utility function for basic validation
    is_valid, errors = validate_prompt_structure(prompt_data)
    
    # Additional validation for techniques_applied
    techniques = prompt_data.get('techniques_applied', [])
    if len(techniques) < 2:
        errors.append(f"Mínimo de 2 técnicas requeridas, encontradas: {len(techniques)}")
    
    return (len(errors) == 0, errors)


def push_prompt_to_langsmith(prompt_name: str, prompt_data: dict) -> bool:
    """
    Push the optimized prompt to LangSmith Hub (PUBLIC).
    
    Args:
        prompt_name: Nome do prompt
        prompt_data: Dados do prompt
        
    Returns:
        True if success, False otherwise
    """
    try:
        # Convert YAML data to ChatPromptTemplate
        system_prompt = prompt_data.get("system_prompt", "")
        user_prompt = prompt_data.get("user_prompt", "{bug_report}")
        
        prompt_template = ChatPromptTemplate.from_messages([
            ("system", system_prompt),
            ("human", user_prompt),
        ])
        
        # Push to LangSmith Hub
        print(f"Pushing prompt to LangSmith Hub: {prompt_name}")
        hub.push(prompt_name, prompt_template)
        print(f"✓ Prompt pushed successfully to: {prompt_name}")
        return True
        
    except Exception as e:
        print(f"❌ Error pushing prompt to LangSmith Hub: {e}")
        return False


def main():
    """Main function"""
    print_section_header("PUSHING OPTIMIZED PROMPT TO LANGSMITH HUB")
    
    # Load the optimized prompt
    prompt_data = load_yaml("prompts/bug_to_user_story_v2.yml")
    if prompt_data is None:
        print("❌ Failed to load prompt from prompts/bug_to_user_story_v2.yml")
        return 1
    
    # Extract the actual prompt data (remove the outer key)
    prompt_key = "bug_to_user_story_v2"
    if prompt_key not in prompt_data:
        print(f"❌ Expected key '{prompt_key}' not found in prompt file")
        return 1
    
    actual_prompt_data = prompt_data[prompt_key]
    
    # Validate the prompt
    print("Validating prompt structure...")
    is_valid, errors = validate_prompt(actual_prompt_data)
    
    if not is_valid:
        print("❌ Prompt validation failed:")
        for error in errors:
            print(f"   - {error}")
        return 1
    
    print("✓ Prompt validation passed")
    
    # Check environment variables
    required_vars = ["LANGSMITH_API_KEY", "USERNAME_LANGSMITH_HUB"]
    if not check_env_vars(required_vars):
        return 1
    
    # Construct the full prompt name
    username = os.getenv("USERNAME_LANGSMITH_HUB")
    full_prompt_name = f"{username}/bug_to_user_story_v2"
    
    # Push the prompt
    success = push_prompt_to_langsmith(full_prompt_name, actual_prompt_data)
    
    if success:
        print("\n✓ Push completed successfully!")
        print(f"  Prompt available at: https://smith.langchain.com/prompts/{full_prompt_name}")
        return 0
    else:
        print("\n❌ Push failed!")
        return 1


if __name__ == "__main__":
    sys.exit(main())