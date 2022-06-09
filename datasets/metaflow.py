import dataclasses
import json
from dataclasses import dataclass
from typing import Dict, List, Optional, Type, Union

from metaflow._vendor.click import ParamType
from metaflow.parameters import Parameter

from datasets import DataFrameType
from datasets._typing import ColumnNames
from datasets.context import Context
from datasets.dataset_plugin import DatasetPlugin, StorageOptions
from datasets.mode import Mode


class _DatasetTypeClass(ParamType):
    name = "Dataset"

    def convert(self, value, param, ctx) -> DatasetPlugin:
        if isinstance(value, str):
            params: _DatasetParams = json.loads(value, cls=_DatasetParamsDecoder)
            params_dict = params.__dict__.copy()
            if "context" in params_dict:
                del params_dict["context"]
            return DatasetPlugin.factory(
                context=params.context if params.context else DatasetPlugin._executor.context, **params_dict
            )
        else:
            return value

    def __str__(self):
        return repr(self)

    def __repr__(self):
        return "Dataset"


@dataclass
class _DatasetParams:
    name: Optional[str] = None
    logical_key: Optional[str] = None
    columns: Optional[ColumnNames] = None
    run_id: Optional[str] = None
    run_time: Optional[int] = None
    mode: Union[Mode, str] = Mode.READ
    options: Optional[StorageOptions] = None
    options_by_context: Optional[Dict[Union[Context, str], StorageOptions]] = None
    context: Optional[Union[Context, str]] = None

    def to_json(self) -> dict:
        ret = dataclasses.asdict(self, dict_factory=lambda x: {k: v for (k, v) in x if v is not None})

        if self.options:
            ret["options"] = self.options.to_json()

        if self.options_by_context:
            ret["options_by_context"] = {str(k): v.to_json() for k, v in self.options_by_context.items()}

        return ret


class _DatasetParamsDecoder(json.JSONDecoder):
    def __init__(self, *args, **kwargs):
        json.JSONDecoder.__init__(self, object_hook=self.object_hook, *args, **kwargs)

    @staticmethod
    def get_storage_subclasses(cls: object) -> list[Type[StorageOptions]]:
        ret: List[Type] = []

        for subclass in cls.__subclasses__():
            ret.append(subclass)
            ret.extend(_DatasetParamsDecoder.get_storage_subclasses(subclass))

        return ret

    def object_hook(self, obj: dict) -> Union[_DatasetParams, StorageOptions]:
        type = obj.get("type")
        if type:
            # remove "type"
            del obj["type"]

            mapping: Dict[str, Type[StorageOptions]] = {
                f.__name__.lower(): f for f in _DatasetParamsDecoder.get_storage_subclasses(StorageOptions)
            }

            return mapping[type.lower()](**obj)
        elif (
            "options" not in obj
            and len(obj.keys())
            and all(isinstance(v, StorageOptions) for v in obj.values())
        ):
            return {DatasetPlugin._get_context(k): v for k, v in obj.items()}
        else:
            params = {k: obj[k] for k in _DatasetParams().__dict__.keys() if k in obj}

            mode = params.get("mode")
            if mode:
                params["mode"] = mode if isinstance(mode, Mode) else Mode[mode]

            return _DatasetParams(**params)


_fallback = json.JSONEncoder().default


def to_json_encoder(self, obj):
    return getattr(obj.__class__, "to_json", _fallback)(obj)


json.JSONEncoder.default = to_json_encoder


class DatasetParameter(Parameter, DatasetPlugin):
    def __init__(
        self,
        name: str,
        default: Optional[DatasetPlugin] = None,
        required: Optional[bool] = False,
        help: Optional[str] = None,
        **kwargs,
    ):
        super(DatasetParameter, self).__init__(
            name, required=required, help=help, default=default, type=_DatasetTypeClass(), **kwargs
        )

    def write(self, data: DataFrameType, **kwargs):
        raise NotImplementedError()

    def to_pandas(
        self,
        columns: Optional[str] = None,
        run_id: Optional[str] = None,
        run_time: Optional[int] = None,
        **kwargs,
    ) -> DataFrameType:
        raise NotImplementedError()
