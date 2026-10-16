import os
from pathlib import Path
from typing import MutableMapping

ROOT = Path(__file__).resolve().parents[1]
PROJECT_ROOT = ROOT.parent
DOTENV_VARIABLES = frozenset(
    {
        "AEGIS_ENV",
        "AEGIS_DEMO_ENABLED",
        "AGIES_SECRET",
        "AEGIS_ALLOWED_ORIGINS",
        "AEGIS_AI_MODE",
        "AEGIS_AI_PROVIDER",
        "AEGIS_KYC_VISION",
        "ANTHROPIC_API_KEY",
        "ANTHROPIC_MODEL",
        "AEGIS_OPENAI_API_KEY",
        "AEGIS_OPENAI_MODEL",
        "OPENAI_API_KEY",
        "OPENAI_MODEL",
        "GEMINI_API_KEY",
        "GOOGLE_API_KEY",
        "GEMINI_MODEL",
        "OPENROUTER_API_KEY",
        "OPENROUTER_MODEL",
        "GOOGLE_CLOUD_PROJECT",
        "FIRESTORE_DATABASE",
        "FIRESTORE_AGENT_NOTIFICATIONS",
        "DATABASE_URL",
        "AEGIS_STORAGE_BACKEND",
        "FIRESTORE_EMULATOR_HOST",
        "AEGIS_WORKER_ENABLED",
        "AEGIS_SCHEDULER_TOKEN",
    }
)


def load_project_env(
    path: Path = PROJECT_ROOT / ".env", environ: MutableMapping[str, str] | None = None
) -> set[str]:
    """Load only supported application settings; injected settings always win.

    This intentionally does not execute shell syntax, expand substitutions,
    change process/proxy/tool settings, or log any setting value. Plain values,
    optional export prefixes, quoted values and inline comments are supported.
    """
    import re

    target = os.environ if environ is None else environ
    try:
        if not path.is_file():
            return set()
        content = path.read_text(encoding="utf-8-sig")
    except (OSError, UnicodeError):
        raise RuntimeError(
            "The project .env file could not be read; check its permissions and UTF-8 encoding."
        ) from None
    loaded = set()
    for line_number, raw_line in enumerate(content.splitlines(), 1):
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("export "):
            line = line[7:].lstrip()
        name, separator, raw_value = line.partition("=")
        name = name.strip()
        if not separator or name not in DOTENV_VARIABLES or name in target:
            continue
        value = raw_value.strip()
        if value.startswith(('"', "'")):
            quote = value[0]
            # Quotes are literal: no shell escapes or variable expansion.
            end = value.find(quote, 1)
            if end < 0 or (
                value[end + 1 :].strip()
                and not value[end + 1 :].lstrip().startswith("#")
            ):
                raise RuntimeError(
                    f"The project .env file contains invalid quoting on line {line_number}."
                )
            value = value[1:end]
        else:
            value = re.split(r"\s+#", value, maxsplit=1)[0].rstrip()
        if "\x00" in value:
            raise RuntimeError(
                f"The project .env file contains an invalid value on line {line_number}."
            )
        target[name] = value
        loaded.add(name)
    return loaded


load_project_env()


def openai_key_configured() -> bool:
    return bool(
        os.getenv("AEGIS_OPENAI_API_KEY", "").strip()
        or os.getenv("OPENAI_API_KEY", "").strip()
    )


def _automatic_provider() -> str:
    # Existing provider priority is stable; Gemini activates when it is the available key.
    if os.getenv("ANTHROPIC_API_KEY", "").strip():
        return "claude"
    if openai_key_configured():
        return "openai"
    if os.getenv("OPENROUTER_API_KEY", "").strip():
        return "openrouter"
    return "gemini" if gemini_key_configured() else "local"


def gemini_key_configured() -> bool:
    return bool(
        os.getenv("GEMINI_API_KEY", "").strip()
        or os.getenv("GOOGLE_API_KEY", "").strip()
    )


def resolve_mode(variable: str, *, default: str = "auto") -> str:
    requested = os.getenv(variable, default).strip().lower()
    if requested not in {"auto", "local", "claude", "openai", "gemini", "openrouter"}:
        raise RuntimeError(
            f"{variable} must be auto, local, claude, openai, gemini or openrouter"
        )
    if requested == "auto":
        return _automatic_provider()
    return requested


def resolve_ai_mode() -> str:
    if "AEGIS_AI_PROVIDER" in os.environ:
        return resolve_mode("AEGIS_AI_PROVIDER")
    return resolve_mode("AEGIS_AI_MODE")


