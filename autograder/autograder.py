from autograder.models.abstract.step import Step
from autograder.models.pipeline_execution import PipelineExecution
from autograder.services.report.reporter_service import ReporterService
from autograder.services.upstash_driver import UpstashDriver
from autograder.steps.export_step import ExporterStep
from autograder.steps.feedback_step import FeedbackStep
from autograder.steps.grade_step import GradeStep
from autograder.steps.load_template_step import TemplateLoaderStep
from autograder.steps.pre_flight_step import PreFlightStep
from autograder.steps.build_tree_step import BuildTreeStep

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


def build_pipeline(
                 template_name,
                 include_feedback,
                 grading_criteria,
                 feedback_config,
                 setup_config = None,
                 custom_template = None,
                 feedback_mode = None) -> AutograderPipeline:
    """
    Build the AutograderPipeline object based on configuration.

    Args:
        template_name: Name of the template to use
        include_feedback: Whether to include feedback generation
        grading_criteria: Criteria configuration dictionary
        feedback_config: Configuration for feedback generation
        setup_config: Pre-flight setup configuration
        custom_template: Custom template object (if any)
        feedback_mode: Mode for feedback generation
    Returns:
        Configured AutograderPipeline
    """
    pipeline = AutograderPipeline()

    # Load template
    pipeline.add_step(TemplateLoaderStep(template_name, custom_template)) # Passes the template to the next step

    pipeline.add_step(BuildTreeStep(grading_criteria)) # Uses template to match selected tests in criteria and builds tree

    # Pre-flight checks (if configured)
    if setup_config:
        pipeline.add_step(PreFlightStep(setup_config))

    pipeline.add_step(GradeStep()) # Generates GradingResult with final score and result tree

    # Feedback generation (if configured)
    if include_feedback:
        reporter_service = ReporterService(feedback_mode=feedback_mode)
        pipeline.add_step(FeedbackStep(reporter_service, feedback_config)) # Uses GradingResult to generate feedback and appends it to GradingResult

    # Export results
    pipeline.add_step(ExporterStep(UpstashDriver)) # Exports final results and feedback to external system

    return pipeline


