def create_adapter(connection_type: str, config: dict, secrets: dict | None = None):
    """Lazy import keeps parser/catalog utilities usable without HTTP extras."""
    from .factory import create_adapter as factory

    return factory(connection_type, config, secrets)


__all__ = ["create_adapter"]
