import sys, os
import subprocess
from osgeo import gdal, osr
from osgeo.gdalconst import *
from pyproj import Transformer
import numpy as np
from scipy import ndimage

gdal.UseExceptions()

nodataval = -9999
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

def GetSpatialData(pars):

    Files = [pars['DTM_File'], pars['VegHT_File'], pars['VegCover_File']]
    OFNames = [pars['GISDir'] + '/DTM.tif', pars['GISDir'] + '/VegHT.tif', pars['GISDir'] + '/Cover.tif']

    projwin = str(pars['NSWE'][2]) + ' ' + str(pars['NSWE'][0]) + ' ' + str(pars['NSWE'][3]) + ' ' + str(pars['NSWE'][1])
    te = str(pars['NSWE'][2]) + ' ' + str(pars['NSWE'][1]) + ' ' + str(pars['NSWE'][3]) + ' ' + str(pars['NSWE'][0])
    tr = str(pars['CellSize']) + ' ' + str(pars['CellSize'])

    c = 0
    for File in Files:

        OFName = OFNames[c]
        OFName_tmp = OFNames[c].replace('.tif', '_tmp.tif')

        if not os.path.exists(OFName) or pars['Overwrite']:
            print('Getting data from ' + File)
            
            if not os.path.exists(pars['GISDir']):
                os.makedirs(pars['GISDir'])

            if pars['UseOriginalPixels'] == False:
                if pars['Cutline_File'] == '':
                    cmd = 'gdalwarp -wo NUM_THREADS=ALL_CPUS  -multi -co "COMPRESS=DEFLATE" -co "BIGTIFF=IF_SAFER" -overwrite -t_srs "' + pars['Target_SRS'] + '" -te ' + te + ' -tr ' + tr + ' -r ' + pars['Resample'] + ' "' + File + '" "' + OFName + '"'
                else:
                    cmd = 'gdalwarp -wo NUM_THREADS=ALL_CPUS  -multi -co "COMPRESS=DEFLATE" -co "BIGTIFF=IF_SAFER" -overwrite -t_srs "' + pars['Target_SRS'] + '" -te ' + te + ' -tr ' + tr + ' -r ' + pars['Resample'] + ' -cutline "' + pars['Cutline_File'] + '" -dstnodata -9999 "' + File + '" "' + OFName + '"'
                exec_cmd(cmd, pars['Verbose'])
                    
            else:
                cmd = 'gdal_translate -co NUM_THREADS=ALL_CPUS -co "COMPRESS=DEFLATE" -co "BIGTIFF=IF_SAFER" -projwin ' + projwin + ' "' + File + '" "' + OFName + '"'
                exec_cmd(cmd, pars['Verbose'])
                    
                if not (pars['Cutline_File'] == ''):
                    os.rename(OFNames[c], OFName_tmp)
                    cmd = 'gdalwarp -wo NUM_THREADS=ALL_CPUS  -multi -co "COMPRESS=DEFLATE" -co "BIGTIFF=IF_SAFER" -overwrite -cutline "' + pars['Cutline_File'] + '" -dstnodata -9999 "' + OFName_tmp + '" "' + OFName + '"'
                    exec_cmd(cmd, pars['Verbose'])
                    os.remove(OFName_tmp)

            if pars['CreatePyramids']:
                cmd = 'gdaladdo --config COMPRESS_OVERVIEW DEFLATE --config BIGTIFF_OVERVIEW IF_SAFER -r average -ro "' + OFName + '"'
                exec_cmd(cmd, pars['Verbose'])
                        
        c = c + 1

    # Create the low resolution terrain file (for interpolation of forcing data)
    
    OFName = pars['GISDir'] + '/DTM_small.tif'
    if 'DTM_LoRes_File' in pars:
        File = pars['DTM_LoRes_File']
    else:
        File = pars['DTM_File']
    
    if not os.path.exists(OFName) or pars['Overwrite']:
    
        print('Creating low resolution terrain file')
        
        ds = gdal.Open(pars['GISDir'] + '/DTM.tif')
        ulx, xres, xskew, uly, yskew, yres  = ds.GetGeoTransform()
        lrx = ulx + (ds.RasterXSize * xres)
        lry = uly + (ds.RasterYSize * yres)
        ts_x = np.round((lrx - ulx) / pars['CellSize_LowRes'])
        ts_y = np.round((uly - lry) / pars['CellSize_LowRes'])
        srs = osr.SpatialReference()
        srs.ImportFromWkt(ds.GetProjectionRef())
        prj = srs.ExportToProj4()
        ds = None
        
        # ts = str(ts_x) + ' ' + str(ts_y)
        # cmd = 'gdalwarp -wo NUM_THREADS=ALL_CPUS  -multi -co "COMPRESS=DEFLATE" -co "BIGTIFF=IF_SAFER" -overwrite -t_srs "' + prj + '" -te ' + te + ' -ts ' + ts + ' -r bilinear "' + File + '" "' + OFName + '"'
        tr = str(pars['CellSize_LowRes']) + ' ' + str(pars['CellSize_LowRes'])
        cmd = 'gdalwarp -wo NUM_THREADS=ALL_CPUS  -multi -co "COMPRESS=DEFLATE" -co "BIGTIFF=IF_SAFER" -overwrite -t_srs "' + prj + '" -te ' + te + ' -tr ' + tr + ' -r bilinear "' + File + '" "' + OFName + '"'
        exec_cmd(cmd, pars['Verbose'])
        
    OFName = pars['GISDir'] + '/Flat.tif'
    
    if not os.path.exists(OFName) or pars['Overwrite']:
    
        print('Creating flat surface map')
        
        DTM_small = ReadRaster(pars['GISDir'] + '/DTM_small.tif', pars['Verbose'])
        Flat = np.ones(DTM_small.shape) * np.nanmean(DTM_small)
        WriteRasterMatch(Flat, OFName, pars['GISDir'] + '/DTM_small.tif', pars['CreatePyramids'], pars['Verbose'])
        

