import os
import io
import sys
import json
import time
import traceback
import numpy as np
import pandas as pd
import datetime as dtm

from pymodbus.client import ModbusTcpClient
# from pymodbus.framer.socket_framer import ModbusSocketFramer

try:
    root = os.path.dirname(os.path.abspath(__file__))
except:
    root = os.getcwd()

# Import FMLC
from fmlc import eFMU, controller_stack, check_error, pdlog_to_df

import doper.data.modbus as modbus_io

class dummy_connect():
    def close(self):
        pass

def address_to_tuple(address):
    address = address.split(':')
    address[1] = int(address[1])
    if len(address) != 3:
        address.append(0) # set slave to 0
    else:
        address[2] = int(address[2])
    return tuple(address)

class communication_scada(eFMU):
    def __init__(self):
        self.input = {'input-data':None, 'timeout':None, 'channels':None, 'mode':None}
        self.output = {'output-data':None, 'duration':None}
        
        self.init = True
        
    def res_to_msg(self, res):
        if not 'error' in res.columns:
            msg = 'ERROR: No result returned. Check channels dataframe.'
        elif res['error'].str.contains('ERROR').any():
            msg = 'ERROR: See "output-data".'
        else:
            msg = 'Done.'
        return msg
        
    def read_modbus(self, channel, client, sleep=0.5, max_tries=1, dev_id=0):
        register = channel['register']
        mode = channel['mode']
        default = channel['default']
        
        # holding register
        holding = True
        if 'holding' in channel.keys():
            holding = channel['holding']
            
        # byte order
        order = ['big','little']
        if 'order' in channel.keys():
            order = channel['order']
            if isinstance(order, str):
                order = json.loads(order)
        
        # read register
        try:
            if mode == 'int':
                r, i = modbus_io.read_register_int16(client, register, \
                    dev_id, sleep=sleep, holding=holding, order=order)
            elif mode == 'uint':
                r, i = modbus_io.read_register_uint16(client, register, \
                    dev_id, sleep=sleep, holding=holding, order=order)
            elif mode == 'float':
                r, i = modbus_io.read_register_float32(client, register, \
                    dev_id, sleep=sleep, holding=holding, order=order)
            elif mode == 'coil':
                r, i = modbus_io.read_coil(client, register, \
                    dev_id, sleep=sleep)
            else:
                return default, f'ERROR: Mode "{mode}" not implemented.'

            if i > max_tries:
                return default, f'ERROR: Could not read value after {i} attempts.'
            else:
                return [r, '']                
        except Exception as e:
            return default, f'ERROR: {e}'
        
    def write_modbus(self, channel, value, client, sleep=0.5, max_tries=1, dev_id=0):
        register = channel['register']
        mode = channel['mode']
        
        # byte order
        order = ['big','little']
        if 'order' in channel.keys():
            order = channel['order'] 
        
        # write register
        try:
            if mode == 'int':
                i = modbus_io.write_register_int16(client, register, \
                    dev_id, int(value), sleep=sleep, order=order)
            elif mode == 'uint':
                i = modbus_io.write_register_uint16(client, register, \
                    dev_id, int(value), sleep=sleep, order=order)
            elif mode == 'float':
                i = modbus_io.write_register_float32(client, register, \
                    dev_id, value, sleep=sleep, order=order)
            elif mode == 'coil':
                i = modbus_io.write_coil(client, register, \
                    dev_id, value, sleep=sleep)
            else:
                return f'ERROR: Mode "{mode}" not implemented.'
            
            if i > max_tries:
                return f'ERROR: Could not write value after {i} attempts.'
            else:
                return ''
        except Exception as e:
            return f'ERROR: {e}'

    def get_scada(self):
        res = []
        
        # get scada
        try:
            # connect modbus
            clients = {'dummy': dummy_connect()}
            channels = json.loads(self.input['channels'])
            
            if pd.DataFrame(channels)['name'].duplicated().any():
                raise ValueError(f'Duplicated entries in channel names.')
                
            #address = np.unique([e['address'] for e in channels])
            #if len(address) > 1:
            #    raise ValueError (f'Only same addresses are supported. {address}')
            #address = address_to_tuple(address[0])
            #client = ModbusTcpClient(host=address[0], port=address[1], framer=ModbusSocketFramer)
            #client.connect()

            # connect clients
            clients = {}
            for addr in sorted(np.unique([e['address'] for e in channels])):
                addr2 = address_to_tuple(addr)
                clients[addr] = ModbusTcpClient(host=addr2[0], port=addr2[1])#, framer=ModbusSocketFramer)
                clients[addr].connect()
            
            # read
            for c in channels:
                st = time.time()
                r = {}
                addr = c['address']
                if c['register'] == -1:
                    # dummy; use default
                    r['value'] = c['default']
                    r['error'] = ''
                    r['valid'] = 0
                else:
                    r['value'], r['error'] = self.read_modbus(c, clients[addr], dev_id=address_to_tuple(addr)[2])
                    r['valid'] = int(r['error'] == '')
                r['name'] = c['name']
                r['duration'] = time.time()-st
                res.append(r)
            res = pd.DataFrame(res)
        except Exception as e:
            e = f'ERROR: {e}\n\n{traceback.format_exc()}'
            res = pd.DataFrame(res)
            for c in channels:
                if not c['name'] in res['name']:
                    res.loc[len(res), ['name', 'value', 'error', 'valid', 'duration']] = \
                        [c['name'], c['default'], f'ERROR: {e}', int(False), 0]
        finally:
            [client.close() for client in clients.values()]
        if 'name' in res.columns:
            res.index = res['name']
        return res
        
    def set_scada(self):
        inputs = pd.read_json(io.StringIO(self.input['input-data']))
        res = []
        
        # set scada
        try:
            # Connect modbus
            client = dummy_connect()
            channels = json.loads(self.input['channels'])
            
            if pd.DataFrame(channels)['name'].duplicated().any():
                raise ValueError(f'Duplicated entries in channel names.')
            
            address = np.unique([e['address'] for e in channels])
            if len(address) > 1:
                raise ValueError (f'Only same addresses are supported. {address}')
            address = address_to_tuple(address[0])
            client = ModbusTcpClient(host=address[0], port=address[1])#, framer=ModbusSocketFramer)
            client.connect()
            # Write
            for c in channels:
                name = c['name']
                st = time.time()
                r = {}
                if name in inputs['name'].values:
                    v = inputs['value'][inputs['name']==name].values[-1] # FIXME always latest element
                    r['value'] = v
                    r['error'] = self.write_modbus(c, v, client, dev_id=address[2])
                    r['valid'] = int(r['error'] == '')
                else:
                    r['value'] = None
                    r['error'] = f'ERROR: Channel "{name}" not in input-data.'
                    r['valid'] = int(False)
                r['name'] = name
                r['duration'] = time.time()-st
                res.append(r)
            res = pd.DataFrame(res)
        except Exception as e:
            e = f'ERROR: {e}\n\n{traceback.format_exc()}'
            res = pd.DataFrame(res)
            for c in channels:
                if not c['name'] in res['name']:
                    res.loc[len(res), ['name', 'value', 'error', 'valid', 'duration']] = \
                        [c['name'], c['value'], f'ERROR: {e}', int(False), 0]
        finally:
            client.close()
        if 'name' in res.columns:
            res.index = res['name']
        return res
        
    def check_data(self, data):
        if (data == -1 or not data) and self.init:
            return 'INFO: Waiting to initialize.'
        elif (data == -1 or not data) and not self.init:
            return 'ERROR: Missing data.'
        
    def compute(self):
        st = time.time()
        self.mode = self.input['mode']
        if self.mode == 'get_scada':
            self.res = self.get_scada()
            self.output['output-data'] = self.res.to_json()
            msg = self.res_to_msg(self.res)
            self.init = False
        elif self.mode == 'set_scada':
            e = self.check_data(self.input['input-data'])
            if e:
                msg = e
            else:
                self.res = self.set_scada()
                self.output['output-data'] = self.res.to_json()
                msg = self.res_to_msg(self.res)
                self.init = False
        else:
            msg = 'ERROR: Unknown mode.'
        self.output['duration'] = time.time()-st
        return msg