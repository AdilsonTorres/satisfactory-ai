# Satisfactory AFK Bot + Temporal

Bot local para farm AFK no Satisfactory. Sem cloud, sem LLM em loop.  
Temporal para orquestração, retry automático e debug de histórico.

> **Requisito de SO:** Windows — `pydirectinput` e `pygetwindow` são Windows-only.

## Stack

| Componente | Lib | Por quê |
|---|---|---|
| Captura de tela | `mss` | ~1ms por frame |
| Detecção visual | `opencv-python` | template matching, zero treinamento |
| Inputs 3D | `pydirectinput` | DirectInput, funciona em jogos 3D |
| OCR (inventário) | `pytesseract` | leitura de quantidades |
| Orquestração | `temporalio` | retry, histórico, pausável |
| Pacotes | `uv` | gerenciamento de dependências rápido |
| Serviços Temporal | Docker Compose | PostgreSQL + Temporal + UI em containers |

---

## Setup

### 1. Pré-requisitos

- [uv](https://docs.astral.sh/uv/getting-started/installation/) — gerenciador de pacotes
- [Docker Desktop](https://www.docker.com/products/docker-desktop/) (com Compose)
- Python 3.11+
- [Tesseract OCR](https://github.com/UB-Mannheim/tesseract/wiki) no PATH (para leitura de inventário)

### 2. Instalar dependências

```bash
uv sync
```

### 3. Subir os serviços Temporal via Docker

```bash
docker compose up -d
```

Isso sobe:
- **PostgreSQL** — banco de persistência do Temporal (porta 5432, interna)
- **Temporal Server** — engine de orquestração (porta 7233)
- **Temporal UI** — interface web de debug em http://localhost:8233

Verifique se subiu:
```bash
docker compose ps
```

### 4. Criar os templates

Este é o passo mais importante. O bot precisa de imagens de referência
para reconhecer elementos do jogo.

```bash
# Com o Satisfactory aberto em modo janela:
uv run python capture_template.py
```

O script vai te guiar para capturar cada template necessário.
**Dica:** Capture templates com o jogo na resolução que você vai usar (ex: 1920x1080).

### 5. Rodar o worker

```bash
uv run python workers/worker.py
```

### 6. Disparar workflows

```bash
# Farm de gifts (modo mais simples)
temporal workflow start \
  --workflow-type GiftFarmWorkflow \
  --task-queue satisfactory-bot \
  --input '{}'

# Patrulha de combate
temporal workflow start \
  --workflow-type CombatPatrolWorkflow \
  --task-queue satisfactory-bot \
  --input '{"max_kills": 30}'

# Sessão completa (gifts + combate alternados)
temporal workflow start \
  --workflow-type AfkSessionWorkflow \
  --task-queue satisfactory-bot \
  --input '{"gift_cycles": 10, "combat_kills_per_rotation": 5, "total_rotations": 10}'
```

---

## Debug com Temporal

### UI web (recomendado)

Acesse **http://localhost:8233** enquanto o worker roda.

Você verá:
- Timeline de execução de cada workflow
- Qual activity falhou e com qual erro
- Quantas tentativas de retry foram feitas
- Input e output de cada step

### CLI

```bash
# Lista todos os workflows
temporal workflow list

# Ver histórico completo de um workflow
temporal workflow show --workflow-id <id>

# Terminar um workflow
temporal workflow terminate --workflow-id <id> --reason "testando"
```

### Derrubar e limpar os containers

```bash
# Para os containers (mantém os dados)
docker compose down

# Para e apaga os volumes (reset total do Temporal)
docker compose down -v
```

---

## Calibração de combate

### 1. Sensitivity factor

Em `utils/input.py`, a função `aim_at_screen_position` tem um `sensitivity_factor`.  
Teste assim: aponte manualmente para um inimigo, anote a posição na tela,
e ajuste o factor até o bot acertar.

### 2. Templates de inimigos

Capture templates de inimigos em diferentes ângulos/distâncias.
Use threshold mais baixo (0.65-0.70) para inimigos — eles se movem
e a silhueta muda.

### 3. Modo de teste sem loop

```python
# teste_combate.py — rode isolado para calibrar
from utils.vision import Vision
from utils import input as inp

v = Vision()
result = v.find_enemy()
print(f"Inimigo: {result}")
```

---

## Estrutura do projeto

```
satisfactory-ai/
├── activities/
│   └── game_activities.py   # ações atômicas (collect, craft, fight, loot)
├── workflows/
│   └── satisfactory_workflows.py  # lógica de alto nível
├── workers/
│   └── worker.py            # ponto de entrada do Temporal
├── utils/
│   ├── vision.py            # captura + template matching
│   └── input.py             # mouse/teclado via DirectInput
├── templates/               # imagens PNG dos elementos do jogo (você cria)
├── capture_template.py      # helper para criar templates
├── pyproject.toml           # dependências (uv)
└── docker-compose.yml       # Temporal + PostgreSQL + UI
```

---

## Limitações conhecidas

- **Navegação:** o bot usa sequências de teclas gravadas, não pathfinding.
  Se um bicho empurrar o personagem, a navegação até o workshop pode falhar.
  O Temporal vai fazer retry, mas pode não chegar lá.

- **Combate:** targeting funciona para inimigos parados ou lentos.
  Spitters rápidos em movimento podem não ser atingidos consistentemente.

- **Resolução:** templates capturados em 1920x1080 não funcionam em outra
  resolução. Recapture se mudar a resolução.