def GetSkyViewMaps(pars):

    SagaGISLoc = pars['SagaGISLoc']

    ## Create skyview factor maps (bare earth)

    DTM = ReadRaster(pars['GISDir'] + '/DTM.tif', pars['Verbose'])
    Cover = ReadRaster(pars['GISDir'] + '/Cover.tif', pars['Verbose'])
    Cover[Cover < 0] = 0
    Cover[Cover > 100] = 0
    Cover[np.isnan(Cover)] = 0
    VegHT = ReadRaster(pars['GISDir'] + '/VegHT.tif', pars['Verbose'])
    VegHT[VegHT < 0] = 0
    VegHT[np.isnan(VegHT)] = 0
            
    dem = pars['GISDir'] + '/DTM.tif'
    svf = pars['GISDir'] + '/SkyView_noVeg.tif'
    
    if not os.path.exists(svf) or pars['Overwrite']:
    
        print('Creating ' + svf)
        cmd = '"' + SagaGISLoc.replace('\\','/') + '/saga_cmd" ta_lighting 3 -DEM "' + dem + '" -SVF "' + svf + '" -RADIUS ' + str(pars['RADIUS']) + ' -METHOD ' + str(pars['METHOD']) + ' -DLEVEL ' + str(pars['DLEVEL']) + ' -NDIRS ' + str(pars['NDIRS'])
        exec_cmd(cmd, pars['Verbose'])
        
        Data = ReadRaster(svf, pars['Verbose'])
        nanlocs = np.isnan(DTM)
        Data[nanlocs] = nodataval
        WriteRasterMatch(Data, svf, svf, pars['CreatePyramids'], pars['Verbose'])

    ## Create skyview factor maps (with vegetation)
    
    dsm = pars['GISDir'] + '/DSM.tif'
    if not os.path.exists(dsm) or pars['Overwrite']:
        print('Creating ' + dsm)
        DSM = DTM + VegHT
        nanlocs = np.isnan(DTM)
        DSM[nanlocs] = nodataval
        WriteRasterMatch(DSM, dsm, pars['GISDir'] + '/DTM.tif', pars['CreatePyramids'], pars['Verbose'])

    
    c = 0
    for VegRange in pars['VegCoverCategories']:
    
        dsm = pars['GISDir'] + '/DSM_vcat_' + str(c) + '.tif'
        svf = pars['GISDir'] + '/SkyView_withVeg_vcat_' + str(c) + '.tif'
        
        if not os.path.exists(dsm) or pars['Overwrite']:
            print('Creating ' + dsm)

            locs = np.logical_and(Cover > VegRange[0], Cover <= VegRange[1])
            DSM = DTM + VegHT * locs.astype(float)
            nanlocs = np.isnan(DTM)
            DSM[nanlocs] = nodataval
            WriteRasterMatch(DSM, dsm, pars['GISDir'] + '/DTM.tif', pars['CreatePyramids'], pars['Verbose'])

        if not os.path.exists(svf) or pars['Overwrite']:
            print('Creating ' + svf)
            cmd = '"' + SagaGISLoc.replace('\\','/') + '/saga_cmd" ta_lighting 3 -DEM "' + dsm + '" -SVF "' + svf + '" -RADIUS ' + str(pars['RADIUS']) + ' -METHOD ' + str(pars['METHOD']) + ' -DLEVEL ' + str(pars['DLEVEL']) + ' -NDIRS ' + str(pars['NDIRS'])
            exec_cmd(cmd, pars['Verbose'])
            
            SVF = ReadRaster(svf, pars['Verbose'])
            locs = ndimage.binary_dilation(np.logical_and(Cover > VegRange[0], Cover <= VegRange[1]))
            SVF[locs] = nodataval
            nanlocs = np.isnan(DTM)
            SVF[nanlocs] = 0
            WriteRasterMatch(SVF, svf, svf, False, pars['Verbose'])
            
            cmd = '"' + SagaGISLoc.replace('\\','/') + '/saga_cmd" grid_tools 29 -GROW 1.2 -INPUT "' + svf + '" -RESULT "' + svf + '"'
            exec_cmd(cmd, pars['Verbose'])
            
            Data = ReadRaster(svf, pars['Verbose'])
            nanlocs = np.isnan(DTM)
            Data[nanlocs] = nodataval
            WriteRasterMatch(Data, svf, svf, pars['CreatePyramids'], pars['Verbose'])
            
        c = c+1
            
            
