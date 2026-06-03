import sys
import os
import subprocess
from osgeo import gdal, ogr, osr
from osgeo.gdalconst import *
import numpy as np
import tempfile
import copy
from scipy.io import savemat, loadmat
from datetime import date, timedelta
import netCDF4 as nc4
from scipy import interpolate
from scipy import ndimage
import itertools
import multiprocessing
import time
from matplotlib import pyplot as plt

gdal.UseExceptions()

nodataval = -9999
dtype = GDT_Float32

def daterange(start_date, end_date):
    for n in range(int((end_date - start_date).days)):
        yield start_date + timedelta(n)


def ReadRaster(fname, Verbose):
    
    if Verbose:
        print('Reading ' + fname)
        
    ds = gdal.Open(fname, GA_ReadOnly)
    if ds is None:
        print('Could not open ' + fname)
        sys.exit(1)
    Data = ds.ReadAsArray().astype(float)
    band = ds.GetRasterBand(1)
    nodata_value = band.GetNoDataValue()
    ds = None
    Data[Data == nodata_value] = np.nan
    
    return Data


def GetGeorefInfo(fname):
    ds = gdal.Open(fname, GA_ReadOnly)
    if ds is None:
        print ('Could not open ' + fname)
        sys.exit(1)
    transform = ds.GetGeoTransform()
    projection = ds.GetProjection()
    wkt = ds.GetProjection()
    rows = ds.RasterYSize
    cols = ds.RasterXSize
    ulx = transform[0]
    uly = transform[3]
    pixelWidth = transform[1]
    pixelHeight = transform[5]
    lrx = ulx + (cols * pixelWidth)
    lry = uly + (rows * pixelHeight)
    srs = osr.SpatialReference()
    srs.ImportFromWkt(ds.GetProjectionRef())
    prj = srs.ExportToProj4()
    wkt = srs.ExportToWkt()
    ds = None

    return(rows,cols,ulx,uly,lrx,lry,pixelWidth,pixelHeight,projection,transform,prj,wkt)
    
    
def exec_cmd(cmd, Verbose):

    if Verbose:
        print('Executing command: ' + cmd)

    result = subprocess.run(
        cmd,
        shell=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True
    )

    if result.stdout:
        print(result.stdout)

    if result.stderr:
        print(result.stderr)

    if result.returncode != 0:
        raise RuntimeError(
            f'Command failed with exit code {result.returncode}'
        )
        
        
def WriteRasterMatch(Data, OFName, match_file, CreatePyramids, Verbose):
        
        if Verbose:
            print('Writing ' + OFName)
            
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
        
        
def WriteRaster(Data, OFName, Subdomain, CreatePyramids, Verbose):
        
        if Verbose:
            print('Writing ' + OFName)

        cols = Subdomain['cols']
        rows = Subdomain['rows']
        GeoTransform = Subdomain['transform']
        Projection = Subdomain['projection']
        
        driver = gdal.GetDriverByName("GTiff")
        co = ["COMPRESS=LZW", "BIGTIFF=IF_SAFER"]
        outdata = driver.Create(OFName, cols, rows, 1, dtype, options=co)
        outdata.SetGeoTransform(GeoTransform)
        outdata.SetProjection(Projection)
        outdata.GetRasterBand(1).WriteArray(Data)
        outdata.GetRasterBand(1).SetNoDataValue(nodataval)
        outdata.FlushCache()
        outdata = None
        
        if CreatePyramids:
            cmd = 'gdaladdo --config COMPRESS_OVERVIEW DEFLATE --config BIGTIFF_OVERVIEW IF_SAFER -r average -ro "' + OFName + '"'
            exec_cmd(cmd, Verbose)
        
def fill_nans_with_nearest(data):
    # Create mask of NaNs
    nan_mask = np.isnan(data)

    # Get indices of nearest non-NaN values
    nearest_valid_index = ndimage.distance_transform_edt(nan_mask, return_distances=False, return_indices=True)

    # Use those indices to index into original array
    filled = data[tuple(nearest_valid_index)]
    return filled
        
