import sys, os
import subprocess
from osgeo import gdal, osr
from osgeo.gdalconst import *
from pyproj import Transformer
import numpy as np
from PIL import Image
from scipy.ndimage.filters import maximum_filter
from scipy.ndimage.morphology import generate_binary_structure, binary_erosion
from scipy import interpolate
from datetime import datetime, timedelta
import netCDF4 as nc4
import shutil
from scipy import ndimage
import copy

gdal.UseExceptions()

nodataval = -9999
DIM_i = [31, 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31]
dtype = GDT_Float32

def ReadRaster(fname, Verbose):
    
    if Verbose:
        print('Reading ' + fname)
        
    ds = gdal.Open(fname, GA_ReadOnly)
    if ds is None:
        print('Could not open ' + fname)
        sys.exit(1)
    geotransform = ds.GetGeoTransform()
    band = ds.GetRasterBand(1)
    Data = band.ReadAsArray().astype(float)
    nodata_value = band.GetNoDataValue()
    band = None
    ds = None
    # Data[Data == nodataval] = np.nan
    Data[Data == nodata_value] = np.nan
    
    return Data


def WriteRasterMatch(Data, OFName, match_file, nodataval, CreatePyramids, Verbose):
        
        if Verbose:
            print('Writing ' + OFName)
            
        if not os.path.exists(os.path.dirname(OFName)):
            os.makedirs(os.path.dirname(OFName))
            
        ds = gdal.Open(match_file, GA_ReadOnly)
        if ds is None:
            print('Could not open ' + OFName)
            sys.exit(1)
        geotransform = ds.GetGeoTransform()
        band = ds.GetRasterBand(1)
        cols = ds.RasterXSize
        rows = ds.RasterYSize
        Datatype = dtype
        GeoTransform = ds.GetGeoTransform()
        Projection = ds.GetProjection()
        band=None
        ds=None
        
        driver = gdal.GetDriverByName("GTiff")
        co = ["COMPRESS=DEFLATE", "BIGTIFF=IF_SAFER"]
        outdata = driver.Create(OFName, cols, rows, 1, Datatype, options=co)
        outdata.SetGeoTransform(GeoTransform)
        outdata.SetProjection(Projection)
        outdata.GetRasterBand(1).WriteArray(Data)
        outdata.GetRasterBand(1).SetNoDataValue(nodataval)
        outdata.FlushCache()
        outdata = None
        
        if CreatePyramids:
            cmd = 'gdaladdo --config COMPRESS_OVERVIEW DEFLATE --config BIGTIFF_OVERVIEW IF_SAFER -r average -ro "' + OFName + '"'
            exec_cmd(cmd, Verbose)
        

def daterange(start_date, end_date):
    for n in range(int((end_date - start_date).days)):
        yield start_date + timedelta(n)
        
        
def last_day_of_month(any_day):
    # get close to the end of the month for any day, and add 4 days 'over'
    next_month = any_day.replace(day=28) + timedelta(days=4)
    # subtract the number of remaining 'overage' days to get last day of current month, or said programattically said, the previous day of the first of next month
    return next_month - timedelta(days=next_month.day)
    
    
def exec_cmd(cmd, Verbose):
    if Verbose:
        print('Executing command: ' + cmd)

        subprocess.call(cmd, shell=True)
    else:
        subprocess.call(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.STDOUT)
        
    
