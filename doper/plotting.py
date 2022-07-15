# -*- coding: utf-8 -*-
"""
Created on Wed Jan 26 09:12:35 2022

@author: nicholas
"""

import os
import sys
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import logging

def plot_dynamic_nodes(df, parameter, plotFile = None):
    '''
        A standard plotting template to present results.

        Input
        -----
            df (pandas.DataFrame): The resulting dataframe with the optimization result.
            plot (bool): Flag to plot or return the figure. (default=True)
            plot_times (bool): Flag if time separation should be plotted. (default=True)
            tight (bool): Flag to use tight_layout. (default=True)
            
        Returns
        -------
            None if plot == True.
            else:
                fig (matplotlib figure): Figure of the plot.
                axs (numpy.ndarray of matplotlib.axes._subplots.AxesSubplot): Axis of the plot.
    '''
    
    # number of plot rows is equal to the number of nodes
    n = len(parameter['network']['nodes'])

    
    fig, axs = plt.subplots(nrows=n,ncols=2, figsize=(24, 3*n), sharex=True, sharey=True)
    
    # loop through nodes
    for nn, node in enumerate(parameter['network']['nodes']):
        
        # get node name in order to extract data cols from df
        nodeName = node['node_id']
        
        # define node-specific col names
        importCol = f'Node grid import [kW] {nodeName}'
        exportCol = f'Node grid export [kW] {nodeName}'
        loadServedCol = f'Node load served [kW] {nodeName}'
        pvGenCol = f'Node pv gen [kW] {nodeName}'
        injPowerCol = f'Node power injected [kW] {nodeName}'
        absPowerCol = f'Node power absorbed [kW] {nodeName}'
        
        gensetCol = f'Node genset gen [kW] {nodeName}'
        # batChargeCol = f'Node grid import [kW] {nodeName}'
        # batDischargeCol = f'Node grid import [kW] {nodeName}'
        # loadShedCol = f'Node grid import [kW] {nodeName}'
   
    
        # create energy provision plot
        
        # list of provision columns in results df
        provision_cols = [importCol, absPowerCol]
        consumption_cols = [exportCol, loadServedCol, injPowerCol]
        if parameter['system']['pv']:
            provision_cols += [pvGenCol]
        if parameter['system']['genset']:
            provision_cols += [gensetCol]
        # if parameter['system']['battery']:
        #     provision_cols += ['Battery Discharging Power [kW]']
        #     consumption_cols += ['Battery Charging Power [kW]']
        # if parameter['system']['load_control']:
        #     provision_cols += ['Total Shed Load [kW]']
        



        df[provision_cols].plot.area(ax=axs[nn, 0], title='Energy Provision').legend(loc='upper right')

        df[consumption_cols].plot.area(ax=axs[nn, 1], title='Energy Consumption').legend(loc='upper right')


    
    if plotFile:
        plt.savefig(plotFile, dpi=300)
    else: 
        return fig, axs
    
    
def plot_pv_only(df, plot=True, plotFile = None, tight=True, plot_reg=None, times=[8,12,18,22]):
    '''
        A standard plotting template to present results.

        Input
        -----
            df (pandas.DataFrame): The resulting dataframe with the optimization result.
            plot (bool): Flag to plot or return the figure. (default=True)
            plot_times (bool): Flag if time separation should be plotted. (default=True)
            tight (bool): Flag to use tight_layout. (default=True)
            
        Returns
        -------
            None if plot == True.
            else:
                fig (matplotlib figure): Figure of the plot.
                axs (numpy.ndarray of matplotlib.axes._subplots.AxesSubplot): Axis of the plot.
    '''
    n = 3
    fig, axs = plt.subplots(n,1, figsize=(12, 3*n), sharex=True, sharey=False, gridspec_kw = {'width_ratios':[1]})
    axs = axs.ravel()
    plot_streams(axs[0], df[['Import Power [kW]','Export Power [kW]']], times=times)
    
    # create energy provision plot
        
    plot_streams(axs[2], df[['Tariff Energy [$/kWh]']], times=times)
    
    if plotFile:
        plt.savefig(plotFile)
    if plot:
        if tight:
            plt.tight_layout()
        plt.show()
    else: return fig, axs
    
    
