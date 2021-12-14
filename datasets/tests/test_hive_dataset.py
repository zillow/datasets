from pathlib import Path

import pandas as pd
import pytest
from pandas._testing import assert_frame_equal
from pyspark import pandas as ps
from pyspark.sql import DataFrame as SparkDataFrame, SparkSession
from pyspark.sql.utils import AnalysisException

from datasets import Mode
from datasets.context import Context
from datasets.dataset_plugin import DatasetPlugin
from datasets.exceptions import InvalidOperationException
from datasets.plugins import HiveDataset


@pytest.fixture
def mode():
    return Mode.READ_WRITE


@pytest.fixture
def partition_by() -> str:
    return "col1,col3"


@pytest.fixture
def columns() -> str:
    return "col1,col2,col3"


@pytest.fixture
def hive_table() -> str:
    return "my_hive_table"


@pytest.fixture
def dataset(hive_table: str, partition_by: str, mode: Mode, columns: str):
    return DatasetPlugin.from_keys(
        name="Foo",
        hive_table=hive_table,
        context=Context.BATCH,
        logical_key="my_key",
        columns=columns,
        partition_by=partition_by,
        mode=mode,
    )


@pytest.fixture
def df() -> pd.DataFrame:
    data = {
        "col1": ["A", "A", "A", "B", "B", "B"],
        "col2": [1, 2, 3, 4, 5, 6],
        "col3": ["A1", "A1", "A2", "B1", "B2", "B2"],
    }
    return pd.DataFrame(data)


def test_from_keys_offline_plugin(dataset: HiveDataset, hive_table: str):
    assert dataset.name == "Foo"
    assert dataset.hive_table == hive_table
    assert dataset.key == "my_key"
    assert dataset.partition_by == "col1,col3"


@pytest.mark.parametrize("mode", [Mode.WRITE])
def test_from_read_on_mode_write(dataset: HiveDataset):
    with pytest.raises(InvalidOperationException) as exec_info:
        dataset.to_spark(columns="col1,col2")

    assert f"Cannot read because mode={Mode.WRITE}" in str(exec_info.value)


@pytest.mark.parametrize("partition_by", ["col1,col3"])
@pytest.mark.spark
def test_hive_to_spark(dataset: HiveDataset, df: pd.DataFrame, spark_session: SparkSession):
    # spark_session.sql(f"DESCRIBE FORMATTED {dataset.hive_table}").show(truncate=False, n=100)
    # Create the Hive Table
    dataset.write(df)

    # add a new partition
    data = {"col1": ["C"], "col2": [7], "col3": ["C1"]}
    dataset.write(pd.DataFrame(data))

    # add a new row to an existing partition
    data = {"col1": ["C"], "col2": [8], "col3": ["C1"]}
    dataset.write(pd.DataFrame(data))
    read_spdf = dataset.to_spark_pandas()
    print(f"{len(read_spdf)=}")

    assert read_spdf.columns.to_list() == ["col1", "col2", "col3"]

    spark_df = dataset.to_spark(columns="col1")
    assert spark_df.columns == ["col1"]

    df1 = dataset.to_spark(partitions=dict(col1="A", col3="A1")).toPandas()
    assert df1["col1"].unique().tolist() == ["A"]
    assert df1["col3"].unique().tolist() == ["A1"]

    df2 = dataset.to_spark(partitions=dict(col1="A")).toPandas()
    assert df2["col1"].unique().tolist() == ["A"]
    assert df2["col3"].unique().tolist() == ["A1", "A2"]

    df3 = dataset.to_spark(partitions=dict(col1="C")).toPandas()
    assert df3["col1"].unique().tolist() == ["C"]
    assert sorted(df3["col2"].unique().tolist()) == [7, 8]
    assert df3["col3"].unique().tolist() == ["C1"]


@pytest.mark.spark
def test_hive_write_existing_table(
    dataset: HiveDataset, df: pd.DataFrame, spark_session: SparkSession, data_path: Path
):
    dataset.write(df)

    # Try a different path!
    old_path = dataset._path
    dataset._path = str(data_path / "test_hive_write_existing_table")
    with pytest.raises(AnalysisException) as exec_info:
        dataset.write(df, partition_by="col1")
    assert "It doesn't match the specified location" in str(exec_info.value)
    dataset._path = old_path

    # Try a different partition!
    with pytest.raises(AnalysisException) as exec_info:
        dataset.write(df, partition_by="col1")
    assert "Specified partitioning does not match that of the existing table" in str(exec_info.value)


@pytest.mark.parametrize("partition_by", ["col1,col3,run_id"])
@pytest.mark.parametrize("hive_table", ["test_db.my_hive_table_run_id"])
@pytest.mark.parametrize("columns", ["col1,col2,col3,run_id"])
@pytest.mark.spark
def test_hive_to_spark_run_id(dataset: HiveDataset, df: pd.DataFrame, run_id: str, spark_session):
    spark_session.sql("create database if not exists test_db")

    dataset.write(df)

    spark_df = dataset.to_spark(columns="col1,run_id")
    spark_df.show()
    assert spark_df.columns == ["col1", "run_id"]

    df1: pd.DataFrame = dataset.to_spark(partitions=dict(col1="A", col3="A1")).toPandas()
    assert df1["col1"].unique().tolist() == ["A"]
    assert df1["col2"].tolist() == list(range(1, 3))
    assert df1["col3"].unique().tolist() == ["A1"]
    assert df1["run_id"].unique().tolist() == [run_id]


@pytest.mark.spark
@pytest.mark.parametrize("mode", [Mode.READ])
def test_write_on_read_only_spark_data_frame(dataset: HiveDataset, df: pd.DataFrame):
    sdf: SparkDataFrame = ps.from_pandas(df).to_spark()
    with pytest.raises(InvalidOperationException):
        dataset.write(sdf)


@pytest.mark.spark
@pytest.mark.parametrize("mode", [Mode.WRITE])
def test_read_on_write_only_spark(dataset: HiveDataset, df):
    df: SparkDataFrame = ps.from_pandas(df).to_spark()
    dataset.write(df)
    with pytest.raises(InvalidOperationException):
        dataset.to_spark(columns="col1")


@pytest.mark.parametrize("partition_by", ["col1,col3,run_id"])
@pytest.mark.parametrize("hive_table", ["my_hive_table_spark_pandas"])
@pytest.mark.spark
def test_default_plugin_spark_pandas(dataset: HiveDataset, df: pd.DataFrame, run_id: str, spark_session):
    dataset.write(ps.from_pandas(df))
    read_psdf: ps.DataFrame = dataset.to_spark_pandas(partitions=dict(run_id=run_id))
    assert isinstance(read_psdf, ps.DataFrame)
    read_df = read_psdf.to_pandas()
    del read_df["run_id"]
    assert_frame_equal(df.set_index("col2"), read_df.set_index("col2"), check_like=True)


@pytest.mark.parametrize("mode", [Mode.READ])
@pytest.mark.spark
def test_write_on_read_only_spark_pandas(dataset: HiveDataset):
    df = pd.DataFrame({"col1": ["A", "A", "A", "B", "B", "B"], "col2": [1, 2, 3, 4, 5, 6]})
    with pytest.raises(InvalidOperationException):
        dataset.write(ps.from_pandas(df))
