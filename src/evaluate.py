"""
Script COMPLETO para avaliar prompts otimizados.

Este script:
1. Carrega dataset de avaliação de arquivo .jsonl (datasets/bug_to_user_story.jsonl)
2. Cria/atualiza dataset no LangSmith
3. Puxa prompts otimizados do LangSmith Hub (fonte única de verdade)
4. Executa prompts contra o dataset
5. Calcula 5 métricas (Helpfulness, Correctness, F1-Score, Clarity, Precision)
6. Publica resultados no dashboard do LangSmith
7. Exibe resumo no terminal

Suporta múltiplos providers de LLM:
- OpenAI (gpt-4o, gpt-4o-mini)
- Google Gemini (gemini-1.5-flash, gemini-1.5-pro)

Configure o provider no arquivo .env através da variável LLM_PROVIDER.
"""

import os
import sys
import json
import time
import argparse
from typing import List, Dict, Any
from pathlib import Path
from dotenv import load_dotenv
from langsmith import Client
from langsmith.evaluation import evaluate
from langchain import hub
from langchain_core.prompts import ChatPromptTemplate
from utils import check_env_vars, format_score, print_section_header, get_llm as get_configured_llm
from metrics import evaluate_f1_score, evaluate_clarity, evaluate_precision

load_dotenv()


def get_llm():
    return get_configured_llm(temperature=0)


