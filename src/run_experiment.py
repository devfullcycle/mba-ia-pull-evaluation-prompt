"""
Registra um Experiment no LangSmith para o prompt otimizado (v2).

Diferente de evaluate.py (que calcula as métricas em memória e imprime no
terminal), este script roda a avaliação pelo framework langsmith.evaluate(),
que cria um Experiment vinculado ao dataset. Assim, ao compartilhar o dataset
publicamente, os resultados das 5 métricas aparecem na aba "Experiments".

Reutiliza exatamente as mesmas métricas de metrics.py (nada é alterado nos
arquivos originais do desafio).

Uso:
    $env:PYTHONUTF8=1; .\\venv\\Scripts\\python.exe src\\run_experiment.py
"""

import os
import sys
from dotenv import load_dotenv
from langsmith import Client, evaluate
from langchain import hub

from utils import get_llm as get_configured_llm
from metrics import evaluate_f1_score, evaluate_clarity, evaluate_precision

load_dotenv()

PROMPT_KEY = "bug_to_user_story_v2"


def build_chain():
    """Puxa o prompt v2 do Hub e monta a chain (prompt | llm)."""
    username = os.getenv("USERNAME_LANGSMITH_HUB", "-") or "-"
    prompt_ref = f"{username}/{PROMPT_KEY}"
    print(f"Puxando prompt do Hub: {prompt_ref}")
    prompt_template = hub.pull(prompt_ref)
    llm = get_configured_llm(temperature=0)
    return prompt_template | llm


def make_target(chain):
    """Função avaliada: recebe os inputs do exemplo e devolve a user story."""
    def target(inputs: dict) -> dict:
        response = chain.invoke(inputs)
        return {"answer": response.content}
    return target


def all_metrics(run, example) -> dict:
    """
    Calcula as 5 métricas do desafio para um exemplo e devolve todas de uma vez.

    Base: F1-Score, Clarity, Precision (LLM-as-Judge de metrics.py).
    Derivadas: Helpfulness=(Clarity+Precision)/2, Correctness=(F1+Precision)/2.
    """
    answer = (run.outputs or {}).get("answer", "")
    question = (example.inputs or {}).get("bug_report", "")
    reference = (example.outputs or {}).get("reference", "")

    f1 = evaluate_f1_score(question, answer, reference)["score"]
    clarity = evaluate_clarity(question, answer, reference)["score"]
    precision = evaluate_precision(question, answer, reference)["score"]

    helpfulness = (clarity + precision) / 2
    correctness = (f1 + precision) / 2

    return {
        "results": [
            {"key": "helpfulness", "score": round(helpfulness, 4)},
            {"key": "correctness", "score": round(correctness, 4)},
            {"key": "f1_score", "score": round(f1, 4)},
            {"key": "clarity", "score": round(clarity, 4)},
            {"key": "precision", "score": round(precision, 4)},
        ]
    }


def main() -> int:
    client = Client()
    project_name = os.getenv("LANGSMITH_PROJECT", "prompt-optimization-challenge")
    dataset_name = f"{project_name}-eval"

    print(f"Dataset: {dataset_name}")
    chain = build_chain()

    print("Rodando experimento (langsmith.evaluate)...\n")
    results = evaluate(
        make_target(chain),
        data=dataset_name,
        evaluators=[all_metrics],
        experiment_prefix=PROMPT_KEY,
        max_concurrency=2,
        client=client,
    )

    name = getattr(results, "experiment_name", None)
    print("\n✅ Experiment registrado no dataset.")
    if name:
        print(f"   Nome do experimento: {name}")
    print("   Veja em: LangSmith → Datasets & Experiments → "
          f"{dataset_name} → aba Experiments")
    return 0


if __name__ == "__main__":
    sys.exit(main())