def GetBelowCanopySkyviewFactor(pars):
    
    if 'CanopyTransFactor' not in pars:
        pars['CanopyTransFactor'] = 1
    if 'SVFInterpUnderTreesFactor' not in pars:
        pars['SVFInterpUnderTreesFactor'] = 0

    SagaGISLoc = pars['SagaGISLoc']
    
    OFName = pars['IndexDir'] + '/SkyView.tif'
    
    DTM = ReadRaster(pars['GISDir'] + '/DTM.tif', pars['Verbose'])
    Cover = ReadRaster(pars['GISDir'] + '/Cover.tif', pars['Verbose'])
    Cover[Cover < 0] = 0
    Cover[Cover > 100] = 0
    Cover[np.isnan(Cover)] = 0
    
    x = []
    for VegCoverCategory in pars['VegCoverCategories']:
        x.append((VegCoverCategory[1]+VegCoverCategory[0])/2)
    y = pars['Transmittances']
    f = interpolate.interp1d(x, y, fill_value="extrapolate")
    Canopy_Trans = f(Cover) 
    Canopy_Trans[Canopy_Trans < 0] = 0
    Canopy_Trans[Canopy_Trans > 1] = 1
    Canopy_Trans = Canopy_Trans ** pars['CanopyTransFactor']
        
    if not os.path.exists(OFName) or pars['Overwrite']:
        print('Creating ' + OFName)
        
        svf = pars['GISDir'] + '/SkyView_noVeg.tif'
        SVF_NoVeg = ReadRaster(svf, pars['Verbose'])
        SVF_BelowCanopy = SVF_NoVeg * 1
            
        c = 0
        for VegRange in pars['VegCoverCategories']:
            Transmittance = pars['Transmittances'][c]
            svf = pars['GISDir'] + '/SkyView_withVeg_vcat_' + str(c) + '.tif'
            SVF_BelowCanopy_ = ReadRaster(svf, pars['Verbose'])
            SVF_BelowCanopy_ = SVF_BelowCanopy_ * (1-Transmittance) + SVF_NoVeg * (Transmittance)
            SVF_BelowCanopy = np.minimum(SVF_BelowCanopy, SVF_BelowCanopy_)
            c = c+1
       
        SVF_BelowCanopy = SVF_BelowCanopy * Canopy_Trans
        SVF_BelowCanopy[SVF_BelowCanopy < 0] = 0
        SVF_BelowCanopy[SVF_BelowCanopy > 1] = 1
        
        rows,cols = SVF_BelowCanopy.shape
        nanlocs = np.isnan(DTM)
        SVF_BelowCanopy[nanlocs] = np.nanmean(SVF_BelowCanopy)
        
        if pars['SVFInterpUnderTreesFactor'] > 0:
            SVF_BelowCanopy_0 = copy.deepcopy(SVF_BelowCanopy)
            locs = Cover > 10
            SVF_BelowCanopy[locs] = nodataval
            WriteRasterMatch(SVF_BelowCanopy, OFName, pars['GISDir'] + '/DTM.tif', nodataval, pars['CreatePyramids'], pars['Verbose'])
            cmd = '"' + SagaGISLoc.replace('\\','/') + '/saga_cmd" grid_tools 29 -GROW 1.2 -INPUT "' + OFName + '" -RESULT "' + OFName + '"'
            exec_cmd(cmd, pars['Verbose'])
            SVF_BelowCanopy_interp = ReadRaster(OFName, pars['Verbose'])
            SVF_BelowCanopy = ((1-pars['SVFInterpUnderTreesFactor']) * SVF_BelowCanopy_0) + (pars['SVFInterpUnderTreesFactor'] * SVF_BelowCanopy_interp)
                        
        SVF_BelowCanopy = np.array(Image.fromarray(SVF_BelowCanopy).resize(size=(round(rows/pars['SVFResizeFactor']), round(cols/pars['SVFResizeFactor']))).resize(size=(cols, rows)))
        SVF_BelowCanopy = np.maximum(SVF_BelowCanopy,0)
        SVF_BelowCanopy[nanlocs] = nodataval
        
        WriteRasterMatch(SVF_BelowCanopy, OFName, pars['GISDir'] + '/DTM.tif', nodataval, pars['CreatePyramids'], pars['Verbose'])


