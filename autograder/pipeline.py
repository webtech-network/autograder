from autograder.models.abstract.step import Step
from autograder.models.pipeline_execution import PipelineExecution
from autograder.models.dataclass.submission import Submission

class AutograderPipeline:
    def __init__(self):
        self._steps = []

    def add_step(self, step: Step) -> None:
        self._steps.append(step)

    def run(self, submission:'Submission'):

        pipeline_execution = PipelineExecution.create_pipeline_obj(submission)

        for step in self._steps:
            print("Executing step:", step.__class__.__name__) # TODO: Replace with proper logging

            if not pipeline_execution.get_previous_step.is_successful:
                pipeline_execution.set_failure()
                break

            pipeline_execution = step.execute(pipeline_execution)

        return pipeline_execution



