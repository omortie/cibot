from pydantic_settings import BaseSettings


class CiBotSettings(BaseSettings):
	model_config = {
		"env_prefix": "CIBOT_",
	}

	BACKEND: str = "github"
	STORAGE: str = "github_issue"
