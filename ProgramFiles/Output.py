import sys
import os
import subprocess
from osgeo import gdal, ogr, osr
from osgeo.gdalconst import *
import numpy as np
from scipy.io import savemat, loadmat
from datetime import datetime, date, timedelta
import netCDF4 as nc4
import itertools
import multiprocessing
import time

gdal.UseExceptions()

nodataval = -9999
dtype = GDT_Float32


def daterange(start_date, end_date):
    for n in range(int((end_date - start_date).days)):
        yield start_date + timedelta(n)
        

def exec_cmd(cmd, Verbose):
    if Verbose:
        print('Executing command: ' + cmd)

        subprocess.call(cmd, shell=True)
    else:
        subprocess.call(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.STDOUT)
        
        
def WriteRaster_tif(Data, OFName, Subdomain, CreatePyramids, Verbose):
        
        if Verbose:
            print('Writing ' + OFName)

        cols = Subdomain['cols']
        rows = Subdomain['rows']
        if Subdomain['ModelTimestep'] == 1:
            bands = 1
        elif Subdomain['ModelTimestep'] == 0:
            bands = 24
            
        GeoTransform = Subdomain['transform']
        Projection = Subdomain['projection']
        
        driver = gdal.GetDriverByName("GTiff")
        co = ["COMPRESS=LZW", "BIGTIFF=IF_SAFER"]
        outdata = driver.Create(OFName, cols, rows, bands, dtype, options=co)
        outdata.SetGeoTransform(GeoTransform)
        outdata.SetProjection(Projection)
        
        if Subdomain['ModelTimestep'] == 1:
            outdata.GetRasterBand(1).WriteArray(Data)
            outdata.GetRasterBand(1).SetNoDataValue(nodataval)
        elif Subdomain['ModelTimestep'] == 0:
            for band in range(bands):
                outdata.GetRasterBand(band+1).WriteArray(Data[band,:,:])
                outdata.GetRasterBand(band+1).SetNoDataValue(nodataval)
                
        outdata.FlushCache()
        outdata = None
        
        if CreatePyramids:
            cmd = 'gdaladdo --config COMPRESS_OVERVIEW DEFLATE --config BIGTIFF_OVERVIEW IF_SAFER -r average -ro "' + OFName + '"'
            exec_cmd(cmd, Verbose)
            

def get_nc(c, tlocs, var, pars):
    
    if pars['Verbose']:
        print('Reading ' + var + ' for tile ' + str(c))

    ModelOutputFName = pars['ModelDir'] + '/Tile' + str(c) + '/ModelOutput.nc'
    if os.path.exists(ModelOutputFName):
        ds = nc4.Dataset(ModelOutputFName)
        ncdata = ds[var][tlocs,:]
        ds = None
    else:
        ncdata = []
       
    return ncdata
            

