from dataclasses import dataclass
from typing import Any, Iterable, Mapping

from agent_lens.eval.data_framework.field_names import FieldNames


@dataclass(frozen=True)
class RunInfo:
    raw: Mapping[str, Any]


@dataclass(frozen=True)
class SummaryPoint:
    raw: Mapping[str, Any]
    project_title: str
    language: str

    def to_summary_dict(self) -> dict[str, Any]:
        d = dict(self.raw)
        d[FieldNames.PROJECT] = self.project_title
        d[FieldNames.LANGUAGE] = self.language
        return d


@dataclass(frozen=True)
class ProjectResults:
    raw: Mapping[str, Any]

    @property
    def project_title(self) -> str:
        return str(self.raw[FieldNames.PROJECT])

    @property
    def language(self) -> str:
        return str(self.raw[FieldNames.LANGUAGE])

    def iter_points(self) -> Iterable[SummaryPoint]:
        results = self.raw["results"]
        if not isinstance(results, list):
            raise TypeError("ProjectResults['results'] must be a list")
        return (
            SummaryPoint(
                raw=r, project_title=self.project_title, language=self.language
            )
            for r in results
            if isinstance(r, Mapping)
        )


@dataclass(frozen=True)
class SummaryFile:
    run_info: RunInfo
    projects_results: list[ProjectResults]

    @classmethod
    def from_dict(cls, raw: Mapping[str, Any]) -> "SummaryFile":
        run_info_raw = raw["run_info"]
        projects_raw = raw[FieldNames.PROJECTS_RESULTS]
        if not isinstance(run_info_raw, Mapping):
            raise TypeError("SummaryFile['run_info'] must be a mapping")
        if not isinstance(projects_raw, list):
            raise TypeError(
                f"SummaryFile['{FieldNames.PROJECTS_RESULTS}'] must be a list"
            )

        return cls(
            run_info=RunInfo(raw=run_info_raw),
            projects_results=[
                ProjectResults(raw=p) for p in projects_raw if isinstance(p, Mapping)
            ],
        )
