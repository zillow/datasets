from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Callable, Dict, Iterable, Optional, Tuple, Type, Union

from datasets._typing import ColumnNames
from datasets.context import Context
from datasets.utils.case_utils import is_upper_pascal_case

from .mode import Mode
from .program_executor import ProgramExecutor


_logger = logging.getLogger(__name__)
_logger.setLevel(logging.DEBUG)


@dataclass
class StorageOptions:
    pass


class DatasetPlugin:
    """
    All dataset plugins derive from this class.
    To register as a dataset they must decorate themselves with or call Dataset.register()
    """

    _executor: ProgramExecutor
    _plugins: Dict[StorageOptions, Dataset] = {}
    _META_COLUMNS = ["run_id", "run_time"]

    def __init__(
        self,
        name: str,
        logical_key: Optional[str] = None,
        columns: Optional[ColumnNames] = None,
        run_id: Optional[str] = None,
        run_time: Optional[int] = None,
        mode: Union[Mode, str] = Mode.READ,
        options: Optional[StorageOptions] = None,
    ):
        """

        :param name: The dataset logical name.
        :param logical_key:
            The logical primary key, strongly suggested, and can later be
            used when creating Hive/Dynamo tables or registering with a Catalog.
        :param columns: Fetch columns
        :param run_id: The program run_id partition to select from.
        :param run_time: The program run_time in UTC epochs
        :param mode: The data access read/write mode
        """
        dataset_name_validator(name)
        self.name = name
        self.key = logical_key  # TODO: validate this too!
        self.mode: Mode = mode if isinstance(mode, Mode) else Mode[mode]
        self.columns = columns
        self.run_id = run_id
        self.run_time = run_time
        self.options = options

    @classmethod
    def Dataset(
        cls,
        name: Optional[str] = None,
        logical_key: Optional[str] = None,
        columns: Optional[ColumnNames] = None,
        run_id: Optional[str] = None,
        run_time: Optional[int] = None,
        mode: Union[Mode, str] = Mode.READ,
        options: Optional[Union[StorageOptions, Dict[Context, StorageOptions]]] = None,
        context: Optional[Union[Context, str]] = None,
        *args,
        **kwargs,
    ):
        if name:
            dataset_name_validator(name)
        # Use InitialCaps for class names (or for factory functions that return classes).
        plugin: Type
        plugin, options = plugin_factory(cls._plugins, context=context, options=options)
        return plugin(
            name=name,
            logical_key=logical_key,
            columns=columns,
            run_id=run_id,
            run_time=run_time,
            mode=mode,
            options=options,
            *args,
            **kwargs,
        )

    @classmethod
    def _get_context(cls, context: Optional[Union[Context, str]] = None) -> Context:
        if context:
            return context if isinstance(context, Context) else Context[context]
        else:
            return cls._executor.context

    # C901 'DatasetPlugin.register' is too complex (9)
    # flake8: noqa: C901
    @classmethod
    def register(
        cls, context=Context.BATCH, options: StorageOptions = None, as_default_context_plugin: bool = False
    ) -> Callable:
        if context is None:
            raise ValueError("context cannot be None!")

        if not isinstance(context, Context):
            raise ValueError(f"{context=} is not of type(Context)!")

        def inner_wrapper(wrapped_class: DatasetPlugin) -> DatasetPlugin:
            if as_default_context_plugin:
                if context in default_context_plugins:
                    raise ValueError(f"{context=} already registered in {default_context_plugins=}")
                default_context_plugins[context] = wrapped_class

            if options:
                if options in cls._plugins:
                    raise ValueError(f"{options=} already registered in {cls._plugins=}")
                if options in cls._plugins and wrapped_class != cls._plugins[options]:
                    raise ValueError(f"{options=} already registered as a dataset plugin in {cls._plugins=}!")
                cls._plugins[options] = wrapped_class
            return wrapped_class

        return inner_wrapper

    @classmethod
    def register_executor(cls, executor: ProgramExecutor):
        cls._executor = executor

    def _get_read_columns(self, columns: Optional[ColumnNames] = None) -> Optional[Iterable[str]]:
        read_columns = columns if columns else self.columns
        if read_columns is not None and isinstance(read_columns, str):
            read_columns = read_columns.split(",")
        return read_columns

    def __repr__(self):
        return f"Dataset({self.name=},{self.mode=},{self.key=},{self.columns=})"


def _validate_dataset_name(name: str):
    if not is_upper_pascal_case(name):
        raise ValueError(
            f"'{name}' is not a valid Dataset name.  "
            f"Please use Upper Pascal Case syntax: https://en.wikipedia.org/wiki/Camel_case"
        )
    else:
        pass


dataset_name_validator: Callable = _validate_dataset_name


def _default_plugin_factory(
    registered_plugins: Dict[StorageOptions, DatasetPlugin],
    context: Optional[Union[Context, str]] = None,
    options: Optional[Union[StorageOptions, Dict[Context, StorageOptions]]] = None,
) -> Tuple[DatasetPlugin, Optional[StorageOptions]]:
    context_lookup: Context = DatasetPlugin._get_context(context)

    if options is None:
        return (default_context_plugins[context_lookup], None)

    if isinstance(options, StorageOptions):
        if type(options) not in registered_plugins:
            raise ValueError(f"{type(options)=} not in {registered_plugins.keys=}")
        return (registered_plugins[type(options)], options)
    elif isinstance(options, dict):
        if context_lookup not in options:
            raise ValueError(f"{context_lookup=} not in {options.keys=}")
        options = options[context_lookup]
        plugin = registered_plugins[options]
        return (plugin, options)


plugin_factory: Callable[
    [Dict[StorageOptions, DatasetPlugin], Context, Optional[StorageOptions]],
    Tuple[DatasetPlugin, Optional[StorageOptions]],
] = _default_plugin_factory

default_context_plugins: Dict[Context, DatasetPlugin] = dict()
