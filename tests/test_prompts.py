"""
Testes automatizados para validação de prompts.
"""
import pytest
import yaml
import sys
from pathlib import Path

# Adicionar src ao path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from utils import validate_prompt_structure


def load_prompts(file_path: str):
    """Carrega prompts do arquivo YAML."""
    with open(file_path, 'r', encoding='utf-8') as f:
        return yaml.safe_load(f)


class TestPrompts:
    def test_prompt_has_system_prompt(self):
        """Verifica se o campo 'system_prompt' existe e não está vazio."""
        data = load_prompts("prompts/bug_to_user_story_v2.yml")
        assert "bug_to_user_story_v2" in data
        assert data["bug_to_user_story_v2"]["system_prompt"].strip() != ""

    def test_prompt_has_role_definition(self):
        """Verifica se o prompt define uma persona (ex: "Você é um Product Manager")."""
        data = load_prompts("prompts/bug_to_user_story_v2.yml")
        sp = data["bug_to_user_story_v2"]["system_prompt"].lower()
        assert any(kw in sp for kw in ["você é um", "você é uma", "product manager"])

    def test_prompt_mentions_format(self):
        """Verifica se o prompt exige formato Markdown ou User Story padrão."""
        data = load_prompts("prompts/bug_to_user_story_v2.yml")
        sp = data["bug_to_user_story_v2"]["system_prompt"].lower()
        assert any(kw in sp for kw in ["formato", "markdown", "user story", "como um", "eu quero"])

    def test_prompt_has_few_shot_examples(self):
        """Verifica se o prompt contém exemplos de entrada/saída (técnica Few-shot)."""
        data = load_prompts("prompts/bug_to_user_story_v2.yml")
        sp = data["bug_to_user_story_v2"]["system_prompt"]
        assert "exemplo" in sp.lower() or "example" in sp.lower()

    def test_prompt_no_todos(self):
        """Garante que você não esqueceu nenhum `[TODO]` no texto."""
        data = load_prompts("prompts/bug_to_user_story_v2.yml")
        sp = data["bug_to_user_story_v2"]["system_prompt"]
        assert "[TODO]" not in sp and "TODO:" not in sp

    def test_minimum_techniques(self):
        """Verifica (através dos metadados do yaml) se pelo menos 2 técnicas foram listadas."""
        data = load_prompts("prompts/bug_to_user_story_v2.yml")
        techniques = data["bug_to_user_story_v2"].get("techniques_applied", [])
        assert len(techniques) >= 2


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])