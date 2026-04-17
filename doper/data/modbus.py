import time
# from pymodbus.constants import Endian
# from pymodbus.payload import BinaryPayloadBuilder
# from pymodbus.payload import BinaryPayloadDecoder
from pymodbus.client import ModbusSerialClient
from pymodbus.client import ModbusTcpClient
from pymodbus.client.mixin import ModbusClientMixin

# import binascii
# import struct

MAX_RETRY = 5
SLEEP = 0.5
TIMEOUT = 0.5

# DATATYPES
# https://github.com/pymodbus-dev/pymodbus/blob/dev/pymodbus/client/mixin.py#L680

def address_to_tuple(address):
    address = address.split(':')
    if len(address) > 1:
        if len(address[0]) < 6:
            address[0] = None
        try:
            # TCP
            address[1] = int(address[1])
        except:
            pass
        if len(address) >= 3:
            address[2] = int(address[2])
        else:
            address.append(0) # set slave to 0
        if len(address) >= 4:
            address[3] = int(address[3])
        return tuple(address)
    # RTU (simple)
    return tuple([None, address, 0, 9600])

def get_uniconn(addr):
    return str(':'.join(addr.split(':')[:2]))

def modbus_client(port=None, ip=None, baudrate=9600, stopbits=1, timeout=TIMEOUT):
    if ip:
        port = port if port else 502
        client = ModbusTcpClient(ip, port=port, timeout=timeout)
            #framer=ModbusFramer)
        client.connect()
    else:
        client = ModbusSerialClient(port=port, baudrate=baudrate,
                                    parity='N', bytesize=8, stopbits=stopbits,
                                    timeout=timeout)
        client.connect()
    return client
    
### Holding Registers ###
def set_reading_method(client, holding=True):
    if holding:
        return client.read_holding_registers
    else:
        return client.read_input_registers
    
def swap_bytes_in_registers(registers):
    # 0x1234 -> 0x3412
    return [((r & 0xFF) << 8) | ((r >> 8) & 0xFF) for r in registers]
    
def read_register(client, address, device_id, data_type='int16', decode_res=True,
                  sleep=SLEEP, holding=True, order=['big','little'], batch_data=False):
    reader = set_reading_method(client, holding=holding)
    data_type = ModbusClientMixin.DATATYPE[data_type.upper()]
    count = data_type.value[1]
    res = reader(address, count=count, device_id=device_id)
    i = 0
    while res.isError() and i < MAX_RETRY:
        time.sleep(sleep)
        res = reader(address, count=count, device_id=device_id)
        i += 1
    if batch_data and decode_res:
        res_dec = []
        for rg in res.registers:
            value = client.convert_from_registers(registers=[rg],
                                                  data_type=data_type,
                                                  word_order=order[1])
            res_dec.append(value)
        return res_dec, i
    elif not decode_res:
        return res, i
    else:
        reg_values = res.registers
        if order[0] == 'little':
            reg_values = swap_bytes_in_registers(reg_values)
        value = client.convert_from_registers(registers=reg_values,
                                              data_type=data_type,
                                              word_order=order[1])
        return value, i
    
def write_register(client, address, device_id, value, data_type='int16',
                   sleep=SLEEP, order=['big','little']):
    data_type = ModbusClientMixin.DATATYPE[data_type.upper()]
    payload = client.convert_to_registers(value=value,
                                          data_type=data_type,
                                          word_order=order[1])
    if order[0] == 'little':
        payload = swap_bytes_in_registers(payload)
    res = client.write_registers(address, payload, device_id=device_id)
    i = 0
    while res.isError() and i < MAX_RETRY:
        time.sleep(sleep)
        res = client.write_registers(address, payload, device_id=device_id)
        i += 1
    return i

### Coils ###
def read_coil(client, address, device_id, count=1, sleep=SLEEP):
    res = client.read_coils(address=address, count=count, device_id=device_id)
    i = 0
    while res.isError() and i < MAX_RETRY:
        time.sleep(sleep)
        res = client.read_coils(address=address, count=count, device_id=device_id)
        i += 1
    res = res.bits[:count]
    if len(res) == 1:
        res = res[0]
    return res, i

def write_coil(client, address, device_id, value, sleep=SLEEP):
    res = client.write_coils(address=address, values=value, device_id=device_id)
    i = 0
    while res.isError() and i < MAX_RETRY:
        time.sleep(sleep)
        res = client.write_coils(address=address, values=value, device_id=device_id)
        i += 1
    return i