def Initialize(pars):
    
    if pars['SimulationType'] == 0 or pars['SimulationType'] == 1:
    
        OFName1 = pars['ModelDir'] + '/' + 'Tiles.tif'
        OFName2 = pars['ModelDir'] + '/' + 'ModelInfo.mat'
        if not os.path.exists(os.path.dirname(OFName1)):
            os.makedirs(os.path.dirname(OFName1))
            
        if not os.path.exists(OFName1) or not os.path.exists(OFName2) or pars['ReinitializeModel']:
        
            print('Creating ' + OFName1 + ' and ' + OFName2)
            tmp_dir = tempfile.TemporaryDirectory()
            
            if pars['SimulationType'] == 0:
                fname = pars['GISDir'] + '/DTM.tif'
                DTM = ReadRaster(fname,pars['Verbose'])
                rows,cols,ulx,uly,lrx,lry,pixelWidth,pixelHeight,projection,transform,prj,wkt = GetGeorefInfo(fname)
                
            elif pars['SimulationType'] == 1:
                ifname = pars['GISDir'] + '/DTM.tif'
                ofname = tmp_dir.name + '.tif'
                projwin = str(pars['NSWE'][2]) + ' ' + str(pars['NSWE'][0]) + ' ' + str(pars['NSWE'][3]) + ' ' + str(pars['NSWE'][1])
                
                cmd = 'gdal_translate -projwin ' + projwin + ' "' + ifname + '" "' + ofname + '"'
                exec_cmd(cmd, pars['Verbose'])
                
                DTM = ReadRaster(ofname,pars['Verbose'])
                rows,cols,ulx,uly,lrx,lry,pixelWidth,pixelHeight,projection,transform,prj,wkt = GetGeorefInfo(ofname)
                os.remove(ofname)
                
            Subdomain = {}
            Subdomain['StartYear'] = pars['StartDate'].year
            Subdomain['StartMonth'] = pars['StartDate'].month
            Subdomain['StartDay'] = pars['StartDate'].day
            Subdomain['EndYear'] = pars['EndDate'].year
            Subdomain['EndMonth'] = pars['EndDate'].month
            Subdomain['EndDay'] = pars['EndDate'].day
            Subdomain['ModelTimestep'] = pars['ModelTimestep']
            Subdomain['ForcingSetName'] = pars['ForcingSetName']
            Subdomain['UseHourlySFIFiles'] = pars['UseHourlySFIFiles']
            Subdomain['SimulationType'] = pars['SimulationType']
            
            Subdomain['rows'] = rows
            Subdomain['cols'] = cols
            Subdomain['ulx'] = ulx
            Subdomain['uly'] = uly
            Subdomain['lrx'] = lrx
            Subdomain['lry'] = lry
            Subdomain['pixelWidth'] = pixelWidth
            Subdomain['pixelHeight'] = pixelHeight
            Subdomain['projection'] = projection
            Subdomain['transform'] = transform
            Subdomain['prj'] = prj
            Subdomain['wkt'] = wkt
            
            boxside = np.round(np.sqrt(pars['MaxChunkSize']))*pixelWidth
            
            # Set up vectors defining the discretization of each model tile...
            ncols = int(np.round((lrx-ulx) / boxside))
            nrows = int(np.round((uly-lry) / boxside))
            tile_width = int(np.round((lrx-ulx) / (ncols*pixelWidth)))
            tile_height = int(-np.round((uly-lry) / (nrows*pixelHeight)))
            
            Tiles = []
            for col in range(ncols):
                for row in range(nrows):
                
                    Tile = {}
                    Tile['ulx'] = ulx + (col*tile_width) * pixelWidth
                    Tile['uly'] = uly + (row*tile_height) * pixelHeight
                    if col < ncols - 1:
                        Tile['lrx'] = ulx + col * tile_width * pixelWidth + tile_width * pixelWidth
                    else:
                        Tile['lrx'] = lrx
                    if row < nrows - 1:
                        Tile['lry']  = uly + row * tile_height * pixelHeight + tile_height * pixelHeight
                    else:
                        Tile['lry'] = lry
                        
                    Tile['cols'] = int((Tile['lrx'] - Tile['ulx']) / pixelWidth)
                    Tile['rows'] = int(-(Tile['uly'] - Tile['lry']) / pixelHeight)
                    Tile['xlocs'] = np.arange(col * tile_width, col * tile_width + Tile['cols']).astype(int)
                    Tile['ylocs'] = np.arange(row * tile_height, row * tile_height + Tile['rows']).astype(int)
                    Tile['pixelWidth'] = Subdomain['pixelWidth']
                    Tile['pixelHeight'] = Subdomain['pixelHeight']

                    te = str(Tile['ulx']) + ' ' + str(Tile['lry']) + ' ' + str(Tile['lrx']) + ' ' + str(Tile['uly']) 
                    
                    ifname = pars['GISDir'] + '/DTM.tif'
                    ofname = tmp_dir.name + '/DTM.tif'
                    cmd = 'gdalwarp -overwrite -te ' + te + ' "' + ifname + '" "' + ofname + '"'
                    exec_cmd(cmd, pars['Verbose'])
                    DTM = ReadRaster(ofname, pars['Verbose'])
                    Tile['mask'] = np.array(~np.isnan(DTM)).astype(int)
                    os.remove(ofname)
                    
                    Tiles.append(copy.deepcopy(Tile))
               
            c = 0
            Mask = np.ones([rows,cols]) * nodataval
            for Tile in Tiles:
                xx, yy = np.meshgrid(Tile['xlocs'], Tile['ylocs'])
                Mask[yy, xx] = np.ones([Tile['rows'], Tile['cols']]) * c
                c = c + 1
                  
            WriteRaster(Mask, OFName1, Subdomain, False, pars['Verbose'])
            
            savemat(OFName2, {'Subdomain': Subdomain, 'Tiles': Tiles})
      
    elif pars['SimulationType'] == 2:
    
        OFName1 = pars['ModelDir'] + '/' + 'POIs.tif'
        OFName2 = pars['ModelDir'] + '/' + 'ModelInfo.mat'
        if not os.path.exists(os.path.dirname(OFName1)):
            os.makedirs(os.path.dirname(OFName1))
            
        if not os.path.exists(OFName1) or not os.path.exists(OFName2) or pars['ReinitializeModel']:
       
            print('Creating ' + OFName1 + ' and ' + OFName2)
            tmp_dir = tempfile.TemporaryDirectory()
            
            rows,cols,ulx,uly,lrx,lry,pixelWidth,pixelHeight,projection,transform,prj,wkt = GetGeorefInfo(pars['GISDir'] + '/DTM.tif')

            Subdomain = {}
            Subdomain['StartYear'] = pars['StartDate'].year
            Subdomain['StartMonth'] = pars['StartDate'].month
            Subdomain['StartDay'] = pars['StartDate'].day
            Subdomain['EndYear'] = pars['EndDate'].year
            Subdomain['EndMonth'] = pars['EndDate'].month
            Subdomain['EndDay'] = pars['EndDate'].day
            Subdomain['ModelTimestep'] = pars['ModelTimestep']
            Subdomain['ForcingSetName'] = pars['ForcingSetName']
            Subdomain['UseHourlySFIFiles'] = pars['UseHourlySFIFiles']
            Subdomain['SimulationType'] = pars['SimulationType']
            Subdomain['rows'] = rows
            Subdomain['cols'] = cols
            Subdomain['ulx'] = ulx
            Subdomain['uly'] = uly
            Subdomain['lrx'] = lrx
            Subdomain['lry'] = lry
            Subdomain['pixelWidth'] = pixelWidth
            Subdomain['pixelHeight'] = pixelHeight
            Subdomain['projection'] = projection
            Subdomain['transform'] = transform
            Subdomain['prj'] = prj
            Subdomain['wkt'] = wkt
            
            MaskFName = tmp_dir.name + '.tif'
            Mask_0 = np.ones([rows,cols]) * nodataval
            
            files = os.listdir(pars['POIDir'])
            
            POIs = []
            c = 0
            d = 0
            for file in files:
                if file[-4:] == '.shp' or file[-4:] == '.SHP':
                        
                    print('Reading ' + pars['POIDir'] + '/' + file)
                    cmd = 'ogr2ogr -t_srs "' + prj + '" -dim 2 "' + tmp_dir.name + '/' + file + '" "' + pars['POIDir'] + '/' + file + '"'
                    exec_cmd(cmd, pars['Verbose'])
                    
                    WriteRasterMatch(Mask_0, MaskFName, pars['GISDir'] + '/DTM.tif', False, pars['Verbose'])
                    
                    cmd = 'gdal_rasterize -at -a FID  "' + tmp_dir.name + '/' + file + '" "' + MaskFName + '"'
                    exec_cmd(cmd, pars['Verbose'])
                    Mask = ReadRaster(MaskFName, pars['Verbose'])
                    os.remove(MaskFName)
                    
                    driver = ogr.GetDriverByName("ESRI Shapefile")
                    ds = driver.Open(tmp_dir.name + '/' + file, 0)
                    layer = ds.GetLayer()
                    # layerDefinition = layer.GetLayerDefn()
                    # layer_list = []
                    # for i in range(layerDefinition.GetFieldCount()):
                        # layer_name = layerDefinition.GetFieldDefn(i).GetName()
                        # layer_list.append(layer_name)
                        
                    Names = []
                    FIDs = []                
                    # for x in layer_list:
                    for feature in layer:
                        Names.append(feature.GetField('Name'))
                        FIDs.append(feature.GetField('FID'))        
                    layer = None
                    ds = None
                    
                    Indexes = np.argsort(FIDs)
                    POI = {}
                    
                    for Index in Indexes:
                        POI['Name'] = Names[Index]
                        POI['Locs'] = np.argwhere(Mask == FIDs[Index])
                        d = d+POI['Locs'].size/2
                        if not POI['Locs'].size == 0:
                            POIs.append(copy.deepcopy(POI))
                    
            c = 0
            Mask = np.ones([rows,cols]) * nodataval
            for POI in POIs:
                for loc in POI['Locs']:
                    Mask[loc[0],loc[1]] = c
                    
                c = c+1
               
            WriteRaster(Mask, OFName1, Subdomain, False, pars['Verbose'])

            savemat(OFName2, {'Subdomain': Subdomain, 'POIs': POIs})
            

