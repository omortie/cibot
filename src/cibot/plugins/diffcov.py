import json
import subprocess
from dataclasses import dataclass
from io import BytesIO
from pathlib import Path
from typing import TypedDict, override

import jinja2
from diff_cover.diff_reporter import GitDiffReporter
from diff_cover.report_generator import MarkdownReportGenerator
from diff_cover.violationsreporters.violations_reporter import (
	XmlCoverageReporter,
)
from loguru import logger
from pydantic_settings import BaseSettings

from cibot.backends.base import PrReviewComment
from cibot.plugins.base import BumpType, CiBotPlugin

template_env = jinja2.Environment(
	loader=jinja2.FileSystemLoader(Path(__file__).parent / "templates"),
	autoescape=jinja2.select_autoescape(),
)

COVERAGE_TEMPLATE = template_env.get_template("coverage.jinja.md")


def _generate_section_report(
	reporter: XmlCoverageReporter, git_diff_reporter: GitDiffReporter, compare_branch: str
) -> str:
	"""Generate report for a single section."""
	with BytesIO() as buffer:
		markdown_gen = MarkdownReportGenerator(reporter, git_diff_reporter)
		markdown_gen.generate_report(buffer)
		markdown_string = buffer.getvalue().decode("utf-8").replace("# Diff Coverage", "")
		# strip first header
		markdown_string = markdown_string[markdown_string.find("\n") + 1 :]
		return markdown_string


class DiffCovSettings(BaseSettings):
	model_config = {
		"env_prefix": "DIFF_COV_",
	}
	COMPARE_BRANCH: str = "main"
	RECURSIVE: bool = True
	"""Find coverage files recursively"""
	FAIL_UNDER: float = 100.0


class DiffCovPlugin(CiBotPlugin):
	@override
	def plugin_name(self) -> str:
		return "Diff Coverage"

	@override
	def supported_backends(self) -> tuple[str, ...]:
		return ("*",)

	@property
	def settings(self) -> DiffCovSettings:
		return DiffCovSettings()

	@override
	def on_pr_changed(self, pr: int) -> BumpType | None:
		settings = self.settings
		cov_files = []
		if settings.RECURSIVE:
			cov_files = list(Path.cwd().rglob("coverage.xml"))
		else:
			cov_files = [Path.cwd() / "coverage.xml"]

		grouped_lines_per_file: dict[str, list[tuple[int, int | None]]] = {}
		fail_under_lints: dict[str, str] = {}
		for cov_file in cov_files:
			section_name = cov_file.parent.name
			report = create_report_for_cov_file(cov_file, settings.COMPARE_BRANCH)
			logger.info(f"Processing coverage report for {section_name}\n report is {report}")
			for file, stats in report["src_stats"].items():
				grouped_lines_per_file[file] = self._group_violations(stats["violation_lines"])
				logger.info(f"Grouped lines for {file}: {grouped_lines_per_file[file]}")
			# check fail under
			if report["total_percent_covered"] < settings.FAIL_UNDER:
				logger.error(f"Coverage failed under {settings.FAIL_UNDER}%")
				self._pr_comment = (
					f"{self._pr_comment or ''}\n#### 🔴 Coverage failed for {section_name} section\n"
					+ f"expected {settings.FAIL_UNDER}% got {report['total_percent_covered']}"
				)
				self._should_fail_work_flow = True

		valid_comments: list[tuple[PrReviewComment, tuple[int, int | None]]] = []
		for id_, comment in self.backend.get_review_comments_for_content_id(
			DIFF_COV_REVIEW_COMMENT_ID
		):
			# for now we'll recreate all comments on every run due to complexity management
			self.backend.delete_pr_review_comment(id_)

		for file, violations in grouped_lines_per_file.items():
			for violation in violations:
				start_line, end_line = violation
				self.backend.create_pr_review_comment(
					PrReviewComment(
						content=f"⛔ Missing coverage from line {start_line} to line {end_line}"
						+ "\n<sup>**Don't comment here, it will be deleted**</sup>",
						content_id=DIFF_COV_REVIEW_COMMENT_ID,
						start_line=start_line if end_line != start_line else None,
						end_line=end_line or start_line,
						file=file,
						pr_number=pr,
					)
				)
		
		if not self._should_fail_work_flow:
			self._pr_comment = f"### ✅ Coverage passed"

			
	def _group_violations(self, violation_lines: list[int]) -> list[tuple[int, int | None]]:
		"""
		Return a list of tuples that are basically ranges of serially increasing numbers.

		i.e
		[1, 2, 3, 8, 9, 11]
		should output
		[(1, 3), (8, 9), (11, 11)]
		"""
		ret: list[tuple[int, int | None]] = []
		if not violation_lines:
			return ret
		start = violation_lines[0]
		end = violation_lines[0]
		for num in violation_lines[1:]:
			if num == end + 1:
				end = num
			else:
				ret.append((start, end))
				start = num
				end = num
		ret.append((start, end))
		return ret


DIFF_COV_REVIEW_COMMENT_ID = "diffcov-766f-49c7-a1a8-59f7be1fee8f"


class FileStats(TypedDict):
	percent_covered: float
	violation_lines: list[int]
	covered_lines: list[int]


class Report(TypedDict):
	report_name: str
	diff_name: str
	src_stats: dict[str, FileStats]
	total_num_lines: int
	total_num_violations: int
	total_percent_covered: float
	num_changed_lines: int


def create_report_for_cov_file(cov_file: Path, compare_branch: str) -> Report:
	cmd = f"diff-cover coverage.xml --compare-branch={compare_branch} --json-report report.json"
	if subprocess.run(cmd, shell=True, check=False).returncode != 0:
		raise ValueError("Failed to generate coverage report")

	report: Report = json.loads((Path.cwd() / "report.json").read_text())
	return report


@dataclass
class CovReport:
	header: str
	content: Report