def getData(pars):

    ModelInfoFName = pars['ModelDir'] + '/' + 'ModelInfo.mat'
    a = loadmat(ModelInfoFName, simplify_cells=True)
    Tiles = a['Tiles']
    Subdomain = a['Subdomain']
    
    forcing_list = ['airt', 'wind', 'srad', 'lrad', 'vapp', 'rh', 'rainfall', 'snowfall', 'PET']

    vars = pars['VarList'].split(',')
    
    tlocs = []
    dates = daterange(pars['StartDate'], pars['EndDate']+timedelta(days=1))
    for date_ in dates:
        tloc = (date_ - datetime(Subdomain['StartYear'], Subdomain['StartMonth'], Subdomain['StartDay'])).days
        tlocs.append(tloc)
    
    if Subdomain['ModelTimestep'] == 0:
        tlocs = np.arange(tlocs[0]*24,tlocs[-1]*24+24)
       
    for var in vars:
        
        data = np.zeros([len(tlocs), Subdomain['rows'], Subdomain['cols']]) * np.nan
        
        print('Reading ' + var + ' in all tiles')
        pool = multiprocessing.Pool(processes=min(pars['NProcesses'], len(Tiles)))
        ncdata = pool.starmap(get_nc, zip(range(len(Tiles)), itertools.repeat(tlocs), itertools.repeat(var), itertools.repeat(pars)))
        pool.close() 
        pool.join()
        
        
        # c = 0
        # ncdata = []
        # for Tile in Tiles:
        
            # print('Getting ' + var + ' for tile ' + str(c))
            # ModelOutputFName = pars['ModelDir'] + '/Tile' + str(c) + '/ModelOutput.nc'
            # ds = nc4.Dataset(ModelOutputFName)
            # ncdata.append(ds[var][tlocs,:])
            # ds = None
            # c = c+1
            
        print('Processing ' + var)
        c = 0
        for Tile in Tiles:
            Locs = Tile['mask'].astype(bool)
            nd = np.sum(Locs)
            if nd > 0:
                for t in range(len(tlocs)):
                    ncdata_ = np.zeros([Tile['rows'],Tile['cols']]) * np.nan
                    ncdata_[Tile['mask']==1] = ncdata[c][t,:]
                    
                    xlocs, ylocs = np.meshgrid(Tile['xlocs'], Tile['ylocs'])
                    data[t,ylocs,xlocs] = ncdata_
                
            c = c+1
        # print('hi')

        # c = 0
        # ncdatas = []
        # for Tile in Tiles:
        
            # print('Getting ' + var + ' for tile ' + str(c))
            # ModelOutputFName = pars['ModelDir'] + '/Tile' + str(c) + '/ModelOutput.nc'
            # ds = nc4.Dataset(ModelOutputFName)
            # ncdata_0 = ds[var][tlocs,:]
            # ncdata = []
            # for t in range(len(tlocs)):
                # ncdata_ = np.zeros([Tile['rows'],Tile['cols']]) * np.nan
                # ncdata_[Tile['mask']==1] = ncdata_0[t,:]
                # ncdata.append(ncdata_)

            # ds = None
            # c = c+1
        
            # ncdatas.append(ncdata)
           
        # print('hi')
        # c = 0
        # for Tile in Tiles:

            # xlocs, ylocs = np.meshgrid(Tile['xlocs'], Tile['ylocs'])
            # data[:,ylocs,xlocs] = ncdatas[c]
                
            # c = c+1
        # print('hi')

        print('Writing ' + var)
        dates = daterange(pars['StartDate'], pars['EndDate']+timedelta(days=1))
        data[np.isnan(data)] = nodataval
        t = 0
        for date_ in dates:
            yyyy = str(date_.year)
            mm = str(date_.month)
            if len(mm) < 2:
                mm = '0' + mm
            dd = str(date_.day)
            if len(dd) < 2:
                dd = '0' + dd    
            ofname = pars['OutputDir'] + '/' + yyyy + '/' + mm + '/' + dd + '/' + var + '.tif'
            if not os.path.exists(os.path.dirname(ofname)):
                os.makedirs(os.path.dirname(ofname))
                
            if Subdomain['ModelTimestep'] == 1:
                WriteRaster_tif(data[t,:,:], ofname, Subdomain, pars['CreatePyramids'], pars['Verbose'])
            elif Subdomain['ModelTimestep'] == 0:
                WriteRaster_tif(data[t*24:t*24+24,:,:], ofname, Subdomain, pars['CreatePyramids'], pars['Verbose'])

            t = t+1
        
        
    
    # dates = daterange(pars['StartDate'], pars['EndDate']+timedelta(days=1))
    # for date_ in dates:
        # tloc = (date_ - date(Subdomain['StartYear'], Subdomain['StartMonth'], Subdomain['StartDay'])).days
        
        # for var in vars:
            # data = np.zeros([Subdomain['rows'],Subdomain['cols']]) * np.nan
            
            # print('Getting ' + var + ' map on ' + str(date_.year) + '-' + str(date_.month) + '-' + str(date_.day))
            # c = 0
            # for Tile in Tiles:
                
                # ModelOutputFName = pars['ModelDir'] + '/Tile' + str(c) + '/ModelOutput.nc'
                # ds = nc4.Dataset(ModelOutputFName)
                
                # ncdata = ds[var][tloc,:]
                # ds = None
                # ncdata_ = np.zeros([Tile['rows'],Tile['cols']]) * np.nan
                # ncdata_[Tile['mask']==1] = ncdata
                
                # xlocs, ylocs = np.meshgrid(Tile['xlocs'], Tile['ylocs'])
                # data[ylocs,xlocs] = ncdata_
                # c = c+1
           
            # ofname = pars['OutputDir'] + '/' + str(date_.year) + '/' + str(date_.month) + '/' + str(date_.day) + '/' + var + '.tif'
            # if not os.path.exists(os.path.dirname(ofname)):
                # os.makedirs(os.path.dirname(ofname))
        
            # data[np.isnan(data)] = nodataval
            
            # WriteRaster(data, ofname, Subdomain, pars['CreatePyramids'], pars['Verbose'])