def interp_forcing_data(TileName,FName,Locs,nt,nd,te,tr,pars):

    if not os.path.exists(FName) or pars['OverwriteForcing'] or pars['ReinitializeModel']:
    
        print('Getting forcing data for ' + TileName)
    
        OutVars = {}
        OutVars['AirT'] = np.ones([nt, nd]) * np.nan
        OutVars['RH'] = np.ones([nt, nd]) * np.nan
        OutVars['Pres'] = np.ones([nt, nd]) * np.nan
        OutVars['WindSpeed'] = np.ones([nt, nd]) * np.nan
        OutVars['WindDir'] = np.ones([nt, nd]) * np.nan
        OutVars['Shortwave'] = np.ones([nt, nd]) * np.nan
        OutVars['Longwave'] = np.ones([nt, nd]) * np.nan
        OutVars['Precip'] = np.ones([nt, nd]) * np.nan
        OutVars['Rain'] = np.ones([nt, nd]) * np.nan
        OutVars['Snow'] = np.ones([nt, nd]) * np.nan
        OutVars['PET'] = np.ones([nt, nd]) * np.nan
        
        tr_split = tr.split(' ')
        te_split = te.split(' ')
        xi = np.arange(float(te_split[0]) + float(tr_split[0])/2, float(te_split[2]), float(tr_split[0]))
        yi = np.arange(float(te_split[1]) - float(tr_split[1])/2, float(te_split[3]), -float(tr_split[1]))
        xxi, yyi = np.meshgrid(xi, yi)
        xxi_sub = np.flipud(xxi)[Locs]
        yyi_sub = np.flipud(yyi)[Locs]
        
        d = 0
        for TS in daterange(pars['StartDate'], pars['EndDate'] + timedelta(days=1)):
        
            yyyy = str(TS.year)
            mm = str(TS.month)
            if len(mm) < 2:
                mm = '0' + mm
            dd = str(TS.day)
            if len(dd) < 2:
                dd = '0' + dd
        
            ifname = pars['ForcingDir'] + '/' + yyyy + '/' + mm + '/' + dd + '.nc'
            ds = nc4.Dataset(ifname)
            
            if pars['Verbose']:
                print('Getting forcing data for ' + yyyy + '-' + mm + '-' + dd + ' for ' + TileName)
            
            for Variable in ['AirT', 'RH', 'Pres', 'WindSpeed', 'WindDir', 'Shortwave', 'Longwave', 'Precip', 'Rain', 'Snow', 'PET']:
                
                Data = ds[Variable][:]
                x = ds['X'][:]
                y = np.flipud(ds['Y'])[:]

                # Forcing is hourly, model is hourly
                if Data.shape[0] == 24 and pars['ModelTimestep'] == 0:
                    for i in range(24):
                        Data_sub = fill_nans_with_nearest(Data[i,:,:])
                        # f = interpolate.interp2d(x, y, np.flipud(Data_sub), kind='linear')
                        f = interpolate.RegularGridInterpolator((y, x),np.flipud(Data_sub),method='linear',bounds_error=False,fill_value=np.nan)
                           
                        if pars['SimulationType'] == 2:
                            interp_vals = f(np.column_stack((yyi_sub, xxi_sub)))  
                        else:
                            interp_vals = np.flipud(f(np.column_stack((yyi.ravel(), xxi.ravel()))).reshape(len(yi), len(xi)))[Locs]
                        
                        OutVars[Variable][d*24+i,:] = interp_vals
                            
                elif Data.shape[0] == 24 and pars['ModelTimestep'] == 1:
                    if Variable == 'Precip' or Variable == 'Rain' or Variable == 'Snow':
                        Data_sub = np.sum(Data, axis=0)
                    else:
                        Data_sub = np.mean(Data, axis=0)
                    Data_sub = fill_nans_with_nearest(Data_sub)
                    
                    # f = interpolate.interp2d(x, y, np.flipud(Data_sub), kind='linear')
                    f = interpolate.RegularGridInterpolator((y, x),np.flipud(Data_sub),method='linear',bounds_error=False,fill_value=np.nan)
                    if pars['SimulationType'] == 2:
                        interp_vals = f(np.column_stack((yyi_sub, xxi_sub)))
                    else:
                        interp_vals = np.flipud(f(np.column_stack((yyi.ravel(), xxi.ravel()))).reshape(len(yi), len(xi)))[Locs]
                        
                        
                    OutVars[Variable][d,:] = interp_vals
                        
                elif Data.shape[0] == 1 and pars['ModelTimestep'] == 1:
                    
                    Data_sub = fill_nans_with_nearest(Data[0,:,:])
                    # f = interpolate.interp2d(x, y, np.flipud(Data_sub), kind='linear')
                    f = interpolate.RegularGridInterpolator((y, x),np.flipud(Data_sub),method='linear',bounds_error=False,fill_value=None)
                    
                    if pars['SimulationType'] == 2:
                        interp_vals = f(np.column_stack((yyi_sub, xxi_sub)))
                    else:
                        interp_vals = np.flipud(f(np.column_stack((yyi.ravel(), xxi.ravel()))).reshape(len(yi), len(xi)))[Locs]
                        
                    
                    # X, Y = np.meshgrid(x, y)
                    # Z_check = f(np.column_stack((yyi.ravel(), xxi.ravel()))).reshape(len(yi), len(xi))
                    
                    # plt.pcolormesh(xi, yi, Z_check, shading='auto')
                    # plt.colorbar()
                    # plt.show()
                    
                    # plt.pcolormesh(x, y, Data_sub, shading='auto')
                    # plt.colorbar()
                    # plt.show()
                              
                    # sys.exit()

                    OutVars[Variable][d,:] = interp_vals
                    
                elif Data.shape[0] == 1 and pars['ModelTimestep'] == 0:
                    print('Hourly forcing data must be used to drive an hourly model!!!')
                    sys.exit()      

                
            d = d+1
            ds = None
            
        print('Writing ' + FName)
          
        if not os.path.exists(os.path.dirname(FName)):
            os.makedirs(os.path.dirname(FName))
            
        if os.path.exists(FName):
            os.remove(FName)
            
        with nc4.Dataset(FName, 'w' , format='NETCDF4_CLASSIC') as ds:
        
            # Initialize the dimensions of the dataset
            dim_time = ds.createDimension('time', nt)
            dim_ndata = ds.createDimension('X', nd)
            
            # Ready the Temperature data field
            airt_nc = ds.createVariable('AirT', np.float32, ('time','X'), zlib=True, least_significant_digit=pars['least_significant_digit'])
            airt_nc.standard_name = ['Air Temperature']
            airt_nc.units = ['degrees-C']
            
            # Ready the Relative Humidity data field
            rh_nc = ds.createVariable('RH', np.float32, ('time','X'), zlib=True, least_significant_digit=pars['least_significant_digit'])
            rh_nc.standard_name = ['Relative Humidity']
            rh_nc.units = ['%']
            
            # Ready the Pressure data field
            pres_nc = ds.createVariable('Pres', np.float32, ('time','X'), zlib=True, least_significant_digit=pars['least_significant_digit'])
            pres_nc.standard_name = ['Pressure']
            pres_nc.units = ['Pa']
            
            # Ready the Wind Speed data field
            windspeed_nc = ds.createVariable('WindSpeed', np.float32, ('time','X'), zlib=True, least_significant_digit=pars['least_significant_digit'])
            windspeed_nc.standard_name = ['Wind Speed']
            windspeed_nc.units = ['m/s']
            
            # Ready the Wind Direction data field
            winddir_nc = ds.createVariable('WindDir', np.float32, ('time','X'), zlib=True, least_significant_digit=pars['least_significant_digit'])
            winddir_nc.standard_name = ['Wind Direction']
            winddir_nc.units = ['Degrees']
            
            # Ready the Incoming Solar data field
            shortwave_nc = ds.createVariable('Shortwave', np.float32, ('time','X'), zlib=True, least_significant_digit=pars['least_significant_digit'])
            shortwave_nc.standard_name = ['Incoming Shortwave Radiation']
            shortwave_nc.units = ['W/m^2']
            
            # Ready the Incoming Longwave data field
            longwave_nc = ds.createVariable('Longwave', np.float32, ('time','X'), zlib=True, least_significant_digit=pars['least_significant_digit'])
            longwave_nc.standard_name = ['Incoming Longwave Radiation']
            longwave_nc.units = ['W/m^2']
            
            # Ready the Precipitation data field
            precip_nc = ds.createVariable('Precip', np.float32, ('time','X'), zlib=True, least_significant_digit=pars['least_significant_digit'])
            precip_nc.standard_name = ['Precipitation']
            precip_nc.units = ['mm']
            
            # Ready the Precipitation data field
            rain_nc = ds.createVariable('Rain', np.float32, ('time','X'), zlib=True, least_significant_digit=pars['least_significant_digit'])
            rain_nc.standard_name = ['Rainfall']
            rain_nc.units = ['mm']
            
            # Ready the Precipitation data field
            snow_nc = ds.createVariable('Snow', np.float32, ('time','X'), zlib=True, least_significant_digit=pars['least_significant_digit'])
            snow_nc.standard_name = ['Snowfall']
            snow_nc.units = ['mm']
            
            # Ready the Precipitation data field
            pet_nc = ds.createVariable('PET', np.float32, ('time','X'), zlib=True, least_significant_digit=pars['least_significant_digit'])
            pet_nc.standard_name = ['Potential Evaporation']
            pet_nc.units = ['mm']
            
            # Fill with values
            airt_nc[:] = OutVars['AirT']
            rh_nc[:] = OutVars['RH']
            pres_nc[:] = OutVars['Pres']
            windspeed_nc[:] = OutVars['WindSpeed']
            winddir_nc[:] = OutVars['WindDir']
            shortwave_nc[:] = OutVars['Shortwave']
            longwave_nc[:] = OutVars['Longwave']
            precip_nc[:] = OutVars['Precip']
            rain_nc[:] = OutVars['Rain']
            snow_nc[:] = OutVars['Snow']
            pet_nc[:] = OutVars['PET']
            

