from pydantic_settings import BaseSettings


class CiBotSettings(BaseSettings):
    model_config = {
        "env_prefix": "CIBOT_",
    }

    BACKEND: str = "github"
    STORAGE: str = "github_issue"


class GithubSettings(BaseSettings):
    model_config = {
        "env_prefix": "CIBOT_GITHUB_",
    }
    TOKEN: str | None = None
    REPO_SLUG: str | None = None
