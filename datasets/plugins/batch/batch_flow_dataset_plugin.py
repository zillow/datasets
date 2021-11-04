from typing import TYPE_CHECKING, Iterable, Optional, Tuple, Union

from datasets.context import Context
from datasets.dataset_plugin import DatasetPlugin
from datasets.plugins import BatchDatasetPlugin


if TYPE_CHECKING:
    from metaflow import Run


@DatasetPlugin.register_plugin(constructor_keys={"flow_dataset"}, context=Context.BATCH)
class BatchFlowDatasetPlugin(BatchDatasetPlugin):
    def __init__(
        self,
        flow_dataset: str,
        name: str = None,
        columns: Optional[Union[Iterable[str], str]] = None,
        run_id: Optional[str] = "latest_successful_run",
        class_field_name: Optional[str] = None,
    ):

        self.flow_dataset = flow_dataset
        self.flow_name, self.dataset_name = flow_dataset.split(".")

        run, run_id = _get_run_id(self.flow_name, run_id)

        dataset = getattr(run.data, self.dataset_name)

        super(BatchFlowDatasetPlugin, self).__init__(
            name=dataset.name,
            logical_key=dataset.key,
            columns=columns,
            run_id=run_id,
            class_field_name=class_field_name if class_field_name else (name if name else self.dataset_name),
        )
        # The program name is that of the original dataset name
        self.program_name = dataset.program_name


def _get_run_id(flow_name: str, run_id: Optional[str]) -> Tuple["Run", Optional[str]]:
    from metaflow import Flow, Run

    flow = Flow(flow_name)
    run: Run
    ret_run_id: Optional[str]
    if run_id in ["latest_successful_run", "latest_run"]:
        run = flow.latest_run if run_id == "latest_run" else flow.latest_successful_run
        ret_run_id = run.id
    elif run_id:
        run = flow[run_id]
        ret_run_id = run_id
    else:
        # run_id is None
        run = flow.latest_successful_run
        ret_run_id = None
    return run, ret_run_id
