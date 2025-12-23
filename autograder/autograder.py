from autograder.services.report.reporter_factory import ReporterFactory
from autograder.services.upstash_driver import UpstashDriver
from autograder.pipeline import AutograderPipeline
from autograder.steps.export_step import ExporterStep
from autograder.steps.feedback_step import FeedbackStep
from autograder.steps.grade_step import GradeStep
from autograder.steps.load_template_step import TemplateLoaderStep
from autograder.steps.pre_flight_step import PreFlightStep
from autograder.steps.build_tree_step import BuildTreeStep


def build_pipeline(
                 template_name,
                 include_feedback,
                 grading_criteria,
                 feedback_config,
                 setup_config = None,
                 custom_template = None,
                 feedback_mode = None):

    pipeline = AutograderPipeline()
    if setup_config:
        pipeline.add_step(PreFlightStep(setup_config))
    pipeline.add_step(TemplateLoaderStep(template_name,custom_template))
    pipeline.add_step(BuildTreeStep(grading_criteria))
    pipeline.add_step(GradeStep())
    if include_feedback:
        reporter_service = ReporterFactory.create_reporter_for(feedback_mode)
        pipeline.add_step(FeedbackStep(reporter_service,feedback_config))
    pipeline.add_step(ExporterStep(UpstashDriver)) # Placeholder for remote driver
    return pipeline




