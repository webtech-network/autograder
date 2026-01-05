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
    setup_config=None,
    custom_template=None,
    feedback_mode=None,
    submission_files=None,
    submission_id=None,
):
    """
    Build an autograder pipeline based on configuration.

    Args:
        template_name: Name of the template to use
        include_feedback: Whether to include feedback generation
        grading_criteria: Criteria configuration dictionary
        feedback_config: Configuration for feedback generation
        setup_config: Pre-flight setup configuration
        custom_template: Custom template object (if any)
        feedback_mode: Mode for feedback generation
        submission_files: Student submission files
        submission_id: Optional submission identifier
        is_multi_submission: Whether grading multiple submissions (requires tree building)

    Returns:
        Configured AutograderPipeline
    """
    pipeline = AutograderPipeline()

    # Pre-flight checks (if configured)
    if setup_config:
        pipeline.add_step(PreFlightStep(setup_config))

    # Load template
    pipeline.add_step(TemplateLoaderStep(template_name, custom_template))

    # Parse the criteria tree
    pipeline.add_step(BuildTreeStep(grading_criteria))

    # Grade
    pipeline.add_step(
        GradeStep(submission_files=submission_files, submission_id=submission_id)
    )

    # Feedback generation (if configured)
    if include_feedback:
        reporter_service = ReporterFactory.create_reporter_for(feedback_mode)
        pipeline.add_step(FeedbackStep(reporter_service, feedback_config))

    # Export results
    pipeline.add_step(ExporterStep(UpstashDriver))

    return pipeline
