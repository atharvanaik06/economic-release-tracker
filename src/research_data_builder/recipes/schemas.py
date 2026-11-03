"""Strict, provider-aware schemas for reproducible dataset recipes."""

from datetime import date
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, model_validator

from research_data_builder.providers.domain import DataProvider, Frequency


class StrictModel(BaseModel):
    """Reject unknown fields so misspelled research choices cannot be ignored."""

    model_config = ConfigDict(extra="forbid", frozen=True)


class JoinType(StrEnum):
    INNER = "inner"
    OUTER = "outer"
    LEFT = "left"


class MissingValuePolicy(StrEnum):
    PRESERVE = "preserve"
    DROP_ROWS = "drop_rows"


class OutputFormat(StrEnum):
    CSV = "csv"
    PARQUET = "parquet"


class TransformationOperation(StrEnum):
    LAG = "lag"
    DIFFERENCE = "difference"
    PERCENT_CHANGE = "percent_change"
    SCALE = "scale"


class VariableDefinition(StrictModel):
    """One provider series and its stable output-column name."""

    provider: DataProvider
    indicator_id: str = Field(min_length=1, max_length=128)
    output_name: str = Field(pattern=r"^[a-z][a-z0-9_]{0,127}$")


class TransformationDefinition(StrictModel):
    """One ordered, reviewed transformation for a selected variable."""

    operation: TransformationOperation
    variable: str = Field(pattern=r"^[a-z][a-z0-9_]{0,127}$")
    parameters: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_parameters(self) -> "TransformationDefinition":
        if self.operation in {
            TransformationOperation.LAG,
            TransformationOperation.DIFFERENCE,
            TransformationOperation.PERCENT_CHANGE,
        }:
            periods = self.parameters.get("periods", 1)
            if not isinstance(periods, int) or isinstance(periods, bool) or not 1 <= periods <= 120:
                raise ValueError("period-based transformations require periods between 1 and 120")
        if self.operation is TransformationOperation.SCALE:
            factor = self.parameters.get("factor")
            if not isinstance(factor, int | float) or isinstance(factor, bool) or factor == 0:
                raise ValueError("scale requires a non-zero numeric factor")
        return self


class JoinDefinition(StrictModel):
    """Explicit output join semantics."""

    type: JoinType = JoinType.OUTER
    keys: tuple[str, ...] = ("entity", "period")

    @model_validator(mode="after")
    def validate_keys(self) -> "JoinDefinition":
        if self.keys not in {("entity", "period"), ("period",)}:
            raise ValueError("join keys must be ['entity', 'period'] or ['period']")
        return self


class RecipeDefinition(StrictModel):
    """Complete validated draft that can be frozen into an immutable version."""

    name: str = Field(min_length=1, max_length=255)
    description: str | None = Field(default=None, max_length=1000)
    entities: tuple[str, ...] = Field(default=(), max_length=250)
    start_date: date
    end_date: date
    variables: tuple[VariableDefinition, ...] = Field(min_length=1, max_length=50)
    output_frequency: Frequency
    transformations: tuple[TransformationDefinition, ...] = Field(default=(), max_length=100)
    join: JoinDefinition = Field(default_factory=JoinDefinition)
    missing_values: MissingValuePolicy = MissingValuePolicy.PRESERVE
    formats: tuple[OutputFormat, ...] = (OutputFormat.CSV, OutputFormat.PARQUET)

    @model_validator(mode="after")
    def validate_recipe_semantics(self) -> "RecipeDefinition":
        if self.start_date > self.end_date:
            raise ValueError("start_date cannot be after end_date")
        if len(set(self.entities)) != len(self.entities):
            raise ValueError("entities must be unique")
        if any(not entity.strip() for entity in self.entities):
            raise ValueError("entities cannot contain empty values")

        output_names = [variable.output_name for variable in self.variables]
        if len(set(output_names)) != len(output_names):
            raise ValueError("variable output_name values must be unique")
        if (
            any(variable.provider is DataProvider.WORLD_BANK for variable in self.variables)
            and not self.entities
        ):
            raise ValueError("World Bank variables require at least one entity")
        if any(step.variable not in output_names for step in self.transformations):
            raise ValueError("transformations must reference a selected variable output_name")
        if not self.formats or len(set(self.formats)) != len(self.formats):
            raise ValueError("formats must be non-empty and unique")
        if self.join.keys == ("entity", "period") and not self.entities:
            raise ValueError("entity-period joins require at least one entity")
        return self
