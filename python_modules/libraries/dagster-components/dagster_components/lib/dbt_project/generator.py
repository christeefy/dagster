import os
from pathlib import Path
from typing import Optional

import dagster._check as check
from dbt.cli.main import dbtRunner
from pydantic import BaseModel, Field

from dagster_components.core.component_generator import ComponentGenerateRequest, ComponentGenerator
from dagster_components.generate import generate_component_yaml


class DbtGenerateParams(BaseModel):
    init: bool = Field(default=False)
    project_path: Optional[str] = None


class DbtProjectComponentGenerator(ComponentGenerator):
    generator_params = DbtGenerateParams

    def generate_files(self, request: ComponentGenerateRequest, params: DbtGenerateParams) -> None:
        cwd = os.getcwd()
        if params.project_path:
            # NOTE: CWD is not set "correctly" above so we prepend "../../.." as a temporary hack to
            # make sure the path is right.
            relative_path = os.path.join(
                "../../../", os.path.relpath(params.project_path, start=cwd)
            )
        elif params.init:
            dbtRunner().invoke(["init"])
            subpaths = [
                path for path in Path(cwd).iterdir() if path.is_dir() and path.name != "logs"
            ]
            check.invariant(len(subpaths) == 1, "Expected exactly one subpath to be created.")
            # this path should be relative to this directory
            relative_path = subpaths[0].name
        else:
            relative_path = None

        generate_component_yaml(request, {"dbt": {"project_dir": relative_path}})
