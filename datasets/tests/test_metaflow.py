import json

from datasets import Dataset
from datasets.context import Context
from datasets.dataset_plugin import StorageOptions
from datasets.metaflow import (
    _DatasetParams,
    _DatasetParamsDecoder,
    _DatasetTypeClass,
)
from datasets.mode import Mode
from datasets.plugins.batch.batch_base_plugin import BatchOptions
from datasets.plugins.batch.batch_dataset import BatchDataset
from datasets.plugins.batch.hive_dataset import HiveOptions


def test_dataset_dumps_load():
    dataset = Dataset(
        name="Example",
        logical_key="my_key",
        mode=Mode.READ_WRITE,
        options=BatchOptions(partition_by="foo"),
    )

    json_value = json.dumps(dataset)
    dataset2 = _DatasetTypeClass().convert(json_value, None, None)

    assert dataset2.options.partition_by == "foo"
    assert dataset2.mode == Mode.READ_WRITE
    assert isinstance(dataset2, BatchDataset)
    assert dataset == dataset2


def test_dataset_type_class():
    json_value = (
        '{"name": "HiDataset", "mode": "READ_WRITE", "options":{"type":"HiveOptions", "path":"/foo_hive"}}'
    )
    dataset = _DatasetTypeClass().convert(json_value, None, None)
    assert dataset.name == "HiDataset"
    assert dataset.hive_table_name == "hi_dataset"
    assert dataset.mode == Mode.READ_WRITE
    assert dataset.options.path == "/foo_hive"


def test_dataset_parameters_decoder():
    params = json.loads(
        '{"name": "hi", "columns": "a,b", "mode":"WRITE", "options":{"type":"BatchOptions"}}',
        cls=_DatasetParamsDecoder,
    )
    assert params.name == "hi"
    assert params.columns == "a,b"
    assert params.mode == Mode.WRITE
    assert params.options == BatchOptions()

    # test case insensitivity
    params = json.loads(
        '{"name": "hi", "options":{"type":"batchOptions", "path":"/foo"}}', cls=_DatasetParamsDecoder
    )
    assert params.options == BatchOptions(path="/foo")
    assert params.mode == Mode.READ

    params = json.loads(
        '{"name": "hi", "options":{"type":"HiveOptions", "path":"/p", "partition_by": "a,b", "hive_table_name": "n"}}',
        cls=_DatasetParamsDecoder,
    )
    assert params.options == HiveOptions(path="/p", partition_by="a,b", hive_table_name="n")

    # test empty HiveOptions
    params = json.loads('{"name": "hi", "options":{"type":"HiveOptions"}}', cls=_DatasetParamsDecoder)
    assert params.options == HiveOptions()

    # test dict options_by_context
    params = json.loads(
        '{"name": "hi", "options_by_context": {"ONLINE": {"type":"HiveOptions"}}}', cls=_DatasetParamsDecoder
    )
    assert params.options is None
    assert params.options_by_context == {Context.ONLINE: HiveOptions()}


def test_serialize_deserialize_options():
    def validate(options: StorageOptions):
        json_str = json.dumps(options)
        assert options == json.loads(json_str, cls=_DatasetParamsDecoder)

    validate(BatchOptions(path="hi"))
    validate(HiveOptions())
    validate(HiveOptions(path="p1", partition_by="a,b"))
    validate(HiveOptions(path="woo"))


def test_serialize_deserialize_params():
    def validate(params: _DatasetParams):
        json_str = json.dumps(params)
        value = json.loads(json_str, cls=_DatasetParamsDecoder)
        assert params == value

    validate(_DatasetParams())
    validate(_DatasetParams(options=BatchOptions()))
    validate(_DatasetParams(options=BatchOptions(path="hi")))
    validate(_DatasetParams("Hi", options=BatchOptions(path="hi", partition_by="a,b")))
    validate(_DatasetParams("Hi", options=BatchOptions(path="hi", partition_by=None)))

    d = _DatasetParams("Hi", options_by_context={"ONLINE": BatchOptions(path="hi", partition_by=None)})
    d1 = _DatasetParams("Hi", options_by_context={Context.ONLINE: BatchOptions(path="hi", partition_by=None)})
    assert json.loads(json.dumps(d), cls=_DatasetParamsDecoder) == d1
    validate(d1)

    validate(_DatasetParams("Hi", options=HiveOptions()))
    validate(_DatasetParams("Hi", options=HiveOptions(path="hi")))
    validate(_DatasetParams("Hi", options=HiveOptions(path="wow")))
