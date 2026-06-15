"""
utils/config.py
Carrega config.toml e fornece acesso tipado por caminho de chave.
"""
import tomllib
from pathlib import Path
from typing import Any

_CONFIG_PATH = Path(__file__).parent.parent / "config.toml"
_cache: dict | None = None


def load() -> dict:
    global _cache
    if _cache is None:
        if not _CONFIG_PATH.exists():
            raise FileNotFoundError(
                f"config.toml não encontrado em {_CONFIG_PATH}.\n"
                "O arquivo deve existir na raiz do projeto."
            )
        with open(_CONFIG_PATH, "rb") as f:
            _cache = tomllib.load(f)
    return _cache


def get(key_path: str, default: Any = None) -> Any:
    """Retorna valor por caminho com ponto. Ex: get('vision.default_threshold')"""
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
    """Invalida o cache — útil em testes."""
    global _cache
    _cache = None