def multiInterp(f0):
    
    # st = time.time()
        
    x = np.arange(len(f0[:,0]))
    nonnanlocs = ~np.isnan(f0[:,0])
    fp = f0[nonnanlocs,:]
    xp = x[nonnanlocs]
    if xp.size > 0:
        f = np.array([np.interp(x, xp, fp[:,i]) for i in range(fp[0,:].size)]).T
    else:
        f = np.ones(f0.shape) * np.nan
    
    # print(time.time()-st)
    # from matplotlib import pyplot as plt
    # plt.plot(xp, fp[:,0], 'o')
    # plt.plot(x, f[:,0], '-')
    # plt.show()
    
    return f
        
    
def interp_indexes(TileName,FName,Locs,nt,nd,te,tr,pars):

    if not os.path.exists(FName) or pars['OverwriteIndexes'] or pars['ReinitializeModel']:
    
        print('Reading index data for ' + TileName)
    
        OutVars = {}
        OutVars['LAI'] = np.ones([nd]) * np.nan
        OutVars['Lat'] = np.ones([nd]) * np.nan
        OutVars['Elev'] = np.ones([nd]) * np.nan
        OutVars['Skyview'] = np.ones([nd]) * np.nan
        OutVars['LWI'] = np.ones([nt, nd]) * np.nan
        OutVars['SFI_Direct_UnderCanopy'] = np.ones([nt, nd]) * np.nan
        OutVars['SFI_Diffuse_UnderCanopy'] = np.ones([nt, nd]) * np.nan
        OutVars['SFI_Direct_NoVeg'] = np.ones([nt, nd]) * np.nan
        OutVars['SFI_Diffuse_NoVeg'] = np.ones([nt, nd]) * np.nan
        OutVars['SnowfallIndex_WithVeg'] = np.ones([nt, nd]) * np.nan
        OutVars['SnowfallIndex_NoVeg'] = np.ones([nt, nd]) * np.nan
        
        tmp_dir = tempfile.TemporaryDirectory()
        
        ifname = pars['IndexDir'] + '/LAI.tif'
        ofname = tmp_dir.name + '/tmp_index.tif'
        if pars['Verbose']:
            print('Reading ' + ifname + ' for ' + TileName)
        cmd = 'gdalwarp -overwrite -te ' + te + ' -tr ' + tr + ' "' + ifname + '" "' + ofname + '"'
        exec_cmd(cmd, pars['Verbose'])
        Data = ReadRaster(ofname, pars['Verbose'])
        OutVars['LAI'] = Data[Locs]
        
        ifname = pars['GISDir'] + '/DTM.tif'
        ofname = tmp_dir.name + '/tmp_index.tif'
        if pars['Verbose']:
            print('Reading ' + ifname + ' for ' + TileName)
        cmd = 'gdalwarp -overwrite -te ' + te + ' -tr ' + tr + ' "' + ifname + '" "' + ofname + '"'
        exec_cmd(cmd, pars['Verbose'])
        Data = ReadRaster(ofname, pars['Verbose'])
        OutVars['Elev'] = Data[Locs]
        
        ifname = pars['IndexDir'] + '/Skyview.tif'
        ofname = tmp_dir.name + '/tmp_index.tif'
        if pars['Verbose']:
            print('Reading ' + ifname + ' for ' + TileName)
        cmd = 'gdalwarp -overwrite -te ' + te + ' -tr ' + tr + ' "' + ifname + '" "' + ofname + '"'
        exec_cmd(cmd, pars['Verbose'])
        Data = ReadRaster(ofname, pars['Verbose'])
        OutVars['Skyview'] = Data[Locs]
        
        ds = gdal.Open(ofname)
        gt = ds.GetGeoTransform()

        nx = ds.RasterXSize
        ny = ds.RasterYSize

        # Source CRS
        src = osr.SpatialReference()
        src.ImportFromWkt(ds.GetProjection())

        # Target CRS = lat/lon
        dst = osr.SpatialReference()
        dst.ImportFromEPSG(4326)

        ct = osr.CoordinateTransformation(src, dst)

        # Pixel center coordinates
        cols = np.arange(nx)
        rows = np.arange(ny)

        x = gt[0] + (cols + 0.5) * gt[1]
        y = gt[3] + (rows + 0.5) * gt[5]

        X, Y = np.meshgrid(x, y)

        # Flatten input
        pts = np.column_stack([X.ravel(), Y.ravel()])

        # GDAL bulk transform (no Python loop)
        out = np.array(ct.TransformPoints(pts))

        # out columns: lon, lat, z
        lat = out[:, 0].reshape(ny, nx)

        OutVars["Lat"] = lat[Locs]


        d = 0
        for TS in daterange(pars['StartDate'], pars['EndDate'] + timedelta(days=1)):
        
            yyyy = str(TS.year)
            mm = str(TS.month)
            if len(mm) < 2:
                mm = '0' + mm
            dd = str(TS.day)
            if len(dd) < 2:
                dd = '0' + dd
              
            if os.path.exists(pars['IndexDir'] + '/LWI/Daily/' + mm + '-' + dd + '.tif'):
                ifname = pars['IndexDir'] + '/LWI/Daily/' + mm + '-' + dd + '.tif'
                ofname = tmp_dir.name + '/tmp_index.tif'
                if pars['Verbose']:
                    print('Reading ' + ifname + ' for ' + TileName)
                cmd = 'gdalwarp -overwrite -te ' + te + ' -tr ' + tr + ' "' + ifname + '" "' + ofname + '"'
                exec_cmd(cmd, pars['Verbose'])
                Data = ReadRaster(ofname, pars['Verbose'])
                if pars['ModelTimestep'] == 1:
                    OutVars['LWI'][d,:] = Data[Locs]
                elif pars['ModelTimestep'] == 0:
                    for i in range(24):
                        OutVars['LWI'][d*24+i,:] = Data[Locs]
                            
            if pars['UseHourlySFIFiles'] == False:
                if os.path.exists(pars['IndexDir'] + '/SFI/Daily/' + mm + '-' + dd + '_direct_underCanopy.tif'):
                    # ifname = pars['IndexDir'] + '/LWI/Daily/' + mm + '-' + dd + '.tif'
                    # ofname = tmp_dir.name + '/tmp_index.tif'
                    # if pars['Verbose']:
                        # print('Reading ' + ifname + ' for ' + TileName)
                    # cmd = 'gdalwarp -overwrite -te ' + te + ' -tr ' + tr + ' "' + ifname + '" "' + ofname + '"'
                    # exec_cmd(cmd, pars['Verbose'])
                    # Data = ReadRaster(ofname, pars['Verbose'])
                    # if pars['ModelTimestep'] == 1:
                        # OutVars['LWI'][d,:] = Data[Locs]
                    # elif pars['ModelTimestep'] == 0:
                        # for i in range(24):
                            # OutVars['LWI'][d*24+i,:] = Data[Locs]
                
                    ifname = pars['IndexDir'] + '/SFI/Daily/' + mm + '-' + dd + '_direct_UnderCanopy.tif'
                    ofname = tmp_dir.name + '/tmp_index.tif'
                    if pars['Verbose']:
                        print('Reading ' + ifname + ' for ' + TileName)
                    cmd = 'gdalwarp -overwrite -te ' + te + ' -tr ' + tr + ' "' + ifname + '" "' + ofname + '"'
                    exec_cmd(cmd, pars['Verbose'])
                    Data = ReadRaster(ofname, pars['Verbose'])
                    if pars['ModelTimestep'] == 1:
                        OutVars['SFI_Direct_UnderCanopy'][d,:] = Data[Locs]
                    elif pars['ModelTimestep'] == 0:
                        for i in range(24):
                            OutVars['SFI_Direct_UnderCanopy'][d*24+i,:] = Data[Locs]

                    ifname = pars['IndexDir'] + '/SFI/Daily/' + mm + '-' + dd + '_diffuse_UnderCanopy.tif'
                    ofname = tmp_dir.name + '/tmp_index.tif'
                    if pars['Verbose']:
                        print('Reading ' + ifname + ' for ' + TileName)
                    cmd = 'gdalwarp -overwrite -te ' + te + ' -tr ' + tr + ' "' + ifname + '" "' + ofname + '"'
                    exec_cmd(cmd, pars['Verbose'])
                    Data = ReadRaster(ofname, pars['Verbose'])
                    if pars['ModelTimestep'] == 1:
                        OutVars['SFI_Diffuse_UnderCanopy'][d,:] = Data[Locs]
                    elif pars['ModelTimestep'] == 0:
                        for i in range(24):
                            OutVars['SFI_Diffuse_UnderCanopy'][d*24+i,:] = Data[Locs]
                    
                    ifname = pars['IndexDir'] + '/SFI/Daily/' + mm + '-' + dd + '_direct_NoVeg.tif'
                    ofname = tmp_dir.name + '/tmp_index.tif'
                    if pars['Verbose']:
                        print('Reading ' + ifname)
                    cmd = 'gdalwarp -overwrite -te ' + te + ' -tr ' + tr + ' "' + ifname + '" "' + ofname + '"'
                    exec_cmd(cmd, pars['Verbose'])
                    Data = ReadRaster(ofname, pars['Verbose'])
                    if pars['ModelTimestep'] == 1:
                        OutVars['SFI_Direct_NoVeg'][d,:] = Data[Locs]
                    elif pars['ModelTimestep'] == 0:
                        for i in range(24):
                            OutVars['SFI_Direct_NoVeg'][d*24+i,:] = Data[Locs]
                    
                    ifname = pars['IndexDir'] + '/SFI/Daily/' + mm + '-' + dd + '_diffuse_NoVeg.tif'
                    ofname = tmp_dir.name + '/tmp_index.tif'
                    if pars['Verbose']:
                        print('Reading ' + ifname + ' for ' + TileName)
                    cmd = 'gdalwarp -overwrite -te ' + te + ' -tr ' + tr + ' "' + ifname + '" "' + ofname + '"'
                    exec_cmd(cmd, pars['Verbose'])
                    Data = ReadRaster(ofname, pars['Verbose'])
                    if pars['ModelTimestep'] == 1:
                        OutVars['SFI_Diffuse_NoVeg'][d,:] = Data[Locs]
                    elif pars['ModelTimestep'] == 0:
                        for i in range(24):
                            OutVars['SFI_Diffuse_NoVeg'][d*24+i,:] = Data[Locs]
                            
            elif pars['UseHourlySFIFiles'] == True:
                
                if os.path.exists(pars['IndexDir'] + '/SFI/Hourly/' + mm + '-' + dd + '/00_direct_underCanopy.tif'):
                    for hour in range(24):

                        hh = str(hour)
                        if len(hh) < 2:
                            hh = '0' + hh
                            
                        # ifname = pars['IndexDir'] + '/LWI/Hourly/' + mm + '-' + dd + '/' + hh + '.tif'
                        # ofname = tmp_dir.name + '/tmp_index.tif'
                        # if pars['Verbose']:
                            # print('Reading ' + ifname + ' for ' + TileName)
                        # cmd = 'gdalwarp -overwrite -te ' + te + ' -tr ' + tr + ' "' + ifname + '" "' + ofname + '"'
                        # exec_cmd(cmd, pars['Verbose'])
                        # Data = ReadRaster(ofname, pars['Verbose'])
                        # Data[np.isnan(Data)] = 0
                        # OutVars['LWI'][d*24+hour,:] = Data[Locs]
                            
                        ifname = pars['IndexDir'] + '/SFI/Hourly/' + mm + '-' + dd + '/' + hh + '_direct_UnderCanopy.tif'
                        ofname = tmp_dir.name + '/tmp_index.tif'
                        if pars['Verbose']:
                            print('Reading ' + ifname + ' for ' + TileName)
                        cmd = 'gdalwarp -overwrite -te ' + te + ' -tr ' + tr + ' "' + ifname + '" "' + ofname + '"'
                        exec_cmd(cmd, pars['Verbose'])
                        Data = ReadRaster(ofname, pars['Verbose'])
                        Data[np.isnan(Data)] = 0
                        OutVars['SFI_Direct_UnderCanopy'][d*24+hour,:] = Data[Locs]

                        ifname = pars['IndexDir'] + '/SFI/Hourly/' + mm + '-' + dd + '/' + hh + '_diffuse_UnderCanopy.tif'
                        ofname = tmp_dir.name + '/tmp_index.tif'
                        if pars['Verbose']:
                            print('Reading ' + ifname + ' for ' + TileName)
                        cmd = 'gdalwarp -overwrite -te ' + te + ' -tr ' + tr + ' "' + ifname + '" "' + ofname + '"'
                        exec_cmd(cmd, pars['Verbose'])
                        Data = ReadRaster(ofname, pars['Verbose'])
                        Data[np.isnan(Data)] = 0
                        OutVars['SFI_Diffuse_UnderCanopy'][d*24+hour,:] = Data[Locs]
                        
                        ifname = pars['IndexDir'] + '/SFI/Hourly/' + mm + '-' + dd + '/' + hh + '_direct_NoVeg.tif'
                        ofname = tmp_dir.name + '/tmp_index.tif'
                        if pars['Verbose']:
                            print('Reading ' + ifname + ' for ' + TileName)
                        cmd = 'gdalwarp -overwrite -te ' + te + ' -tr ' + tr + ' "' + ifname + '" "' + ofname + '"'
                        exec_cmd(cmd, pars['Verbose'])
                        Data = ReadRaster(ofname, pars['Verbose'])
                        Data[np.isnan(Data)] = 0
                        OutVars['SFI_Direct_NoVeg'][d*24+hour,:] = Data[Locs]
                        
                        ifname = pars['IndexDir'] + '/SFI/Hourly/' + mm + '-' + dd + '/' + hh + '_diffuse_NoVeg.tif'
                        ofname = tmp_dir.name + '/tmp_index.tif'
                        if pars['Verbose']:
                            print('Reading ' + ifname + ' for ' + TileName)
                        cmd = 'gdalwarp -overwrite -te ' + te + ' -tr ' + tr + ' "' + ifname + '" "' + ofname + '"'
                        exec_cmd(cmd, pars['Verbose'])
                        Data = ReadRaster(ofname, pars['Verbose'])
                        Data[np.isnan(Data)] = 0
                        OutVars['SFI_Diffuse_NoVeg'][d*24+hour,:] = Data[Locs]
                    
            if os.path.exists(pars['IndexDir'] + '/WindIndex/' + yyyy + '/' + mm + '/' + dd + '_withVeg.tif') and pars['UseWindModel']:
            
                ifname = pars['IndexDir'] + '/WindIndex/' + yyyy + '/' + mm + '/' + dd + '_withVeg.tif'
                ofname = tmp_dir.name + '/tmp_index.tif'
                if pars['Verbose']:
                    print('Reading ' + ifname + ' for ' + TileName)
                cmd = 'gdalwarp -overwrite -te ' + te + ' -tr ' + tr + ' "' + ifname + '" "' + ofname + '"'
                exec_cmd(cmd, pars['Verbose'])
                Data = ReadRaster(ofname, pars['Verbose'])
                Data[np.isnan(Data)] = 1
                if pars['ModelTimestep'] == 1:
                    OutVars['SnowfallIndex_WithVeg'][d,:] = Data[Locs]
                elif pars['ModelTimestep'] == 0:
                    for i in range(24):
                        OutVars['SnowfallIndex_WithVeg'][d*24+i,:] = Data[Locs]
                
                ifname = pars['IndexDir'] + '/WindIndex/' + yyyy + '/' + mm + '/' + dd + '_noVeg.tif'
                ofname = tmp_dir.name + '/tmp_index.tif'
                if pars['Verbose']:
                    print('Reading ' + ifname + ' for ' + TileName)
                cmd = 'gdalwarp -overwrite -te ' + te + ' -tr ' + tr + ' "' + ifname + '" "' + ofname + '"'
                exec_cmd(cmd, pars['Verbose'])
                Data = ReadRaster(ofname, pars['Verbose'])
                Data[np.isnan(Data)] = 1
                if pars['ModelTimestep'] == 1:
                    OutVars['SnowfallIndex_NoVeg'][d,:] = Data[Locs]
                elif pars['ModelTimestep'] == 0:
                    for i in range(24):
                        OutVars['SnowfallIndex_NoVeg'][d*24+i,:] = Data[Locs]
                    
            d = d+1
            
        if pars['ModelTimestep'] == 1:
            OutVars['LWI'] = multiInterp(OutVars['LWI'])
            OutVars['SFI_Direct_UnderCanopy'] = multiInterp(OutVars['SFI_Direct_UnderCanopy'])
            OutVars['SFI_Diffuse_UnderCanopy'] = multiInterp(OutVars['SFI_Diffuse_UnderCanopy'])
            OutVars['SFI_Direct_NoVeg'] = multiInterp(OutVars['SFI_Direct_NoVeg'])
            OutVars['SFI_Diffuse_NoVeg'] = multiInterp(OutVars['SFI_Diffuse_NoVeg'])
            if pars['UseWindModel']:
                OutVars['SnowfallIndex_WithVeg'] = multiInterp(OutVars['SnowfallIndex_WithVeg'])
                OutVars['SnowfallIndex_NoVeg'] = multiInterp(OutVars['SnowfallIndex_NoVeg'])
            else:
                OutVars['SnowfallIndex_WithVeg'][:] = 1
                OutVars['SnowfallIndex_NoVeg'][:] = 1
                
            if np.isnan(OutVars['SnowfallIndex_WithVeg'][0,0]):
                OutVars['SnowfallIndex_WithVeg'][:] = 1
                OutVars['SnowfallIndex_NoVeg'][:] = 1
                
        elif pars['ModelTimestep'] == 0:
            for i in range(24):
                locs = np.arange(i,nt,24)
                OutVars['LWI'][locs,:] = multiInterp(OutVars['LWI'][locs,:])
                OutVars['SFI_Direct_UnderCanopy'][locs,:] = multiInterp(OutVars['SFI_Direct_UnderCanopy'][locs,:])
                OutVars['SFI_Diffuse_UnderCanopy'][locs,:] = multiInterp(OutVars['SFI_Diffuse_UnderCanopy'][locs,:])
                OutVars['SFI_Direct_NoVeg'][locs,:] = multiInterp(OutVars['SFI_Direct_NoVeg'][locs,:])
                OutVars['SFI_Diffuse_NoVeg'][locs,:] = multiInterp(OutVars['SFI_Diffuse_NoVeg'][locs,:])
                if pars['UseWindModel']:
                    OutVars['SnowfallIndex_WithVeg'][locs,:] = multiInterp(OutVars['SnowfallIndex_WithVeg'][locs,:])
                    OutVars['SnowfallIndex_NoVeg'][locs,:] = multiInterp(OutVars['SnowfallIndex_NoVeg'][locs,:])
                else:
                    OutVars['SnowfallIndex_WithVeg'][:] = 1
                    OutVars['SnowfallIndex_NoVeg'][:] = 1
            
            if np.isnan(OutVars['SnowfallIndex_WithVeg'][0,0]):
                OutVars['SnowfallIndex_WithVeg'][:] = 1
                OutVars['SnowfallIndex_NoVeg'][:] = 1
        
        # from matplotlib import pyplot as plt
        # plt.plot(OutVars['SFI_Direct_NoVeg'][:,0])
        # plt.show()
        # plt.plot(OutVars['SnowfallIndex_NoVeg'][:,0])
        # plt.show()
        # sys.exit()
        
        print('Writing ' + FName)
          
        if not os.path.exists(os.path.dirname(FName)):
            os.makedirs(os.path.dirname(FName))
            
        if os.path.exists(FName):
            os.remove(FName)
            
        with nc4.Dataset(FName, 'w' , format='NETCDF4_CLASSIC') as ds:
        
            # Initialize the dimensions of the dataset
            dim_time = ds.createDimension('time', nt)
            dim_ndata = ds.createDimension('X', nd)
            
            # Ready the LAI data field
            lai_nc = ds.createVariable('LAI', np.float32, ('X'), zlib=True, least_significant_digit=pars['least_significant_digit'])
            lai_nc.standard_name = ['Leaf Area Index']
            lai_nc.units = ['m']
            
            # Ready the Latitude data field
            lat_nc = ds.createVariable('Lat', np.float32, ('X'), zlib=True, least_significant_digit=pars['least_significant_digit'])
            lat_nc.standard_name = ['Latitude']
            lat_nc.units = ['degrees']
            
            # Ready the Elevation data field
            elev_nc = ds.createVariable('Elev', np.float32, ('X'), zlib=True, least_significant_digit=pars['least_significant_digit'])
            elev_nc.standard_name = ['Elevation']
            elev_nc.units = ['m']
            
            # Ready the Skyview data field
            skyview_nc = ds.createVariable('Skyview', np.float32, ('X'), zlib=True, least_significant_digit=pars['least_significant_digit'])
            skyview_nc.standard_name = ['Skyview Factor']
            skyview_nc.units = ['-']
            
            # Ready the Longwave Index data field
            lwi_nc = ds.createVariable('LWI', np.float32, ('time','X'), zlib=True, least_significant_digit=pars['least_significant_digit'])
            lwi_nc.standard_name = ['Longwave Index']
            lwi_nc.units = ['-']
            
            # Ready the Under Canopy Solar Forcing Index For Direct Solar data field
            sfi_direct_undercanopy_nc = ds.createVariable('SFI_Direct_UnderCanopy', np.float32, ('time','X'), zlib=True, least_significant_digit=pars['least_significant_digit'])
            sfi_direct_undercanopy_nc.standard_name = ['Under Canopy Solar Forcing Index For Direct Solar']
            sfi_direct_undercanopy_nc.units = ['-']
            
            # Ready the Under Canopy Solar Forcing Index For Diffuse Solar data field
            sfi_diffuse_undercanopy_nc = ds.createVariable('SFI_Diffuse_UnderCanopy', np.float32, ('time','X'), zlib=True, least_significant_digit=pars['least_significant_digit'])
            sfi_diffuse_undercanopy_nc.standard_name = ['Under Canopy Solar Forcing Index For Diffuse Solar']
            sfi_diffuse_undercanopy_nc.units = ['-']
            
            # Ready the No Vegetation Solar Forcing Index For Direct Solar data field
            sfi_direct_noveg_nc = ds.createVariable('SFI_Direct_NoVeg', np.float32, ('time','X'), zlib=True, least_significant_digit=pars['least_significant_digit'])
            sfi_direct_noveg_nc.standard_name = ['No Vegetation Solar Forcing Index For Direct Solar']
            sfi_direct_noveg_nc.units = ['-']
            
            # Ready the No Vegetation Solar Forcing Index For Diffuse Solar data field
            sfi_diffuse_noveg_nc = ds.createVariable('SFI_Diffuse_NoVeg', np.float32, ('time','X'), zlib=True, least_significant_digit=pars['least_significant_digit'])
            sfi_diffuse_noveg_nc.standard_name = ['No Vegetation Solar Forcing Index For Diffuse Solar']
            sfi_diffuse_noveg_nc.units = ['-']
            
            # Ready the Wind Distributed Snowfall Index (with Vegetation)
            snowfall_index_withveg_nc = ds.createVariable('SnowfallIndex_WithVeg', np.float32, ('time','X'), zlib=True, least_significant_digit=pars['least_significant_digit'])
            snowfall_index_withveg_nc.standard_name = ['Wind Distributed Snowfall Index (with Vegetation)']
            snowfall_index_withveg_nc.units = ['-']
            
            # Ready the Wind Distributed Snowfall Index (no Vegetation)
            snowfall_index_noveg_nc = ds.createVariable('SnowfallIndex_NoVeg', np.float32, ('time','X'), zlib=True, least_significant_digit=pars['least_significant_digit'])
            snowfall_index_noveg_nc.standard_name = ['Wind Distributed Snowfall Index (no Vegetation)']
            snowfall_index_noveg_nc.units = ['-']
            
            # Fill with values
            
            elev_nc[:] = OutVars['Elev']
            lai_nc[:] = OutVars['LAI']
            lat_nc[:] = OutVars['Lat']
            skyview_nc[:] = OutVars['Skyview']
            lwi_nc[:] = OutVars['LWI']
            sfi_direct_undercanopy_nc[:] = OutVars['SFI_Direct_UnderCanopy']
            sfi_diffuse_undercanopy_nc[:] = OutVars['SFI_Diffuse_UnderCanopy']
            sfi_direct_noveg_nc[:] = OutVars['SFI_Direct_NoVeg']
            sfi_diffuse_noveg_nc[:] = OutVars['SFI_Diffuse_NoVeg']
            snowfall_index_withveg_nc[:] = OutVars['SnowfallIndex_WithVeg']
            snowfall_index_noveg_nc[:] = OutVars['SnowfallIndex_NoVeg']
            

