"""
utils/config.py
Loads config.toml, validates its structure using Pydantic, and provides typed access.
"""

import tomllib
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

_CONFIG_PATH = Path(__file__).parent.parent / "config.toml"
_cache: dict | None = None


# --- Pydantic Models for Validation ---


class TemporalConfig(BaseModel):
    address: str = "localhost:7233"
    namespace: str = "default"
    task_queue: str = "satisfactory-bot"
    persist_task_queue: str = "satisfactory-persist"


class InputConfig(BaseModel):
    cursor_step: int = 2
    cursor_step_pause: float = 0.012
    fail_safe_key: str = "F9"


class RegionConfig(BaseModel):
    x: int
    y: int
    w: int
    h: int


class VisionRegionsConfig(BaseModel):
    inventory_open: RegionConfig | None = None
    doggo_loot_window: RegionConfig | None = None
    pause_menu: RegionConfig | None = None


class VisionConfig(BaseModel):
    monitor_index: int = 1
    default_threshold: float = 0.82
    thresholds: dict[str, float] = Field(default_factory=dict)
    regions: VisionRegionsConfig = Field(default_factory=VisionRegionsConfig)


class HarvestingConfig(BaseModel):
    swing_interval_seconds: float = 0.5


class DoggoConfig(BaseModel):
    name: str
    turn_dx: int = 0


class ScheduleConfig(BaseModel):
    start_time: str = "08:00"
    stop_time: str = "23:00"
    timezone: str = "America/Sao_Paulo"


class TamingConfig(BaseModel):
    drop_point_x: int = 1280
    drop_point_y: int = 720
    micro_yaw_step: int = 40
    micro_yaw_count: int = 4
    home_pitch_down: int = 400
    max_consecutive_misses: int = 3
    name_region_x: int = 740
    name_region_y: int = 180
    name_region_w: int = 560
    name_region_h: int = 60
    tooltip_dx: int = 30
    tooltip_dy: int = 10
    tooltip_w: int = 520
    tooltip_h: int = 140
    tooltip_hover_seconds: float = 0.6
    search_yaw_step: int = 180
    search_yaw_count: int = 8
    search_pitch_rows: list[int] = Field(default_factory=list)
    doggo_loot_slot_x: int = 995
    doggo_loot_slot_y: int = 1045
    loot_slot_patch_half_w: int = 50
    loot_slot_patch_half_h: int = 55
    loot_slot_diff_threshold: float = 12.0
    doggos: list[DoggoConfig] = Field(default_factory=list)
    schedule: ScheduleConfig = Field(default_factory=ScheduleConfig)


class InventoryGridConfig(BaseModel):
    origin_x: int = 568
    origin_y: int = 330
    slot_w: int = 32
    slot_h: int = 32
    columns: int = 10
    rows: int = 5


class InventorySortButtonConfig(BaseModel):
    x: int = 630
    y: int = 575


class InventoryConfig(BaseModel):
    empty_slot_brightness: int = 80


class NavigationConfig(BaseModel):
    to_workshop_forward_1: float = 1.2
    to_workshop_strafe_right: float = 0.8
    to_workshop_forward_2: float = 0.5
    back_to_base_backward_1: float = 1.2
    back_to_base_strafe_left: float = 0.8
    back_to_base_backward_2: float = 0.5


class LocationStepConfig(BaseModel):
    key: str
    duration: float


class LocationConfig(BaseModel):
    arrival_timeout: float = 5.0
    arrival_template: str | None = None
    steps: list[LocationStepConfig] = Field(default_factory=list)


class ExplorationRouteConfig(BaseModel):
    keys: list[str] = Field(default_factory=list)
    duration: float
    turn_dx: int = 0


class ExplorationConfig(BaseModel):
    max_total_duration_seconds: float = 25.0
    screenshot_every_leg: bool = True
    gauge_low_abort: float = 0.25
    health_low_frac: float = 0.4
    check_interval_seconds: float = 1.0
    ascend_every_chunks: int = 2
    ascend_pulse_seconds: float = 0.3
    route: list[ExplorationRouteConfig] = Field(default_factory=list)


class CombatAmmoRegionConfig(BaseModel):
    x: int = 2360
    y: int = 1320
    w: int = 100
    h: int = 40


class CombatConfig(BaseModel):
    aim_sensitivity_factor: float = 0.8
    shoot_bursts: int = 5
    shoot_interval_seconds: float = 0.08
    max_combat_duration_seconds: float = 10.0
    dodge_direction: str = "a"
    low_ammo_threshold: int = 20
    ammo_region: CombatAmmoRegionConfig = Field(default_factory=CombatAmmoRegionConfig)


class DisplayConfig(BaseModel):
    screen_width: int = 2560
    screen_height: int = 1440


class LoggingConfig(BaseModel):
    level: str = "INFO"


class AppConfig(BaseModel):
    temporal: TemporalConfig = Field(default_factory=TemporalConfig)
    input: InputConfig = Field(default_factory=InputConfig)
    vision: VisionConfig = Field(default_factory=VisionConfig)
    harvesting: HarvestingConfig = Field(default_factory=HarvestingConfig)
    taming: TamingConfig = Field(default_factory=TamingConfig)
    inventory_grid: InventoryGridConfig = Field(default_factory=InventoryGridConfig)
    inventory_sort_button: InventorySortButtonConfig = Field(default_factory=InventorySortButtonConfig)
    inventory: InventoryConfig = Field(default_factory=InventoryConfig)
    navigation: NavigationConfig = Field(default_factory=NavigationConfig)
    locations: dict[str, LocationConfig] = Field(default_factory=dict)
    exploration: ExplorationConfig = Field(default_factory=ExplorationConfig)
    combat: CombatConfig = Field(default_factory=CombatConfig)
    display: DisplayConfig = Field(default_factory=DisplayConfig)
    logging: LoggingConfig = Field(default_factory=LoggingConfig)


def load() -> dict:
    global _cache
    if _cache is None:
        if not _CONFIG_PATH.exists():
            raise FileNotFoundError(
                f"config.toml not found at {_CONFIG_PATH}.\nThe file must exist at the project root."
            )
        with open(_CONFIG_PATH, "rb") as f:
            raw_data = tomllib.load(f)
        # Validate using Pydantic and dump to dict
        validated = AppConfig.model_validate(raw_data)
        _cache = validated.model_dump()
    return _cache


def get(key_path: str, default: Any = None) -> Any:
    """Returns a value by dotted path. Ex: get('vision.default_threshold')"""
    try:
        cfg = load()
    except FileNotFoundError:
        return default

    val: Any = cfg
    for k in key_path.split("."):
        if not isinstance(val, dict) or k not in val:
            return default
        val = val[k]
    return val


def reload() -> None:
    """Invalidates the cache — useful in tests."""
    global _cache
    _cache = None
