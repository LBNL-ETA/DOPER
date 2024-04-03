import time
import json
from fmlc.baseclasses import eFMU

class communication_dummy(eFMU):
    def __init__(self):
        self.input = {'input-data': None, 'config': None, 'timeout': None}
        self.output = {'output-data': None, 'duration': None}

    def compute(self):
        st = time.time()

        self.output['output-data'] = {}
        config = json.loads(self.input['config'])
        if isinstance(config, dict):
            self.output['output-data'].update(config)
        else:
            self.output['output-data'] = config

        self.output['duration'] = time.time() - st
        return 'Done.'
