import os
from pathlib import Path
from typing import Any, Iterator, Optional, Sequence, Union

import yaml
from dagster._core.definitions.definitions_class import Definitions
from dagster._core.definitions.events import AssetMaterialization
from dagster._core.definitions.result import MaterializeResult
from dagster_embedded_elt.sling import SlingResource, sling_assets
from dagster_embedded_elt.sling.resources import AssetExecutionContext
from pydantic import BaseModel
from typing_extensions import Self

from dagster_components.core.component import Component, ComponentLoadContext, component_type
from dagster_components.core.component_generator import ComponentGenerateRequest, ComponentGenerator
from dagster_components.core.dsl_schema import AssetAttributes, AssetSpecProcessor, OpSpecBaseModel
from dagster_components.generate import generate_component_yaml


class SlingReplicationParams(BaseModel):
    sling: Optional[SlingResource] = None
    op: Optional[OpSpecBaseModel] = None
    asset_attributes: Optional[AssetAttributes] = None


class SlingReplicationComponentGenerator(ComponentGenerator):
    def generate_files(self, request: ComponentGenerateRequest, params: Any) -> None:
        generate_component_yaml(request, params)
        replication_path = Path(os.getcwd()) / "replication.yaml"
        with open(replication_path, "w") as f:
            yaml.dump(
                {"source": {}, "target": {}, "streams": {}},
                f,
            )


@component_type(name="sling_replication")
class SlingReplicationComponent(Component):
    params_schema = SlingReplicationParams

    def __init__(
        self,
        dirpath: Path,
        resource: SlingResource,
        op_spec: Optional[OpSpecBaseModel],
        asset_processors: Sequence[AssetSpecProcessor],
    ):
        self.dirpath = dirpath
        self.resource = resource
        self.op_spec = op_spec
        self.asset_processors = asset_processors

    @classmethod
    def get_generator(cls) -> SlingReplicationComponentGenerator:
        return SlingReplicationComponentGenerator()

    @classmethod
    def load(cls, context: ComponentLoadContext) -> Self:
        loaded_params = context.load_params(cls.params_schema)
        return cls(
            dirpath=context.path,
            resource=loaded_params.sling or SlingResource(),
            op_spec=loaded_params.op,
            asset_processors=loaded_params.asset_attributes or [],
        )

    def build_defs(self, context: ComponentLoadContext) -> Definitions:
        @sling_assets(
            name=self.op_spec.name if self.op_spec else self.dirpath.stem,
            op_tags=self.op_spec.tags if self.op_spec else {},
            replication_config=self.dirpath / "replication.yaml",
        )
        def _fn(context: AssetExecutionContext, sling: SlingResource):
            yield from self.execute(context=context, sling=sling)

        defs = Definitions(assets=[_fn], resources={"sling": self.resource})
        for transform in self.asset_processors:
            defs = transform.apply(defs, context.templated_value_resolver)
        return defs

    def execute(
        self, context: AssetExecutionContext, sling: SlingResource
    ) -> Iterator[Union[AssetMaterialization, MaterializeResult]]:
        yield from sling.replicate(context=context)
