import os

import pandas as pd  # type: ignore
from metaflow import FlowSpec, step

from datasets import Mode, dataset


flow_dir = os.path.dirname(os.path.realpath(__file__))
my_dataset_foreach_path = os.path.join(flow_dir, "data/my_dataset_foreach")


class ForeachDatasetFlow(FlowSpec):
    @step
    def start(self):
        self.regions = ["A", "B"]
        self.next(self.foreach_split, foreach="regions")

    @dataset(
        name="my_dataset_foreach",
        path=my_dataset_foreach_path,
        partition_by="region",
        mode=Mode.WRITE,
    )
    @step
    def foreach_split(self):
        df = pd.DataFrame({"zpid": [1, 2, 3] if self.input == "A" else [4, 5, 6]})

        # Set
        df["region"] = self.input
        print(f"saving: {self.input=}")

        # Example of writing to a dataset with a path within a foreach split
        self.my_dataset_foreach.write(df)

        self.next(self.join_step)

    @step
    def join_step(self, inputs):
        self.merge_artifacts(inputs, include=["my_dataset_foreach"])
        self.next(self.end)

    @step
    def end(self):
        print(f"I have datasets \n{self.my_dataset_foreach=}\n")
        print(
            self.my_dataset_foreach.read_pandas().to_string(index=False),
        )


if __name__ == "__main__":
    ForeachDatasetFlow()