def GetPotentialSolarMaps(pars):

    SagaGISLoc = pars['SagaGISLoc']

    DTM = ReadRaster(pars['GISDir'] + '/DTM.tif', pars['Verbose'])
    Cover = ReadRaster(pars['GISDir'] + '/Cover.tif', pars['Verbose'])
    Cover[Cover < 0] = 0
    Cover[Cover > 100] = 0
    Cover[np.isnan(Cover)] = 0
    VegHT = ReadRaster(pars['GISDir'] + '/VegHT.tif', pars['Verbose'])
    VegHT[VegHT < 0] = 0
    VegHT[np.isnan(VegHT)] = 0
    
    if pars['ConstantLatitude']:

        src = gdal.Open(pars['GISDir'] + '/DTM.tif')
        ulx, xres, xskew, uly, yskew, yres  = src.GetGeoTransform()
        lrx = ulx + (src.RasterXSize * xres)
        lry = uly + (src.RasterYSize * yres)
        y = (uly + lry) / 2
        x = (ulx + lrx) / 2
        srs = osr.SpatialReference()
        srs.ImportFromWkt(src.GetProjectionRef())
        prj = srs.ExportToProj4()
        trans = Transformer.from_crs(prj,'epsg:4326', always_xy=True)
        (lon,lat) = trans.transform(x,y)
        LocationString = '-LOCATION 0 -LATITUDE ' + str(lat)
    else:
        LocationString = '-LOCATION 1'
    
    ## Create Potential Solar Maps

    for Month in pars['Solar_Months']:
        for Day in pars['Solar_Days']:
            
            mm = str(Month)
            if len(mm) < 2:
                mm = '0' + mm
            dd = str(Day)
            if len(dd) < 2:
                dd = '0' + dd
                
            ## Create terrain only potential solar maps
            
            GRD_DEM = pars['GISDir'] + '/DTM.tif'
            GRD_SVF = pars['GISDir'] + '/SkyView_noVeg.tif'
            
            if pars['Solar_output_step'] == 1:
                GRD_DIRECT = pars['GISDir'] + '/PotentialSolar/Daily/' + mm + '-' + dd + '_direct_noVeg.tif'
                GRD_DIFFUS = pars['GISDir'] + '/PotentialSolar/Daily/' + mm + '-' + dd + '_diffuse_noVeg.tif'
                
                if not os.path.exists(pars['GISDir'] + '/PotentialSolar/Daily'):
                    os.makedirs(pars['GISDir'] + '/PotentialSolar/Daily')
                
                if not os.path.exists(GRD_DIRECT) or not os.path.exists(GRD_DIFFUS) or pars['Overwrite']:
                    print('Creating ' + GRD_DIRECT + ' and ' + GRD_DIFFUS)
                    cmd = '"' + SagaGISLoc.replace('\\','/') + '/saga_cmd" ta_lighting 2 -GRD_DEM "' + GRD_DEM + '" -GRD_SVF "' + GRD_SVF + '" -GRD_DIRECT "' + GRD_DIRECT + '" -GRD_DIFFUS "' + GRD_DIFFUS + '" -SOLARCONST ' + str(pars['SOLARCONST']) + ' -LOCALSVF ' + str(pars['LOCALSVF']) + ' -UNITS 1 -SHADOW ' + str(pars['SHADOW']) + ' ' + LocationString + ' -PERIOD 1 -HOUR_RANGE_MIN 0  -HOUR_RANGE_MAX 24 -HOUR_STEP ' + str(pars['Solar_hour_step']) + ' -DAY ' + '2000-' + mm + '-' + str(Day+1) + ' -METHOD ' + str(pars['METHOD'])  + ' -ATMOSPHERE ' + str(pars['ATMOSPHERE'])  + ' -PRESSURE ' + str(pars['PRESSURE'])  + ' -WATER ' + str(pars['WATER'])  + ' -DUST ' + str(pars['DUST'])  + ' -LUMPED ' + str(pars['LUMPED'])
                    exec_cmd(cmd, pars['Verbose'])
                    
                    Data = ReadRaster(GRD_DIRECT, pars['Verbose'])
                    nanlocs = np.isnan(DTM)
                    Data[nanlocs] = nodataval
                    WriteRasterMatch(Data, GRD_DIRECT, GRD_DIRECT, pars['CreatePyramids'], pars['Verbose'])
                    
                    Data = ReadRaster(GRD_DIFFUS, pars['Verbose'])
                    nanlocs = np.isnan(DTM)
                    Data[nanlocs] = nodataval
                    WriteRasterMatch(Data, GRD_DIFFUS, GRD_DIFFUS, pars['CreatePyramids'], pars['Verbose'])
                
            elif pars['Solar_output_step'] == 0:
                for hour in range(24):
                    hh = str(hour)
                    if len(hh) < 2:
                        hh = '0' + hh
                        
                    GRD_DIRECT = pars['GISDir'] + '/PotentialSolar/Hourly/' + mm + '-' + dd + '/' + hh + '_direct_noVeg.tif'
                    GRD_DIFFUS = pars['GISDir'] + '/PotentialSolar/Hourly/' + mm + '-' + dd + '/' + hh + '_diffuse_noVeg.tif'
        
                    if not os.path.exists(pars['GISDir'] + '/PotentialSolar/Hourly/' + mm + '-' + dd):
                        os.makedirs(pars['GISDir'] + '/PotentialSolar/Hourly/' + mm + '-' + dd)
                    
                    if not os.path.exists(GRD_DIRECT) or not os.path.exists(GRD_DIFFUS) or pars['Overwrite']:
                        print('Creating ' + GRD_DIRECT + ' and ' + GRD_DIFFUS)
                        cmd = '"' + SagaGISLoc.replace('\\','/') + '/saga_cmd" ta_lighting 2 -GRD_DEM "' + GRD_DEM + '" -GRD_SVF "' + GRD_SVF + '" -GRD_DIRECT "' + GRD_DIRECT + '" -GRD_DIFFUS "' + GRD_DIFFUS + '" -SOLARCONST ' + str(pars['SOLARCONST']) + ' -LOCALSVF ' + str(pars['LOCALSVF']) + ' -UNITS 1 -SHADOW ' + str(pars['SHADOW']) + ' ' + LocationString + ' -PERIOD 1 -HOUR_RANGE_MIN ' + str(hour) + ' -HOUR_RANGE_MAX ' + str(hour+1) + ' -HOUR_STEP ' + str(pars['Solar_hour_step']) + ' -DAY ' + '2000-' + mm + '-' + str(Day+1) + ' -METHOD ' + str(pars['METHOD'])  + ' -ATMOSPHERE ' + str(pars['ATMOSPHERE'])  + ' -PRESSURE ' + str(pars['PRESSURE'])  + ' -WATER ' + str(pars['WATER'])  + ' -DUST ' + str(pars['DUST'])  + ' -LUMPED ' + str(pars['LUMPED'])
                        exec_cmd(cmd, pars['Verbose'])
                        
                        Data = ReadRaster(GRD_DIRECT, pars['Verbose'])
                        nanlocs = np.isnan(DTM)
                        Data[nanlocs] = nodataval
                        WriteRasterMatch(Data, GRD_DIRECT, GRD_DIRECT, pars['CreatePyramids'], pars['Verbose'])
                        
                        Data = ReadRaster(GRD_DIFFUS, pars['Verbose'])
                        nanlocs = np.isnan(DTM)
                        Data[nanlocs] = nodataval
                        WriteRasterMatch(Data, GRD_DIFFUS, GRD_DIFFUS, pars['CreatePyramids'], pars['Verbose'])

            ## Create potential solar maps that include vegetation
            
            if pars['Solar_output_step'] == 1:
                c = 0
                
                GRD_DEM = pars['GISDir'] + '/DSM.tif'
                GRD_DIRECT = pars['GISDir'] + '/PotentialSolar/Daily/' + mm + '-' + dd + '_direct_top.tif'
                
                if not os.path.exists(pars['GISDir'] + '/PotentialSolar/Daily'):
                    os.makedirs(pars['GISDir'] + '/PotentialSolar/Daily')
                    
                if not os.path.exists(GRD_DIRECT) or pars['Overwrite']:
                    print('Creating ' + GRD_DIRECT)
                    cmd = '"' + SagaGISLoc.replace('\\','/') + '/saga_cmd" ta_lighting 2 -GRD_DEM "' + GRD_DEM + '" -GRD_SVF "' + GRD_SVF + '" -GRD_DIRECT "' + GRD_DIRECT + '" -SOLARCONST ' + str(pars['SOLARCONST']) + ' -LOCALSVF ' + str(pars['LOCALSVF']) + ' -UNITS 1 -SHADOW ' + str(pars['SHADOW']) + ' ' + LocationString + ' -PERIOD 1 -HOUR_RANGE_MIN 0 -HOUR_RANGE_MAX 24 -HOUR_STEP ' + str(pars['Solar_hour_step']) + ' -DAY ' + '2000-' + mm + '-' + str(Day+1) + ' -METHOD ' + str(pars['METHOD'])  + ' -ATMOSPHERE ' + str(pars['ATMOSPHERE'])  + ' -PRESSURE ' + str(pars['PRESSURE'])  + ' -WATER ' + str(pars['WATER'])  + ' -DUST ' + str(pars['DUST'])  + ' -LUMPED ' + str(pars['LUMPED'])
                    exec_cmd(cmd, pars['Verbose'])
                        
                    Data = ReadRaster(GRD_DIRECT, pars['Verbose'])
                    nanlocs = np.isnan(DTM)
                    Data[nanlocs] = nodataval
                    WriteRasterMatch(Data, GRD_DIRECT, GRD_DIRECT, pars['CreatePyramids'], pars['Verbose'])
                
                for VegRange in pars['VegCoverCategories']:
                
                    GRD_DEM = pars['GISDir'] + '/DSM_vcat_' + str(c) + '.tif'
                    GRD_SVF = pars['GISDir'] + '/SkyView_withVeg_vcat_' + str(c) + '.tif'
                    GRD_DIRECT = pars['GISDir'] + '/PotentialSolar/Daily/' + mm + '-' + dd + '_direct_withVeg_vcat_' + str(c) + '.tif'
                    GRD_DIFFUS = pars['GISDir'] + '/PotentialSolar/Daily/' + mm + '-' + dd + '_diffuse_withVeg_vcat_' + str(c) + '.tif'
                    
                    if not os.path.exists(pars['GISDir'] + '/PotentialSolar/Daily'):
                        os.makedirs(pars['GISDir'] + '/PotentialSolar/Daily')
                        
                    if not os.path.exists(GRD_DIRECT) or not os.path.exists(GRD_DIFFUS) or pars['Overwrite']:
                        print('Creating ' + GRD_DIRECT + ' and ' + GRD_DIFFUS)
                        cmd = '"' + SagaGISLoc.replace('\\','/') + '/saga_cmd" ta_lighting 2 -GRD_DEM "' + GRD_DEM + '" -GRD_SVF "' + GRD_SVF + '" -GRD_DIRECT "' + GRD_DIRECT + '" -GRD_DIFFUS "' + GRD_DIFFUS + '" -SOLARCONST ' + str(pars['SOLARCONST']) + ' -LOCALSVF ' + str(pars['LOCALSVF']) + ' -UNITS 1 -SHADOW ' + str(pars['SHADOW']) + ' ' + LocationString + ' -PERIOD 1 -HOUR_RANGE_MIN 0 -HOUR_RANGE_MAX 24 -HOUR_STEP ' + str(pars['Solar_hour_step']) + ' -DAY ' + '2000-' + mm + '-' + str(Day+1) + ' -METHOD ' + str(pars['METHOD'])  + ' -ATMOSPHERE ' + str(pars['ATMOSPHERE'])  + ' -PRESSURE ' + str(pars['PRESSURE'])  + ' -WATER ' + str(pars['WATER'])  + ' -DUST ' + str(pars['DUST'])  + ' -LUMPED ' + str(pars['LUMPED'])
                        exec_cmd(cmd, pars['Verbose'])
                       
                        PSolar = ReadRaster(GRD_DIFFUS, pars['Verbose'])
                        locs = ndimage.binary_dilation(np.logical_and(Cover > VegRange[0], Cover <= VegRange[1]))
                        PSolar[locs] = nodataval
                        nanlocs = np.isnan(DTM)
                        PSolar[nanlocs] = 0
                        
                        WriteRasterMatch(PSolar, GRD_DIFFUS, GRD_DIFFUS, False, pars['Verbose'])
            
                        cmd = '"' + SagaGISLoc.replace('\\','/') + '/saga_cmd" grid_tools 29 -GROW 1.2 -INPUT "' + GRD_DIFFUS + '" -RESULT "' + GRD_DIFFUS + '"'
                        exec_cmd(cmd, pars['Verbose'])
                        
                        Data = ReadRaster(GRD_DIRECT, pars['Verbose'])
                        nanlocs = np.isnan(DTM)
                        Data[nanlocs] = nodataval
                        WriteRasterMatch(Data, GRD_DIRECT, GRD_DIRECT, pars['CreatePyramids'], pars['Verbose'])
                        
                        Data = ReadRaster(GRD_DIFFUS, pars['Verbose'])
                        nanlocs = np.isnan(DTM)
                        Data[nanlocs] = nodataval
                        WriteRasterMatch(Data, GRD_DIFFUS, GRD_DIFFUS, pars['CreatePyramids'], pars['Verbose'])
                        
                    c = c+1
                    
            elif pars['Solar_output_step'] == 0:
                for hour in range(24):
                    hh = str(hour)
                    if len(hh) < 2:
                        hh = '0' + hh

                    c = 0
                    
                    GRD_DEM = pars['GISDir'] + '/DSM.tif'
                    GRD_DIRECT = pars['GISDir'] + '/PotentialSolar/Hourly/' + mm + '-' + dd + '/' + hh + '_direct_top.tif'
                    
                    if not os.path.exists(pars['GISDir'] + '/PotentialSolar/Hourly/' + mm + '-' + dd):
                        os.makedirs(pars['GISDir'] + '/PotentialSolar/Hourly/' + mm + '-' + dd)
                        
                    if not os.path.exists(GRD_DIRECT) or pars['Overwrite']:
                        print('Creating ' + GRD_DIRECT)
                        cmd = '"' + SagaGISLoc.replace('\\','/') + '/saga_cmd" ta_lighting 2 -GRD_DEM "' + GRD_DEM + '" -GRD_SVF "' + GRD_SVF + '" -GRD_DIRECT "' + GRD_DIRECT + '" -GRD_DIFFUS "' + GRD_DIFFUS + '" -SOLARCONST ' + str(pars['SOLARCONST']) + ' -LOCALSVF ' + str(pars['LOCALSVF']) + ' -UNITS 1 -SHADOW ' + str(pars['SHADOW']) + ' ' + LocationString + ' -PERIOD 1 -HOUR_RANGE_MIN ' + str(hour) + ' -HOUR_RANGE_MAX ' + str(hour+1) + ' -HOUR_STEP ' + str(pars['Solar_hour_step']) + ' -DAY ' + '2000-' + mm + '-' + str(Day+1) + ' -METHOD ' + str(pars['METHOD'])  + ' -ATMOSPHERE ' + str(pars['ATMOSPHERE'])  + ' -PRESSURE ' + str(pars['PRESSURE'])  + ' -WATER ' + str(pars['WATER'])  + ' -DUST ' + str(pars['DUST'])  + ' -LUMPED ' + str(pars['LUMPED'])
                        exec_cmd(cmd, pars['Verbose'])
                            
                        Data = ReadRaster(GRD_DIRECT, pars['Verbose'])
                        nanlocs = np.isnan(DTM)
                        Data[nanlocs] = nodataval
                        WriteRasterMatch(Data, GRD_DIRECT, GRD_DIRECT, pars['CreatePyramids'], pars['Verbose'])
                    
                    
                    for VegRange in pars['VegCoverCategories']:

                        GRD_DEM = pars['GISDir'] + '/DSM_vcat_' + str(c) + '.tif'
                        GRD_SVF = pars['GISDir'] + '/SkyView_withVeg_vcat_' + str(c) + '.tif'    
                        GRD_DIRECT = pars['GISDir'] + '/PotentialSolar/Hourly/' + mm + '-' + dd + '/' + hh + '_direct_withVeg_vcat_' + str(c) + '.tif'
                        GRD_DIFFUS = pars['GISDir'] + '/PotentialSolar/Hourly/' + mm + '-' + dd + '/' + hh + '_diffuse_withVeg_vcat_' + str(c) + '.tif'

                        if not os.path.exists(pars['GISDir'] + '/PotentialSolar/Hourly/' + mm + '-' + dd):
                            os.makedirs(pars['GISDir'] + '/PotentialSolar/Hourly/' + mm + '-' + dd)

                        if not os.path.exists(GRD_DIRECT) or not os.path.exists(GRD_DIFFUS) or pars['Overwrite']:
                            print('Creating ' + GRD_DIRECT + ' and ' + GRD_DIFFUS)
                            cmd = '"' + SagaGISLoc.replace('\\','/') + '/saga_cmd" ta_lighting 2 -GRD_DEM "' + GRD_DEM + '" -GRD_SVF "' + GRD_SVF + '" -GRD_DIRECT "' + GRD_DIRECT + '" -GRD_DIFFUS "' + GRD_DIFFUS + '" -SOLARCONST ' + str(pars['SOLARCONST']) + ' -LOCALSVF ' + str(pars['LOCALSVF']) + ' -UNITS 1 -SHADOW ' + str(pars['SHADOW']) + ' ' + LocationString + ' -PERIOD 1 -HOUR_RANGE_MIN ' + str(hour) + ' -HOUR_RANGE_MAX ' + str(hour+1) + ' -HOUR_STEP ' + str(pars['Solar_hour_step']) + ' -DAY ' + '2000-' + mm + '-' + str(Day+1) + ' -METHOD ' + str(pars['METHOD'])  + ' -ATMOSPHERE ' + str(pars['ATMOSPHERE'])  + ' -PRESSURE ' + str(pars['PRESSURE'])  + ' -WATER ' + str(pars['WATER'])  + ' -DUST ' + str(pars['DUST'])  + ' -LUMPED ' + str(pars['LUMPED'])
                            exec_cmd(cmd, pars['Verbose'])
                            
                            PSolar = ReadRaster(GRD_DIFFUS, pars['Verbose'])
                            # PSolar[VegHT >2] = nodataval
                            locs = ndimage.binary_dilation(np.logical_and(Cover > VegRange[0], Cover <= VegRange[1]))
                            PSolar[locs] = nodataval
                            nanlocs = np.isnan(DTM)
                            PSolar[nanlocs] = 0

                            WriteRasterMatch(PSolar, GRD_DIFFUS, GRD_DIFFUS, False, pars['Verbose'])

                            cmd = '"' + SagaGISLoc.replace('\\','/') + '/saga_cmd" grid_tools 29 -GROW 1.2 -INPUT "' + GRD_DIFFUS + '" -RESULT "' + GRD_DIFFUS + '"'
                            exec_cmd(cmd, pars['Verbose'])
                            
                            Data = ReadRaster(GRD_DIRECT, pars['Verbose'])
                            nanlocs = np.isnan(DTM)
                            Data[nanlocs] = nodataval
                            WriteRasterMatch(Data, GRD_DIRECT, GRD_DIRECT, pars['CreatePyramids'], pars['Verbose'])
                            
                            Data = ReadRaster(GRD_DIFFUS, pars['Verbose'])
                            nanlocs = np.isnan(DTM)
                            Data[nanlocs] = nodataval
                            WriteRasterMatch(Data, GRD_DIFFUS, GRD_DIFFUS, pars['CreatePyramids'], pars['Verbose'])

                        c = c+1

            ## Create flat surface potential solar maps
            
            GRD_DEM = pars['GISDir'] + '/Flat.tif'
            
            if pars['Solar_output_step'] == 1:

                GRD_DIRECT = pars['GISDir'] + '/PotentialSolar/Daily/' + mm + '-' + dd + '_direct_flat.tif'
                GRD_DIFFUS = pars['GISDir'] + '/PotentialSolar/Daily/' + mm + '-' + dd + '_diffuse_flat.tif'
                
                if not os.path.exists(pars['GISDir'] + '/PotentialSolar/Daily'):
                    os.makedirs(pars['GISDir'] + '/PotentialSolar/Daily')
                            
                if not os.path.exists(GRD_DIRECT) or not os.path.exists(GRD_DIFFUS) or pars['Overwrite']:
                    print('Creating ' + GRD_DIRECT + ' and ' + GRD_DIFFUS)
                    cmd = '"' + SagaGISLoc.replace('\\','/') + '/saga_cmd" ta_lighting 2 -GRD_DEM "' + GRD_DEM + '" -GRD_DIRECT "' + GRD_DIRECT + '" -GRD_DIFFUS "' + GRD_DIFFUS + '" -SOLARCONST ' + str(pars['SOLARCONST']) + ' -LOCALSVF 0 -UNITS 1 -SHADOW ' + str(pars['SHADOW']) + ' ' + LocationString + ' -PERIOD 1 -HOUR_RANGE_MIN 0 -HOUR_RANGE_MAX 24 -HOUR_STEP ' + str(pars['Solar_hour_step']) + ' -DAY ' + '2000-' + mm + '-' + str(Day+1) + ' -METHOD ' + str(pars['METHOD'])  + ' -ATMOSPHERE ' + str(pars['ATMOSPHERE'])  + ' -PRESSURE ' + str(pars['PRESSURE'])  + ' -WATER ' + str(pars['WATER'])  + ' -DUST ' + str(pars['DUST'])  + ' -LUMPED ' + str(pars['LUMPED'])
                    exec_cmd(cmd, pars['Verbose'])
                        
            elif pars['Solar_output_step'] == 0:
                for hour in range(24):
                    hh = str(hour)
                    if len(hh) < 2:
                        hh = '0' + hh
                        
                    GRD_DIRECT = pars['GISDir'] + '/PotentialSolar/Hourly/' + mm + '-' + dd + '/' + hh + '_direct_flat.tif'
                    GRD_DIFFUS = pars['GISDir'] + '/PotentialSolar/Hourly/' + mm + '-' + dd + '/' + hh + '_diffuse_flat.tif'
        
                    if not os.path.exists(pars['GISDir'] + '/PotentialSolar/Hourly/' + mm + '-' + dd):
                        os.makedirs(pars['GISDir'] + '/PotentialSolar/Hourly/' + mm + '-' + dd)
                        
                    if not os.path.exists(GRD_DIRECT) or not os.path.exists(GRD_DIFFUS) or pars['Overwrite']:
                        print('Creating ' + GRD_DIRECT + ' and ' + GRD_DIFFUS)
                        cmd = '"' + SagaGISLoc.replace('\\','/') + '/saga_cmd" ta_lighting 2 -GRD_DEM "' + GRD_DEM + '" -GRD_DIRECT "' + GRD_DIRECT + '" -GRD_DIFFUS "' + GRD_DIFFUS + '" -SOLARCONST ' + str(pars['SOLARCONST']) + ' -LOCALSVF 0 -UNITS 1 -SHADOW ' + str(pars['SHADOW']) + ' ' + LocationString + ' -PERIOD 1 -HOUR_RANGE_MIN ' + str(hour) + ' -HOUR_RANGE_MAX ' + str(hour+1) + ' -HOUR_STEP ' + str(pars['Solar_hour_step']) + ' -DAY ' + '2000-' + mm + '-' + str(Day+1) + ' -METHOD ' + str(pars['METHOD'])  + ' -ATMOSPHERE ' + str(pars['ATMOSPHERE'])  + ' -PRESSURE ' + str(pars['PRESSURE'])  + ' -WATER ' + str(pars['WATER'])  + ' -DUST ' + str(pars['DUST'])  + ' -LUMPED ' + str(pars['LUMPED'])
                        exec_cmd(cmd, pars['Verbose'])


