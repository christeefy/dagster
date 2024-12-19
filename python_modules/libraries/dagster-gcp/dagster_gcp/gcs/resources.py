from typing import Any, Iterator, Optional

from dagster import ConfigurableResource, IAttachDifferentObjectToOpContext, resource
from dagster._core.definitions.resource_definition import dagster_maintained_resource
from google.cloud import storage
from pydantic import Field

from dagster_gcp.bigquery.utils import setup_gcp_creds
from dagster_gcp.gcs.file_manager import GCSFileManager


class GCSResource(ConfigurableResource, IAttachDifferentObjectToOpContext):
    """Resource for interacting with Google Cloud Storage.

    Example:
        .. code-block::

            @asset
            def my_asset(gcs: GCSResource):
                with gcs.get_client() as client:
                    # client is a google.cloud.storage.Client
                    ...
    """

    project: Optional[str] = Field(default=None, description="Project name")
    gcp_credentials: Optional[str] = Field(
        default=None,
        description=(
            "GCP authentication credentials. If provided, a temporary file will be created"
            " with the credentials and ``GOOGLE_APPLICATION_CREDENTIALS`` will be set to the"
            " temporary file. To avoid issues with newlines in the keys, you must base64"
            " encode the key. You can retrieve the base64 encoded key with this shell"
            " command: ``cat $GOOGLE_AUTH_CREDENTIALS | base64``"
        ),
    )

    def get_client(self) -> Iterator[storage.Client]:
        """Creates a GCS Client.

        Returns: google.cloud.storage.Client
        """
        yield _gcs_client_from_config(project=self.project, gcp_credentials=self.gcp_credentials)

    def get_object_to_set_on_execution_context(self) -> Any:
        return self.get_client()


@dagster_maintained_resource
@resource(
    config_schema=GCSResource.to_config_schema(),
    description="This resource provides a GCS client",
)
def gcs_resource(init_context) -> Iterator[storage.Client]:
    with GCSResource.from_resource_context(init_context).get_client() as client:
        yield client


class GCSFileManagerResource(ConfigurableResource, IAttachDifferentObjectToOpContext):
    """FileManager that provides abstract access to GCS."""

    project: Optional[str] = Field(default=None, description="Project name")
    gcp_credentials: Optional[str] = Field(
        default=None,
        description=(
            "GCP authentication credentials. If provided, a temporary file will be created"
            " with the credentials and ``GOOGLE_APPLICATION_CREDENTIALS`` will be set to the"
            " temporary file. To avoid issues with newlines in the keys, you must base64"
            " encode the key. You can retrieve the base64 encoded key with this shell"
            " command: ``cat $GOOGLE_AUTH_CREDENTIALS | base64``"
        ),
    )
    gcs_bucket: str = Field(description="GCS bucket to store files")
    gcs_prefix: str = Field(default="dagster", description="Prefix to add to all file paths")

    def get_client(self) -> Iterator[GCSFileManager]:
        """Creates a :py:class:`~dagster_gcp.GCSFileManager` object that implements the
        :py:class:`~dagster._core.storage.file_manager.FileManager` API .

        Returns: GCSFileManager
        """
        with _gcs_client_from_config(
            project=self.project, gcp_credentials=self.gcp_credentials
        ) as gcs_client:
            yield GCSFileManager(
                client=gcs_client,
                gcs_bucket=self.gcs_bucket,
                gcs_base_key=self.gcs_prefix,
            )

    def get_object_to_set_on_execution_context(self) -> Any:
        with self.get_client() as client:
            yield client


@dagster_maintained_resource
@resource(config_schema=GCSFileManagerResource.to_config_schema())
def gcs_file_manager(context):
    """FileManager that provides abstract access to GCS.

    Implements the :py:class:`~dagster._core.storage.file_manager.FileManager` API.
    """
    with GCSFileManagerResource.from_resource_context(context).get_client() as client:
        yield client


def _gcs_client_from_config(
    project: Optional[str], gcp_credentials: Optional[str]
) -> Iterator[storage.Client]:
    """Creates a GCS Client.

    Args:
        project: The GCP project

    Returns: A GCS client.
    """
    if gcp_credentials:
        with setup_gcp_creds(gcp_credentials):
            yield storage.client.Client(project=project)
    else:
        yield storage.client.Client(project=project)
