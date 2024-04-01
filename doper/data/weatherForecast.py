# Distributed Optimal and Predictive Energy Resources (DOPER) Copyright (c) 2019
# The Regents of the University of California, through Lawrence Berkeley
# National Laboratory (subject to receipt of any required approvals
# from the U.S. Dept. of Energy). All rights reserved.

""""Distributed Optimal and Predictive Energy Resources
Weather forecast module.
"""

import io
import re
import os
import sys
import time
import json
import pygrib
import requests
import warnings
import traceback
import numpy as np
import pandas as pd
import urllib.request
import datetime as dtm

warnings.filterwarnings('ignore', message='The forecast module algorithms and features are highly experimental.')
warnings.filterwarnings('ignore', message="The HRRR class was deprecated in pvlib 0.9.1 and will be removed in a future release.")

try:
    root = os.path.dirname(os.path.abspath(__file__))
    from .resources.pvlib.forecast import HRRR
except:
    root = os.getcwd()
    sys.path.append(os.path.join(root, '..', 'doper'))
    from resources.pvlib.forecast import HRRR

from fmlc.baseclasses import eFMU

datetime_mask = "20[0-9][0-9]-[0-1][0-9]-[0-3][0-9] [0-2][0-9]:[0-5][0-9]:[0-5][0-9]"

FC_TO_PVLIV_MAP = {
    '9:Total Cloud Cover:% (instant):lambert:atmosphere:level 0 -': 'Total_cloud_cover_entire_atmosphere',
    '7:2 metre temperature:K (instant):lambert:heightAboveGround:level 2 m': 'Temperature_height_above_ground',
    'wind_speed_u': 0,
    'wind_speed_v': 0,
    'Low_cloud_cover_low_cloud': 0,
    'Medium_cloud_cover_middle_cloud': 0,
    'High_cloud_cover_high_cloud': 0,
    'Pressure_surface': 0,
    'Wind_speed_gust_surface': 0
}

def download_latest_hrrr(lat, lon, dt, hour, tmp_dir='',
                         debug=False, store_file=False):
    '''
    Documentation and API: https://nomads.ncep.noaa.gov/gribfilter.php?ds=hrrr_2d
    Full HRRR files: https://nomads.ncep.noaa.gov/pub/data/nccf/com/hrrr/prod/
    Historic HRRR files: https://www.ncei.noaa.gov/data/rapid-refresh/access/
    '''
    
    # make url for download (from API)
    url = f'https://nomads.ncep.noaa.gov/cgi-bin/filter_hrrr_2d.pl?dir=%2F'
    fname = f'hrrr.t{dt.strftime("%H")}z.wrfsfcf{hour:02}.grib2'
    url += f'hrrr.{dt.strftime("%Y%m%d")}%2Fconus&file={fname}'
    url += f'&var_TCDC=on&var_TMP=on&all_lev=on&subregion=&'
    # url += f'&var_TCDC=on&var_TMP=on&lev_2_m_above_ground=on&subregion=&'
    url += f'toplat={int(lat+1)}&leftlon={int(lon-1)}&rightlon={int(lon+1)}&bottomlat={int(lat-1)}'
    
    # download forecast
    fname = os.path.join(tmp_dir, fname)
    try:
        if store_file:
            urllib.request.urlretrieve(url, fname)
        else:
            fname = requests.get(url).content
        return fname
    except Exception as e:
        if debug:
            print(url)
            print(e)
        return None

def get_nearest_data(lat, lon, fname):
    
    # open file
    grib = pygrib.open(fname)
    
    # get grib locations
    lat_grib = grib[1].latlons()[0]
    lon_grib = grib[1].latlons()[1]

    # calculate distances
    abslat = np.abs(lat_grib - lat)
    abslon = np.abs(lon_grib - lon)
    c = np.maximum(abslon, abslat)

    # select nearest
    x, y = np.where(c == np.min(c))
    x, y = x[0], y[0]
    
    # get data
    res = {'lat': lat_grib[x, y],
           'lon': lon_grib[x, y],
           'x': x, 'y': y}
    for g in grib:
        name = str(g).split(':fcst time')[0]
        res[name] = g.values[x, y]

    return res

