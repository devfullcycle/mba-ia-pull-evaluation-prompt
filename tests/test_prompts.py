"""
Testes automatizados para validação de prompts.
"""
import pytest
import sys
from pathlib import Path

# Adicionar src ao path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from utils import validate_prompt_structure, load_yaml

PROMPT_FILE = Path(__file__).parent.parent / "prompts" / "bug_to_user_story_v2.yml"
PROMPT_KEY = "bug_to_user_story_v2"


class TestPrompts:
    @pytest.fixture(autouse=True)
    def setup(self):
        data = load_yaml(str(PROMPT_FILE))
        self.prompt = data[PROMPT_KEY]
        self.system_prompt = self.prompt.get("system_prompt", "")

    def test_prompt_has_system_prompt(self):
        """Verifica se o campo 'system_prompt' existe e não está vazio."""
        is_valid, errors = validate_prompt_structure(self.prompt)
        assert is_valid, f"Estrutura inválida: {errors}"

    def test_prompt_has_role_definition(self):
        """Verifica se o prompt define uma persona (ex: "Você é um Product Manager")."""
        assert "Você é" in self.system_prompt, \
            "Prompt não define uma persona — adicione uma frase como 'Você é um especialista em...'"

    def test_prompt_mentions_format(self):
        """Verifica se o prompt exige formato Markdown ou User Story padrão."""
        has_user_story_template = (
            "Como um" in self.system_prompt
            and "eu quero" in self.system_prompt
            and "para que" in self.system_prompt
        )
        has_acceptance_criteria = "Critérios de Aceitação" in self.system_prompt
        has_gherkin = (
            "Dado que" in self.system_prompt
            and "Quando" in self.system_prompt
            and "Então" in self.system_prompt
        )

        assert has_user_story_template, \
            "Prompt não menciona o template de User Story (Como um... eu quero... para que...)"
        assert has_acceptance_criteria, \
            "Prompt não menciona 'Critérios de Aceitação'"
        assert has_gherkin, \
            "Prompt não menciona formato Gherkin (Dado que / Quando / Então)"

    def test_prompt_has_few_shot_examples(self):
        """Verifica se o prompt contém exemplos de entrada/saída (técnica Few-shot)."""
        example_count = self.system_prompt.count("Exemplo")
        output_count = self.system_prompt.count("Output:")

        assert example_count >= 2, \
            f"Esperado >= 2 exemplos few-shot, encontrado: {example_count}"
        assert output_count >= 2, \
            f"Exemplos few-shot devem ter seção 'Output:', encontrado: {output_count}"
        assert "Relato de Bug" in self.system_prompt, \
            "Exemplos few-shot devem conter 'Relato de Bug' como entrada"

    def test_prompt_no_todos(self):
        """Garante que você não esqueceu nenhum `[TODO]` no texto."""
        assert "TODO" not in self.system_prompt, \
            "Prompt contém TODO não resolvido — revise o conteúdo"

    def test_minimum_techniques(self):
        """Verifica (através dos metadados do yaml) se pelo menos 2 técnicas foram listadas."""
        techniques = self.prompt.get("techniques_applied", [])
        assert len(techniques) >= 2, \
            f"Mínimo de 2 técnicas requeridas, encontradas: {len(techniques)}"


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
