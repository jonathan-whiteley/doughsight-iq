"""
Application settings using Pydantic BaseSettings.

Loads configuration from environment variables and .env file.
In Databricks Apps, most values are auto-configured.
For local development, uses ~/.databrickscfg or .env file.
"""

import os
from typing import Optional
from pydantic import Field
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings loaded from environment."""

    # === App Title ===
    app_title: str = Field(
        default="DoughSight IQ",
        description="Application title",
    )

    # === Databricks SQL Warehouse ===
    databricks_warehouse_id: Optional[str] = Field(
        default=None,
        description="SQL Warehouse ID for querying Delta tables",
    )

    # === Unity Catalog ===
    catalog_name: str = Field(
        default="jdub_demo",
        description="Unity Catalog name",
    )
    schema_name: str = Field(
        default="lce_store_ops",
        description="Schema name within the catalog",
    )

    # === Lakebase Configuration ===
    lakebase_instance_name: Optional[str] = Field(
        default=None,
        description="Lakebase PostgreSQL instance name",
    )
    lakebase_database_name: Optional[str] = Field(
        default="lce_store_ops",
        description="Database name within Lakebase instance",
    )
    databricks_database_port: int = Field(
        default=5432,
        description="PostgreSQL port",
    )

    # === Database Pool Settings ===
    db_pool_size: int = Field(default=5)
    db_max_overflow: int = Field(default=10)
    db_command_timeout: int = Field(default=30)
    db_pool_timeout: int = Field(default=10)
    db_pool_recycle_interval: int = Field(default=3600)

    # === Model Serving Endpoints ===
    demand_forecast_endpoint: str = Field(
        default="lce-demand-forecast",
        description="Demand forecasting model endpoint",
    )
    labor_optimizer_endpoint: str = Field(
        default="lce-labor-optimizer",
        description="Labor optimization model endpoint",
    )
    inventory_predictor_endpoint: str = Field(
        default="lce-inventory-predictor",
        description="Inventory prediction model endpoint",
    )
    dough_scheduler_endpoint: str = Field(
        default="lce-dough-scheduler",
        description="Dough prep and temper schedule optimizer endpoint",
    )

    # === Genie Space ===
    genie_space_id: Optional[str] = Field(
        default=None,
        description="Genie Space ID for AI chatbot",
    )

    # === Databricks Workspace (for Genie embed iframe) ===
    databricks_host: Optional[str] = Field(
        default=None,
        description="Databricks workspace host (e.g. https://xxx.cloud.databricks.com)",
    )
    workspace_id: Optional[str] = Field(
        default=None,
        description="Workspace/org id for the Genie embed URL (?o=...); looked up from the workspace when unset",
    )

    # === External APIs ===
    ticketmaster_api_key: Optional[str] = Field(
        default=None,
        description="Ticketmaster Discovery API key",
    )

    # === Pagination Defaults ===
    default_limit: int = Field(default=100)
    max_limit: int = Field(default=1000)

    model_config = {
        "env_file": ".env",
        "env_file_encoding": "utf-8",
        "case_sensitive": False,
        "extra": "allow",
    }

    @property
    def table_prefix(self) -> str:
        """Get the full table prefix (catalog.schema)."""
        return f"{self.catalog_name}.{self.schema_name}"

    def get_table_path(self, table_name: str) -> str:
        """Get full path for a table."""
        return f"{self.table_prefix}.{table_name}"


# Singleton instance
settings = Settings()


def get_settings() -> Settings:
    """
    Dependency injection function for FastAPI endpoints.
    
    Returns:
        The application settings instance.
    """
    return settings