def get_hrrr_forecast(lat, lon, dt, tz='America/Los_Angeles', max_hour=16,
                      tmp_dir='', debug=False, store_file=False):

    # convert timestep to hourly
    dt = dt.replace(minute=0, second=0, microsecond=0, nanosecond=0).tz_localize(None)

    # bug in pygrib 2.1.5 does not allow object as input
    store_file = True
    
    res = {}
    for h in range(max_hour+1):
        st = time.time()

        # convert local time to utc
        dt_utc = dt.tz_localize(tz).tz_convert('UTC').tz_localize(None)

        # get latest hrrr file
        fcObj = download_latest_hrrr(lat, lon, dt_utc, h,
                                     tmp_dir=tmp_dir,
                                     debug=debug,
                                     store_file=store_file)
        
        if fcObj:
            # make readable (pygrib 2.1.5 should support but doesn't)
            if not store_file:
                binary_io = io.BytesIO(fcObj)
                buffer_io = io.BufferedReader(binary_io)
        
            # determine nearest gridpoint
            r = get_nearest_data(lat, lon, fcObj)
        else:
            # no forecast received
            r = {}

        r['duration'] = time.time()-st

        # add to output
        res[h] = r
        
    # make dataframe
    res = pd.DataFrame(res).transpose()
    res.index = [pd.to_datetime(dt)+pd.DateOffset(hours=ix) for ix in res.index]
    
    return res

class weather_forecaster(eFMU):
    '''
    This class gathers the weather forecasts at one station on a specified frequency. It uses pvlib to
    reference NOAA's HRRR forecast model, and returns the temperature and solar irradiation values. It
    requires a configuration file that specifies the station and sampling frequency.
    '''
    
    def __init__(self):
        '''
        Reads the config information and initializes the forecaster.
        
        Input
        -----
        config (dict): The configuration file. Example fiven in "get_default_config".
        '''
        self.input = {'input-data': None, 'config': None, 'timeout': None}
        self.output = {'output-data':None, 'duration':None}
        
        self.forecaster = None
        
    def check_data(self, data, ranges):
        for k, r in ranges.items():
            if k in data.columns:
                if not (data[k].min() >= r[0]):
                    self.msg += f'ERROR: Entry "{k}" is out of range {data[k].min()} >= {r[0]}.\n'
                if not (data[k].max() <= r[1]):
                    self.msg += f'ERROR: Entry "{k}" is out of range {data[k].max()} <= {r[1]}.\n'
            else:
                self.msg += f'ERROR: Entry "{k}" is missing.\n'

    def compute(self, now=None):
        '''
        Gathers forecasts for the specified station. Returns either the forecast and error messages.
        
        Input
        -----
        now (str): String representation of the local time the forecast is requested for. None (defualt)
            falls back to using the user's current clock time.
        
        Return
        ------
        data (pd.DataFrame): The forecast as data frame with date time as index. Empty data frame on error.
        msg (str): Error messages or empty string when no errors.
        '''
        
        self.msg = ''
        st = time.time()
        
        # initialize
        self.config = self.input['config']

        # prepare inputs
        tz = self.config['tz']
        if now == None:
            now = pd.to_datetime(time.time(), unit='s')
            now = now.replace(minute=0, second=0, microsecond=0, nanosecond=0)
            now = now.tz_localize('UTC').tz_convert(tz)
        start_time = pd.to_datetime(now)
        
        # FIXME
        start_time = start_time - dtm.timedelta(hours=1)
        # print('WARNING: Time in local time:', now, 'NOAA is 1h behind (DST?)', start_time)

        final_time = start_time + pd.Timedelta(hours=self.config['horizon'])
        
        # get forecast
        self.forecast = pd.DataFrame()
        try:
            if self.config['source'] == 'noaa_hrrr':
                if not self.forecaster:
                    
                    # setup forecaster
                    self.forecaster = get_hrrr_forecast

                    # setup pvlib processor
                    self.pvlib_processor = HRRR()
                    self.pvlib_processor.set_location(start_time.tz,
                                                      self.config['lat'],
                                                      self.config['lon'])

                # tmp dir
                if not os.path.exists(self.config['tmp_dir']):
                    os.mkdir(self.config['tmp_dir'])

                # get forecast
                self.forecast = self.forecaster(self.config['lat'],
                                                self.config['lon'],
                                                start_time,
                                                tz=tz,
                                                max_hour=self.config['horizon'],
                                                tmp_dir=self.config['tmp_dir'],
                                                debug=self.config['debug'])
                
            elif self.config['source'] == 'json':

                # read forecast form json
                self.forecast = pd.read_json(io.StringIO(self.input['input-data'])).sort_index()
                
            else:

                # method not implemented
                self.msg += f'ERROR: Source option "{self.config["source"]}" not valid.\n'
                
            # check index
            for i, ix in enumerate(self.forecast.index):
                if not bool(re.match(datetime_mask, str(ix))):
                    self.msg += f'ERROR: External forecast date format incorrect "{ix}" at position {i}.\n'
                    
            # check and convert to numeric
            for c in self.forecast.columns:
                self.forecast[c] = pd.to_numeric(self.forecast[c], errors='coerce')
            if self.forecast.isnull().values.any():
                self.msg += f'ERROR: NaNs in forecast at: {self.forecast.index[self.forecast.isnull().any(axis=1)]}.\n'

            # check index
            if self.msg == '':
                self.forecast.index = pd.to_datetime(self.forecast.index, format='%Y-%m-%d %H:%M:%S')
                if not len(self.forecast) == self.config['horizon']+1:
                    self.msg += f'ERROR: Forecast length {len(self.forecast)} is not horizon {self.config["horizon"]+1}.\n'
                if not self.forecast.index[0] == start_time.tz_localize(None):
                    self.msg += f'ERROR: Forecast start "{self.forecast.index[0]}" not ' \
                        + f'start_time "{start_time.tz_localize(None)}".\n'
                if not self.forecast.index[-1] == final_time.tz_localize(None):
                    self.msg += f'ERROR: Forecast final "{self.forecast.index[-1]}" not ' \
                        + f'final_time "{final_time.tz_localize(None)}".\n'
                if self.forecast.resample('1h').asfreq().isnull().values.any():
                    self.msg += f'ERROR: Missing timestamp in forecast.\n'
                    
        except Exception as e:
            self.msg += f'ERROR: {e}\n\n{traceback.format_exc()}\n'
            self.forecast = pd.DataFrame()
                        
        # process data
        self.data = pd.DataFrame()
        if self.msg == '':
            try:
                # check forecast
                self.check_data(self.forecast, self.config['forecast_cols'])

                # process
                if self.msg == '':
                    # direct pvlib form forecast
                    direct = {k: v for k, v in FC_TO_PVLIV_MAP.items() if isinstance(v, str)}
                    self.pvlib_fc = self.forecast[direct.keys()].copy(deep=True).rename(columns=direct)
                    # computed from forecast
                    computed = {k: v for k, v in FC_TO_PVLIV_MAP.items() if not isinstance(v, str)}
                    for k, v in computed.items():
                        self.pvlib_fc[k] = v
                    self.pvlib_fc.index = self.pvlib_fc.index.tz_localize(tz)
                    # duplicate last beacuse of bug in pvlib
                    self.pvlib_fc.loc[self.pvlib_fc.index[-1]+pd.DateOffset(hours=1), :] = self.pvlib_fc.iloc[-1]
                    self.data = self.pvlib_processor.process_data(self.pvlib_fc)
                    self.data = self.data.loc[self.pvlib_fc.index[:-1]]
                    self.data.index = self.data.index.tz_localize(None)
                    self.data = self.data[self.config['output_cols'].keys()]

                    # FIXME
                    self.data = self.data.iloc[1:]
                    # print('WARNING: Removing first timestep (last hour) due to NOAA 1h behind')
            except Exception as e:
                self.msg += f'ERROR: {e}.\n\n{traceback.format_exc()}\n'
                self.data = pd.DataFrame()

        # check data
        if self.msg == '' and self.config['output_cols']:
            self.check_data(self.data, self.config['output_cols'])

        # return
        self.init = False
        if self.config['json_return']:
            self.output['output-data'] = self.data.to_json()
        else:
            self.output['output-data'] = self.data
        self.output['duration'] = time.time() - st

        if self.msg == '':
            return 'Done.'
        return self.msg