def GetWindIndexMaps(pars):
    
    SagaGISLoc = pars['SagaGISLoc']
    
    DTM = ReadRaster(pars['GISDir'] + '/DTM.tif', pars['Verbose'])
    Cover = ReadRaster(pars['GISDir'] + '/Cover.tif', pars['Verbose'])
    Cover[Cover < 0] = 0
    Cover[Cover > 100] = 0
    Cover[np.isnan(Cover)] = 0
    VegHT = ReadRaster(pars['GISDir'] + '/VegHT.tif', pars['Verbose'])
    VegHT[VegHT < 0] = 0
    VegHT[np.isnan(VegHT)] = 0
    
    if not os.path.exists(pars['GISDir'] + '/WindEffect/'):
        os.makedirs(pars['GISDir'] + '/WindEffect/')
                            
    for WindDir in pars['WindDirs']:
    
        wd = str(WindDir)
        if len(wd) < 2:
            wd = '0' + wd
    
        DEM = pars['GISDir'] + '/DTM.tif'
        EFFECT = pars['GISDir'] + '/WindEffect/' + wd + '_noVeg.tif'
        
        if not os.path.exists(EFFECT) or pars['Overwrite']:
            print('Creating ' + EFFECT)

            if pars['WindEffectModel'] == 0:
                cmd = '"' + SagaGISLoc.replace('\\','/') + '/saga_cmd" ta_morphometry 15 -DEM "' + DEM + '" -EFFECT "' + EFFECT + '" -DIR_UNITS 1 -MAXDIST ' + str(pars['MAXDIST']) + ' -DIR_CONST ' + str(WindDir+180) + ' -OLDVER ' + str(pars['OLDVER']) + ' -ACCEL ' + str(pars['ACCEL']) + ' -PYRAMIDS ' + str(pars['PYRAMIDS'])
            elif pars['WindEffectModel'] == 1:
                cmd = '"' + SagaGISLoc.replace('\\','/') + '/saga_cmd" ta_morphometry 29 -ELEVATION "' + DEM + '" -SHELTER "' + EFFECT + '" -DIRECTION ' + str(WindDir) + ' -TOLERANCE ' + str(pars['TOLERANCE']) + ' -DISTANCE ' + str(pars['DISTANCE']) + ' -QUANTILE ' + str(pars['QUANTILE']) + ' -NEGATIVES ' + str(pars['NEGATIVES']) + ' -METHOD ' + str(pars['METHOD'])
            exec_cmd(cmd, pars['Verbose'])
            
            Data = ReadRaster(EFFECT, pars['Verbose'])
            nanlocs = np.isnan(DTM)
            Data[nanlocs] = nodataval
            if pars['WindEffectModel'] == 1:
                Data = Data / np.nanmean(Data)
            WriteRasterMatch(Data, EFFECT, EFFECT, pars['CreatePyramids'], pars['Verbose'])
        
        c = 0
        for VegRange in pars['VegCoverCategories']:
            EFFECT = pars['GISDir'] + '/WindEffect/' + wd + '_withVeg_vcat_' + str(c) + '.tif'    
            DSM = pars['GISDir'] + '/DSM_vcat_' + str(c) + '.tif'
            
            if not os.path.exists(EFFECT) or pars['Overwrite']:
                print('Creating ' + EFFECT)
                if pars['WindEffectModel'] == 0:
                    cmd = '"' + SagaGISLoc.replace('\\','/') + '/saga_cmd" ta_morphometry 15 -DEM "' + DSM + '" -EFFECT "' + EFFECT + '" -DIR_UNITS 1 -MAXDIST ' + str(pars['MAXDIST']) + ' -DIR_CONST ' + str(WindDir+180) + ' -OLDVER ' + str(pars['OLDVER']) + ' -ACCEL ' + str(pars['ACCEL']) + ' -PYRAMIDS ' + str(pars['PYRAMIDS'])
                elif pars['WindEffectModel'] == 1:
                    cmd = '"' + SagaGISLoc.replace('\\','/') + '/saga_cmd" ta_morphometry 29 -ELEVATION "' + DSM + '" -SHELTER "' + EFFECT + '" -DIRECTION ' + str(WindDir) + ' -TOLERANCE ' + str(pars['TOLERANCE']) + ' -DISTANCE ' + str(pars['DISTANCE']) + ' -QUANTILE ' + str(pars['QUANTILE']) + ' -NEGATIVES ' + str(pars['NEGATIVES']) + ' -METHOD ' + str(pars['METHOD'])
                exec_cmd(cmd, pars['Verbose'])
                
                WindEffect = ReadRaster(EFFECT, pars['Verbose'])
                # WindEffect[VegHT >2] = nodataval
                locs = ndimage.binary_dilation(np.logical_and(Cover > VegRange[0], Cover <= VegRange[1]))
                WindEffect[locs] = nodataval
                nanlocs = np.isnan(DTM)
                WindEffect[nanlocs] = 0
                WriteRasterMatch(WindEffect, EFFECT, EFFECT, False, pars['Verbose'])

                cmd = '"' + SagaGISLoc.replace('\\','/') + '/saga_cmd" grid_tools 29 -GROW 1.2 -INPUT "' + EFFECT + '" -RESULT "' + EFFECT + '"'
                exec_cmd(cmd, pars['Verbose'])
                  
                WindEffect = ReadRaster(EFFECT, pars['Verbose'])
                nanlocs = np.isnan(DTM)
                WindEffect[nanlocs] = nodataval
                if pars['WindEffectModel'] == 1:
                    Data = Data / np.nanmean(Data)
                WriteRasterMatch(WindEffect, EFFECT, EFFECT, pars['CreatePyramids'], pars['Verbose'])
                
            c = c+1