from pathlib import Path
from typing import TYPE_CHECKING, Callable, Iterable, Optional, Tuple

import pandas
import pandas as pd

from datasets import Mode
from datasets._typing import ColumnNames
from datasets.context import Context
from datasets.dataset_plugin import DatasetPlugin
from datasets.exceptions import InvalidOperationException
from datasets.utils import _pascal_to_snake_case


if TYPE_CHECKING:
    import dask.dataframe as dd
    import pyspark


@DatasetPlugin.register(constructor_keys={"name"}, context=Context.BATCH)
class BatchDatasetPlugin(DatasetPlugin):
    """
    The default plugin for the BATCH execution context.
    """

    _dataset_path_func: Callable = None

    def __init__(
        self,
        name: str,
        logical_key: str = None,
        columns: Optional[ColumnNames] = None,
        run_id: Optional[str] = None,
        mode: Mode = Mode.READ,
        partition_by: Optional[ColumnNames] = None,
        path: Optional[str] = None,
    ):
        self.path = path
        self.partition_by = partition_by
        self.program_name = self._executor.current_program_name
        super(BatchDatasetPlugin, self).__init__(
            name=name,
            logical_key=logical_key,
            columns=columns,
            run_id=run_id,
            mode=mode,
        )
        self._table_name = _pascal_to_snake_case(name)

    def _get_path_filters_columns(
        self, columns: Optional[ColumnNames] = None, run_id: Optional[str] = None
    ) -> Tuple[str, Optional[list], Optional[Iterable[str]]]:
        path = self._get_dataset_path()
        read_columns = self._get_read_columns(columns)
        filters = None
        query_run_id = run_id if run_id else self.run_id
        if query_run_id:
            filters = [("run_id", "=", query_run_id)]
        return path, filters, read_columns

    def read_pandas(
        self,
        columns: Optional[str] = None,
        storage_format: str = "parquet",
        run_id: Optional[str] = None,
        **kwargs,
    ) -> pd.DataFrame:
        if not (self.mode & Mode.READ):
            raise InvalidOperationException(f"Cannot read because mode={self.mode}")

        path, filters, read_columns = self._get_path_filters_columns(columns, run_id=run_id)

        df: pd.DataFrame
        if storage_format == "parquet":
            df = pandas.read_parquet(path, columns=read_columns, engine="pyarrow", filters=filters, **kwargs)
        elif storage_format == "csv":
            df = pandas.read_csv(path, columns=read_columns, filters=filters, **kwargs)

        for meta_column in self._META_COLUMNS:
            if meta_column in df and (read_columns is None or meta_column not in read_columns):
                del df[meta_column]
        return df

    def write(self, data: pd.DataFrame, **kwargs):
        if not (self.mode & Mode.WRITE):
            raise InvalidOperationException(f"Cannot write because mode={self.mode}")

        if not isinstance(data, pd.DataFrame):
            assert ValueError("data is not a pandas DataFrame")

        if self.partition_by:
            if isinstance(self.partition_by, str):
                partition_cols = self.partition_by.split(",")
            else:
                partition_cols = self.partition_by
        else:
            partition_cols = list()

        if self.path is None or "run_id" in partition_cols:
            # Only partition on run_id if @dataset(path="s3://..") is not given
            # or run_id is in partition_cols
            if "run_id" not in partition_cols:
                partition_cols.append("run_id")
            self.run_id = self._executor.current_run_id  # DO NOT ALLOW OVERWRITE OF ANOTHER RUN ID
            data["run_id"] = self.run_id

        data.to_parquet(
            self._get_dataset_path(),
            engine=kwargs.get("engine", "pyarrow"),
            compression=kwargs.get("compression", "snappy"),
            index=kwargs.get("index", False),
            partition_cols=partition_cols,
            **kwargs,
        )

    def read_dask(
        self, columns: Optional[str] = None, run_id: Optional[str] = None, **kwargs
    ) -> "dd.DataFrame":
        if not (self.mode & Mode.READ):
            raise InvalidOperationException(f"Cannot read because mode={self.mode}")

        import dask.dataframe as dd

        path, filters, read_columns = self._get_path_filters_columns(columns, run_id=run_id)
        return dd.read_parquet(
            path,
            columns=read_columns,
            filters=filters if filters and len(filters) else None,
            engine=kwargs.get("engine", "pyarrow"),
            **kwargs,
        )

    def read_spark(
        self, columns: Optional[str] = None, run_id: Optional[str] = None, conf=None, **kwargs
    ) -> "pyspark.sql.DataFrame":
        if not (self.mode & Mode.READ):
            raise InvalidOperationException(f"Cannot read because mode={self.mode}")

        from pyspark import SparkConf
        from pyspark.sql import DataFrame, SparkSession

        path, _, read_columns = self._get_path_filters_columns(columns, run_id=run_id)

        read_columns = read_columns if read_columns else ["*"]
        if self.run_id:
            read_columns.append("run_id")

        if conf is None:
            conf = SparkConf()
        spark_session: SparkSession = SparkSession.builder.config(conf=conf).getOrCreate()

        df: DataFrame = spark_session.read.parquet(path).select(*read_columns)
        if self.run_id:
            df = df.where(df["run_id"] == self.run_id)
        return df

    @classmethod
    def _register_dataset_path_func(cls, func: Callable):
        cls._dataset_path_func = func

    def _get_dataset_path(self) -> str:
        if self.path is not None:
            return self.path
        else:
            if BatchDatasetPlugin._dataset_path_func:
                return BatchDatasetPlugin._dataset_path_func(self)
            else:
                return str(
                    Path(self._executor.datastore_path)
                    / "datastore"
                    / (self.program_name if self.program_name else self._executor.current_program_name)
                    / self._table_name
                )

    def __repr__(self):
        return (
            f"BatchDatasetPlugin({self.name=},{self.key=},{self.partition_by=},"
            f"{self.run_id=},{self.columns=},"
            f"dataset_path={self._get_dataset_path()},{self._table_name=})"
        )
