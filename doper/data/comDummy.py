import time
from fmlc.baseclasses import eFMU

class communication_dummy(eFMU):
    def __init__(self):
        self.input = {'input-data': None, 'config': None, 'timeout': None}
        self.output = {'output-data': None, 'duration': None}

    def compute(self):
        st = time.time()

        self.output['output-data'] = {}
        for k, v in self.input['config']:
            self.output['output-data'][k] = v

        self.output['duration'] = time.time() - st
        return 'Done.'
