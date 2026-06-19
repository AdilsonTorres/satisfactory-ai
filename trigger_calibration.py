import asyncio
import json
from temporalio.client import Client
from workflows.satisfactory_workflows import TemplateOrchestrationWorkflow

async def main():
    client = await Client.connect("localhost:7233")
    print("Conectado ao Temporal. Iniciando TemplateOrchestrationWorkflow...")
    result = await client.execute_workflow(
        TemplateOrchestrationWorkflow.run,
        args=["2560x1440"],
        id="calibration-workflow-run",
        task_queue="satisfactory-bot",
    )
    print("\n=== Workflow concluído! Resultados: ===")
    print(json.dumps(result, indent=2, ensure_ascii=False))

if __name__ == "__main__":
    asyncio.run(main())