def GetVerticalLAI(pars):
    
    if 'CanopyTransFactor' not in pars:
        pars['CanopyTransFactor'] = 1

    OFName = pars['IndexDir'] + '/LAI.tif'
    
    DTM = ReadRaster(pars['GISDir'] + '/DTM.tif', pars['Verbose'])
    Cover = ReadRaster(pars['GISDir'] + '/Cover.tif', pars['Verbose'])
    Cover[Cover < 0] = 0
    Cover[Cover > 100] = 0
    Cover[np.isnan(Cover)] = 0
    VegHT = ReadRaster(pars['GISDir'] + '/VegHT.tif', pars['Verbose'])
    VegHT[VegHT < 0] = 0
    VegHT[np.isnan(VegHT)] = 0
    
    x = []
    for VegCoverCategory in pars['VegCoverCategories']:
        x.append((VegCoverCategory[1]+VegCoverCategory[0])/2)
    y = pars['Transmittances']
    f = interpolate.interp1d(x, y, fill_value="extrapolate")
    Canopy_Trans = f(Cover) 
    Canopy_Trans[Canopy_Trans < 0] = 0
    Canopy_Trans[Canopy_Trans > 1] = 1
    Canopy_Trans = Canopy_Trans ** pars['CanopyTransFactor']
    
    if not os.path.exists(OFName) or pars['Overwrite']:
        print('Creating ' + OFName)
        
        if 'LAI_exp' not in pars:
            pars['LAI_exp'] = 1

        LAI = (1-Canopy_Trans) * pars['LAI_ref'] * (VegHT / pars['H_ref']) ** pars['LAI_exp']
        # LAI = (1-Canopy_Trans) * pars['LAI_ref']
        
        rows,cols = LAI.shape
        nanlocs = np.isnan(DTM)
        LAI[nanlocs] = np.nanmean(LAI)
        LAI = np.array(Image.fromarray(LAI).resize(size=(round(rows/pars['LAIResizeFactor']), round(cols/pars['LAIResizeFactor']))).resize(size=(cols, rows)))
        LAI = np.maximum(LAI,0)
        LAI[nanlocs] = nodataval
        
        WriteRasterMatch(LAI, OFName, pars['GISDir'] + '/DTM.tif', nodataval, pars['CreatePyramids'], pars['Verbose'])
        

