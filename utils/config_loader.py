


class Config:
    def __init__(self,config_file : str):
        self.config = {} #config json parsing to dict
        self.base_config = None
        self.bonus_config = None
        self.penalty_config = None





class TestConfig():
    def __init__(self,type):
        self.type = type
        self.weight = 0
        self.sub_configs = []
    def load(self,config:dict):
        self.weight = config['weight']
        for subj in config['subjects']:
            sub_config = SubTestConfig.create(subj,config['subjects'][subj])
            self.sub_configs.append(sub_config)
    @classmethod
    def create(cls,type,config:dict):
        config = cls(type)
        config.load(config)
        return config


class SubTestConfig(TestConfig):
    def __init__(self,type):
        super().__init__(type)
        self.convention = ""
    def load(self,config:dict):
        self.weight = config['weight']
        self.convention = config['convention']
    @classmethod
    def create(cls,type,config:dict):
        sub_config = SubTestConfig(type)
        sub_config.load(config)
        return sub_config




