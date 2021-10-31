import pandas as pd
from metaflow import Flow, FlowSpec, step

from datasets import Mode, dataset


class InputOutputDatasetFlow(FlowSpec):
    @dataset(flow_dataset="HelloDatasetFlow.output_dataset", name="hello_dataset")
    @dataset(name="output_dataset", partition_by="date_key,region", mode=Mode.WRITE)
    @step
    def start(self):
        df: pd.DataFrame = self.hello_dataset.read_pandas()
        df["date_key"] = "10-01-2021"
        self.output_dataset.write(df)

        self.next(self.end)

    @step
    def end(self):
        print(f"I have dataset \n{self.output_dataset=}")
        print(
            "self.my_dataset.read_pandas:\n",
            self.output_dataset.read_pandas().to_string(index=False),
        )

        # Another way to access hello_dataset
        run = Flow("HelloDatasetFlow").latest_successful_run
        my_df = run.data.hello_dataset.read_pandas(run_id=run.id)
        print(my_df.to_string(index=False))


if __name__ == "__main__":
    InputOutputDatasetFlow()
