"""
Script COMPLETO para avaliar prompts otimizados.

Este script:
1. Carrega o dataset de avaliação do arquivo .jsonl (datasets/bug_to_user_story.jsonl)
2. Cria (ou reutiliza) o dataset de avaliação no LangSmith
3. Puxa o prompt otimizado do LangSmith Prompt Hub (fonte única de verdade)
4. Roda o prompt contra o dataset como um EXPERIMENTO do LangSmith
5. Calcula 5 métricas por exemplo (Helpfulness, Correctness, F1-Score, Clarity, Precision)
6. Publica cada nota como feedback no experimento, visível no dashboard do LangSmith
7. Exibe o resumo no terminal e imprime o link direto do experimento

Suporta múltiplos providers de LLM: OpenAI e Google Gemini.
Os modelos não são fixados aqui: defina LLM_MODEL e EVAL_MODEL no .env,
consultando a documentação oficial do provider escolhido.

Configure o provider no arquivo .env através da variável LLM_PROVIDER.
"""

import os
import sys
import json
from typing import List, Dict, Any
from pathlib import Path
from dotenv import load_dotenv
from langsmith import Client
from langchain_core.prompts import ChatPromptTemplate
from utils import check_env_vars, format_score, print_section_header, get_llm as get_configured_llm
from metrics import evaluate_f1_score, evaluate_clarity, evaluate_precision

load_dotenv()

# Nota mínima exigida em CADA métrica e também na média geral
APPROVAL_THRESHOLD = 0.8

# Ordem em que as métricas aparecem no relatório e no LangSmith
METRIC_KEYS = ["helpfulness", "correctness", "f1_score", "clarity", "precision"]


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
        for ds in client.list_datasets(dataset_name=dataset_name):
            if ds.name == dataset_name:
                print(f"   ✓ Dataset '{dataset_name}' já existe, usando existente")
                print(f"   ✓ {ds.url}")
                return dataset_name

        dataset = client.create_dataset(dataset_name=dataset_name)

        for example in examples:
            client.create_example(
                dataset_id=dataset.id,
                inputs=example["inputs"],
                outputs=example["outputs"]
            )

        print(f"   ✓ Dataset criado com {len(examples)} exemplos")
        print(f"   ✓ {dataset.url}")
        return dataset_name

    except Exception as e:
        print(f"   ⚠️  Erro ao criar dataset: {e}")
        return dataset_name


def pull_prompt_from_langsmith(client: Client, prompt_name: str) -> ChatPromptTemplate:
    try:
        print(f"   Puxando prompt do LangSmith Hub: {prompt_name}")

        # dangerously_pull_public_prompt=True é obrigatório sempre que o identificador
        # tem dono explícito ("owner/nome"). O LangSmith bloqueia esse pull por padrão
        # porque um prompt do Hub é um objeto LangChain serializado, que pode vir de
        # terceiros. Como aqui o prompt é o seu (ou o prompt semente do desafio),
        # o risco é conhecido e aceito.
        prompt = client.pull_prompt(prompt_name, dangerously_pull_public_prompt=True)

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
            print(f"3. Confira se USERNAME_LANGSMITH_HUB no .env é o seu handle do Hub")
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


def build_target(prompt_template: ChatPromptTemplate, llm: Any):
    """
    Monta a função que o LangSmith executa para cada exemplo do dataset.

    Recebe os inputs do exemplo (ex: {"bug_report": "..."}) e devolve a saída
    do modelo num dicionário. Cada chamada vira um run dentro do experimento.
    """
    chain = prompt_template | llm

    def target(inputs: dict) -> dict:
        response = chain.invoke(inputs)
        return {"answer": response.text}

    return target


