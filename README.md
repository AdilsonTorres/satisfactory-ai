# Satisfactory AFK Bot + Temporal

Bot local para farm AFK no Satisfactory. Sem cloud, sem LLM em loop.  
Orquestração via Temporal para retries automáticos, histórico detalhado de execuções e debug visual.

> **Requisito de SO:** Linux (X11 / Xwayland).

## Stack

| Componente | Lib / Ferramenta | Por quê |
|---|---|---|
| Captura de tela | `mss` | ~1ms por frame |
| Detecção visual | `opencv-python` | Template matching, zero treinamento |
| Inputs 3D | `pynput` | Emulação de mouse e teclado compatível com Linux (X11/Xwayland) |
| Foco de Janela | `xdotool` | Busca e ativa a janela do jogo automaticamente |
| OCR (inventário) | `pytesseract` | Leitura visual de quantidades de itens no inventário |
| Orquestração | `temporalio` | Retry estruturado, controle de fluxo (pausa/resume/stop) e persistência |
| Pacotes | `uv` | Gerenciamento rápido de dependências Python |
| Serviços Temporal | Docker Compose | PostgreSQL + Temporal Server + Temporal Web UI |

---

## Setup

### 1. Pré-requisitos (Linux)

- [uv](https://docs.astral.sh/uv/getting-started/installation/)
- [Docker](https://docs.docker.com/engine/install/) (com Compose V2)
- Python 3.11+
- `xdotool` no PATH
- `tesseract-ocr` no PATH
- `imagemagick` no PATH (fallback de captura de tela usado quando `mss` falha, ex: em alguns compositores Xwayland)

No Ubuntu/Debian, você pode instalar as dependências do sistema com:
```bash
sudo apt update
sudo apt install xdotool tesseract-ocr imagemagick
```

### 2. Instalar dependências Python
Use o `uv` para sincronizar e criar o ambiente virtual:
```bash
uv sync
```

### 3. Subir os serviços do Temporal
Suba os containers do Temporal Server e PostgreSQL em segundo plano:
```bash
docker compose up -d
docker compose ps   # confirmar que os 3 serviços estão healthy/running
```

| Serviço | Porta | Descrição |
|---|---|---|
| Temporal Server | 7233 | Porta gRPC onde o worker e o cliente se conectam |
| Temporal UI | 8233 | Dashboard web local para debugar os workflows (http://localhost:8233) |
| PostgreSQL | (interna) | Armazenamento de estado e histórico de execução dos workflows |

### 4. Criar os templates
O bot utiliza imagens de template para tomar decisões na tela do jogo. Capture-os com:
```bash
# Com o Satisfactory aberto e focado:
uv run python capture_template.py
```

**Antes de iniciar o worker, verifique as correspondências de imagem:**
```bash
uv run python debug_run.py --scan
```
Isso tirará um screenshot atual da tela e salvará uma versão anotada em `debug_screenshots/` mostrando quais templates foram localizados e com qual grau de confiança.

### 5. Executar o worker
Com os serviços do Temporal rodando e os templates prontos, inicie o worker:
```bash
uv run python workers/worker.py
```

### 6. Disparar workflows
Dispare os workflows através da CLI do Temporal:

```bash
# Farm de gifts dos Lizard Doggos
temporal workflow start \
  --workflow-type GiftFarmWorkflow \
  --task-queue satisfactory-bot \
  --input '{"ammo_per_craft": 50, "screenshot_every_cycles": 10}'

# Patrulha de combate estática
temporal workflow start \
  --workflow-type CombatPatrolWorkflow \
  --task-queue satisfactory-bot \
  --input '{"max_kills": 30, "screenshot_every_kills": 5}'

# Sessão AFK completa (alterna Gift Farm e Combate)
temporal workflow start \
  --workflow-type AfkSessionWorkflow \
  --task-queue satisfactory-bot \
  --input '{"gift_cycles": 10, "combat_kills_per_rotation": 5, "total_rotations": 20, "screenshot_every_rotations": 1}'

# Colheita manual de um node de recurso (jogador já posicionado no alcance)
temporal workflow start \
  --workflow-type ResourceHarvestWorkflow \
  --task-queue satisfactory-bot \
  --input '{"swings_per_cycle": 20, "cycles": 0, "screenshot_every_cycles": 10}'

# Domesticação de Lizard Doggo selvagem (best-effort, revisar screenshots)
temporal workflow start \
  --workflow-type TameDoggoWorkflow \
  --task-queue satisfactory-bot \
  --input '{"max_attempts": 5, "seconds_between_attempts": 15}'

# Expedição de combate: vai a um local, mata, reabastece munição se preciso,
# volta e guarda o loot num storage
temporal workflow start \
  --workflow-type CombatExpeditionWorkflow \
  --task-queue satisfactory-bot \
  --input '{"location": "example_kill_zone", "max_kills": 10, "min_ammo_to_depart": 20, "ammo_per_craft": 50}'
```

### Calibrando o CombatExpeditionWorkflow

Esse workflow precisa de mais calibração manual do que os outros porque
generaliza navegação para **locais arbitrários**, não só o Workshop fixo:

1. **Locais** (`config.toml [locations.<nome>]`): duplique o bloco
   `example_kill_zone` para cada zona de combate que quiser, com a sequência
   real de tecla/duração até lá partindo da base. Ajuste também `base` com o
   caminho de volta. `arrival_template` é opcional — sem ele, a navegação é
   "às cegas" como o `navigate_to_equipment_workshop` original.
2. **Munição** (`config.toml [combat.ammo_region]`): região da tela onde o
   contador de munição aparece no HUD da arma, para o OCR ler. Tire um
   screenshot (`debug_run.py --screenshot`) e meça x,y,w,h em pixels. Se não
   calibrar, `check_ammo_count` retorna -1 e o workflow ignora o gating de
   munição (não bloqueia, mas também não reabastece sozinho).
3. **Storage** (`templates/storage_prompt.png`, `templates/storage_open.png`):
   capture com `capture_template.py` olhando para um storage container e
   com o container aberto.
4. **Grid de inventário** (`config.toml [inventory_grid]`): coordenadas do
   primeiro slot e espaçamento entre slots, usadas pelo shift-click que
   deposita o loot. Esse passo é best-effort — `open_storage_and_deposit_loot`
   não verifica se a transferência funcionou, só que o storage abriu.

---

## Controle em runtime (Signals & Queries)

Enquanto os workflows estão rodando, você pode interagir com eles sem reiniciar o processo:

```bash
# Pausar (espera concluir a atividade atual e entra em pausa)
temporal workflow signal --workflow-id <id> --name pause

# Retomar execução
temporal workflow signal --workflow-id <id> --name resume

# Parar graciosamente (aguarda finalizar a atividade em progresso)
temporal workflow signal --workflow-id <id> --name stop

# Consultar estatísticas da sessão atual em tempo real
temporal workflow query --workflow-id <id> --query-type get_stats
```

---

## Jogando manualmente? Capture dados para melhorar o bot

Quando você está jogando normalmente (não AFK), pode rodar em paralelo um
script que **só observa a tela e nunca envia input** — seguro para deixar
aberto num terminal enquanto joga com o teclado/mouse:

```bash
# Tira um screenshot a cada 4s (default) em captures/, descartando frames
# quase idênticos ao último salvo. Ctrl+C para parar.
uv run python passive_capture.py

# Mais frequente, com limite de screenshots:
uv run python passive_capture.py --interval 2 --max-shots 300
```

Depois da sessão, revise os screenshots e recorte templates novos ou
melhores variantes dos existentes (ex: o mesmo inimigo em poses diferentes,
o Doggo selvagem, a janela de loot do Doggo):

```bash
uv run python label_captures.py
```

Para cada imagem você digita o nome do template para recortar (sobrescreve
ou cria `templates/<nome>.png`), `d` para descartar a imagem, ou Enter para
pular. Imagens já revisadas vão para `captures/_reviewed/`.

Para validar se os templates/thresholds atuais funcionam bem contra
screenshots reais de gameplay (em vez de só a tela do momento):

```bash
uv run python debug_run.py --scan-dir captures
```

Isso reporta a taxa de detecção de cada template no lote — útil para notar
thresholds desalinhados ou templates que precisam ser recapturados antes da
próxima sessão AFK.

---

## Debug e visualização

### Script de debug autônomo (sem Temporal)
```bash
# Procura e anota todos os templates na tela atual
uv run python debug_run.py --scan

# Procura um template específico
uv run python debug_run.py --find gift_prompt

# Testa a sensibilidade da busca com threshold customizado
uv run python debug_run.py --find enemy_spitter --threshold 0.65

# Apenas tira um screenshot do monitor principal
uv run python debug_run.py --screenshot
```
Todas as imagens anotadas e capturadas são salvas com timestamp no diretório `debug_screenshots/`.

### Screenshots automáticos em erros/eventos
Os workflows geram capturas automaticamente em situações relevantes:
- Falhas/Exceções em atividades: `error_{nome_atividade}_TIMESTAMP.png`
- Inventário cheio: `inv_full_cycle_N_TIMESTAMP.png`
- Morte do personagem: `player_death_TIMESTAMP.png`
- Botão de respawn ausente: `respawn_not_found_TIMESTAMP.png`

### Dashboard do Temporal UI
Abra **http://localhost:8233** no seu navegador para:
- Visualizar a linha do tempo detalhada das atividades.
- Identificar parâmetros de entrada e saída de cada passo.
- Investigar logs de erro detalhados e tentativas de retry de atividades que falharam.

---

## Calibração e Ajustes

### 1. Fator de Sensibilidade do Mouse
Em `utils/input.py`, o método `aim_at_screen_position` utiliza a propriedade `aim_sensitivity_factor` definida no `config.toml`. Ajuste-a se a mira estiver passando do alvo ou virando pouco.

### 2. Thresholds de Comparação Visual
Os limites de precisão para detectar imagens estão configurados na seção `[vision.thresholds]` no `config.toml`:
- Elementos estáticos de menu: `0.85–0.90` (alta precisão).
- Prompts de interação e botões: `0.80–0.85`.
- Inimigos móveis: `0.65–0.70` (para compensar movimentos rápidos e variações de silhueta).

### 3. Ajuste de Navegação por Teclas
Como o bot utiliza tempos de movimentação predefinidos (ex: andar para frente por 1.2s), ajuste as durações de tecla em segundos na seção `[navigation]` do `config.toml` até alinhar perfeitamente com os caminhos da sua base de operações.

---

## Limitações conhecidas
- **Navegação Cega:** O bot usa pressões de tecla de duração fixa para caminhar. Se o personagem colidir ou for empurrado por um inimigo, a rota pode desviar. O Temporal lidará com isso através do fluxo de retries das atividades falhas.
- **Combate Móvel:** O rastreamento de alvos é reativo e funciona melhor contra inimigos lentos. Inimigos rápidos (como Spitters ágeis) podem exigir mais munição.
- **Inimigos Hazard (dano em área):** Cliff Hog Nuclear (radiação) e Elite Gas Stinger (gás venenoso) não são engajados pelo loop normal de combate — o bot recua (`retreat_from_hazard`) em vez de tentar matá-los, já que o aim-and-shoot estático não é seguro contra dano em área.
- **Colheita de Recursos:** `ResourceHarvestWorkflow` não navega até o node — o jogador precisa posicionar o personagem manualmente dentro do alcance de interação antes de disparar o workflow.
- **Expedição de Combate:** `CombatExpeditionWorkflow` depende de `[locations.*]` calibrados manualmente para cada zona — sem isso, a navegação "às cegas" pode terminar em qualquer lugar. O depósito de loot via `open_storage_and_deposit_loot` é best-effort (shift-click em todo o grid do inventário, sem confirmar a transferência) e a leitura de munição via OCR pode falhar silenciosamente (retorna -1, e o workflow não bloqueia o combate nesse caso).
- **Domesticação de Doggo:** `TameDoggoWorkflow` é best-effort. O cue visual de sucesso (Doggo comendo, pulando e "chiando") é fraco demais para template matching confiável — o workflow só registra que ofereceu a berry, não que a domesticação funcionou. Revise os screenshots em `debug_screenshots/` manualmente.
- **Resolução de Tela:** Os templates capturados em uma resolução específica (ex: 1920x1080) são específicos dela. Caso altere a resolução do jogo, recapture-os.
- **Fora de escopo (não automatizável nesta arquitetura):** Hard Drives e Somersloops exigem navegação por um mapa aberto sem pathfinding (locais fixos mas distantes, muitas vezes atrás de pré-requisitos de logística); construção exige mira livre com feedback visual em tempo real do Build Gun; exploração de Power Slugs/Mercer Spheres não tem um prompt de UI fixo para ancorar a detecção. Nenhum desses é viável com visão por template matching + macros de teclado fixos.
