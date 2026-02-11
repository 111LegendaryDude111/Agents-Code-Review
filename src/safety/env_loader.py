import os


def load_env_file(path: str = ".env", override: bool = False) -> None:
    """
    Lightweight .env loader without external dependencies.
    Supports simple KEY=VALUE lines, comments (#), and optional quoted values.
    """
    if not os.path.exists(path):
        return

    try:
        with open(path, encoding="utf-8") as env_file:
            for raw_line in env_file:
                line = raw_line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue

                key, value = line.split("=", 1)
                key = key.strip()
                value = value.strip()

                if not key:
                    continue

                # Strip optional matching quotes.
                if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
                    value = value[1:-1]

                if override or key not in os.environ:
                    os.environ[key] = value
    except OSError:
        # Best-effort local loading.
        return
