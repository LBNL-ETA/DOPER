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
    from ..resources.pvlib.forecast import HRRR
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
                      tmp_dir='', debug=False, store_file=False, forecast_age=2):
    """
    Utility function to dowlnoad NOAA's HRRR forecast data.

    Inputs
    ------
    lat (float): latitude of location.
    lon (float): longitude of location.
    dt (pd.Timestamp): current date time.
    tz (str): time zone of location.
    max_hour (int): forecast horizon.
    tmp_dir (str): temporary directory for HRRR downloads.
    debug (bool): debug flag.
    store_file (bool): store HRRR downloads.
    forecast_age (int): age of HRRR forecast, in hours. 
    """

    # convert timestep to hourly
    dt = dt.replace(minute=0, second=0, microsecond=0, nanosecond=0).tz_localize(None)

    # convert local time to utc
    dt_utc = dt.tz_localize(tz).tz_convert('UTC').tz_localize(None)
    # NOTE: use forecast from X hours ago since NOAA is usually behind
    dt_utc = dt_utc - pd.DateOffset(hours=forecast_age)

    # bug in pygrib 2.1.5 does not allow object as input
    store_file = True

    res = {}
    for h in range(forecast_age, max_hour+forecast_age+1):
        st = time.time()

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

            # FIXME: deleting file manually due to pygrib 2.1.5 bug
            try:
                if not debug:
                    os.remove(fcObj)
            except:
                pass
        else:
            # no forecast received
            r = {}

        r['duration'] = time.time()-st

        # add to output
        res[dt_utc+pd.DateOffset(hours=h)] = r
        
    # make dataframe
    res = pd.DataFrame(res).transpose()
    res.index = pd.to_datetime(res.index).tz_localize('UTC').tz_convert(tz).tz_localize(None)
    
    return res

def get_noaa_hrrr_forecast(config, start_time, tz, forecaster=None, pvlib_processor=None):
    """Download NOAA HRRR forecast, initialize forecaster and processor if needed."""

    # initialize on first call
    if not forecaster:
        forecaster = get_hrrr_forecast
        pvlib_processor = HRRR()
        pvlib_processor.set_location(start_time.tz, config['lat'], config['lon'])

    # ensure tmp dir exists
    if not os.path.exists(config['tmp_dir']):
        os.mkdir(config['tmp_dir'])

    # download forecast
    forecast = forecaster(config['lat'], config['lon'], start_time,
                          tz=tz, max_hour=config['horizon'],
                          tmp_dir=config['tmp_dir'], debug=config['debug'])

    return forecast, forecaster, pvlib_processor

def check_forecast(forecast, config, start_time, final_time):
    """Validate forecast index format, numeric values, and time alignment."""
    msg = ''

    # check index format
    for i, ix in enumerate(forecast.index):
        if not bool(re.match(datetime_mask, str(ix))):
            msg += f'ERROR: External forecast date format incorrect "{ix}" at position {i}.\n'

    # check and convert to numeric
    for c in forecast.columns:
        forecast[c] = pd.to_numeric(forecast[c], errors='coerce')
    if forecast.isnull().values.any():
        msg += f'ERROR: NaNs in forecast at: {forecast.index[forecast.isnull().any(axis=1)]}.\n'

    # check index alignment
    if msg == '':
        forecast.index = pd.to_datetime(forecast.index, format='%Y-%m-%d %H:%M:%S')
        if not (len(forecast)-1) == config['horizon']:
            msg += f'ERROR: Forecast length {len(forecast)-1} is not horizon {config["horizon"]}.\n'
        if not forecast.index[0] == start_time.tz_localize(None):
            msg += f'ERROR: Forecast start "{forecast.index[0]}" not ' \
                + f'start_time "{start_time.tz_localize(None)}".\n'
        if not forecast.index[-1] == final_time.tz_localize(None):
            msg += f'ERROR: Forecast final "{forecast.index[-1]}" not ' \
                + f'final_time "{final_time.tz_localize(None)}".\n'
        if forecast.resample('1h').asfreq().isnull().values.any():
            msg += f'ERROR: Missing timestamp in forecast.\n'

    return forecast, msg

