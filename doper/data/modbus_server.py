import io
import os
import sys
import json
import time
import logging
import traceback
import numpy as np
import pandas as pd
import datetime as dtm
import subprocess as sp

from pymodbus.server import StartTcpServer
# from pymodbus.framer.socket_framer import ModbusSocketFramer
from pymodbus.datastore import ModbusSequentialDataBlock, ModbusDeviceContext, ModbusServerContext

try:
    root = os.path.dirname(os.path.abspath(__file__))
    is_jupyter = False
except:
    root = os.getcwd()
    is_jupyter = True

# Import FMLC
from fmlc import eFMU, controller_stack, check_error, pdlog_to_df
from fmlc.stackedclasses import PythonDB_wrapper, write_db, read_db

from pymodbus.client.mixin import ModbusClientMixin
# import doper.data.modbus as modbus_io

class registerDummy:
    def __init__(self, v):
        self.registers = v

class ModbusHandler():
    """Creates an instance of a single SCADA register."""
    
    def __init__(self, name, rtype, db_addr):
        """Initialize the sigle register."""
        self.name = name
        self.rtype = rtype
        self.db_addr = db_addr
        self.client = ModbusClientMixin()
        
    def getValue(self):
        """Get current value."""
        v = read_db(self.db_addr)[self.name]
        if self.rtype.lower() == 'float':
            return self.client.convert_to_registers(value=v,
                                                    data_type='float32')
        elif self.rtype.lower() == 'int':
            return self.client.convert_to_registers(value=v,
                                                    data_type='int16')            
        else:
            return v
        
    def setValue(self, v):
        """Set new value."""
        if self.rtype.lower() == 'float':
            v = self.client.convert_from_registers(registers=v,
                                                   data_type='float32')
        elif self.rtype.lower() == 'int':
            v = [v]
            v = self.client.convert_from_registers(registers=v,
                                                   data_type='int16')
        write_db({self.name: v}, self.db_addr)


class ModbusDataBlock(ModbusSequentialDataBlock):
    """Creates an instance of ModbusSequentialDataBlock
    but overwrites getValues and setValues with custom functions for SCADA.
    See more information: https://github.com/pymodbus-dev/pymodbus/blob/dev/pymodbus/datastore/store.py#L124C7-L124C32
    """
    
    def __init__(self, address, values):
        """Initialize the datastore.

        :param address: The starting address of the datastore
        :param values: Either a list or a dictionary of values
        """
        self.address = address
        if hasattr(values, "__iter__"):
            self.values = list(values)
        else:
            self.values = [values]
        self.default_value = -1

    def getValues(self, address, count=1):
        """Return the requested values of the datastore.

        :param address: The starting address
        :param count: The number of values to retrieve
        :returns: The requested values from a:a+c
        """
        start = address - self.address
        res = []
        stored_next = False
        for i in range(start, start + count):
            if stored_next:
                res.append(v[1])
                stored_next = False
            else:
                if isinstance(self.values[i], ModbusHandler):
                    # get from SCADA
                    v = self.values[i].getValue()
                    if isinstance(v, list):
                        res.append(v[0])
                        stored_next = True
                else:
                    # directly from pymodbus
                    res.append(self.values[i])
        return res

    def setValues(self, address, values):
        """Set the requested values of the datastore.

        :param address: The starting address
        :param values: The new values to be set
        """
        if not isinstance(values, list):
            values = [values]
        start = address - self.address
        stored_next = False
        for i, v in zip(range(start, start + len(values)), values):
            if stored_next:
                stored_next = False
                vv.append(v)
                self.values[i-1].setValue(vv)
            else:
                if isinstance(self.values[i], ModbusHandler):
                    # set SCADA
                    if 'float' in self.values[i].rtype:
                        stored_next = True
                        vv = [v]
                    else:
                        self.values[i].setValue(v)
                else:
                    # directly from pymodbus
                    self.values[i] = v

def make_dynamic_registers(channels, db_addr):
    registers = []
    for r in range(0, channels['register'].max()+2):
        if r in channels['register'].values:
            tt = channels[channels['register']==r]
            registers.append(ModbusHandler(tt['name'].values[0], tt['mode'].values[0], db_addr))
        else:
            # not in registers, add as dummy
            registers.append(0)
    hr = ModbusDataBlock(1, registers)
    return hr

