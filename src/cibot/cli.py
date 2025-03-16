import itertools
from functools import cache
from pathlib import Path
from typing import TYPE_CHECKING, Annotated

from cibot.plugins.semver import SemverPlugin
import jinja2
import msgspec
import typer
from loguru import logger
from typer import Typer

from cibot.backends.base import CiBotBackendBase
from cibot.plugins.base import CiBotPlugin, VersionBumpPlugin
from cibot.settings import CiBotSettings, GithubSettings
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
			from cibot.backends.github_backend import GithubBackend

			repo = get_github_repo()
			storage = get_storage()
			return GithubBackend(repo, storage, pr_number=pr_number)
		case _:
			raise ValueError(f"Unknown backend {backend_name}")


PLUGINS_REGISTRY = {
	"deferred_release": DeferredReleasePlugin,
	"semver": SemverPlugin,
	
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
	version: str

	def as_key(self) -> str:
		return f"release-pr-{self.pr}-{self.version}"


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
		self.backend.configure_git("cibot", "cibot@no.reply")

	def on_pr_changed(self, pr: int):
		results = [plugin.on_pr_changed(pr) for plugin in self.plugins]
		self.check_for_errors()

		if release_type := next((res for res in results if res is not None), None):
			# find plugin for release_type
			if not (
				version_bump_plugin := next(
					plugin for plugin in self.plugins if isinstance(plugin, VersionBumpPlugin)
				)
			):
				logger.error("no plugin found for version bump")
			logger.info(f"Found version bump plugin: {version_bump_plugin.plugin_name()}")
			next_version = version_bump_plugin.next_version(release_type)
			release_marker = ReleasePrMarker(pr, next_version)
			if self.storage.get(release_marker.as_key(), ReleasePrMarker):
				logger.info(f"Release workflow for PR #{pr} already ran")
				return

			logger.info(f"next version is {next_version}")
			git_changes = itertools.chain(
				plugin.prepare_release(release_type, next_version) for plugin in self.plugins
			)


			if list(git_changes):
				for change in git_changes:
					self.backend.git("add", str(change))
				self.backend.git("commit", "-m", f"Prepare release for PR #{pr}")
			self.check_for_errors()
			self.backend.git("push")
			self.storage.set(release_marker.as_key(), release_marker)
			self.comment_on_pr(pr)

	def on_commit_to_main(self):
		for plugin in self.plugins:
			plugin.on_commit_to_main(self.backend.get_current_commit_hash())
		self.check_for_errors()

	def check_for_errors(self):
		for plugin in self.plugins:
			if plugin.should_fail_workflow():
				raise ValueError(f"Plugin {plugin.plugin_name()} failed")

	def comment_on_pr(self, pr: int):  # sourcery skip: use-join
		plugin_comments = {
			plugin.plugin_name(): plugin.provide_comment_for_pr() for plugin in self.plugins
		}
		content = ""
		for plugin_name, comment in plugin_comments.items():
			content += f"### {plugin_name}\n{comment}\n___\n"
		self.backend.create_pr_comment(content)


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
