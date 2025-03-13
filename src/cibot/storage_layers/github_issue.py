import contextlib
import json

from loguru import logger
import msgspec
from pydantic_settings import BaseSettings
from github.Repository import Repository
from cibot.storage_layers.base import BaseStorage


class Settings(BaseSettings):
    model_config = {
        "env_prefix": "CIBOT_STORAGE_GH_ISSUE_",
    }
    number: int | None = None
    
    
class GithubIssueStorage(BaseStorage):
    def __init__(self, repo: Repository) -> None:
        settings = Settings()
        if not settings.number:
            raise ValueError("missing STORAGE_ISSUE_NUMBER")
        issue = repo.get_issue(settings.number)
        logger.info(f"Found issue {issue.title}")    
        self.issue = issue

    def get_json_part_from_comment(self) -> dict[str, bytes] | None:
        body = self.issue.body
        with contextlib.suppress(Exception):
            return json.loads(body.split("```json")[1].split("```")[0].strip())

    def get[T](self, key: str, type_: type[T]) -> T | None:
        if raw := self.get_json_part_from_comment():
            return msgspec.json.decode(raw[key], type=type_)
        return None


    def set(self, key: str, value: msgspec.Struct) -> None:
        raw = msgspec.json.encode(value)
        comment_base = """
        ### CIBot Storage Layer
        ### Do not edit this comment
        ```json
        {}
        ```
        """
        if exists := self.get_json_part_from_comment():
            exists[key] = raw
            new_comment = comment_base.format(json.dumps(exists))
        else:
            new_comment = comment_base.format(json.dumps({key: raw}))
        self.issue.edit(body=new_comment)
