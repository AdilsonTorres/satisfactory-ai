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
| Pacotes | `uv` | gerenciamento rápido de dependências |
| Serviços Temporal | Docker Compose | PostgreSQL + Temporal Server + UI |

---

## Setup

### 1. Pré-requisitos

- [uv](https://docs.astral.sh/uv/getting-started/installation/)
- [Docker Desktop](https://www.docker.com/products/docker-desktop/) (com Compose V2)
- Python 3.11+
- [Tesseract OCR](https://github.com/UB-Mannheim/tesseract/wiki) no PATH

### 2. Instalar dependências

```bash
uv sync
```

### 3. Subir os serviços Temporal

```bash
docker compose up -d
docker compose ps   # confirmar que os 3 serviços estão healthy/running
```

| Serviço | Porta | Descrição |
|---|---|---|
| Temporal Server | 7233 | gRPC — o worker conecta aqui |
| Temporal UI | 8233 | Dashboard web de debug |
| PostgreSQL | (interna) | persistência dos workflows |

### 4. Criar os templates

Este é o passo mais importante. O bot não vê o jogo — ele compara imagens.

```bash
# Com o Satisfactory aberto em modo janela, na resolução que vai usar:
uv run python capture_template.py
```

**Antes de rodar o worker, verifique os templates:**

```bash
uv run python debug_run.py --scan
```

Isso escaneia a tela atual e salva um screenshot anotado em `debug_screenshots/` mostrando o que foi detectado.

### 5. Rodar o worker

```bash
uv run python workers/worker.py
```

### 6. Disparar workflows

```bash
# Farm de gifts
temporal workflow start \
  --workflow-type GiftFarmWorkflow \
  --task-queue satisfactory-bot \
  --input '{"ammo_per_craft": 50, "screenshot_every_cycles": 10}'

# Patrulha de combate
temporal workflow start \
  --workflow-type CombatPatrolWorkflow \
  --task-queue satisfactory-bot \
  --input '{"max_kills": 30, "screenshot_every_kills": 5}'

# Sessão completa
temporal workflow start \
  --workflow-type AfkSessionWorkflow \
  --task-queue satisfactory-bot \
  --input '{"gift_cycles": 10, "combat_kills_per_rotation": 5, "total_rotations": 20, "screenshot_every_rotations": 1}'
```

---

## Controle em runtime

Enquanto o workflow roda, você pode controlá-lo sem reiniciar:

```bash
# Pausar (termina o ciclo atual e espera)
temporal workflow signal --workflow-id <id> --name pause

# Retomar
temporal workflow signal --workflow-id <id> --name resume

# Encerrar graciosamente (sem matar no meio de uma activity)
temporal workflow signal --workflow-id <id> --name stop

# Ver estatísticas em tempo real (sem pausar)
temporal workflow query --workflow-id <id> --query-type get_stats
# Retorna: {"gifts": 42, "ammo_crafted": 150, "cycles": 30, "status": "running"}
```

---

## Debug e verificação visual

### Script de debug standalone (sem Temporal)

```bash
# Escaneia todos os templates na tela atual
uv run python debug_run.py --scan

# Procura um template específico
uv run python debug_run.py --find gift_prompt

# Testa com threshold menor (útil para inimigos em movimento)
uv run python debug_run.py --find enemy_spitter --threshold 0.65

# Screenshot simples da tela atual
uv run python debug_run.py --screenshot
```

Todos os outputs ficam em `debug_screenshots/` com timestamp.

### Screenshots automáticos

Os workflows tiram screenshots automaticamente em situações importantes:

| Evento | Arquivo gerado |
|---|---|---|
| Erro em qualquer activity | `error_{activity_name}_TIMESTAMP.png` |
| Inventário cheio detectado | `inv_full_cycle_N_TIMESTAMP.png` |
| Personagem morreu | `player_death_TIMESTAMP.png` |
| Botão de respawn não encontrado | `respawn_not_found_TIMESTAMP.png` |
| A cada N ciclos de gift farm | `gift_cycle_N_TIMESTAMP.png` |
| A cada N kills de combate | `kill_N_TIMESTAMP.png` |
| A cada N rotações (AfkSession) | `rotation_N_TIMESTAMP.png` |

### UI do Temporal

Acesse **http://localhost:8233** enquanto o worker roda:

- Timeline de execução de cada workflow
- Qual activity falhou e com qual erro
- Quantas tentativas de retry foram feitas
- Input e output de cada step

### CLI do Temporal

```bash
# Lista todos os workflows ativos
temporal workflow list

# Histórico completo de um workflow (cada activity, input, output, retries)
temporal workflow show --workflow-id <id>

# Terminar forçado (use `stop` signal de preferência)
temporal workflow terminate --workflow-id <id> --reason "motivo"
```

### Derrubar os containers

```bash
# Para (mantém dados)
docker compose down

# Reset total (apaga banco do Temporal)
docker compose down -v
```

---

## Calibração

### 1. Sensitivity factor (mira)

Em `utils/input.py`, `aim_at_screen_position` tem um `sensitivity_factor`.  
Teste empiricamente: rode `debug_run.py --find enemy_spitter`, veja onde o template foi detectado,
e ajuste o factor até a mira acertar.

### 2. Thresholds de template

| Elemento | Threshold recomendado | Motivo |
|---|---|---|
| Menus estáticos (workshop, craft) | 0.85–0.90 | Posição fixa na tela |
| Gifts, prompts de interação | 0.80–0.85 | Variam pouco |
| Inimigos | 0.65–0.70 | Se movem, silhueta muda |
| Barra de vida baixa | 0.75–0.80 | Cor varia com dano progressivo |

Ajuste em `activities/game_activities.py` no `get_vision()` ou nos `v.find()` individuais.

### 3. Durações de movimento (navegação)

Em `activities/game_activities.py`, `navigate_to_equipment_workshop` usa durações em segundos.  
Teste com `debug_run.py --find equipment_workshop_prompt` após se mover para calibrar.

---

## Estrutura do projeto

```
satisfactory-ai/
├── activities/
│   └── game_activities.py     # ações atômicas (collect, craft, fight, loot, screenshot)
├── workflows/
│   └── satisfactory_workflows.py  # lógica + signals pause/resume/stop + queries
├── workers/
│   └── worker.py              # ponto de entrada do Temporal
├── utils/
│   ├── vision.py              # captura + template matching
│   ├── input.py               # mouse/teclado via DirectInput
│   └── screenshot.py          # debug screenshots com timestamp
├── templates/                 # PNGs dos elementos do jogo (você cria)
├── debug_screenshots/         # screenshots gerados em runtime (gitignored)
├── capture_template.py        # cria os templates
├── debug_run.py               # testa templates sem o Temporal rodando
├── pyproject.toml             # dependências (uv)
└── docker-compose.yml         # Temporal + PostgreSQL + UI
```

---

## Limitações conhecidas

- **Navegação:** usa sequências de teclas gravadas, não pathfinding. Se um bicho empurrar o personagem, a rota para o Workshop pode falhar. O Temporal faz retry automaticamente.
- **Combate:** targeting funciona bem para inimigos lentos. Spitters rápidos em movimento podem não ser atingidos consistentemente.
- **Resolução:** templates capturados em 1920×1080 não funcionam em outra resolução. Recapture se mudar.
