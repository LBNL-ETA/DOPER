import time
from pymodbus.constants import Endian
from pymodbus.payload import BinaryPayloadBuilder
from pymodbus.payload import BinaryPayloadDecoder
from pymodbus.client import ModbusSerialClient
from pymodbus.client import ModbusTcpClient

import binascii
import struct

MAX_RETRY = 5
SLEEP = 0.5
TIMEOUT = 0.5

def modbus_client(port=None, ip=None, baudrate=9600, stopbits=1, timeout=TIMEOUT):
    if ip:
        port = port if port else 502
        client = ModbusTcpClient(ip, port=port, timeout=timeout)
            #framer=ModbusFramer)
        client.connect()
    else:
        client = ModbusSerialClient("rtu", port=port, baudrate=baudrate,
                                    parity='N', bytesize=8, stopbits=stopbits,
                                    timeout=timeout)
    return client
    
def set_reading_method(client, holding=True):
    if holding:
        return client.read_holding_registers
    else:
        return client.read_input_registers
        
def decode(res, byteorder='big', wordorder='little', has_registers=True):
    val = res.registers if has_registers else [res]
    decoder = BinaryPayloadDecoder.fromRegisters(val, \
        byteorder = Endian.BIG if byteorder == 'big' else Endian.LITTLE,
        wordorder = Endian.BIG if wordorder == 'big' else Endian.LITTLE)
    return decoder
    
def encode(byteorder='big', wordorder='little'):
    encoder = BinaryPayloadBuilder( \
        byteorder = Endian.BIG if byteorder == 'big' else Endian.LITTLE,
        wordorder = Endian.BIG if wordorder == 'big' else Endian.LITTLE)
    return encoder

def read_register_float32(client, address, inv_id, count=2,
                          sleep=SLEEP, holding=True, order=['big','little']):
    reader = set_reading_method(client, holding=holding)
    res = reader(address, count=count, slave=inv_id)
    i = 0
    while res.isError() and i < MAX_RETRY:
        time.sleep(sleep)
        res = reader(address, count=count, slave=inv_id)
        i += 1
    decoder = decode(res, byteorder=order[0], wordorder=order[1])
    return decoder.decode_32bit_float(), i

def read_register_int16(client, address, inv_id, count=1, decode_res=True,
                        sleep=SLEEP, holding=True, order=['big','little'], batch_data=False):
    reader = set_reading_method(client, holding=holding)
    res = reader(address, count=count, slave=inv_id)
    i = 0
    while res.isError() and i < MAX_RETRY:
        time.sleep(sleep)
        res = reader(address, count=count, slave=inv_id)
        i += 1
    if batch_data and decode_res:
        res_dec = []
        for rg in res.registers:
            decoder = decode(rg, byteorder=order[0], wordorder=order[1], has_registers=False)
            res_dec.append(decoder.decode_16bit_int())
        return res_dec, i
    elif not decode_res:
        return res, i
    else:
        decoder = decode(res, byteorder=order[0], wordorder=order[1])
        return decoder.decode_16bit_int(), i
    
def read_register_uint16(client, address, inv_id, count=1,
                         sleep=SLEEP, holding=True, order=['big','little']):
    reader = set_reading_method(client, holding=holding)
    res = reader(address, count=count, slave=inv_id)
    i = 0
    while res.isError() and i < MAX_RETRY:
        time.sleep(sleep)
        res = reader(address, count=count, slave=inv_id)
        i += 1
    decoder = decode(res, byteorder=order[0], wordorder=order[1])
    return decoder.decode_16bit_uint(), i
    
def read_coil(client, address, inv_id, count=1, sleep=SLEEP):
    res = client.read_coils(address=address, count=count, slave=inv_id)
    i = 0
    while res.isError() and i < MAX_RETRY:
        time.sleep(sleep)
        res = client.read_coils(address=address, count=count, slave=inv_id)
        i += 1
    res = res.bits[:count]
    if len(res) == 1:
        res = res[0]
    return res, i
   
def write_register_int16(client, address, inv_id, value,
                         sleep=SLEEP, order=['big','little']):
    builder = encode(byteorder=order[0], wordorder=order[1])
    builder.add_16bit_int(value)
    res = client.write_registers(address, builder.to_registers(), slave=inv_id)
    i = 0
    while res.isError() and i < MAX_RETRY:
        time.sleep(sleep)
        res = client.write_registers(address, builder.to_registers(), slave=inv_id)
        i += 1
    return i
    
def write_register_uint16(client, address, inv_id, value,
                          sleep=SLEEP, order=['big','little']):
    builder = encode(byteorder=order[0], wordorder=order[1])
    builder.add_16bit_uint(value)
    res = client.write_registers(address, builder.to_registers(), slave=inv_id)
    i = 0
    while res.isError() and i < MAX_RETRY:
        time.sleep(sleep)
        res = client.write_registers(address, builder.to_registers(), slave=inv_id)
        i += 1
    return i
    
def write_register_float32(client, address, inv_id, value,
                           sleep=SLEEP, order=['big','little']):    
    builder = encode(byteorder=order[0], wordorder=order[1])
    builder.add_32bit_float(value)
    res = client.write_registers(address, builder.to_registers(), slave=inv_id)
    i = 0
    while res.isError() and i < MAX_RETRY:
        time.sleep(sleep)
        res = client.write_registers(address, builder.to_registers(), slave=inv_id)
        i += 1
    return i
    
def write_coil(client, address, inv_id, value, sleep=SLEEP):
    res = client.write_coils(address=address, values=value, slave=inv_id)
    i = 0
    while res.isError() and i < MAX_RETRY:
        time.sleep(sleep)
        res = client.write_coils(address=address, values=value, slave=inv_id)
        i += 1
    return i
