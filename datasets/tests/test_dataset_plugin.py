import pandas as pd
import pytest

from datasets.context import Context
from datasets.dataset_plugin import DatasetPlugin
from datasets.plugins import BatchDatasetPlugin
from datasets.tests.conftest import TestExecutor


@DatasetPlugin.register_plugin(constructor_keys={"name"}, context=Context.STREAMING)
class TestDefaultStreamingDatasetPlugin(DatasetPlugin):
    def __init__(self, **kwargs):
        super(TestDefaultStreamingDatasetPlugin, self).__init__(**kwargs)


@DatasetPlugin.register_plugin(constructor_keys={"name"}, context=Context.ONLINE)
class TestDefaultOnlineDatasetPlugin(DatasetPlugin):
    def __init__(self, **kwargs):
        super(TestDefaultOnlineDatasetPlugin, self).__init__(**kwargs)


@DatasetPlugin.register_plugin(constructor_keys={"test_name"}, context=Context.BATCH)
class TestNameDatasetPlugin(DatasetPlugin):
    db = pd.DataFrame(
        {"key": ["first", "second", "third", "fourth"], "value": [1, 2, 3, 4]},
    )
    db.set_index("key")

    def __init__(self, test_name: str, **kwargs):
        super(TestNameDatasetPlugin, self).__init__(name=test_name, **kwargs)

    def read(self, key):
        return self.db[self.db.key.isin(key)]


@DatasetPlugin.register_plugin(constructor_keys={"test_name", "test_name2"}, context=Context.BATCH)
class TestName2DatasetPlugin(DatasetPlugin):
    def __init__(self, test_name: str, test_name2: str, **kwargs):
        super(TestName2DatasetPlugin, self).__init__(name=f"{test_name}.{test_name2}", **kwargs)


@DatasetPlugin.register_plugin(constructor_keys={"test_fee"}, context=Context.ONLINE | Context.STREAMING)
class TestFeeOnlineDatasetPlugin(DatasetPlugin):
    def __init__(self, test_fee: str, **kwargs):
        super(TestFeeOnlineDatasetPlugin, self).__init__(name=test_fee, **kwargs)


def test_from_keys_dataset_factory_latency():
    import datetime

    a = datetime.datetime.now()
    dataset = DatasetPlugin.from_keys(test_name="foo")
    b = datetime.datetime.now()
    c = b - a
    assert c.microseconds < 500  # less than 0.5 ms, it actually takes ~24 microseconds

    assert dataset.name == "foo"
    assert isinstance(dataset, TestNameDatasetPlugin)


def test_from_keys():
    dataset = DatasetPlugin.from_keys(name="foo")
    assert isinstance(dataset, BatchDatasetPlugin)

    dataset = DatasetPlugin.from_keys(test_name="foo")
    assert dataset.name == "foo"
    assert dataset.read(["first", "fourth"])["value"].to_list() == [1, 4]
    assert isinstance(dataset, TestNameDatasetPlugin)

    dataset = DatasetPlugin.from_keys(test_name="t1", test_name2="t2")
    assert dataset.name == "t1.t2"
    assert isinstance(dataset, TestName2DatasetPlugin)

    dataset = DatasetPlugin.from_keys(test_fee="test_fee", context=Context.ONLINE)
    assert dataset.name == "test_fee"
    assert isinstance(dataset, TestFeeOnlineDatasetPlugin)

    dataset = DatasetPlugin.from_keys(test_fee="test_fee", context=Context.STREAMING)
    assert dataset.name == "test_fee"
    assert isinstance(dataset, TestFeeOnlineDatasetPlugin)

    dataset = DatasetPlugin.from_keys(test_fee="test_fee", context="STREAMING")
    assert isinstance(dataset, TestFeeOnlineDatasetPlugin)


def test_from_keys_consistent_access():
    dataset = DatasetPlugin.from_keys(name="foo")
    assert dataset.name == "foo"
    assert isinstance(dataset, BatchDatasetPlugin)

    TestExecutor.current_context = Context.STREAMING
    dataset = DatasetPlugin.from_keys(name="foo")
    assert dataset.name == "foo"
    assert isinstance(dataset, TestDefaultStreamingDatasetPlugin)

    TestExecutor.current_context = Context.ONLINE
    dataset = DatasetPlugin.from_keys(name="foo")
    assert dataset.name == "foo"
    assert isinstance(dataset, TestDefaultOnlineDatasetPlugin)

    TestExecutor.current_context = Context.BATCH


def test_register_plugin():
    with pytest.raises(ValueError) as execinfo:

        @DatasetPlugin.register_plugin(constructor_keys={"name"}, context=Context.ONLINE)
        class FooPlugin(DatasetPlugin):
            def __init__(self, **kwargs):
                super(FooPlugin, self).__init__(**kwargs)

    assert "already registered" in str(execinfo.value)

    with pytest.raises(ValueError) as execinfo:

        @DatasetPlugin.register_plugin(constructor_keys=None, context=Context.ONLINE)
        class FooPlugin1(DatasetPlugin):
            def __init__(self, **kwargs):
                super(FooPlugin1, self).__init__(**kwargs)

    assert "constructor_keys cannot be None" in str(execinfo.value)

    with pytest.raises(ValueError) as execinfo:

        @DatasetPlugin.register_plugin(constructor_keys={"name"}, context=None)
        class FooPlugin2(DatasetPlugin):
            def __init__(self, **kwargs):
                super(FooPlugin2, self).__init__(**kwargs)

    assert "context cannot be None" in str(execinfo.value)