def interp_forcing_data_tile(Tile, c, pars):

    if pars['ModelTimestep'] == 0:
        nt = ((pars['EndDate'] - pars['StartDate']).days + 1) * 24
    elif pars['ModelTimestep'] == 1:
        nt = (pars['EndDate'] - pars['StartDate']).days + 1 
        
    Locs = Tile['mask'].astype(bool)
    nd = np.sum(Locs)
    if nd > 0:
        FName = pars['ModelDir'] + '/Tile' + str(c) + '/' + 'Forcing.nc'
        rows = int(Tile['rows'])
        cols = int(Tile['cols'])

        te = str(Tile['ulx']) + ' ' + str(Tile['lry']) + ' ' + str(Tile['lrx']) + ' ' + str(Tile['uly'])
        tr = str(Tile['pixelWidth']) + ' ' + str(Tile['pixelHeight']) 
            
        interp_forcing_data('Tile ' + str(c),FName,Locs,nt,nd,te,tr,pars)


def InterpForcingData(pars):

    if pars['SimulationType'] == 0 or pars['SimulationType'] == 1:
    
        a = loadmat(pars['ModelDir'] + '/' + 'ModelInfo.mat',simplify_cells=True)
        Tiles = a['Tiles']
        
        # c = 0
        # for Tile in Tiles:
            # interp_forcing_data_tile(Tiles[0],c,pars)

        pool = multiprocessing.Pool(processes=min(pars['NProcesses'], len(Tiles)))
        pool.starmap(interp_forcing_data_tile, zip(Tiles, range(len(Tiles)), itertools.repeat(pars)))
        pool.close() 
        pool.join()
                
    elif pars['SimulationType'] == 2:
    
        a = loadmat(pars['ModelDir'] + '/' + 'ModelInfo.mat',squeeze_me=True)
        Subdomain = a['Subdomain']
        POIGrid = ReadRaster(pars['ModelDir'] + '/' + 'POIs.tif', pars['Verbose'])
        Locs = POIGrid >= 0
        
        if pars['ModelTimestep'] == 0:
            nt = ((pars['EndDate'] - pars['StartDate']).days + 1) * 24
        elif pars['ModelTimestep'] == 1:
            nt = (pars['EndDate'] - pars['StartDate']).days + 1 
                
        nd = np.sum(Locs)
        if nd > 0:
            FName = pars['ModelDir'] + '/' + 'Forcing.nc'
            rows = int(Subdomain['rows'])
            cols = int(Subdomain['cols'])
            
            te = str(Subdomain['ulx']) + ' ' + str(Subdomain['lry']) + ' ' + str(Subdomain['lrx']) + ' ' + str(Subdomain['uly'])
            tr = str(Subdomain['pixelWidth']) + ' ' + str(Subdomain['pixelHeight']) 
                
            interp_forcing_data('POIs',FName,Locs,nt,nd,te,tr,pars)
        
   