def make_scada_server(slave_ids=None, log_level=logging.WARN):
    # send pid
    # print(os.getpid())
    
    # read config
    db_addr = sys.argv[1]
    channels = pd.read_json(io.StringIO(sys.argv[2]))
    channels = channels.sort_values('register')
    if len(sys.argv) > 3:
        if sys.argv[3] == 'debug':
            log_level = logging.DEBUG

    # make context
    if 'slave_id' in channels.columns:
        slaves = {}
        for slave_id in sorted(channels['slave_id'].unique()):
            # make dyanmic registers
            hr = make_dynamic_registers(channels[channels['slave_id']==slave_id], db_addr)
            slaves[slave_id] = ModbusDeviceContext(hr=hr)
        single = False
    else:
        # make dyanmic registers
        hr = make_dynamic_registers(channels, db_addr)
        slaves = ModbusDeviceContext(hr=hr)
        single = True
    context = ModbusServerContext(slaves=slaves, single=single)

    # setup logging
    logging.basicConfig()
    log = logging.getLogger('pymodbus')
    log.setLevel(log_level)

    # start server
    address = channels['address'].iloc[0].split(':')
    address[1] = int(address[1])
    StartTcpServer(context=context,
                   address=address)
                #    framer=ModbusSocketFramer)

def kill_scada_server():
    x = sp.check_output(['ps -eaf | grep scada_server.py'], shell=True)
    pids = [int(xx.split('root     ')[1][0:5]) for xx in x.decode().split('\n')[:-3]]
    for p in pids:
        sp.call([f"kill -9 {p}"], shell=True, cwd=root)

class server_scada(eFMU):
    def __init__(self):
        self.input = {'input-data':None, 'debug':None, 'timeout':None, 'channels':None}
        self.output = {'output-data':None, 'duration':None}
        
        self.init = True
        self.database = None
        self.modbus = None
        
    def check_data(self, data):
        if (data == -1 or not data) and self.init:
            return 'INFO: Waiting to initialize.'
        elif (data == -1 or not data) and not self.init:
            return 'ERROR: Missing data.'
        return ''

    def check_init_db(self):
        # check if database is running and responding
        if self.database:
            try:
                read_db(self.database.address)
            except:
                self.database = None

        # start database if not running
        self.name = self.channels.iloc[0]['address']
        if self.database is None:
            self.database = PythonDB_wrapper(self.name, 'pythonDB')
            self.database.address = '127.0.0.1:'+str(self.database.port)
            # init database
            write_db({r[1]['name']: r[1]['default'] for r in self.channels.iterrows()}, self.database.address)

        return self.database.error

    def check_init_modbus(self):
        # check if modbus is running and responding
        if self.modbus:
            try:
                pass
            except:
                self.modbus.kill()
                self.modbus = None

        # start modbus if not running
        if self.modbus is None:
            log_level = 'debug' if self.input['debug'] else ''
            self.modbus = sp.Popen([f"exec python3 -u scada_server.py {self.database.address} '{self.channels.to_json()}' {log_level}"], shell=True, cwd=root)
            
        return ''       
        
    def compute(self):
        st = time.time()
        msg = ''

        # check input data
        msg += self.check_data(self.input['input-data'])
        
        if msg == '':
            self.channels = pd.read_json(io.StringIO(self.input['channels']))
            
            # check if pythonDB is running otherwise start it
            msg += self.check_init_db()

            # check if Modbus Server is running otherwise start it
            msg += self.check_init_modbus()
        
        # sync Modbus with Controller stack
        if msg == '':
            try:
                channels_write = self.channels['name'][self.channels['access']=='r'].values
                input_data = pd.read_json(io.StringIO(self.input['input-data'])).set_index('name')['value'].to_dict()
                write_db({k:v for k,v in input_data.items() if k in channels_write}, self.database.address)
                channels_read = self.channels['name'][self.channels['access']=='w'].values
                self.output['output-data'] = {k:v for k,v in read_db(self.database.address).items() if k in channels_read}
            except Exception as e:
                msg += f'ERROR: {e}\n\n{traceback.format_exc()}'

        self.init = False
        self.output['duration'] = time.time()-st
        return msg

if __name__ == '__main__' and not is_jupyter:
    make_scada_server()