def resolve_kyc_mode() -> str:
    requested = os.getenv("AEGIS_KYC_VISION", "auto").strip().lower()
    if requested == "auto":
        selected = resolve_ai_mode()
        return selected if selected in {"claude", "openai", "gemini"} else "local"
    if requested == "openrouter":
        raise RuntimeError("AEGIS_KYC_VISION does not support openrouter; choose local, claude, openai, gemini or auto")
    return resolve_mode("AEGIS_KYC_VISION")


ENV = os.getenv("AEGIS_ENV", "development")
PRODUCTION = ENV in {"production", "demo"}
DEMO_ENABLED = (
    os.getenv("AEGIS_DEMO_ENABLED", "false" if PRODUCTION else "true").lower() == "true"
)
DATABASE_URL = os.getenv("DATABASE_URL", f"sqlite:///{ROOT / 'data' / 'aegis.db'}")
if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = "postgresql+psycopg://" + DATABASE_URL[len("postgres://") :]
elif DATABASE_URL.startswith("postgresql://"):
    DATABASE_URL = "postgresql+psycopg://" + DATABASE_URL[len("postgresql://") :]
SECRET = os.getenv("AGIES_SECRET", "local-demo-secret-change-in-production")
ALLOWED_ORIGINS = [
    x.strip()
    for x in os.getenv(
        "AEGIS_ALLOWED_ORIGINS",
        "http://localhost:3000,http://127.0.0.1:3000,http://localhost:8000,http://127.0.0.1:8000",
    ).split(",")
    if x.strip()
]
SESSION_SECONDS = 8 * 60 * 60
MAX_UPLOAD = 5 * 1024 * 1024
AI_MODE = resolve_ai_mode()
KYC_MODE = resolve_kyc_mode()


def validate_configuration():
    if ENV not in {"development", "test", "production", "demo"}:
        raise RuntimeError("AEGIS_ENV must be development, test, demo or production")
    storage = os.getenv("AEGIS_STORAGE_BACKEND", "firestore")
    if storage not in {"firestore", "memory"}:
        raise RuntimeError("AEGIS_STORAGE_BACKEND must be firestore or memory")
    if storage == "firestore" and not os.getenv("GOOGLE_CLOUD_PROJECT", "").strip():
        raise RuntimeError("Firestore requires GOOGLE_CLOUD_PROJECT")
    if (
        resolve_ai_mode() == "claude" or resolve_kyc_mode() == "claude"
    ) and not os.getenv("ANTHROPIC_API_KEY", "").strip():
        raise RuntimeError("Claude mode requires ANTHROPIC_API_KEY")
    if (
        resolve_ai_mode() == "openai" or resolve_kyc_mode() == "openai"
    ) and not openai_key_configured():
        raise RuntimeError(
            "OpenAI mode requires AEGIS_OPENAI_API_KEY (or the local OPENAI_API_KEY alias)"
        )
    if (
        resolve_ai_mode() == "gemini" or resolve_kyc_mode() == "gemini"
    ) and not gemini_key_configured():
        raise RuntimeError("Gemini mode requires GEMINI_API_KEY or GOOGLE_API_KEY")
    if resolve_ai_mode() == "openrouter" and not os.getenv("OPENROUTER_API_KEY", "").strip():
        raise RuntimeError("OpenRouter mode requires OPENROUTER_API_KEY")
    if os.getenv("FIRESTORE_AGENT_NOTIFICATIONS", "false").lower() == "true" and not os.getenv(
        "GOOGLE_CLOUD_PROJECT", ""
    ).strip():
        raise RuntimeError(
            "Firestore agent notifications require GOOGLE_CLOUD_PROJECT"
        )
    if PRODUCTION:
        if DEMO_ENABLED and ENV == "production":
            raise RuntimeError("Demo data and simulator must be disabled in production")
        if (
            len(SECRET) < 32
            or not SECRET.strip()
            or SECRET == "local-demo-secret-change-in-production"
            or SECRET.upper().startswith(("REPLACE_", "CHANGE_ME", "YOUR_SECRET"))
        ):
            raise RuntimeError(
                "Production requires a strong AGIES_SECRET of at least 32 characters"
            )
        if storage != "firestore" or os.getenv("FIRESTORE_EMULATOR_HOST"):
            raise RuntimeError("Hosted environments require live Firestore, never memory or the emulator")
        if not ALLOWED_ORIGINS or any(
            not x.startswith("https://") or "*" in x for x in ALLOWED_ORIGINS
        ):
            raise RuntimeError(
                "Production requires explicit HTTPS AEGIS_ALLOWED_ORIGINS"
            )