def get_default_config():
    config = {}
    # config['name'] = 'Berkeley'
    config['lat'] = 37.8715
    config['lon'] = -122.2501
    config['tz'] = 'US/Pacific'
    config['horizon'] = 16
    config['tmp_dir'] = os.path.join(root, 'tmp')
    config['debug'] = False
    config['source'] = 'noaa_hrrr'
    config['json_return'] = True
    config['forecast_cols'] = {
        '9:Total Cloud Cover:% (instant):lambert:atmosphere:level 0 -': [0, 100],
        '7:2 metre temperature:K (instant):lambert:heightAboveGround:level 2 m': [200, 400]
    }
    config['output_cols'] = {'temp_air': [-50, 50],
                             'ghi': [0, 1000],
                             'dni': [0, 1500],
                             'dhi': [0, 1000]}
    return config

if __name__ == '__main__':
    
    # get config
    config = get_default_config()
    
    # initialize
    forecaster = weather_forecaster()
    forecaster.input['config'] = config

    # for defcon setup
    if len(sys.argv) == 2:
        forecaster.input['config']['source'] = 'json'
        forecaster.input['input-data'] = pd.read_csv(sys.argv[1], index_col=0).to_json()
    
    # get forecast
    msg = forecaster.compute(now=None)
    res = pd.read_json(io.StringIO(forecaster.output['output-data']))
    
    # check for errors
    if msg != 'Done.':
        print(msg)
    else:
        print(res.round(1))