def load_dataset_from_jsonl(jsonl_path: str) -> List[Dict[str, Any]]:
    examples = []

    try:
        with open(jsonl_path, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if line:  # Ignorar linhas vazias
                    example = json.loads(line)
                    examples.append(example)

        return examples

    except FileNotFoundError:
        print(f"❌ Arquivo não encontrado: {jsonl_path}")
        print("\nCertifique-se de que o arquivo datasets/bug_to_user_story.jsonl existe.")
        return []
    except json.JSONDecodeError as e:
        print(f"❌ Erro ao parsear JSONL: {e}")
        return []
    except Exception as e:
        print(f"❌ Erro ao carregar dataset: {e}")
        return []


def create_evaluation_dataset(client: Client, dataset_name: str, jsonl_path: str) -> str:
    print(f"Criando dataset de avaliação: {dataset_name}...")

    examples = load_dataset_from_jsonl(jsonl_path)

    if not examples:
        print("❌ Nenhum exemplo carregado do arquivo .jsonl")
        return dataset_name

    print(f"   ✓ Carregados {len(examples)} exemplos do arquivo {jsonl_path}")

    try:
        datasets = client.list_datasets(dataset_name=dataset_name)
        existing_dataset = None

        for ds in datasets:
            if ds.name == dataset_name:
                existing_dataset = ds
                break

        if existing_dataset:
            print(f"   ✓ Dataset '{dataset_name}' já existe, usando existente")
            return dataset_name
        else:
            dataset = client.create_dataset(dataset_name=dataset_name)

            for example in examples:
                client.create_example(
                    dataset_id=dataset.id,
                    inputs=example["inputs"],
                    outputs=example["outputs"]
                )

            print(f"   ✓ Dataset criado com {len(examples)} exemplos")
            return dataset_name

    except Exception as e:
        print(f"   ⚠️  Erro ao criar dataset: {e}")
        return dataset_name


def pull_prompt_from_langsmith(prompt_name: str) -> ChatPromptTemplate:
    try:
        print(f"   Puxando prompt do LangSmith Hub: {prompt_name}")
        prompt = hub.pull(prompt_name)
        print(f"   ✓ Prompt carregado com sucesso")
        return prompt

    except Exception as e:
        error_msg = str(e).lower()

        print(f"\n{'=' * 70}")
        print(f"❌ ERRO: Não foi possível carregar o prompt '{prompt_name}'")
        print(f"{'=' * 70}\n")

        if "not found" in error_msg or "404" in error_msg:
            print("⚠️  O prompt não foi encontrado no LangSmith Hub.\n")
            print("AÇÕES NECESSÁRIAS:")
            print("1. Verifique se você já fez push do prompt otimizado:")
            print(f"   python src/push_prompts.py")
            print()
            print("2. Confirme se o prompt foi publicado com sucesso em:")
            print(f"   https://smith.langchain.com/prompts")
            print()
            print(f"3. Certifique-se de que o nome do prompt está correto: '{prompt_name}'")
            print()
            print("4. Se você alterou o prompt no YAML, refaça o push:")
            print(f"   python src/push_prompts.py")
        else:
            print(f"Erro técnico: {e}\n")
            print("Verifique:")
            print("- LANGSMITH_API_KEY está configurada corretamente no .env")
            print("- Você tem acesso ao workspace do LangSmith")
            print("- Sua conexão com a internet está funcionando")

        print(f"\n{'=' * 70}\n")
        raise


def evaluate_prompt_on_example(
    prompt_template: ChatPromptTemplate,
    example: Any,
    llm: Any
) -> Dict[str, Any]:
    try:
        inputs = example.inputs if hasattr(example, 'inputs') else {}
        outputs = example.outputs if hasattr(example, 'outputs') else {}

        chain = prompt_template | llm

        response = chain.invoke(inputs)
        answer = response.content

        reference = outputs.get("reference", "") if isinstance(outputs, dict) else ""

        if isinstance(inputs, dict):
            question = inputs.get("question", inputs.get("bug_report", inputs.get("pr_title", "N/A")))
        else:
            question = "N/A"

        return {
            "answer": answer,
            "reference": reference,
            "question": question
        }

    except Exception as e:
        print(f"      ⚠️  Erro ao avaliar exemplo: {e}")
        import traceback
        print(f"      Traceback: {traceback.format_exc()}")
        return {
            "answer": "",
            "reference": "",
            "question": ""
        }


def evaluate_prompt(
    prompt_name: str,
    dataset_name: str,
    client: Client,
    waiting_mode: bool = False
) -> Dict[str, float]:
    print(f"\n🔍 Avaliando: {prompt_name}")

    try:
        prompt_template = pull_prompt_from_langsmith(prompt_name)
        llm = get_llm()
        chain = prompt_template | llm

        def target_with_delay(inputs):
            if waiting_mode:
                print(f"      [Quota] Aguardando 10s antes da chamada ao LLM...")
                time.sleep(10)
            return chain.invoke(inputs)

        # Wrappers para adaptar as métricas locais ao formato do LangSmith evaluate()
        def langsmith_f1(run, example):
            if waiting_mode:
                print(f"      [Quota] Aguardando 10s antes de avaliar F1...")
                time.sleep(10)
            bug_report = run.inputs.get("bug_report", "")
            reference = example.outputs.get("reference", "")
            res = evaluate_f1_score(bug_report, run.outputs["output"].content, reference)
            return {"key": "f1_score", "score": res["score"], "comment": res["reasoning"]}

        def langsmith_clarity(run, example):
            if waiting_mode:
                print(f"      [Quota] Aguardando 10s antes de avaliar Clarity...")
                time.sleep(10)
            bug_report = run.inputs.get("bug_report", "")
            reference = example.outputs.get("reference", "")
            res = evaluate_clarity(bug_report, run.outputs["output"].content, reference)
            return {"key": "clarity", "score": res["score"], "comment": res["reasoning"]}

        def langsmith_precision(run, example):
            if waiting_mode:
                print(f"      [Quota] Aguardando 10s antes de avaliar Precision...")
                time.sleep(10)
            bug_report = run.inputs.get("bug_report", "")
            reference = example.outputs.get("reference", "")
            res = evaluate_precision(bug_report, run.outputs["output"].content, reference)
            return {"key": "precision", "score": res["score"], "comment": res["reasoning"]}

        print(f"   Iniciando experimento no LangSmith...")
        
        results = evaluate(
            target_with_delay,
            data=dataset_name,
            evaluators=[langsmith_f1, langsmith_clarity, langsmith_precision],
            experiment_prefix=f"eval-{prompt_name}",
            client=client,
            max_concurrency=1
        )

        # Extrair médias do experimento a partir dos resultados retornados pelo LangSmith.
        # Não chamamos a LLM novamente: usamos apenas os dados já gerados pelo evaluate().
        score_buckets = {"f1_score": [], "clarity": [], "precision": []}

        for row in results:
            evaluation_results = row["evaluation_results"]
            if isinstance(evaluation_results, dict):
                evaluation_results = evaluation_results.get("results", [])

            for item in evaluation_results or []:
                key = item.get("key") if isinstance(item, dict) else getattr(item, "key", None)
                score = item.get("score", 0.0) if isinstance(item, dict) else getattr(item, "score", 0.0)
                if key in score_buckets and score is not None:
                    score_buckets[key].append(score)

        avg_f1 = (
            sum(score_buckets["f1_score"]) / len(score_buckets["f1_score"])
            if score_buckets["f1_score"]
            else 0.0
        )
        avg_clarity = (
            sum(score_buckets["clarity"]) / len(score_buckets["clarity"])
            if score_buckets["clarity"]
            else 0.0
        )
        avg_precision = (
            sum(score_buckets["precision"]) / len(score_buckets["precision"])
            if score_buckets["precision"]
            else 0.0
        )

        print(f"   ✓ Resultado agregado: f1={avg_f1:.4f}, clarity={avg_clarity:.4f}, precision={avg_precision:.4f}")

        return {
            "helpfulness": round((avg_clarity + avg_precision) / 2, 4),
            "correctness": round((avg_f1 + avg_precision) / 2, 4),
            "f1_score": round(avg_f1, 4),
            "clarity": round(avg_clarity, 4),
            "precision": round(avg_precision, 4)
        }

    except Exception as e:
        print(f"   ❌ Erro na avaliação: {e}")
        return {
            "helpfulness": 0.0,
            "correctness": 0.0,
            "f1_score": 0.0,
            "clarity": 0.0,
            "precision": 0.0
        }


def display_results(prompt_name: str, scores: Dict[str, float]) -> bool:
    print("\n" + "=" * 50)
    print(f"Prompt: {prompt_name}")
    print("=" * 50)

    print("\nMétricas LangSmith:")
    print(f"  - Helpfulness: {format_score(scores['helpfulness'], threshold=0.9)}")
    print(f"  - Correctness: {format_score(scores['correctness'], threshold=0.9)}")

    print("\nMétricas Customizadas:")
    print(f"  - F1-Score: {format_score(scores['f1_score'], threshold=0.9)}")
    print(f"  - Clarity: {format_score(scores['clarity'], threshold=0.9)}")
    print(f"  - Precision: {format_score(scores['precision'], threshold=0.9)}")

    average_score = sum(scores.values()) / len(scores)

    print("\n" + "-" * 50)
    print(f"📊 MÉDIA GERAL: {average_score:.4f}")
    print("-" * 50)

    passed = average_score >= 0.9

    if passed:
        print(f"\n✅ STATUS: APROVADO (média >= 0.9)")
    else:
        print(f"\n❌ STATUS: REPROVADO (média < 0.9)")
        print(f"⚠️  Média atual: {average_score:.4f} | Necessário: 0.9000")

    return passed


def main():
    parser = argparse.ArgumentParser(description="Avaliação de prompts via LangSmith")
    parser.add_argument("--original", action="store_true", help="Avaliar a versão v1 (original) em vez da v2")
    parser.add_argument("--waiting-mode", action="store_true", help="Adiciona um atraso entre as chamadas ao LLM para evitar limites de cota")
    args = parser.parse_args()

    print_section_header("AVALIAÇÃO DE PROMPTS OTIMIZADOS")

    provider = os.getenv("LLM_PROVIDER", "openai")
    llm_model = os.getenv("LLM_MODEL", "gpt-4o-mini")
    eval_model = os.getenv("EVAL_MODEL", "gpt-4o")

    print(f"Provider: {provider}")
    print(f"Modelo Principal: {llm_model}")
    print(f"Modelo de Avaliação: {eval_model}\n")

    required_vars = ["LANGSMITH_API_KEY", "LLM_PROVIDER"]
    if provider == "openai":
        required_vars.append("OPENAI_API_KEY")
    elif provider in ["google", "gemini"]:
        required_vars.append("GOOGLE_API_KEY")

    if not check_env_vars(required_vars):
        return 1

    client = Client()
    project_name = os.getenv("LANGCHAIN_PROJECT", "prompt-optimization-challenge-resolved")

    jsonl_path = "datasets/bug_to_user_story.jsonl"

    if not Path(jsonl_path).exists():
        print(f"❌ Arquivo de dataset não encontrado: {jsonl_path}")
        print("\nCertifique-se de que o arquivo existe antes de continuar.")
        return 1

    dataset_name = f"{project_name}-eval"
    create_evaluation_dataset(client, dataset_name, jsonl_path)

    print("\n" + "=" * 70)
    print("PROMPTS PARA AVALIAR")
    print("=" * 70)
    print("\nEste script irá puxar prompts do LangSmith Hub.")
    print("Certifique-se de ter feito push dos prompts antes de avaliar:")
    print("  python src/push_prompts.py\n")

    version = "v1" if args.original else "v2"
    prompts_to_evaluate = [f"bug_to_user_story_{version}"]

    all_passed = True
    evaluated_count = 0
    results_summary = []

    for prompt_name in prompts_to_evaluate:
        evaluated_count += 1

        try:
            scores = evaluate_prompt(prompt_name, dataset_name, client, waiting_mode=args.waiting_mode)

            passed = display_results(prompt_name, scores)
            all_passed = all_passed and passed

            results_summary.append({
                "prompt": prompt_name,
                "scores": scores,
                "passed": passed
            })

        except Exception as e:
            print(f"\n❌ Falha ao avaliar '{prompt_name}': {e}")
            all_passed = False

            results_summary.append({
                "prompt": prompt_name,
                "scores": {
                    "helpfulness": 0.0,
                    "correctness": 0.0,
                    "f1_score": 0.0,
                    "clarity": 0.0,
                    "precision": 0.0
                },
                "passed": False
            })

    print("\n" + "=" * 50)
    print("RESUMO FINAL")
    print("=" * 50 + "\n")

    if evaluated_count == 0:
        print("⚠️  Nenhum prompt foi avaliado")
        return 1

    print(f"Prompts avaliados: {evaluated_count}")
    print(f"Aprovados: {sum(1 for r in results_summary if r['passed'])}")
    print(f"Reprovados: {sum(1 for r in results_summary if not r['passed'])}\n")

    if all_passed:
        print("✅ Todos os prompts atingiram média >= 0.9!")
        print(f"\n✓ Confira os resultados em:")
        print(f"  https://smith.langchain.com/projects/{project_name}")
        print("\nPróximos passos:")
        print("1. Documente o processo no README.md")
        print("2. Capture screenshots das avaliações")
        print("3. Faça commit e push para o GitHub")
        return 0
    else:
        print("⚠️  Alguns prompts não atingiram média >= 0.9")
        print("\nPróximos passos:")
        print("1. Refatore os prompts com score baixo")
        print("2. Faça push novamente: python src/push_prompts.py")
        print("3. Execute: python src/evaluate.py novamente")
        return 1

if __name__ == "__main__":
    sys.exit(main())
