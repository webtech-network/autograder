from autograder.models.abstract.step import Step
from autograder.services.pre_flight_service import PreFlightService


class PreFlightStep(Step):
    def __init__(self, setup_config):
        self._setup_config = setup_config
        self._pre_flight_service = PreFlightService
    def execute(self, input):
        pass