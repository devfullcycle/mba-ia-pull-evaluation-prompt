"""
Testes automatizados para validação do prompt otimizado (v2).

Rode com:
    pytest tests/test_prompts.py -v
"""
import pytest
import yaml
import sys
from pathlib import Path

# Adicionar src ao path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from utils import validate_prompt_structure  # noqa: F401 (disponível para uso/extensão)

PROMPT_FILE = Path(__file__).parent.parent / "prompts" / "bug_to_user_story_v2.yml"
PROMPT_KEY = "bug_to_user_story_v2"


def load_prompts(file_path: str):
    """Carrega prompts do arquivo YAML."""
    with open(file_path, 'r', encoding='utf-8') as f:
        return yaml.safe_load(f)


def get_prompt_data():
    """Carrega o v2 e desembrulha a chave de topo, se existir."""
    data = load_prompts(PROMPT_FILE)
    if isinstance(data, dict) and PROMPT_KEY in data:
        return data[PROMPT_KEY]
    return data


class TestPrompts:
    @pytest.fixture(autouse=True)
    def _setup(self):
        self.prompt = get_prompt_data()
        self.system = (self.prompt.get("system_prompt") or "")
        self.user = (self.prompt.get("user_prompt") or "")

    def test_prompt_has_system_prompt(self):
        """Verifica se o campo 'system_prompt' existe e não está vazio."""
        assert "system_prompt" in self.prompt, "Campo 'system_prompt' ausente no YAML"
        assert self.system.strip() != "", "'system_prompt' está vazio"

    def test_prompt_has_role_definition(self):
        """Verifica se o prompt define uma persona (ex: 'Você é um Product Manager')."""
        system_lower = self.system.lower()
        assert "você é" in system_lower, "Prompt não define uma persona com 'Você é...'"
        assert any(
            role in system_lower
            for role in ["product manager", "product owner", "gerente de produto"]
        ), "Persona não identifica um papel de produto (ex.: Product Manager)"

    def test_prompt_mentions_format(self):
        """Verifica se o prompt exige formato Markdown ou User Story padrão."""
        system_lower = self.system.lower()
        assert "markdown" in system_lower or "user story" in system_lower, (
            "Prompt não menciona o formato esperado (Markdown / User Story)"
        )

    def test_prompt_has_few_shot_examples(self):
        """Verifica se o prompt contém exemplos de entrada/saída (técnica Few-shot)."""
        system_lower = self.system.lower()
        assert "exemplo 1" in system_lower and "exemplo 2" in system_lower, (
            "Prompt não contém ao menos 2 exemplos rotulados (Exemplo 1, Exemplo 2)"
        )
        # Cada exemplo é um par Bug Report -> User Story
        assert system_lower.count("bug report:") >= 2, (
            "Few-shot deve conter ao menos 2 pares de entrada (Bug Report:)"
        )
        assert system_lower.count("user story:") >= 2, (
            "Few-shot deve conter ao menos 2 pares de saída (User Story:)"
        )

    def test_prompt_no_todos(self):
        """Garante que você não esqueceu nenhum '[TODO]' no texto."""
        full_text = f"{self.system}{self.user}"
        assert "TODO" not in full_text, "Ainda existe um TODO no prompt"

    def test_minimum_techniques(self):
        """Verifica (via metadados do yaml) se pelo menos 2 técnicas foram listadas."""
        techniques = self.prompt.get("techniques_applied", [])
        assert isinstance(techniques, list), "'techniques_applied' deve ser uma lista"
        assert len(techniques) >= 2, (
            f"Mínimo de 2 técnicas requeridas, encontradas: {len(techniques)}"
        )


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