def interp_indexes_tile(Tile, c, pars):

    if pars['ModelTimestep'] == 0:
        nt = ((pars['EndDate'] - pars['StartDate']).days + 1) * 24
    elif pars['ModelTimestep'] == 1:
        nt = (pars['EndDate'] - pars['StartDate']).days + 1 
        
    Locs = Tile['mask'].astype(bool)
    nd = np.sum(Locs)
    
    if nd > 0:
        FName = pars['ModelDir'] + '/Tile' + str(c) + '/' + 'Indexes.nc'
        rows = int(Tile['rows'])
        cols = int(Tile['cols'])

        te = str(Tile['ulx']) + ' ' + str(Tile['lry']) + ' ' + str(Tile['lrx']) + ' ' + str(Tile['uly'])
        tr = str(Tile['pixelWidth']) + ' ' + str(Tile['pixelHeight']) 
            
        interp_indexes('Tile ' + str(c),FName,Locs,nt,nd,te,tr,pars)
    
    
def InterpIndexes(pars):

    if pars['SimulationType'] == 0 or pars['SimulationType'] == 1:
    
        a = loadmat(pars['ModelDir'] + '/' + 'ModelInfo.mat',simplify_cells=True)
        Tiles = a['Tiles']

        # c = 0
        # for Tile in Tiles:
            # interp_indexes_tile(Tiles[0],c,pars)
            
        pool = multiprocessing.Pool(processes=min(pars['NProcesses'], len(Tiles)))
        pool.starmap(interp_indexes_tile, zip(Tiles, range(len(Tiles)), itertools.repeat(pars)))
        pool.close() 
        pool.join()
                
    elif pars['SimulationType'] == 2:
    
        a = loadmat(pars['ModelDir'] + '/' + 'ModelInfo.mat',squeeze_me=True)
        Subdomain = a['Subdomain']
        POIGrid = ReadRaster(pars['ModelDir'] + '/' + 'POIs.tif', pars['Verbose'])
        Locs = POIGrid >= 0
        
        if pars['ModelTimestep'] == 0:
            nt = ((pars['EndDate'] - pars['StartDate']).days + 1) * 24
        elif pars['ModelTimestep'] == 1:
            nt = (pars['EndDate'] - pars['StartDate']).days + 1
                
        nd = np.sum(Locs)
        if nd > 0:
            FName = pars['ModelDir'] + '/' + 'Indexes.nc'
            rows = int(Subdomain['rows'])
            cols = int(Subdomain['cols'])
            
            te = str(Subdomain['ulx']) + ' ' + str(Subdomain['lry']) + ' ' + str(Subdomain['lrx']) + ' ' + str(Subdomain['uly'])
            tr = str(Subdomain['pixelWidth']) + ' ' + str(Subdomain['pixelHeight']) 
                
            interp_indexes('POIs',FName,Locs,nt,nd,te,tr,pars)
    

            