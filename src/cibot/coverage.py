import logging
import os
import sys
import xml.etree.ElementTree as etree
from io import BytesIO
from pathlib import Path

import jinja2
from diff_cover.diff_reporter import GitDiffReporter
from diff_cover.git_diff import GitDiffTool
from diff_cover.git_path import GitPathTool
from diff_cover.report_generator import MarkdownReportGenerator
from diff_cover.violationsreporters.violations_reporter import (
    XmlCoverageReporter,
)

try:
    from . import githubref
except ImportError:
    import githubref

template_env = jinja2.Environment(
    loader=jinja2.FileSystemLoader(Path(__file__).parent / "templates"),
    autoescape=jinja2.select_autoescape(),
)

COVERAGE_TEMPLATE = template_env.get_template("coverage.jinja.md")


class ProgrammaticDiffCover:
    def __init__(self, coverage_path: Path, compare_branch: str = "main"):
        self.coverage_path = coverage_path
        self.compare_branch = compare_branch
        self.git_diff = GitDiffTool(range_notation="...", ignore_whitespace=True)
        self.git_diff.diff_committed()
        self.git_diff_reporter = GitDiffReporter(
            git_diff=self.git_diff,
            include_untracked=True,
            ignore_staged=False,
            ignore_unstaged=False,
        )
        self.section_name = self.coverage_path.parent.name
        self.reporter = self._create_reporter(coverage_path)

    @staticmethod
    def _create_reporter(path: Path) -> XmlCoverageReporter:
        try:
            return XmlCoverageReporter(
                [etree.parse(path)],
                src_roots=[path.parent.name],
            )
        except Exception as e:
            logging.error("Failed to create reporter for %s: %s", path, e)
            raise

    def generate_report(self) -> dict[str, str]:
        """Generate combined markdown report and coverage data."""
        try:
            section_md = self._generate_section_report(self.reporter)
            if "No lines with coverage information in this diff." in section_md:
                return {}
            return {"name": self.section_name, "content": section_md}
        except Exception as exception:  # noqa: BLE001
            logging.error(
                "Failed to generate %s report: %s", self.section_name, exception
            )
            return {}

    def _generate_section_report(
        self,
        reporter: XmlCoverageReporter,
    ) -> str:
        """Generate report for a single section."""
        with BytesIO() as buffer:
            markdown_gen = MarkdownReportGenerator(reporter, self.git_diff_reporter)
            markdown_gen.generate_report(buffer)
            markdown_string = (
                buffer.getvalue().decode("utf-8").replace("# Diff Coverage", "")
            )
            return markdown_string.replace(
                "## Diff: origin/main...HEAD, staged, unstaged and untracked changes",
                "",
            )


def main():
    session = githubref.get_github_session(os.getenv("BOT_TOKEN", ""))
    pr = githubref.get_pr(session, int(os.getenv("PR_NUMBER", "")))
    GitPathTool.set_cwd(Path.cwd())
    sections = [
        ProgrammaticDiffCover(
            coverage_path=Path(x).absolute(), compare_branch="main"
        ).generate_report()
        for x in sys.argv[1:]
    ]
    content = COVERAGE_TEMPLATE.render(
        sections=sections,
    )

    githubref.create_or_update_bot_comment(
        pr,
        content,
        identifier="438e0fc3-cf8d-4282-8856-c3e3b6a06a2f",
    )


if __name__ == "__main__":
    main()