def plot_standard1(df, plot=True, tight=True, plot_reg=None, times=[8,12,18,22]):
    '''
        A standard plotting template to present results.

        Input
        -----
            df (pandas.DataFrame): The resulting dataframe with the optimization result.
            plot (bool): Flag to plot or return the figure. (default=True)
            plot_times (bool): Flag if time separation should be plotted. (default=True)
            tight (bool): Flag to use tight_layout. (default=True)
            
        Returns
        -------
            None if plot == True.
            else:
                fig (matplotlib figure): Figure of the plot.
                axs (numpy.ndarray of matplotlib.axes._subplots.AxesSubplot): Axis of the plot.
    '''
    # Check if include regulation
    if plot_reg == None and df[['Reg Up [kW]','Reg Dn [kW]','Tariff Reg Up [$/kWh]','Tariff Reg Dn [$/kWh]']].abs().sum().sum() > 0:
        plot_reg = True
    n = 4 + (2 if plot_reg else 0)
    fig, axs = plt.subplots(n,1, figsize=(12, 3*n), sharex=True, sharey=False, gridspec_kw = {'width_ratios':[1]})
    axs = axs.ravel()
    plot_streams(axs[0], df[['Import Power [kW]','Export Power [kW]']], times=times)
    
    # create energy provision plot
    if 'Battery Power [kW]' in df.columns:
        plot_streams(axs[1], df[['Battery Power [kW]','Load Power [kW]','PV Power [kW]']],
                         times=times)
    else:
        plot_streams(axs[1], df[['Load Power [kW]','PV Power [kW]']],
                         times=times)
        
    plot_streams(axs[2], df[['Tariff Energy [$/kWh]']], times=times)
    plot_streams(axs[3], df[['Battery SOC [%]']], times=times)
    if plot_reg:
        plot_streams(axs[4], df[['Reg Up [kW]','Reg Dn [kW]']], times=times)
        plot_streams(axs[5], df[['Tariff Reg Up [$/kWh]','Tariff Reg Dn [$/kWh]']], times=times)
    if plot:
        if tight:
            plt.tight_layout()
        plt.show()
    else: return fig, axs
    
    
def plot_dynamic(df, parameter, plot=True,  plotFile = None, tight=True, plot_reg=None, times=[8,12,18,22]):
    '''
        A standard plotting template to present results.

        Input
        -----
            df (pandas.DataFrame): The resulting dataframe with the optimization result.
            plot (bool): Flag to plot or return the figure. (default=True)
            plot_times (bool): Flag if time separation should be plotted. (default=True)
            tight (bool): Flag to use tight_layout. (default=True)
            
        Returns
        -------
            None if plot == True.
            else:
                fig (matplotlib figure): Figure of the plot.
                axs (numpy.ndarray of matplotlib.axes._subplots.AxesSubplot): Axis of the plot.
    '''
    
    # number of subplots. eventually dynamically determined
    n = 4
    
    if parameter['system']['battery']:
        # if batteries are enabled, add plot for SOC
        n += 1
    
    fig, axs = plt.subplots(n,1, figsize=(12, 3*n), sharex=True, sharey=False, gridspec_kw = {'width_ratios':[1]})
    axs = axs.ravel()
    # plot_streams(axs[0], df[['Import Power [kW]','Export Power [kW]']], times=times)
    df[['Import Power [kW]','Export Power [kW]']].plot(ax=axs[0], title = 'Power Flow at PCC')
    
    # create energy provision plot
    
    # list of provision columns in results df
    provision_cols = ['Import Power [kW]']
    consumption_cols = ['Load Power [kW]', 'Export Power [kW]']
    if parameter['system']['pv']:
        provision_cols += ['PV Power [kW]']
    if parameter['system']['genset']:
        provision_cols += ['Genset Power [kW]']
    if parameter['system']['battery']:
        provision_cols += ['Battery Discharging Power [kW]']
        consumption_cols += ['Battery Charging Power [kW]']
    if parameter['system']['load_control']:
        provision_cols += ['Total Shed Load [kW]']

    df[provision_cols].plot.area(ax=axs[1], title='Energy Provision').legend(loc='upper right')
    # df[provision_cols].plot.area(ax=axs[1], title='Energy Provision').legend(bbox_to_anchor=(1.0, 1.0))
    df[consumption_cols].plot.area(ax=axs[2], title='Energy Consumption').legend(loc='upper right')
    if parameter['system']['battery']:
        df[['Battery Aggregate SOC [-]']].plot(ax=axs[3], title='Battery SOC')
    df[['Tariff Energy [$/kWh]']].plot(ax=axs[n-1], title='Tariff Energy Price')
    
    if plotFile:
        plt.savefig(plotFile, dpi=300)
    if plot:
        if tight:
            plt.tight_layout()
        plt.show()
    else: return fig, axs
    
    
def formatExternalData(df):
    '''
    

    Parameters
    ----------
    df : TYPE
        DESCRIPTION.

    Returns
    -------
    None.

    '''
    
    supplyList = ['pvGen', 'genset', 'gridImport', 'powerAbs', 'batDischarge']
    
    demandList = ['gridExport', 'load',  'powerInj', 'batCharge']
    
    # set index to col
    # df['ts'] = df.index
    df['ts'] = np.arange(len(df))
    
    # melt df
    df = df.melt(id_vars=['ts'])
    
    # create node col
    df[['src', 'node']] = df['variable'].str.split('_', 1, expand=True)
    
    # drop variable col
    df.drop(['variable'], axis=1, inplace=True)
    
    # add group based on source
    df['group'] = 'NA'
    df.group[df.src.isin(supplyList)] = 'supply'
    df.group[df.src.isin(demandList)] = 'demand'
    
    # return reformatted df
    return df