def evaluate_all_metrics(inputs: dict, outputs: dict, reference_outputs: dict) -> Dict[str, Any]:
    """
    Avaliador do LangSmith: roda os três juízes uma única vez por exemplo e
    devolve as 5 métricas de uma vez.

    O LangSmith grava cada item da lista "results" como um feedback separado,
    então as 5 notas aparecem por exemplo no dashboard e são agregadas
    automaticamente no experimento.
    """
    question = (inputs or {}).get("bug_report", "")
    answer = (outputs or {}).get("answer", "") or ""
    reference = (reference_outputs or {}).get("reference", "")

    if not answer:
        return {
            "results": [
                {"key": key, "score": 0.0, "comment": "Resposta vazia"}
                for key in METRIC_KEYS
            ]
        }

    f1 = evaluate_f1_score(question, answer, reference)
    clarity = evaluate_clarity(question, answer, reference)
    precision = evaluate_precision(question, answer, reference)

    scores = {
        "f1_score": f1["score"],
        "clarity": clarity["score"],
        "precision": precision["score"],
    }
    # Métricas derivadas das métricas base
    scores["helpfulness"] = round((scores["clarity"] + scores["precision"]) / 2, 4)
    scores["correctness"] = round((scores["f1_score"] + scores["precision"]) / 2, 4)

    comments = {
        "f1_score": f1.get("reasoning", ""),
        "clarity": clarity.get("reasoning", ""),
        "precision": precision.get("reasoning", ""),
        "helpfulness": "Média entre Clarity e Precision",
        "correctness": "Média entre F1-Score e Precision",
    }

    return {
        "results": [
            {"key": key, "score": scores[key], "comment": comments[key]}
            for key in METRIC_KEYS
        ]
    }


def run_experiment(client: Client, prompt_name: str, dataset_name: str):
    """
    Executa o prompt contra o dataset como um experimento do LangSmith.

    Devolve (scores_medios, url_do_experimento).
    """
    print(f"\n🔍 Avaliando: {prompt_name}")

    prompt_template = pull_prompt_from_langsmith(client, prompt_name)
    llm = get_llm()

    print("   Rodando experimento no LangSmith...")

    results = client.evaluate(
        build_target(prompt_template, llm),
        data=dataset_name,
        evaluators=[evaluate_all_metrics],
        experiment_prefix=prompt_name.replace("/", "-"),
        # Sequencial de propósito: os planos gratuitos de LLM costumam ter limite
        # baixo de requisições por minuto. Se o seu limite permitir, suba esse valor.
        max_concurrency=1,
        metadata={
            "prompt": prompt_name,
            "llm_model": os.getenv("LLM_MODEL", ""),
            "eval_model": os.getenv("EVAL_MODEL", ""),
            "provider": os.getenv("LLM_PROVIDER", ""),
        },
    )

    collected = {key: [] for key in METRIC_KEYS}

    for i, row in enumerate(results, 1):
        per_example = {}

        for result in row["evaluation_results"]["results"]:
            if result.key in collected and result.score is not None:
                collected[result.key].append(result.score)
                per_example[result.key] = result.score

        print(
            f"      [{i}] "
            f"F1:{per_example.get('f1_score', 0.0):.2f} "
            f"Clarity:{per_example.get('clarity', 0.0):.2f} "
            f"Precision:{per_example.get('precision', 0.0):.2f}"
        )

    scores = {
        key: round(sum(values) / len(values), 4) if values else 0.0
        for key, values in collected.items()
    }

    return scores, results.url


def display_results(prompt_name: str, scores: Dict[str, float]) -> bool:
    print("\n" + "=" * 50)
    print(f"Prompt: {prompt_name}")
    print("=" * 50)

    print("\nMétricas Derivadas:")
    print(f"  - Helpfulness: {format_score(scores['helpfulness'], threshold=APPROVAL_THRESHOLD)}")
    print(f"  - Correctness: {format_score(scores['correctness'], threshold=APPROVAL_THRESHOLD)}")

    print("\nMétricas Base:")
    print(f"  - F1-Score: {format_score(scores['f1_score'], threshold=APPROVAL_THRESHOLD)}")
    print(f"  - Clarity: {format_score(scores['clarity'], threshold=APPROVAL_THRESHOLD)}")
    print(f"  - Precision: {format_score(scores['precision'], threshold=APPROVAL_THRESHOLD)}")

    average_score = sum(scores.values()) / len(scores)

    print("\n" + "-" * 50)
    print(f"📊 MÉDIA GERAL: {average_score:.4f}")
    print("-" * 50)

    all_above_threshold = all(score >= APPROVAL_THRESHOLD for score in scores.values())
    passed = all_above_threshold and average_score >= APPROVAL_THRESHOLD

    if passed:
        print(f"\n✅ STATUS: APROVADO - Todas as métricas >= {APPROVAL_THRESHOLD}")
    else:
        print(f"\n❌ STATUS: REPROVADO")
        failed_metrics = [name for name, score in scores.items() if score < APPROVAL_THRESHOLD]
        if failed_metrics:
            print(f"⚠️  Métricas abaixo de {APPROVAL_THRESHOLD}: {', '.join(failed_metrics)}")
        print(f"⚠️  Média atual: {average_score:.4f} | Necessário: {APPROVAL_THRESHOLD:.4f}")

    return passed


