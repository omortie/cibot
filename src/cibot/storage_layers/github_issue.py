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
    
class Bucket(msgspec.Struct):
    plugin_srorage: dict[str, bytes]


class GithubIssueStorage(BaseStorage):
    def __init__(self, repo: Repository) -> None:
        settings = Settings()
        if not settings.number:
            raise ValueError("missing STORAGE_ISSUE_NUMBER")
        issue = repo.get_issue(settings.number)
        logger.info(f"Found issue {issue.title}")    
        self.issue = issue

    def get_json_part_from_comment(self) -> Bucket | None:
        body = self.issue.body
        with contextlib.suppress(Exception):
            return msgspec.json.decode(body.split("```json")[1].split("```")[0].strip(), type=Bucket)

    def get[T](self, key: str, type_: type[T]) -> T | None:
        if bucket := self.get_json_part_from_comment():
            return msgspec.json.decode(bucket.plugin_srorage[key], type=type_)
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
        if bucket := self.get_json_part_from_comment():
            bucket.plugin_srorage[key] = raw
            new_comment = comment_base.format(msgspec.json.encode(bucket))
        else:
            new_comment = comment_base.format(msgspec.json.encode(Bucket(plugin_srorage={key: raw})))
        self.issue.edit(body=new_comment)
