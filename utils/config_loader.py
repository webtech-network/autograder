import json

from aiohttp import WSMessage


class Config:
    def __init__(self):
        self.config = {}
        self.base_config = None
        self.bonus_config = None
        self.penalty_config = None

    def parse_config(self, config_file: str):
        try:
            with open(config_file, 'r', encoding='utf-8') as file:
                self.config = json.load(file)
        except FileNotFoundError:
            raise Exception(f"Config file '{config_file}' not found.")
        except json.JSONDecodeError as e:
            raise Exception(f"Error parsing JSON from '{config_file}': {e}")

    def load_base_config(self):
        self.base_config = TestConfig.create("base", self.config)

    def load_bonus_config(self):
        self.bonus_config = TestConfig.create("bonus", self.config)

    def load_penalty_config(self):
        self.penalty_config = TestConfig.create("penalty", self.config)

    @classmethod
    def create_config(cls, config_file: str):
        response = cls()
        try:
            response.parse_config(config_file)
            response.load_base_config()
            response.load_bonus_config()
            response.load_penalty_config()
        except Exception as e:
            raise Exception(f"Failed to create config: {e}")
        return response


class TestConfig:
    def __init__(self, ctype):
        self.ctype = ctype
        self.weight = 0
        self.sub_configs = []

    def load(self, config: dict):
        try:
            section = config[self.ctype]
            self.weight = section['weight']
            self.load_subjects(section['subjects'].items())
        except KeyError as e:
            raise Exception(f"Missing expected key in config for '{self.ctype}': {e}")
    def load_subjects(self, subjects: dict):
        if subjects is None or subjects == {}:
            return False
        for subj, val in subjects.items():
            sub_config = SubTestConfig.create(subj, val)
            self.sub_configs.append(sub_config)


    def __str__(self):
        display = f"Config ctype: {self.ctype}\n"
        display += f"Weight: {self.weight}\n"
        for sub_config in self.sub_configs:
            display += f"{sub_config}\n"
        return display

    @classmethod
    def create(cls, ctype, config_dict: dict):
        response = cls(ctype)
        response.load(config_dict)
        return response


class SubTestConfig(TestConfig):
    def __init__(self, ctype):
        super().__init__(ctype)
        self.convention = ""

    def load(self, config: dict):
        try:
            self.weight = config['weight']
            self.convention = config['test_path']
        except KeyError as e:
            raise Exception(f"Missing key in subtest config for '{self.ctype}': {e}")

    def __str__(self):
        display = f"\tConfig ctype: {self.ctype}\n"
        display += f"\tWeight: {self.weight}\n"
        display += f"\tConvention: {self.convention}\n"
        return display