def GetBelowCanopySFIMaps(pars):

    SagaGISLoc = pars['SagaGISLoc']
    
    if 'CanopyTransFactor' not in pars:
        pars['CanopyTransFactor'] = 1
    if 'SVFInterpUnderTreesFactor' not in pars:
        pars['SVFInterpUnderTreesFactor'] = 0

    DTM = ReadRaster(pars['GISDir'] + '/DTM.tif', pars['Verbose'])
    Cover = ReadRaster(pars['GISDir'] + '/Cover.tif', pars['Verbose'])
    Cover[Cover < 0] = 0
    Cover[Cover > 100] = 0
    Cover[np.isnan(Cover)] = 0
    # Canopy_Trans = (np.exp(-(Cover/100*pars['CanopyTrans'])))
    
    x = []
    for VegCoverCategory in pars['VegCoverCategories']:
        x.append((VegCoverCategory[1]+VegCoverCategory[0])/2)
    y = pars['Transmittances']
    f = interpolate.interp1d(x, y, fill_value="extrapolate")
    Canopy_Trans = f(Cover) 
    Canopy_Trans[Canopy_Trans < 0] = 0
    Canopy_Trans[Canopy_Trans > 1] = 1
    Canopy_Trans = Canopy_Trans ** pars['CanopyTransFactor']
    
    if pars['Solar_output_step'] == 1:
        prefix = 'Daily'
    if pars['Solar_output_step'] == 0:
        prefix = 'Hourly'
        
    for root, subFolder, files in os.walk(pars['GISDir'] + '/PotentialSolar'):
        for file in files:
            if file[-17:] == '_direct_noVeg.tif' and prefix in root:
            
                psolar_base = root + '/' + file.replace('_direct_noVeg.tif','')
                OFName_Direct_UnderCanopy = root.replace(pars['GISDir'],pars['IndexDir']).replace('PotentialSolar','SFI') + '/' + file.replace('_direct_noVeg.tif','_direct_underCanopy.tif')
                OFName_Diffuse_UnderCanopy = root.replace(pars['GISDir'],pars['IndexDir']).replace('PotentialSolar','SFI') + '/' + file.replace('_direct_noVeg.tif','_diffuse_underCanopy.tif')
                OFName_Direct_NoVeg = root.replace(pars['GISDir'],pars['IndexDir']).replace('PotentialSolar','SFI') + '/' + file
                OFName_Diffuse_NoVeg = root.replace(pars['GISDir'],pars['IndexDir']).replace('PotentialSolar','SFI') + '/' + file.replace('_direct_noVeg.tif','_diffuse_noVeg.tif')
                IndexDir = os.path.dirname(OFName_Direct_UnderCanopy)
        
                if not os.path.exists(IndexDir):
                    os.makedirs(IndexDir)
                    
                if not os.path.exists(OFName_Direct_UnderCanopy) or not os.path.exists(OFName_Direct_NoVeg) or pars['Overwrite']:
                    print('Creating ' + OFName_Direct_UnderCanopy)
                    print('Creating ' + OFName_Direct_NoVeg)
                    
                    psolar = psolar_base + '_direct_noVeg.tif'
                    PSolar_NoVeg = ReadRaster(psolar, pars['Verbose'])
                    PSolar_BelowCanopy = PSolar_NoVeg * 1
                        
                    c = 0
                    for VegRange in pars['VegCoverCategories']:
                        Transmittance = pars['Transmittances'][c]
                        # Transmittance = 1 - (pars['VegCoverCategories'][c][0] + pars['VegCoverCategories'][c][1]) / 200
                        psolar = psolar_base + '_direct_withVeg_vcat_' + str(c) + '.tif'
                        PSolar_BelowCanopy_ = ReadRaster(psolar, pars['Verbose'])
                        PSolar_BelowCanopy_ = PSolar_BelowCanopy_ * (1-Transmittance) + PSolar_NoVeg * (Transmittance)
                        PSolar_BelowCanopy = np.minimum(PSolar_BelowCanopy, PSolar_BelowCanopy_)
                        c = c+1
                     
                    PSolar_BelowCanopy = PSolar_BelowCanopy * Canopy_Trans
                    PSolar_BelowCanopy[PSolar_BelowCanopy < 0] = 0
                    
                    rows,cols = PSolar_BelowCanopy.shape
                    psolar = psolar_base + '_direct_flat.tif'
                    PSolar_Flat = ReadRaster(psolar, pars['Verbose'])
                    PSolar_Flat = np.array(Image.fromarray(PSolar_Flat).resize(size=(cols, rows)))
                    SFI_BelowCanopy = PSolar_BelowCanopy / PSolar_Flat
                    SFI_NoVeg = PSolar_NoVeg / PSolar_Flat

                    nanlocs = np.isnan(DTM)
                    SFI_BelowCanopy[nanlocs] = np.nanmean(SFI_BelowCanopy)

                    if pars['SFIInterpUnderTreesFactor'] > 0:
                        SFI_BelowCanopy_0 = copy.deepcopy(SFI_BelowCanopy)
                        locs = Cover > 10
                        SFI_BelowCanopy[locs] = nodataval
                        WriteRasterMatch(SFI_BelowCanopy, OFName_Direct_UnderCanopy, pars['GISDir'] + '/DTM.tif', nodataval, pars['CreatePyramids'], pars['Verbose'])
                        cmd = '"' + SagaGISLoc.replace('\\','/') + '/saga_cmd" grid_tools 29 -GROW 1.2 -INPUT "' + OFName_Direct_UnderCanopy + '" -RESULT "' + OFName_Direct_UnderCanopy + '"'
                        exec_cmd(cmd, pars['Verbose'])
                        SFI_BelowCanopy_interp = ReadRaster(OFName_Direct_UnderCanopy, pars['Verbose'])
                        SFI_BelowCanopy = ((1-pars['SVFInterpUnderTreesFactor']) * SFI_BelowCanopy_0) + (pars['SVFInterpUnderTreesFactor'] * SFI_BelowCanopy_interp)
 
                    SFI_BelowCanopy = np.array(Image.fromarray(SFI_BelowCanopy).resize(size=(round(rows/pars['SFIResizeFactor']), round(cols/pars['SFIResizeFactor']))).resize(size=(cols, rows)))
                    SFI_BelowCanopy = np.maximum(SFI_BelowCanopy,0)
                    SFI_BelowCanopy[nanlocs] = nodataval

                    SFI_NoVeg[nanlocs] = np.nanmean(SFI_NoVeg)
                    SFI_NoVeg = np.array(Image.fromarray(SFI_NoVeg).resize(size=(round(rows/pars['SFIResizeFactor']), round(cols/pars['SFIResizeFactor']))).resize(size=(cols, rows)))
                    SFI_NoVeg = np.maximum(SFI_NoVeg,0)
                    SFI_NoVeg[nanlocs] = nodataval

                    WriteRasterMatch(SFI_BelowCanopy, OFName_Direct_UnderCanopy, pars['GISDir'] + '/DTM.tif', nodataval, pars['CreatePyramids'], pars['Verbose'])
                    WriteRasterMatch(SFI_NoVeg, OFName_Direct_NoVeg, pars['GISDir'] + '/DTM.tif', nodataval, pars['CreatePyramids'], pars['Verbose'])
                
                if not os.path.exists(OFName_Diffuse_UnderCanopy) or not os.path.exists(OFName_Diffuse_NoVeg) or pars['Overwrite']:
                    print('Creating ' + OFName_Diffuse_UnderCanopy)
                    print('Creating ' + OFName_Diffuse_NoVeg)
                    
                    psolar = psolar_base + '_diffuse_noVeg.tif'
                    PSolar_NoVeg = ReadRaster(psolar, pars['Verbose'])
                    PSolar_BelowCanopy = PSolar_NoVeg * 1
                        
                    c = 0
                    for VegRange in pars['VegCoverCategories']:
                        Transmittance = pars['Transmittances'][c]
                        # Transmittance = 1 - (pars['VegCoverCategories'][c][0] + pars['VegCoverCategories'][c][1]) / 200
                        psolar = psolar_base + '_diffuse_withVeg_vcat_' + str(c) + '.tif'
                        PSolar_BelowCanopy_ = ReadRaster(psolar, pars['Verbose'])
                        PSolar_BelowCanopy_ = PSolar_BelowCanopy_ * (1-Transmittance) + PSolar_NoVeg * (Transmittance)
                        PSolar_BelowCanopy = np.minimum(PSolar_BelowCanopy, PSolar_BelowCanopy_)
                        c = c+1
                    
                    PSolar_BelowCanopy = PSolar_BelowCanopy * Canopy_Trans
                    PSolar_BelowCanopy[PSolar_BelowCanopy < 0] = 0
                    
                    rows,cols = PSolar_BelowCanopy.shape
                    psolar = psolar_base + '_diffuse_flat.tif'
                    PSolar_Flat = ReadRaster(psolar, pars['Verbose'])
                    PSolar_Flat = np.array(Image.fromarray(PSolar_Flat).resize(size=(cols, rows)))
                    SFI_BelowCanopy = PSolar_BelowCanopy / PSolar_Flat
                    SFI_NoVeg = PSolar_NoVeg / PSolar_Flat

                    nanlocs = np.isnan(DTM)
                    SFI_BelowCanopy[nanlocs] = np.nanmean(SFI_BelowCanopy)

                    if pars['SFIInterpUnderTreesFactor'] > 0:
                        SFI_BelowCanopy_0 = copy.deepcopy(SFI_BelowCanopy)
                        locs = Cover > 0
                        SFI_BelowCanopy[locs] = nodataval
                        WriteRasterMatch(SFI_BelowCanopy, OFName_Diffuse_UnderCanopy, pars['GISDir'] + '/DTM.tif', nodataval, pars['CreatePyramids'], pars['Verbose'])
                        cmd = '"' + SagaGISLoc.replace('\\','/') + '/saga_cmd" grid_tools 29 -GROW 1.2 -INPUT "' + OFName_Diffuse_UnderCanopy + '" -RESULT "' + OFName_Diffuse_UnderCanopy + '"'
                        exec_cmd(cmd, pars['Verbose'])
                        SFI_BelowCanopy_interp = ReadRaster(OFName_Diffuse_UnderCanopy, pars['Verbose'])
                        SFI_BelowCanopy = ((1-pars['SVFInterpUnderTreesFactor']) * SFI_BelowCanopy_0) + (pars['SVFInterpUnderTreesFactor'] * SFI_BelowCanopy_interp)
                    
                    SFI_BelowCanopy = np.array(Image.fromarray(SFI_BelowCanopy).resize(size=(round(rows/pars['SFIResizeFactor']), round(cols/pars['SFIResizeFactor']))).resize(size=(cols, rows)))
                    SFI_BelowCanopy = np.maximum(SFI_BelowCanopy,0)
                    SFI_BelowCanopy[nanlocs] = nodataval

                    SFI_NoVeg[nanlocs] = np.nanmean(SFI_NoVeg)
                    SFI_NoVeg = np.array(Image.fromarray(SFI_NoVeg).resize(size=(round(rows/pars['SFIResizeFactor']), round(cols/pars['SFIResizeFactor']))).resize(size=(cols, rows)))
                    SFI_NoVeg = np.maximum(SFI_NoVeg,0)
                    SFI_NoVeg[nanlocs] = nodataval
                
                    WriteRasterMatch(SFI_BelowCanopy, OFName_Diffuse_UnderCanopy, pars['GISDir'] + '/DTM.tif', nodataval, pars['CreatePyramids'], pars['Verbose'])
                    WriteRasterMatch(SFI_NoVeg, OFName_Diffuse_NoVeg, pars['GISDir'] + '/DTM.tif', nodataval, pars['CreatePyramids'], pars['Verbose'])
                    