def main():
    print_section_header("AVALIAÇÃO DE PROMPTS OTIMIZADOS")

    provider = os.getenv("LLM_PROVIDER", "")
    llm_model = os.getenv("LLM_MODEL", "")
    eval_model = os.getenv("EVAL_MODEL", "")

    print(f"Provider: {provider}")
    print(f"Modelo Principal: {llm_model}")
    print(f"Modelo de Avaliação: {eval_model}\n")

    required_vars = [
        "LANGSMITH_API_KEY",
        "LANGSMITH_PROJECT",
        "USERNAME_LANGSMITH_HUB",
        "LLM_PROVIDER",
        "LLM_MODEL",
        "EVAL_MODEL",
    ]
    if provider == "openai":
        required_vars.append("OPENAI_API_KEY")
    elif provider in ["google", "gemini"]:
        required_vars.append("GOOGLE_API_KEY")

    if not check_env_vars(required_vars):
        return 1

    client = Client()
    project_name = os.getenv("LANGSMITH_PROJECT")
    username = os.getenv("USERNAME_LANGSMITH_HUB")

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

    prompts_to_evaluate = [
        f"{username}/bug_to_user_story_v2",
    ]

    all_passed = True
    results_summary = []

    for prompt_name in prompts_to_evaluate:
        try:
            scores, experiment_url = run_experiment(client, prompt_name, dataset_name)
            passed = display_results(prompt_name, scores)
            all_passed = all_passed and passed

            results_summary.append({
                "prompt": prompt_name,
                "scores": scores,
                "passed": passed,
                "url": experiment_url,
            })

        except Exception as e:
            print(f"\n❌ Falha ao avaliar '{prompt_name}': {e}")
            all_passed = False

            results_summary.append({
                "prompt": prompt_name,
                "scores": {key: 0.0 for key in METRIC_KEYS},
                "passed": False,
                "url": None,
            })

    print("\n" + "=" * 50)
    print("RESUMO FINAL")
    print("=" * 50 + "\n")

    print(f"Prompts avaliados: {len(results_summary)}")
    print(f"Aprovados: {sum(1 for r in results_summary if r['passed'])}")
    print(f"Reprovados: {sum(1 for r in results_summary if not r['passed'])}\n")

    print("Resultados no LangSmith (notas gravadas como feedback no experimento):")
    for result in results_summary:
        if result["url"]:
            print(f"  {result['prompt']}")
            print(f"    {result['url']}")

    if all_passed:
        print(f"\n✅ Todos os prompts atingiram todas as métricas >= {APPROVAL_THRESHOLD}!")
        print("\nPróximos passos:")
        print("1. Documente o processo no README.md")
        print("2. Capture screenshots das avaliações")
        print("3. Faça commit e push para o GitHub")
        return 0
    else:
        print(f"\n⚠️  Alguns prompts não atingiram todas as métricas >= {APPROVAL_THRESHOLD}")
        print("\nPróximos passos:")
        print("1. Refatore os prompts com score baixo")
        print("2. Faça push novamente: python src/push_prompts.py")
        print("3. Execute: python src/evaluate.py novamente")
        return 1


if __name__ == "__main__":
    sys.exit(main())
