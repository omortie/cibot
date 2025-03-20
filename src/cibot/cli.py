import itertools
from functools import cache
from pathlib import Path
from typing import TYPE_CHECKING, Annotated

import jinja2
import msgspec
import typer
from loguru import logger
from typer import Typer

from cibot.backends.base import CiBotBackendBase
from cibot.plugins.base import CiBotPlugin, VersionBumpPlugin
from cibot.plugins.diffcov import DiffCovPlugin
from cibot.plugins.semver import SemverPlugin
from cibot.settings import CiBotSettings
from cibot.storage_layers.base import BaseStorage

from .plugins.deferred_release import DeferredReleasePlugin

if TYPE_CHECKING:
	from github.Repository import Repository


app = Typer(name="management")
template_env = jinja2.Environment(
	loader=jinja2.FileSystemLoader(Path(__file__).parent / "templates"),
	autoescape=jinja2.select_autoescape(),
)


@cache
def get_github_repo() -> "Repository":
	from github import Github

	from cibot.backends.github_backend import GithubSettings

	settings = GithubSettings()
	if not settings.TOKEN:
		raise ValueError("missing GITHUB_TOKEN")
	if not settings.REPO_SLUG:
		raise ValueError("missing GITHUB_REPO_SLUG")
	client = Github(settings.TOKEN)
	return client.get_repo(settings.REPO_SLUG)


def get_storage() -> BaseStorage:
	settings = CiBotSettings()
	match settings.STORAGE:
		case "github_issue":
			from cibot.storage_layers.github_issue import GithubIssueStorage

			repo = get_github_repo()
			return GithubIssueStorage(repo)
		case _:
			raise ValueError(f"Unknown storage {settings.STORAGE}")


def get_backend(pr_number: int | None) -> CiBotBackendBase:
	settings = CiBotSettings()
	backend_name = settings.BACKEND
	if not backend_name:
		raise ValueError("BACKEND environment variable is not set")
	match backend_name:
		case "github":
			from cibot.backends.github_backend import GithubBackend, GithubSettings

			repo = get_github_repo()
			storage = get_storage()
			return GithubBackend(repo, storage, pr_number=pr_number, settings=GithubSettings())
		case _:
			raise ValueError(f"Unknown backend {backend_name}")


PLUGINS_REGISTRY = {
	"deferred_release": DeferredReleasePlugin,
	"semver": SemverPlugin,
	"diffcov": DiffCovPlugin,
}


def get_plugins(
	plugins: list[str], backend: CiBotBackendBase, storage: BaseStorage
) -> list[CiBotPlugin]:
	out = []
	for name in plugins:
		logger.info(f"Loading plugin {name}")
		out.append(PLUGINS_REGISTRY[name](backend, storage))
		if name not in PLUGINS_REGISTRY:
			raise ValueError(f"Unknown plugin {name}")
	return out


class ReleasePrMarker(msgspec.Struct):
	"""Mark a release PR workflow as already ran"""

	pr: int
	bump_type: str

	def as_key(self) -> str:
		return f"release-pr-{self.pr}-{self.bump_type}"


class PluginRunner:
	def __init__(
		self,
		plugins: list[CiBotPlugin],
		backend: CiBotBackendBase,
		storage: BaseStorage,
	) -> None:
		self.backend = backend
		self.storage = storage
		self.plugins = plugins
		self.backend.configure_git()

	def on_pr_changed(self, pr: int):
		results = [plugin.on_pr_changed(pr) for plugin in self.plugins]

		if release_type := next((res for res in results if res is not None), None):
			# find plugin for release_type
			version_bump_plugin = next(
				plugin for plugin in self.plugins if isinstance(plugin, VersionBumpPlugin)
			)
			logger.info(f"Found version bump plugin: {version_bump_plugin.plugin_name()}")
			next_version = version_bump_plugin.next_version(release_type)
			release_marker = ReleasePrMarker(pr, bump_type=release_type.name)
			if self.storage.get(release_marker.as_key(), ReleasePrMarker):
				logger.info(f"Release workflow for PR #{pr} already ran")
				return

			logger.info(f"next version is {next_version}")
			git_changes = list(
				itertools.chain(
					*[plugin.prepare_release(release_type, next_version) for plugin in self.plugins]
				)
			)
			logger.info(f"commiting {git_changes} changes")
			if git_changes:
				for change in git_changes:
					self.backend.git("add", str(change))
				self.backend.git("commit", "-m", f"Prepare release for PR #{pr}")
				self.backend.git("push")

			self.storage.set(release_marker.as_key(), release_marker)
		self.comment_on_pr(pr)
		self.check_for_errors()

	def on_commit_to_main(self):
		release_infos = [
			plugin.on_commit_to_main(self.backend.get_current_commit_hash())
			for plugin in self.plugins
		]
		release_info = next((info for info in release_infos if info), None)
		if release_info:
			self.backend.publish_release(release_info)
		self.check_for_errors()

	def check_for_errors(self):
		for plugin in self.plugins:
			if plugin.should_fail_workflow():
				raise ValueError(f"Plugin {plugin.plugin_name()} failed")

	def comment_on_pr(self, pr: int):  # sourcery skip: use-join
		plugin_comments = {
			plugin.plugin_name(): plugin.provide_comment_for_pr() for plugin in self.plugins
		}
		for plugin_name, comment in plugin_comments.items():
			if comment:
				self.backend.upsert_pr_comment(comment[0], comment_id=comment[1])


def get_runner(plugins: list[str], pr_number: int | None = None) -> PluginRunner:
	backend = get_backend(pr_number)
	storage = get_storage()
	return PluginRunner(get_plugins(plugins, backend, storage), backend, storage)


EMPTY_LIST = []


@app.command()
def on_pr_changed(pr: int, plugin: Annotated[list[str], typer.Option()]):
	runner = get_runner(plugin, pr_number=pr)
	runner.on_pr_changed(pr)


@app.command()
def on_commit_to_main(plugin: Annotated[list[str], typer.Option()]):
	runner = get_runner(plugin)
	runner.on_commit_to_main()


def main():
	app()