def GetLongwaveEnhancementMaps(pars):

    SagaGISLoc = pars['SagaGISLoc']
    
    DTM = ReadRaster(pars['GISDir'] + '/DTM.tif', pars['Verbose'])
    SkyView = ReadRaster(pars['IndexDir'] + '/SkyView.tif', pars['Verbose'])
    VegHT = ReadRaster(pars['GISDir'] + '/VegHT.tif', pars['Verbose'])
    VegHT[VegHT < 0] = 0
    VegHT[np.isnan(VegHT)] = 0
    Cover = ReadRaster(pars['GISDir'] + '/Cover.tif', pars['Verbose'])
    Cover[Cover < 0] = 0
    Cover[Cover > 100] = 0
    Cover[np.isnan(Cover)] = 0
    
    for root, subFolder, files in os.walk(pars['GISDir'] + '/PotentialSolar'):
        for file in files:
            if file[-17:] == '_direct_noVeg.tif' and 'Hourly' not in root:
                
                psolar_base = root + '/' + file.replace('_direct_noVeg.tif','')
                OFName = root.replace(pars['GISDir'],pars['IndexDir']).replace('PotentialSolar','LWI') + '/' + file.replace('_direct_noVeg.tif','.tif')
                IndexDir = os.path.dirname(OFName)
                
                if not os.path.exists(IndexDir):
                    os.makedirs(IndexDir)
                    
                    
                if not os.path.exists(OFName) or pars['Overwrite']:
                    print('Creating ' + OFName)
                    
                    sf_noveg_file = root + '/' + file
                    sf_top_file = root + '/' + file.replace('noVeg','top')
                    sf_flat_file = root + '/' + file.replace('noVeg','flat')

                    sf_top = ReadRaster(sf_top_file, pars['Verbose'])
                    sf_noveg = ReadRaster(sf_noveg_file, pars['Verbose'])
                    sf_flat = ReadRaster(sf_flat_file, pars['Verbose'])
                    rows,cols = sf_top.shape
                    sf_flat = np.array(Image.fromarray(sf_flat).resize(size=(cols, rows)))
                    
                    LWI_positive = np.maximum((1-VegHT/pars['LWIHeightRed']),0) * np.maximum((sf_top - sf_noveg)/sf_flat,0)
                    LWI = LWI_positive

                    nanlocs = np.isnan(DTM)
                    LWI[nanlocs] = np.nanmean(LWI)
                    
                    
                    LWI = np.array(Image.fromarray(LWI).resize(size=(round(rows/pars['LWIResizeFactor']), round(cols/pars['LWIResizeFactor']))).resize(size=(cols, rows)))
                    LWI = np.maximum(LWI,0)
                    LWI[nanlocs] = nodataval
                    
                    WriteRasterMatch(LWI, OFName, pars['GISDir'] + '/DTM.tif', nodataval, pars['CreatePyramids'], pars['Verbose'])
                  