def process_forecast(forecast, config, tz, pvlib_processor):
    """Process HRRR forecast through pvlib to compute irradiance and temperature."""

    # map to pvlib column names
    direct = {k: v for k, v in FC_TO_PVLIV_MAP.items() if isinstance(v, str)}
    pvlib_fc = forecast[direct.keys()].copy(deep=True).rename(columns=direct)
    # fill computed fields with defaults
    computed = {k: v for k, v in FC_TO_PVLIV_MAP.items() if not isinstance(v, str)}
    for k, v in computed.items():
        pvlib_fc[k] = v
    pvlib_fc.index = pvlib_fc.index.tz_localize(tz)
    # duplicate last row (pvlib bug workaround)
    pvlib_fc.loc[pvlib_fc.index[-1]+pd.DateOffset(hours=1), :] = pvlib_fc.iloc[-1]
    data = pvlib_processor.process_data(pvlib_fc)
    data = data.loc[pvlib_fc.index[:-1]]
    data.index = data.index.tz_localize(None)
    data = data[config['output_cols'].keys()]

    return data

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
        self.pvlib_processor = None
        self.last_valid_forecast = None
        self.last_valid_forecast_time = None

    def check_data(self, data, ranges):
        for k, r in ranges.items():
            if k in data.columns:
                if not (data[k].min() >= r[0]):
                    self.msg += f'ERROR: Entry "{k}" is out of range {data[k].min()} >= {r[0]}.\n'
                if not (data[k].max() <= r[1]):
                    self.msg += f'ERROR: Entry "{k}" is out of range {data[k].max()} <= {r[1]}.\n'
            else:
                self.msg += f'ERROR: Entry "{k}" is missing.\n'

    def compute(self):
        '''
        Gathers forecasts for the specified station. Returns either the forecast and error messages.
        
        Input
        -----
        
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
        now = self.input.get('time', None) # from FMLC
        if now is None:
            now = time.time()
        now_ts = pd.to_datetime(now, unit='s')
        now_ts = now_ts.replace(minute=0, second=0, microsecond=0, nanosecond=0)
        now_ts = now_ts.tz_localize('UTC').tz_convert(tz)
        start_time = pd.to_datetime(now_ts)
        final_time = start_time + pd.Timedelta(hours=self.config['horizon'])
        
        # check if stored forecast can be reused
        refresh_time = self.config.get('refresh_time', None)
        use_stored = (
            refresh_time is not None and
            self.last_valid_forecast is not None and
            (now - self.last_valid_forecast_time) < refresh_time and
            now_ts.hour == self.last_valid_forecast.index[0].hour
        )

        # get forecast
        self.forecast = pd.DataFrame()
        try:
            if use_stored:
                # reuse last valid forecast within refresh window
                self.forecast = self.last_valid_forecast.copy()

            elif self.config['source'] == 'noaa_hrrr':
                # download hrrr forecast
                self.forecast, self.forecaster, self.pvlib_processor = get_noaa_hrrr_forecast(
                    self.config, start_time, tz, self.forecaster, self.pvlib_processor)

            elif self.config['source'] == 'json':
                # read forecast from json
                self.forecast = pd.read_json(io.StringIO(self.input['input-data'])).sort_index()

            else:
                # method not implemented
                self.msg += f'ERROR: Source option "{self.config["source"]}" not valid.\n'

            # check forecast
            self.forecast, fc_msg = check_forecast(self.forecast, self.config, start_time, final_time)
            self.msg += fc_msg

        except Exception as e:
            self.msg += f'ERROR: {e}\n\n{traceback.format_exc()}\n'
            self.forecast = pd.DataFrame()

        # process data (noaa_hrrr only)
        self.data = pd.DataFrame()
        if self.msg == '' and self.config['source'] == 'noaa_hrrr':
            try:
                # check forecast columns
                self.check_data(self.forecast, self.config['forecast_cols'])

                # process through pvlib
                if self.msg == '':
                    self.data = process_forecast(self.forecast, self.config, tz, self.pvlib_processor)
            except Exception as e:
                self.msg += f'ERROR: {e}.\n\n{traceback.format_exc()}\n'
                self.data = pd.DataFrame()

        # check data
        if self.msg == '' and self.config['output_cols']:
            self.check_data(self.data, self.config['output_cols'])

        # use last valid forecast as fallback
        if self.msg == '':
            # store last valid forecast
            self.last_valid_forecast = self.forecast.copy()
            self.last_valid_forecast_time = now
        elif self.last_valid_forecast is not None:
            self.forecast = self.last_valid_forecast.copy()
            if self.config['source'] == 'noaa_hrrr' and self.pvlib_processor is not None:
                self.data = process_forecast(self.forecast, self.config, tz, self.pvlib_processor)

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
    config['tmp_dir'] = 'tmp'
    config['debug'] = False
    config['source'] = 'noaa_hrrr'
    config['refresh_time'] = 15*60 # 15 minutes
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
    # FMLC hidden input
    forecaster.input['time'] = time.time()

    # for defcon setup
    if len(sys.argv) == 2:
        forecaster.input['config']['source'] = 'json'
        forecaster.input['input-data'] = pd.read_csv(sys.argv[1], index_col=0).to_json()
    
    # get forecast
    msg = forecaster.compute()
    res = pd.read_json(io.StringIO(forecaster.output['output-data']))
    
    # check for errors
    if msg != 'Done.':
        print(msg)
    else:
        print(res.round(1))
