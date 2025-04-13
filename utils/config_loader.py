import json

from _pytest.config import Config


class Config:
    def __init__(self):
        self.config = {} #config json parsing to dict
        self.base_config = None
        self.bonus_config = None
        self.penalty_config = None
    def parse_config(self,config_file : str):
        self.config = json.load(open(config_file))
    def load_base_config(self):
        self.base_config = TestConfig.create("base",self.config)
    def load_bonus_config(self):
        self.bonus_config = TestConfig.create("bonus",self.config)
    def load_penalty_config(self):
        self.penalty_config = TestConfig.create("penalty",self.config)
    @classmethod
    def create_config(cls,config_file : str) -> Config:
        response = Config()
        response.parse_config(config_file)
        response.load_base_config()
        response.load_bonus_config()
        response.load_penalty_config()
        return response


class TestConfig():
    def __init__(self,ctype):
        self.ctype = ctype
        self.weight = 0
        self.sub_configs = []
    def load(self,config:dict):
        self.weight = config[self.ctype]['weight']
        for subj in config[self.ctype]['subjects']:
            sub_config = SubTestConfig.create(subj,config[self.ctype]['subjects'][subj])
            self.sub_configs.append(sub_config)
    def __str__(self):
        display = f"Config ctype: {self.ctype}\n"
        display += f"Weight: {self.weight}\n"
        for sub_config in self.sub_configs:
            display += f"{sub_config}\n"
        return display
    @classmethod
    def create(cls,ctype,config_dict:dict):
        response = cls(ctype)
        response.load(config_dict)
        return response


class SubTestConfig(TestConfig):
    def __init__(self,ctype):
        super().__init__(ctype)
        self.convention = ""
    def load(self,config:dict):
        self.weight = config['weight']
        self.convention = config['test_path']
    def __str__(self):
        display = f"\tConfig ctype: {self.ctype}\n"
        display += f"\tWeight: {self.weight}\n"
        display += f"\tConvention: {self.convention}\n"
        return display