def GetSnowfallDistributionMults(pars):

    SagaGISLoc = pars['SagaGISLoc']

    DTM = ReadRaster(pars['GISDir'] + '/DTM.tif', pars['Verbose'])
    Cover = ReadRaster(pars['GISDir'] + '/Cover.tif', pars['Verbose'])
    Cover[Cover < 0] = 0
    Cover[Cover > 100] = 0
    Cover[np.isnan(Cover)] = 0
    Skyview = ReadRaster(pars['IndexDir'] + '/SkyView.tif', pars['Verbose'])
    
    rows_0,cols_0 = DTM.shape
        
    # Timestamps of start and end dates
    STStamp = datetime(pars['StartYear'],pars['StartMonth'],1)
    ETStamp = datetime(pars['EndYear'],pars['EndMonth'],1)
    ETStamp = last_day_of_month(ETStamp)
    
    # Get data for first timestamp
    yyyy = str(STStamp.year)
    mm = str(STStamp.month)
    if len(mm) < 2:
        mm = '0' + mm
    dd = str(STStamp.day)
    if len(dd) < 2:
        dd = '0' + dd
    ncfile = pars['ForcingDir'] + '/' + yyyy + '/' + mm + '/' + dd + '.nc'
    ds = nc4.Dataset(ncfile)
    X = ds['X'][:]
    Y = ds['Y'][:]
    time = ds['time'][:]
    cols = X.shape[0]
    rows = Y.shape[0]
    times = time.shape[0]
    
    first_map = True
    
    d = 0
    for TS in daterange(STStamp, ETStamp + timedelta(days=1)):
        DIM = DIM_i[TS.month - 1]
        if TS.month == 2 and (np.mod(TS.year,4) == 0 and (np.mod(TS.year,100) > 0 or np.mod(TS.year,400) == 0)):
            DIM = DIM + 1
            
        yyyy = str(TS.year)
        mm = str(TS.month)
        if len(mm) < 2:
            mm = '0' + mm
        dd = str(TS.day)
        if len(dd) < 2:
            dd = '0' + dd
            
        ncfile = pars['ForcingDir'] + '/' + yyyy + '/' + mm + '/' + dd + '.nc'
        
        ds = nc4.Dataset(ncfile)
        ppt_day = ds['Precip'][:]
        
        # In case we have hourly data
        if ppt_day.ndim > 2:
            ppt_day = np.sum(ppt_day,0)

        airt_day = ds['AirT'][:]
        snow_day = ds['Snow'][:]
        winddir_day = ds['WindDir'][:]
        windspeed_day = ds['WindSpeed'][:]
        
        c = 0
        for WindDir in pars['WindDirs']:
            if WindDir == pars['WindDir']:
                loc = c
            c = c+1
            
        loc_m2 = loc - 2
        loc_m1 = loc - 1
        loc_p1 = loc + 1
        loc_p2 = loc + 2
        if loc_m2 < 0:
            loc_m2 = loc_m2 + c
        if loc_m1 < 0:
            loc_m1 = loc_m1 + c
        if loc_p1 > c:
            loc_p1 = loc_p1 - c
        if loc_p2 > c:
            loc_p2 = loc_p2 - c 
        
        if pars['IncludeAllDays'] or (np.nanmax(ppt_day) > pars['PThresh'] and np.nanmin(airt_day) < pars['TThresh']):
        
            OFName1 = pars['IndexDir'] + '/WindIndex/' + yyyy + '/' + mm + '/' + dd + '_noVeg.tif'
            OFName2 = pars['IndexDir'] + '/WindIndex/' + yyyy + '/' + mm + '/' + dd + '_withVeg.tif'
            
            if not pars['ForceDirection'] or first_map:
                first_map = False
                OFName1_first = OFName1
                OFName2_first = OFName2
                
                
                if not os.path.exists(pars['IndexDir'] + '/WindIndex/' + yyyy + '/' + mm):
                    os.makedirs(pars['IndexDir'] + '/WindIndex/' + yyyy + '/' + mm)
                
                if not os.path.exists(OFName1) or not os.path.exists(OFName2) or pars['Overwrite']:
                
                    print('Creating' + OFName1 + ' and ' + OFName2)
                    
                    WindEffect_noVeg = np.zeros([rows_0,cols_0])
                    WindEffect_withVeg = np.zeros([rows_0,cols_0])
                    ddir = pars['WindDirs'][1]-pars['WindDirs'][0]
                    if times == 1:
                        sum_wgt = windspeed_day
                    else:
                        sum_wgt = np.sum(windspeed_day, axis=0)
                    
                    c = 0
                    for WindDir in pars['WindDirs']:
                        if not pars['ForceDirection']:
                            if WindDir == 0:
                                wgt = np.sum(windspeed_day * ((winddir_day >= 360-ddir/2) | (winddir_day < ddir/2)),axis=0)
                            else:
                                wgt = np.sum(windspeed_day * ((winddir_day >= WindDir-ddir/2) & (winddir_day < WindDir + ddir/2)),axis=0)
                            
                            wgt = np.array(np.squeeze(wgt))
                            sum_wgt = np.array(np.squeeze(sum_wgt))
                            
                            factor = np.array(Image.fromarray(wgt/sum_wgt).resize(size=(cols_0, rows_0)))
                        
                        else:
                            if c == loc_m2 or c == loc_p2:
                                factor = np.ones(DTM.shape) * 0.05
                            elif c == loc_m1 or c == loc_p1:
                                factor = np.ones(DTM.shape) * 0.2
                            elif c == loc:
                                factor = np.ones(DTM.shape) * 0.5
                            else:
                                factor = np.zeros(DTM.shape)
                                
                        if np.sum(factor) > 0:
                        
                            wd = str(WindDir)
                            if len(wd) < 2:
                                wd = '0' + wd
                            
                            NoVegFile = pars['GISDir'] + '/WindEffect/' + wd + '_noVeg.tif'
                            NoVegWindEffect = ReadRaster(NoVegFile, pars['Verbose'])  
                            NoVegWindEffect[NoVegWindEffect < 0.5] = 0.5
                            NoVegWindEffect = 1 / NoVegWindEffect
                            
                            WithVegWindEffect = NoVegWindEffect * 1                        

                            d = 0
                            for VegRange in pars['VegCoverCategories']:
                                Transmittance = pars['Transmittances'][d]
                                WithVegFile = pars['GISDir'] + '/WindEffect/' + wd + '_withVeg_vcat_' + str(d) + '.tif'
                                WithVegWindEffect_ = ReadRaster(WithVegFile, pars['Verbose'])
                                WithVegWindEffect_[WithVegWindEffect_ < 0.5] = 0.5
                                WithVegWindEffect_ = 1 / WithVegWindEffect_
                                WithVegWindEffect_ = WithVegWindEffect_ * (1-Transmittance) + NoVegWindEffect * (Transmittance)
                                WithVegWindEffect = np.maximum(WithVegWindEffect, WithVegWindEffect_)
                                
                                d = d+1
                        
                            WindEffect_noVeg = WindEffect_noVeg + factor * NoVegWindEffect
                            WindEffect_withVeg = WindEffect_withVeg + factor * WithVegWindEffect
                            nanlocs = np.isnan(WithVegWindEffect)
                            print(np.sum(nanlocs))
                        
                        c = c+1
                        
                    WindEffect_withVeg = WindEffect_withVeg + (Skyview) / (1+pars['WindVegInfluence'])
                    
                    nanlocs = np.isnan(DTM)
                    WindEffect_withVeg[nanlocs] = np.nanmean(WindEffect_withVeg)
                    WindEffect_noVeg[nanlocs] = np.nanmean(WindEffect_noVeg)

                    WindEffect_withVeg = np.array(Image.fromarray(WindEffect_withVeg).resize(size=(round(rows_0/pars['WindEffectResizeFactor']), round(cols_0/pars['WindEffectResizeFactor']))).resize(size=(cols_0, rows_0)))
                    WindEffect_noVeg = np.array(Image.fromarray(WindEffect_noVeg).resize(size=(round(rows_0/pars['WindEffectResizeFactor']), round(cols_0/pars['WindEffectResizeFactor']))).resize(size=(cols_0, rows_0)))
                    
                    WindEffect_withVeg[nanlocs] = np.nan
                    WindEffect_noVeg[nanlocs] = np.nan
                    
                    if pars['ForceUnity']:
                        WindEffect_withVeg = WindEffect_withVeg / np.nanmean(WindEffect_withVeg)
                        WindEffect_noVeg = WindEffect_noVeg / np.nanmean(WindEffect_noVeg)
                        
                    nanlocs = np.isnan(DTM)
                    WindEffect_noVeg[nanlocs] = nodataval
                    WindEffect_withVeg[nanlocs] = nodataval
                    
                    WriteRasterMatch(WindEffect_noVeg, OFName1, pars['GISDir'] + '/DTM.tif', nodataval, pars['CreatePyramids'], pars['Verbose'])
                    WriteRasterMatch(WindEffect_withVeg, OFName2, pars['GISDir'] + '/DTM.tif', nodataval, pars['CreatePyramids'], pars['Verbose'])
            
            else:
            
                if not os.path.exists(OFName1) or not os.path.exists(OFName2) or pars['Overwrite']:
                    print('Creating' + OFName1 + ' and ' + OFName2)
                    if not os.path.exists(os.path.dirname(OFName1)):
                        os.makedirs(os.path.dirname(OFName1))
                        
                    shutil.copyfile(OFName1_first, OFName1)
                    shutil.copyfile(OFName2_first, OFName2)
            
        d = d+1
 