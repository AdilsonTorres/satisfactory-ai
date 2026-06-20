import asyncio
import json
import argparse
from temporalio.client import Client
from workflows.satisfactory_workflows import TemplateOrchestrationWorkflow

async def main():
    parser = argparse.ArgumentParser(description="Dispara o workflow de calibração visual.")
    parser.add_argument(
        "--target",
        default="hud",
        choices=["hud", "workshop"],
        help="Alvo da calibração: 'hud' (padrão) ou 'workshop'."
    )
    parser.add_argument(
        "--resolution",
        default="2560x1440",
        help="Resolução do jogo (ex: 2560x1440)."
    )
    args = parser.parse_args()

    client = await Client.connect("localhost:7233")
    print(f"Conectado ao Temporal. Iniciando TemplateOrchestrationWorkflow(target='{args.target}', resolution='{args.resolution}')...")
    
    result = await client.execute_workflow(
        TemplateOrchestrationWorkflow.run,
        args=[args.target, args.resolution],
        id="calibration-workflow-run",
        task_queue="satisfactory-bot",
    )
    print("\n=== Workflow concluído! Resultados: ===")
    print(json.dumps(result, indent=2, ensure_ascii=False))

if __name__ == "__main__":
    asyncio.run(main())
