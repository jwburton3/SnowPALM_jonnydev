import sys, os
import subprocess
from datetime import date, datetime,timedelta
from osgeo import gdal, osr
from osgeo.gdalconst import *
from pyproj import Transformer
from scipy.interpolate import griddata
from scipy.interpolate import Rbf
import netCDF4 as nc4
import numpy as np
from scipy import interpolate
import tempfile

gdal.UseExceptions()

# nodataval = 9999
DIM_i = [31, 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31]
padding_prism = 0.25
max_retries = 3

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
    # Data[Data == nodataval] = np.nan
    Data[Data == nodata_value] = np.nan
    ds = None
    
    return Data

def GetGeorefInfo(fname):
    ds = gdal.Open(fname, GA_ReadOnly)
    if ds is None:
        print ('Could not open ' + fname)
        sys.exit(1)
    transform = ds.GetGeoTransform()
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

    return(rows,cols,ulx,uly,lrx,lry,pixelWidth,pixelHeight,prj,wkt)


# def DownloadGriddedForcingData(pars):
    # # Timestamps of start and end dates
    # STStamp = date(pars['StartYear'],pars['StartMonth'],1)
    # ETStamp = date(pars['EndYear'],pars['EndMonth'],1)
    # ETStamp = last_day_of_month(ETStamp)

    # # Loop through desired dates (+ 1 extra day - because of typical NLDAS time offset)
    # for TS in daterange(STStamp, ETStamp + timedelta(days=2)):

        # doy = (TS - date(TS.year,1,1) + timedelta(days=1)).days
        # yyyy = str(TS.year)
        # mm = str(TS.month)
        # if len(mm) < 2:
            # mm = '0' + mm
        # dd = str(TS.day)
        # if len(dd) < 2:
            # dd = '0' + dd
        # ddd = str(doy);
        # if len(ddd) < 3:
            # ddd = '0' + ddd
        # if len(ddd) < 3:
            # ddd = '0' + ddd
            
        # # Download monthly PRISM PPT data on first day of month
        # if TS.day == 1 and not TS == ETStamp + timedelta(days=1):
            # # First try downloading the stable data (available further back in time than ~6 months in the past)
            # of1 = pars['PRISMForcingDir'] + '/ppt/' + yyyy + '/PRISM_ppt_stable_4kmM' + str(pars['prism_ppt_version']) + '_' + yyyy + mm + '_bil.zip';
            # url = pars['PRISMDataLoc'] + '/ppt/' + yyyy + '/PRISM_ppt_stable_4kmM' + str(pars['prism_ppt_version']) + '_' + yyyy + mm + '_bil.zip';
            # if not os.path.exists('PRISM/ppt/' + yyyy):
                # os.makedirs('PRISM/ppt/' + yyyy)
            # if not os.path.exists(of1):
                # print('Downloading ' + url + ' to ' + of1)
                # exec_cmd('wget -O "' + of1 + '" "' + url + '"', pars['Verbose']);
            # if os.path.exists(of1):
                # if os.path.getsize(of1) == 0:
                    # os.remove(of1)
            
            # # Second try downloading the provisional data (available further back in time than ~6 months in the past)
            # if not os.path.exists(of1):
                # of2 = pars['PRISMForcingDir'] + '/ppt/' + yyyy + '/PRISM_ppt_provisional_4kmM' + str(pars['prism_ppt_version']) + '_' + yyyy + mm + '_bil.zip';
                # url = pars['PRISMDataLoc'] + '/ppt/' + yyyy + '/PRISM_ppt_provisional_4kmM' + str(pars['prism_ppt_version']) + '_' + yyyy + mm + '_bil.zip';
                # if not os.path.exists('PRISM/ppt/' + yyyy):
                    # os.makedirs('PRISM/ppt/' + yyyy)
                # if not os.path.exists(of2):
                    # print('Downloading ' + url + ' to ' + of2)
                    # exec_cmd('wget -O "' + of2 + '" "' + url + '"', pars['Verbose']);
                # if os.path.exists(of2):
                    # if os.path.getsize(of2) == 0:
                        # os.remove(of2)
       
        # # Download monthly PRISM TMean data on first day of month
        # if TS.day == 1 and not TS == ETStamp + timedelta(days=1):
            # # First try downloading the stable data (available further back in time than ~6 months in the past)
            # of1 = pars['PRISMForcingDir'] + '/tmean/' + yyyy + '/PRISM_tmean_stable_4kmM' + str(pars['prism_tmean_version']) + '_' + yyyy + mm + '_bil.zip';
            # url = pars['PRISMDataLoc'] + '/tmean/' + yyyy + '/PRISM_tmean_stable_4kmM' + str(pars['prism_tmean_version']) + '_' + yyyy + mm + '_bil.zip';
            # if not os.path.exists('PRISM/tmean/' + yyyy):
                # os.makedirs('PRISM/tmean/' + yyyy)
            # if not os.path.exists(of1):
                # print('Downloading ' + url + ' to ' + of1)
                # exec_cmd('wget -O "' + of1 + '" "' + url + '"', pars['Verbose']);
            # if os.path.exists(of1):
                # if os.path.getsize(of1) == 0:
                    # os.remove(of1)
            
            # # Second try downloading the provisional data (available further back in time than ~6 months in the past)
            # if not os.path.exists(of1):
                # of2 = pars['PRISMForcingDir'] + '/tmean/' + yyyy + '/PRISM_tmean_provisional_4kmM' + str(pars['prism_tmean_version']) + '_' + yyyy + mm + '_bil.zip';
                # url = pars['PRISMDataLoc'] + '/tmean/' + yyyy + '/PRISM_tmean_provisional_4kmM' + str(pars['prism_tmean_version']) + '_' + yyyy + mm + '_bil.zip';
                # if not os.path.exists('PRISM/tmean/' + yyyy):
                    # os.makedirs('PRISM/tmean/' + yyyy)
                # if not os.path.exists(of2):
                    # print('Downloading ' + url + ' to ' + of2)
                    # exec_cmd('wget -O "' + of2 + '" "' + url + '"', pars['Verbose']);
                # if os.path.exists(of2):
                    # if os.path.getsize(of2) == 0:
                        # os.remove(of2)

        # # Download NLDAS data
        # for hour in range(0,24):
            # hh = str(hour)
            # if len(hh) < 2:
                # hh = '0' + hh
            
            # of = pars['NLDASForcingDir'] + '/NLDAS_FORA0125_H.2.0/' + yyyy + '/' + ddd + '/NLDAS_FORA0125_H.A' + yyyy + mm + dd + '.' + hh + '00.020.nc'
            # url = pars['NLDASDataLoc'] + '/NLDAS_FORA0125_H.2.0/' + yyyy + '/' + ddd + '/NLDAS_FORA0125_H.A' + yyyy + mm + dd + '.' + hh + '00.020.nc' 
            # if not os.path.exists('NLDAS/' + yyyy + '/' + ddd):
                # os.makedirs('NLDAS/' + yyyy + '/' + ddd)
            # if not os.path.exists(of):
                # print('Downloading ' + url + ' to ' + of)
                # exec_cmd('wget --user ' + pars['NLDASUsername'] + ' --password ' + pars['NLDASPassword'] + ' -O "' + of + '" "' + url + '"', pars['Verbose']);
            # if os.path.exists(of):
                # if os.path.getsize(of) == 0:
                    # os.remove(of)

def DownloadMonthly800mPRISMData(pars):
    # Timestamps of start and end dates
    STStamp = date(pars['StartYear'],pars['StartMonth'],1)
    ETStamp = date(pars['EndYear'],pars['EndMonth'],1)
    ETStamp = last_day_of_month(ETStamp)

    # Loop through desired dates (+ 1 extra day - because of typical NLDAS time offset)
    for TS in daterange(STStamp, ETStamp + timedelta(days=2)):
        

        doy = (TS - date(TS.year,1,1) + timedelta(days=1)).days
        yyyy = str(TS.year)
        mm = str(TS.month)
        if len(mm) < 2:
            mm = '0' + mm
        dd = str(TS.day)
        if len(dd) < 2:
            dd = '0' + dd
        ddd = str(doy);
        if len(ddd) < 3:
            ddd = '0' + ddd
        if len(ddd) < 3:
            ddd = '0' + ddd

        # Download monthly PRISM PPT data on first day of month
        if TS.day == 1 and not TS == ETStamp + timedelta(days=1):
            # First try downloading the stable data (available further back in time than ~6 months in the past)
            of1 = pars['PRISMForcingDir'] + '/800m/ppt/monthly/' + yyyy + '/prism_ppt_us_30s_' + yyyy + mm + '.zip';
            url = pars['PRISMDataLoc'] + '/800m/ppt/monthly/' + yyyy + '/prism_ppt_us_30s_' + yyyy + mm + '.zip';
            if not os.path.exists(pars['PRISMForcingDir'] + '/800m/ppt/monthly/' + yyyy):
                os.makedirs(pars['PRISMForcingDir'] + '/800m/ppt/monthly/' + yyyy)

            for retry in range(0,max_retries):
                if not os.path.exists(of1):
                    print('Downloading ' + url + ' to ' + of1)
                    exec_cmd('wget -O "' + of1 + '" "' + url + '"', pars['Verbose']);
                if os.path.exists(of1):
                    if os.path.getsize(of1) == 0:
                        os.remove(of1)
            
            # Download monthly PRISM tmean data on first day of month
            of1 = pars['PRISMForcingDir'] + '/800m/tmean/monthly/' + yyyy + '/prism_tmean_us_30s_' + yyyy + mm + '.zip';
            url = pars['PRISMDataLoc'] + '/800m/tmean/monthly/' + yyyy + '/prism_tmean_us_30s_' + yyyy + mm + '.zip';
            if not os.path.exists(pars['PRISMForcingDir'] + '/800m/tmean/monthly/' + yyyy):
                os.makedirs(pars['PRISMForcingDir'] + '/800m/tmean/monthly/' + yyyy)

            for retry in range(0,max_retries):
                if not os.path.exists(of1):
                    print('Downloading ' + url + ' to ' + of1)
                    exec_cmd('wget -O "' + of1 + '" "' + url + '"', pars['Verbose']);
                if os.path.exists(of1):
                    if os.path.getsize(of1) == 0:
                        os.remove(of1)

def DownloadMonthly4kmPRISMData(pars):
    # Timestamps of start and end dates
    STStamp = date(pars['StartYear'],pars['StartMonth'],1)
    ETStamp = date(pars['EndYear'],pars['EndMonth'],1)
    ETStamp = last_day_of_month(ETStamp)

    # Loop through desired dates (+ 1 extra day - because of typical NLDAS time offset)
    for TS in daterange(STStamp, ETStamp + timedelta(days=2)):
        

        doy = (TS - date(TS.year,1,1) + timedelta(days=1)).days
        yyyy = str(TS.year)
        mm = str(TS.month)
        if len(mm) < 2:
            mm = '0' + mm
        dd = str(TS.day)
        if len(dd) < 2:
            dd = '0' + dd
        ddd = str(doy);
        if len(ddd) < 3:
            ddd = '0' + ddd
        if len(ddd) < 3:
            ddd = '0' + ddd

        # Download monthly PRISM PPT data on first day of month
        if TS.day == 1 and not TS == ETStamp + timedelta(days=1):
            # First try downloading the stable data (available further back in time than ~6 months in the past)
            of1 = pars['PRISMForcingDir'] + '/4km/ppt/monthly/' + yyyy + '/prism_ppt_us_25m_' + yyyy + mm + '.zip';
            url = pars['PRISMDataLoc'] + '/4km/ppt/monthly/' + yyyy + '/prism_ppt_us_25m_' + yyyy + mm + '.zip';
            if not os.path.exists(pars['PRISMForcingDir'] + '/4km/ppt/monthly/' + yyyy):
                os.makedirs(pars['PRISMForcingDir'] + '/4km/ppt/monthly/' + yyyy)

            for retry in range(0,max_retries):
                if not os.path.exists(of1):
                    print('Downloading ' + url + ' to ' + of1)
                    exec_cmd('wget -O "' + of1 + '" "' + url + '"', pars['Verbose']);
                if os.path.exists(of1):
                    if os.path.getsize(of1) == 0:
                        os.remove(of1)
            
            # First try downloading the stable data (available further back in time than ~6 months in the past)
            of1 = pars['PRISMForcingDir'] + '/4km/tmean/monthly/' + yyyy + '/prism_tmean_us_25m_' + yyyy + mm + '.zip';
            url = pars['PRISMDataLoc'] + '/4km/tmean/monthly/' + yyyy + '/prism_tmean_us_25m_' + yyyy + mm + '.zip';
            if not os.path.exists(pars['PRISMForcingDir'] + '/4km/tmean/monthly/' + yyyy):
                os.makedirs(pars['PRISMForcingDir'] + '/4km/tmean/monthly/' + yyyy)

            for retry in range(0,max_retries):
                if not os.path.exists(of1):
                    print('Downloading ' + url + ' to ' + of1)
                    exec_cmd('wget -O "' + of1 + '" "' + url + '"', pars['Verbose']);
                if os.path.exists(of1):
                    if os.path.getsize(of1) == 0:
                        os.remove(of1)
            
def DownloadNLDAS2Data(pars):
    # Timestamps of start and end dates
    STStamp = date(pars['StartYear'],pars['StartMonth'],1)
    ETStamp = date(pars['EndYear'],pars['EndMonth'],1)
    ETStamp = last_day_of_month(ETStamp)

    # Loop through desired dates (+ 1 extra day - because of typical NLDAS time offset)
    for TS in daterange(STStamp, ETStamp + timedelta(days=2)):

        doy = (TS - date(TS.year,1,1) + timedelta(days=1)).days
        yyyy = str(TS.year)
        mm = str(TS.month)
        if len(mm) < 2:
            mm = '0' + mm
        dd = str(TS.day)
        if len(dd) < 2:
            dd = '0' + dd
        ddd = str(doy);
        if len(ddd) < 3:
            ddd = '0' + ddd
        if len(ddd) < 3:
            ddd = '0' + ddd

        # Download NLDAS data
        for hour in range(0,24):
            hh = str(hour)
            if len(hh) < 2:
                hh = '0' + hh
            
            of = pars['NLDASForcingDir'] + '/NLDAS_FORA0125_H.2.0/' + yyyy + '/' + ddd + '/NLDAS_FORA0125_H.A' + yyyy + mm + dd + '.' + hh + '00.020.nc'
            url = pars['NLDASDataLoc'] + '/NLDAS_FORA0125_H.2.0/' + yyyy + '/' + ddd + '/NLDAS_FORA0125_H.A' + yyyy + mm + dd + '.' + hh + '00.020.nc' 
            if not os.path.exists(pars['NLDASForcingDir'] + '/NLDAS_FORA0125_H.2.0/' + yyyy + '/' + ddd):
                os.makedirs(pars['NLDASForcingDir'] + '/NLDAS_FORA0125_H.2.0/' + yyyy + '/' + ddd)

            for retry in range(0,max_retries):
                if not os.path.exists(of):
                    print('Downloading ' + url + ' to ' + of)
                    exec_cmd('wget --user ' + pars['NLDASUsername'] + ' --password ' + pars['NLDASPassword'] + ' -O "' + of + '" "' + url + '"', pars['Verbose']);
                if os.path.exists(of):
                    if os.path.getsize(of) == 0:
                        os.remove(of)


def GetForcingData(pars):

    ## Load Spatial Information
    
    rows,cols,ulx,uly,lrx,lry,pixelWidth,pixelHeight,prj,wkt = GetGeorefInfo(pars['LoResDTMFile'])
    te = str(ulx) + ' ' + str(lry) + ' ' + str(lrx) + ' ' + str(uly)
    tr = str(pixelWidth) + ' ' + str(pixelHeight)

    x = np.linspace(ulx + pixelWidth/2, lrx - pixelWidth/2, cols) 
    y = np.linspace(lry - pixelHeight/2, uly + pixelHeight/2, rows)
    x_2d, y_2d = np.meshgrid(x, y)

    trans = Transformer.from_crs(prj,'epsg:4326', always_xy=True)
    (ullon,ullat) = trans.transform(ulx,uly)
    (lrlon,lrlat) = trans.transform(lrx,lry)
    projwin = str(ullon - padding_prism) + ' ' + str(ullat + padding_prism) + ' ' + str(lrlon + padding_prism) + ' ' + str(lrlat - padding_prism)

    ## Load Daily or Hourly Station Data if required
    
    if pars['DataSource'] == 1:
        if pars['OutputTimestep'] == 1:
            files = [pars['DailyForcingFile']]
        elif pars['OutputTimestep'] == 0:
            files = [pars['HourlyForcingFile']]
        
        fid = open(files[0], 'r')
        lines = fid.readlines()
        fid.close()
        nl = len(lines)-3
        nf = len(files)
        
        StationYs = np.zeros(nf) * np.nan
        StationXs = np.zeros(nf) * np.nan
        StationElevs = np.zeros(nf) * np.nan
        StationYears = np.zeros((nl,nf)) * np.nan
        StationMonths = np.zeros((nl,nf)) * np.nan
        StationDays = np.zeros((nl,nf)) * np.nan
        StationHours = np.zeros((nl,nf)) * np.nan
        StationPrecip = np.zeros((nl,nf)) * np.nan
        StationRain = np.zeros((nl,nf)) * np.nan
        StationSnow = np.zeros((nl,nf)) * np.nan
        StationAirT = np.zeros((nl,nf)) * np.nan
        StationPres = np.zeros((nl,nf)) * np.nan
        StationRH = np.zeros((nl,nf)) * np.nan
        StationWindSpeed = np.zeros((nl,nf)) * np.nan
        StationWindAngle = np.zeros((nl,nf)) * np.nan
        StationDSWRF = np.zeros((nl,nf)) * np.nan
        StationDLWRF = np.zeros((nl,nf)) * np.nan
        StationPET = np.zeros((nl,nf)) * np.nan
        
        f = 0
        for file in files:  
            print('Reading ' + file)
            fid = open(file, 'r')
            lines = fid.readlines()
            fid.close()
            l = 0
            
            for line in lines:
                fields = line.split(',')
                if l == 0:
                    StationLat = float(fields[1])
                    StationLon = float(fields[2])
                    trans = Transformer.from_crs('epsg:4326',prj, always_xy=True)
                    (StationXs[f], StationYs[f]) = trans.transform(StationLon, StationLat)
                    StationElevs[f] = float(fields[3])
                elif l > 2:
                    StationYears[l-3,f] = float(fields[0])
                    StationMonths[l-3,f] = float(fields[1])
                    StationDays[l-3,f] = float(fields[2])
                    StationHours[l-3,f] = float(fields[3])
                    StationPrecip[l-3,f] = float(fields[4])
                    StationRain[l-3,f] = float(fields[5])
                    StationSnow[l-3,f] = float(fields[6])
                    StationAirT[l-3,f] = float(fields[7])
                    StationPres[l-3,f] = float(fields[8])
                    StationRH[l-3,f] = float(fields[9])
                    StationWindSpeed[l-3,f] = float(fields[10])
                    StationWindAngle[l-3,f] = float(fields[11])
                    StationDSWRF[l-3,f] = float(fields[12])
                    StationDLWRF[l-3,f] = float(fields[13])
                    StationPET[l-3,f] = float(fields[14])
                    
                l = l+1
            f = f+1
            
    ## Load Monthly Station Data if required
    
    if pars['ApplyPPTLapseRate'] == 2 or pars['ApplyAirTLapseRate'] == 2:
        files = [pars['MonthlyForcingFile']]
        fid = open(files[0], 'r')
        lines = fid.readlines()
        fid.close()
        nl = len(lines)-3
        nf = len(files)
        
        MonthlyStationYs = np.zeros(nf) * np.nan
        MonthlyStationXs = np.zeros(nf) * np.nan
        MonthlyStationElevs = np.zeros(nf) * np.nan
        MonthlyStationYears = np.zeros((nl,nf)) * np.nan
        MonthlyStationMonths = np.zeros((nl,nf)) * np.nan
        MonthlyStationPrecip = np.zeros((nl,nf)) * np.nan
        MonthlyStationAirT = np.zeros((nl,nf)) * np.nan
        
        f = 0
        for file in files:  
            print('Reading ' + file)
            fid = open(file, 'r')
            lines = fid.readlines()
            fid.close()
            l = 0
            
            for line in lines:
                fields = line.split(',')
                if l == 0:
                    MonthlyStationLat = float(fields[1])
                    MonthlyStationLon = float(fields[2])
                    trans = Transformer.from_crs('epsg:4326',prj, always_xy=True)
                    (MonthlyStationXs[f], MonthlyStationYs[f]) = trans.transform(MonthlyStationLon, MonthlyStationLat)
                    MonthlyStationElevs[f] = float(fields[3])
                elif l > 2:
                    MonthlyStationYears[l-3,f] = float(fields[0])
                    MonthlyStationMonths[l-3,f] = float(fields[1])
                    MonthlyStationPrecip[l-3,f] = float(fields[2])
                    MonthlyStationAirT[l-3,f] = float(fields[3])
                    
                l = l+1
            f = f+1
            
    # Timestamps of start and end dates
    STStamp = datetime(pars['StartYear'],pars['StartMonth'],1)
    ETStamp = datetime(pars['EndYear'],pars['EndMonth'],1)
    ETStamp = last_day_of_month(ETStamp)
    
    tmp_dir = tempfile.TemporaryDirectory()
    
    for TS in daterange(STStamp, ETStamp + timedelta(days=1)):
    
        DIM = DIM_i[TS.month - 1]
        if TS.month == 2 and (np.mod(TS.year,4) == 0 and (np.mod(TS.year,100) > 0 or np.mod(TS.year,400) == 0)):
            DIM = DIM + 1
        
        if TS.day == 1:
            c = 0
            airt = np.zeros([24*DIM, rows, cols]) * np.nan
            rh = np.zeros([24*DIM, rows, cols]) * np.nan
            pres = np.zeros([24*DIM, rows, cols]) * np.nan
            windspeed = np.zeros([24*DIM, rows, cols]) * np.nan
            winddir = np.zeros([24*DIM, rows, cols]) * np.nan
            dlwrf = np.zeros([24*DIM, rows, cols]) * np.nan
            ppt = np.zeros([24*DIM, rows, cols]) * np.nan
            rain = np.zeros([24*DIM, rows, cols]) * np.nan
            snow = np.zeros([24*DIM, rows, cols]) * np.nan
            dswrf = np.zeros([24*DIM, rows, cols]) * np.nan
            pet = np.zeros([24*DIM, rows, cols]) * np.nan
    
        for hour in range(0,24):
        
            combined_hour = hour-pars['UTCOffset']
            TS_nldas = TS + timedelta(hours=combined_hour)
            doy = (date(TS_nldas.year,TS_nldas.month,TS_nldas.day) - date(TS_nldas.year,1,1) + timedelta(days=1)).days
            yyyy = str(TS_nldas.year)
            mm = str(TS_nldas.month)
            if len(mm) < 2:
                mm = '0' + mm
            dd = str(TS_nldas.day)
            if len(dd) < 2:
                dd = '0' + dd
            hh = str(TS_nldas.hour)
            if len(hh) < 2:
                hh = '0' + hh
            ddd = str(doy);
            if len(ddd) < 3:
                ddd = '0' + ddd
            if len(ddd) < 3:
                ddd = '0' + ddd
            
            # Get NLDAS data
            if pars['DataSource'] == 0 or pars['FillWithNLDAS']:
                fname = pars['NLDASForcingDir'] + '/NLDAS_FORA0125_H.002/' + yyyy + '/' + ddd + '/NLDAS_FORA0125_H.A' + yyyy + mm + dd + '.' + hh + '00.002.grb'
                if os.path.exists(fname):
                    print('Reading ' + fname)
                    tmpfilename = tmp_dir.name + '/tmp_NLDAS.tif'
                    cmd = 'gdalwarp -tr ' + tr + ' -te ' + te + ' -multi -r ' + pars['NLDASResamplingMethod'] + ' -overwrite -t_srs "' + prj + '" "' + fname + '" "' + tmpfilename + '"'
                    exec_cmd(cmd, pars['Verbose'])
                    data = ReadRaster(tmpfilename, pars['Verbose'])
                    os.remove(tmpfilename)

                    airt[c,:,:] = data[0,:,:]
                    pres[c,:,:] = data[2,:,:]

                    AIRT = airt[c,:,:]
                    PRES = pres[c,:,:]
                    SPFH = data[1,:,:]
                    VAPP = PRES * SPFH / (0.622 + SPFH);
                    ESAT = 0.6108 * np.exp(17.27 * AIRT / (237.3 + AIRT)) * 1000     # in Pa
                    RH = np.maximum(0, np.minimum(1, (VAPP / ESAT))) * 100
                    rh[c,:,:] = RH

                    UGRD = data[3,:,:]
                    VGRD = data[4,:,:]
                    WINDSPEED = np.sqrt(UGRD**2 + VGRD**2)
                    WINDANGLE = (270-np.rad2deg(np.arctan2(VGRD, UGRD)))
                    WINDANGLE[WINDANGLE > 360] = WINDANGLE[WINDANGLE > 360] - 360   # From north, clockwise

                    windspeed[c,:,:] = WINDSPEED
                    winddir[c,:,:] = WINDANGLE

                    dlwrf[c,:,:] = data[5,:,:]
                    ppt[c,:,:] = data[9,:,:]
                    dswrf[c,:,:] = data[10,:,:]
                    pet[c,:,:] = data[8,:,:]

                else:

                    # Build filename for new NLDAS v2.0 NetCDF
                    fname = os.path.join(
                        pars['NLDASForcingDir'],
                        'NLDAS_FORA0125_H.2.0',
                        yyyy,
                        ddd,
                        f'NLDAS_FORA0125_H.A{yyyy}{mm}{dd}.{hh}00.020.nc'
                    )

                    if os.path.exists(fname):
                        print('Reading ' + fname)
                        tmp_vrt = os.path.join(tmp_dir.name, 'tmp_NLDAS.vrt')
                        tmp_warped = os.path.join(tmp_dir.name, 'tmp_NLDAS_warped.tif')

                        # List of subdatasets to extract and map to arrays
                        sds_vars = {
                            'Tair': 'airt',
                            'Qair': 'SPFH',
                            'PSurf': 'pres',
                            'Wind_E': 'UGRD',
                            'Wind_N': 'VGRD',
                            'LWdown': 'dlwrf',
                            'Rainf': 'ppt',
                            'SWdown': 'dswrf',
                            'PotEvap': 'pet'
                        }

                        # Build a VRT with all subdatasets
                        vrt_list = [f'NETCDF:{fname}:{var}' for var in sds_vars.keys()]
                        cmd_vrt = f'gdalbuildvrt -separate {tmp_vrt} ' + ' '.join(vrt_list)
                        exec_cmd(cmd_vrt, pars['Verbose'])

                        # Warp the VRT once
                        cmd_warp = (
                            f'gdalwarp -s_srs "EPSG:4326" -tr {tr} -te {te} -multi -r {pars["NLDASResamplingMethod"]} '
                            f'-overwrite -t_srs "{prj}" "{tmp_vrt}" "{tmp_warped}"'
                        )
                        exec_cmd(cmd_warp, pars['Verbose'])

                        # Read all bands from the warped file
                        data_all = ReadRaster(tmp_warped, pars['Verbose'])
                        os.remove(tmp_vrt)
                        os.remove(tmp_warped)

                        # Map bands to variables
                        for i, array_name in enumerate(sds_vars.values()):
                            if array_name == 'airt':
                                airt[c,:,:] = data_all[i,:,:]
                            elif array_name == 'SPFH':
                                SPFH = data_all[i,:,:]
                            elif array_name == 'pres':
                                pres[c,:,:] = data_all[i,:,:]
                            elif array_name == 'UGRD':
                                UGRD = data_all[i,:,:]
                            elif array_name == 'VGRD':
                                VGRD = data_all[i,:,:]
                            elif array_name == 'dlwrf':
                                dlwrf[c,:,:] = data_all[i,:,:]
                            elif array_name == 'ppt':
                                ppt[c,:,:] = data_all[i,:,:]
                            elif array_name == 'dswrf':
                                dswrf[c,:,:] = data_all[i,:,:]
                            elif array_name == 'pet':
                                pet[c,:,:] = data_all[i,:,:]

                        # Compute derived variables
                        AIRT = airt[c,:,:]-273.15
                        PRES = pres[c,:,:]
                        VAPP = PRES * SPFH / (0.622 + SPFH)
                        ESAT = 0.6108 * np.exp(17.27 * AIRT / (237.3 + AIRT)) * 1000  # in Pa
                        RH = np.clip(VAPP / ESAT, 0, 1) * 100
                        rh[c,:,:] = RH

                        WINDSPEED = np.sqrt(UGRD**2 + VGRD**2)
                        WINDANGLE = 270 - np.rad2deg(np.arctan2(VGRD, UGRD))
                        WINDANGLE[WINDANGLE > 360] -= 360
                        windspeed[c,:,:] = WINDSPEED
                        winddir[c,:,:] = WINDANGLE

                        # from matplotlib import pyplot as plt
                        # plt.imshow(airt[c,:,:])
                        # plt.colorbar()
                        # plt.show()
                        # sys.exit()

                    else:
                        print("File not found:", fname)
                        airt[c,:,:] = airt[c-1,:,:]
                        rh[c,:,:] = rh[c-1,:,:]
                        pres[c,:,:] = pres[c-1,:,:]
                        windspeed[c,:,:] = windspeed[c-1,:,:]
                        winddir[c,:,:] = winddir[c-1,:,:] 
                        dlwrf[c,:,:] = dlwrf[c-1,:,:]
                        ppt[c,:,:] = ppt[c-1,:,:]
                        dswrf[c,:,:] = dswrf[c-1,:,:]
                        pet[c,:,:] = pet[c-1,:,:]

                # else:
                    # # Build filename for new NLDAS v2.0 NetCDF
                    # fname = os.path.join(
                        # pars['NLDASForcingDir'],
                        # 'NLDAS_FORA0125_H.2.0',
                        # yyyy,
                        # ddd,
                        # f'NLDAS_FORA0125_H.A{yyyy}{mm}{dd}.{hh}00.020.nc'
                    # )

                    # if os.path.exists(fname):
                        # print('Reading ' + fname)
                        # tmpfilename = tmp_dir.name + '/tmp_NLDAS.tif'

                        # List of subdatasets to extract
                        # sds_vars = {
                            # 'Tair': 'airt',
                            # 'Qair': 'SPFH',
                            # 'PSurf': 'pres',
                            # 'Wind_E': 'UGRD',
                            # 'Wind_N': 'VGRD',
                            # 'LWdown': 'dlwrf',
                            # 'Rainf': 'ppt',
                            # 'SWdown': 'dswrf',
                            # 'PotEvap': 'pet'
                        # }

                        # for var_name, array_name in sds_vars.items():
                            # cmd = (
                                # f'gdalwarp -s_srs "EPSG:4326" -tr {tr} -te {te} -multi -r {pars["NLDASResamplingMethod"]} '
                                # f'-overwrite -t_srs "{prj}" "NETCDF:{fname}:{var_name}" "{tmpfilename}"'
                            # )
                            # exec_cmd(cmd, pars['Verbose'])
                            # data = ReadRaster(tmpfilename, pars['Verbose'])
                            # os.remove(tmpfilename)

                            # Assign data to appropriate array
                            # if array_name == 'airt':
                                # airt[c,:,:] = data
                            # elif array_name == 'SPFH':
                                # SPFH = data
                            # elif array_name == 'pres':
                                # pres[c,:,:] = data
                            # elif array_name == 'UGRD':
                                # UGRD = data
                            # elif array_name == 'VGRD':
                                # VGRD = data
                            # elif array_name == 'dlwrf':
                                # dlwrf[c,:,:] = data
                            # elif array_name == 'ppt':
                                # ppt[c,:,:] = data
                            # elif array_name == 'dswrf':
                                # dswrf[c,:,:] = data
                            # elif array_name == 'pet':
                                # pet[c,:,:] = data

                        # Compute derived variables
                        # AIRT = airt[c,:,:]
                        # PRES = pres[c,:,:]
                        # VAPP = PRES * SPFH / (0.622 + SPFH)
                        # ESAT = 0.6108 * np.exp(17.27 * AIRT / (237.3 + AIRT)) * 1000  # in Pa
                        # RH = np.clip(VAPP / ESAT, 0, 1) * 100
                        # rh[c,:,:] = RH

                        # WINDSPEED = np.sqrt(UGRD**2 + VGRD**2)
                        # WINDANGLE = 270 - np.rad2deg(np.arctan2(VGRD, UGRD))
                        # WINDANGLE[WINDANGLE > 360] -= 360  # From north, clockwise
                        # windspeed[c,:,:] = WINDSPEED
                        # winddir[c,:,:] = WINDANGLE

                    # else:
                        # print("File not found:", fname)

            # # Get Station Data
            if pars['DataSource'] == 1:
                if pars['OutputTimestep'] == 0:
                    tloc = (StationYears[:,0] == TS.year) * (StationMonths[:,0] == TS.month) * (StationDays[:,0] == TS.day) * (StationHours[:,0] == hour)
                    factor = 1
                elif pars['OutputTimestep'] == 1:
                    tloc = (StationYears[:,0] == TS.year) * (StationMonths[:,0] == TS.month) * (StationDays[:,0] == TS.day)
                    factor = 1/24
                
                if not np.isnan(StationAirT[tloc][0]):
                    airt[c,:,:] = np.ones([rows, cols]) * StationAirT[tloc][0]
                if not np.isnan(StationRH[tloc][0]):
                    rh[c,:,:] = np.ones([rows, cols]) * StationRH[tloc][0]
                if not np.isnan(StationPres[tloc][0]):
                    pres[c,:,:] = np.ones([rows, cols]) * StationPres[tloc][0]
                if not np.isnan(StationWindSpeed[tloc][0]):
                    windspeed[c,:,:] = np.ones([rows, cols]) * StationWindSpeed[tloc][0]
                if not np.isnan(StationWindAngle[tloc][0]):
                    winddir[c,:,:] = np.ones([rows, cols]) * StationWindAngle[tloc][0]
                if not np.isnan(StationDLWRF[tloc][0]):
                    dlwrf[c,:,:] = np.ones([rows, cols]) * StationDLWRF[tloc][0]
                if not np.isnan(StationDSWRF[tloc][0]):
                    dswrf[c,:,:] = np.ones([rows, cols]) * StationDSWRF[tloc][0]
                if not np.isnan(StationPrecip[tloc][0]):
                    ppt[c,:,:] = np.ones([rows, cols]) * StationPrecip[tloc][0] * factor
                if not np.isnan(StationRain[tloc][0]):
                    rain[c,:,:] = np.ones([rows, cols]) * StationRain[tloc][0] * factor
                if not np.isnan(StationSnow[tloc][0]):
                    snow[c,:,:] = np.ones([rows, cols]) * StationSnow[tloc][0] * factor
                if not np.isnan(StationPET[tloc][0]):
                    pet[c,:,:] = np.ones([rows, cols]) * StationPET[tloc][0] * factor
                
                  
            c = c+1
         
        if TS.day == DIM:
        
            ## Apply PRISM precipitation lapse rates
            if pars['ApplyPPTLapseRate'] == 1 or pars['ApplyPPTLapseRate'] == 2:
            
                yyyy = str(TS.year)
                mm = str(TS.month)
                if len(mm) < 2:
                    mm = '0' + mm

                fname1 = pars['PRISMForcingDir'] + '/4km/ppt/monthly/' + yyyy + '/prism_ppt_us_25m_' + yyyy + mm + '.zip';
                tmpfilename = tmp_dir.name + '/tmp_PRISM.tif'

                if os.path.exists(fname1):
                    print('Reading ' + fname1)
                    cmd = 'gdal_translate  -projwin ' + projwin + ' "/vsizip/' + fname1 + '/' + os.path.basename(fname1).replace('.zip','.tif') + '" "' + tmpfilename + '"'
                    exec_cmd(cmd, pars['Verbose']) 
                    PRISM_ppt = ReadRaster(tmpfilename, pars['Verbose'])
                else:
                    print(fname1 + ' does not exist!!! Download data first')
                    sys.exit()

                if 'PRISM_DTM' not in locals():

                    fname = pars['PRISMForcingDir'] + '/../US_DEM.tif'

                    rows_prism,cols_prism,ulx_prism,uly_prism,lrx_prism,lry_prism,pixelWidth_prism,pixelHeight_prism,prj_prism,wkt_prism = GetGeorefInfo(tmpfilename)
                    te_prism = str(ulx_prism) + ' ' + str(lry_prism) + ' ' + str(lrx_prism) + ' ' + str(uly_prism)
                    tr_prism = str(pixelWidth_prism) + ' ' + str(pixelHeight_prism)
                    
                    cmd = 'gdalwarp -tr ' + tr_prism + ' -te ' + te_prism + ' -multi -r bilinear -overwrite -t_srs "' + prj_prism + '" "' + fname + '" "' + tmpfilename + '"'

                    exec_cmd(cmd, pars['Verbose'])
                    PRISM_DTM = ReadRaster(tmpfilename, pars['Verbose'])
                    DTM = ReadRaster(pars['LoResDTMFile'], pars['Verbose'])
            
                M = np.zeros(PRISM_DTM.shape) * np.nan;
                B = np.zeros(PRISM_DTM.shape) * np.nan;
                R = np.tile(np.reshape(range(rows_prism), (-1,1)), [1, cols_prism]);
                C = np.tile(range(cols_prism), [rows_prism, 1])
                for r in range(rows_prism):
                    for c in range(cols_prism):
                        locs = (R >= r - pars['PRISMLapsePX']) * (R <= r + pars['PRISMLapsePX']) * (C >= c - pars['PRISMLapsePX']) * (C <= c + pars['PRISMLapsePX'])
                        y = PRISM_ppt[locs]
                        x = PRISM_DTM[locs]
                        slope, intercept = np.polyfit(x,y,1)
                        M[r,c] = slope
                        B[r,c] = intercept
             
                M[np.isnan(PRISM_ppt)] = np.nan;
                B[np.isnan(PRISM_ppt)] = np.nan;
                M[(PRISM_ppt == 0) + (np.isnan(M))] = 0;
                B[(PRISM_ppt == 0) + (np.isnan(B))] = 0;

                x = np.linspace(ulx_prism + pixelWidth_prism/2, lrx_prism - pixelWidth_prism/2, cols_prism) 
                y = np.linspace(lry_prism - pixelHeight_prism/2, uly_prism + pixelHeight_prism/2, rows_prism)
                x_prism, y_prism = np.meshgrid(x, y)

                x_prism_local = np.zeros(x_prism.shape) * np.nan
                y_prism_local = np.zeros(y_prism.shape) * np.nan
                trans = Transformer.from_crs('epsg:4326',prj, always_xy=True)
                for r in range(rows_prism):
                    for c in range(cols_prism):
                        (x_prism_local[r,c], y_prism_local[r,c]) = trans.transform(x_prism[r,c], y_prism[r,c])

                # Interpolate lapse rate parameters onto model forcing grid and combine
                M_grid = griddata((x_prism_local.flatten(),y_prism_local.flatten()),M.flatten(),(x_2d,y_2d),method='linear')
                B_grid = griddata((x_prism_local.flatten(),y_prism_local.flatten()),B.flatten(),(x_2d,y_2d),method='linear')
                Lapse_ppt_interp = M_grid * DTM + B_grid

                if pars['ApplyPPTLapseRate'] == 2:
                    dist = np.sqrt((x_2d - MonthlyStationXs[0])**2 + (y_2d - MonthlyStationYs[0])**2)
                    loc = dist == np.min(dist)
                    tloc = (MonthlyStationYears[:,0] == TS.year) * (MonthlyStationMonths[:,0] == TS.month)
                    
                    if not np.isnan(MonthlyStationPrecip[tloc][0]):
                        Lapse_ppt_interp = Lapse_ppt_interp * MonthlyStationPrecip[tloc][0] / Lapse_ppt_interp[loc]
            
            else:
                Lapse_ppt_interp = np.array([])
            
            ## Apply PRISM temperature lapse rates
            if pars['ApplyAirTLapseRate'] == 1 or pars['ApplyAirTLapseRate'] == 2:
            
                yyyy = str(TS.year)
                mm = str(TS.month)
                if len(mm) < 2:
                    mm = '0' + mm

                fname1 = pars['PRISMForcingDir'] + '/4km/tmean/monthly/' + yyyy + '/prism_tmean_us_25m_' + yyyy + mm + '.zip';
                tmpfilename = tmp_dir.name + '/tmp_PRISM.tif'

                if os.path.exists(fname1):
                    print('Reading ' + fname1)
                    cmd = 'gdal_translate  -projwin ' + projwin + ' "/vsizip/' + fname1 + '/' + os.path.basename(fname1).replace('.zip','.tif') + '" "' + tmpfilename + '"'
                    exec_cmd(cmd, pars['Verbose']) 
                    PRISM_tmean = ReadRaster(tmpfilename, pars['Verbose'])
                else:
                    print(fname1 + ' does not exist!!! Download data first')
                    sys.exit()
                  
                if 'PRISM_DTM' not in locals():

                    fname = pars['PRISMForcingDir'] + '/../US_DEM.tif'

                    rows_prism,cols_prism,ulx_prism,uly_prism,lrx_prism,lry_prism,pixelWidth_prism,pixelHeight_prism,prj_prism = GetGeorefInfo(tmpfilename)
                    te_prism = str(ulx_prism) + ' ' + str(lry_prism) + ' ' + str(lrx_prism) + ' ' + str(uly_prism)
                    tr_prism = str(pixelWidth_prism) + ' ' + str(pixelHeight_prism)

                    cmd = 'gdalwarp -tr ' + tr_prism + ' -te ' + te_prism + ' -multi -r bilinear -overwrite -t_srs "' + prj_prism + '" "' + fname + '" "' + tmpfilename + '"'

                    exec_cmd(cmd, pars['Verbose'])
                    PRISM_DTM = ReadRaster(tmpfilename, pars['Verbose'])
                    DTM = ReadRaster(pars['LoResDTMFile'], pars['Verbose'])
                    
                os.remove(tmpfilename)
                
                M = np.zeros(PRISM_DTM.shape) * np.nan;
                B = np.zeros(PRISM_DTM.shape) * np.nan;
                R = np.tile(np.reshape(range(rows_prism), (-1,1)), [1, cols_prism]);
                C = np.tile(range(cols_prism), [rows_prism, 1])
                for r in range(rows_prism):
                    for c in range(cols_prism):
                        locs = (R >= r - pars['PRISMLapsePX']) * (R <= r + pars['PRISMLapsePX']) * (C >= c - pars['PRISMLapsePX']) * (C <= c + pars['PRISMLapsePX'])
                        y = PRISM_tmean[locs]
                        x = PRISM_DTM[locs]
                        slope, intercept = np.polyfit(x,y,1)
                        M[r,c] = slope
                        B[r,c] = intercept
             
                M[np.isnan(PRISM_tmean)] = np.nan;
                B[np.isnan(PRISM_tmean)] = np.nan;
                M[np.isnan(M)] = 0;
                B[np.isnan(B)] = 0;

                x = np.linspace(ulx_prism + pixelWidth_prism/2, lrx_prism - pixelWidth_prism/2, cols_prism) 
                y = np.linspace(lry_prism - pixelHeight_prism/2, uly_prism + pixelHeight_prism/2, rows_prism)
                x_prism, y_prism = np.meshgrid(x, y)

                x_prism_local = np.zeros(x_prism.shape) * np.nan
                y_prism_local = np.zeros(y_prism.shape) * np.nan
                trans = Transformer.from_crs('epsg:4326',prj, always_xy=True)
                for r in range(rows_prism):
                    for c in range(cols_prism):
                        (x_prism_local[r,c], y_prism_local[r,c]) = trans.transform(x_prism[r,c], y_prism[r,c])

                # Interpolate lapse rate parameters onto model forcing grid and combine
                M_grid = griddata((x_prism_local.flatten(),y_prism_local.flatten()),M.flatten(),(x_2d,y_2d),method='linear')
                B_grid = griddata((x_prism_local.flatten(),y_prism_local.flatten()),B.flatten(),(x_2d,y_2d),method='linear')
                Lapse_tmean_interp = M_grid * DTM + B_grid

                if pars['ApplyAirTLapseRate'] == 2:
                    dist = np.sqrt((x_2d - MonthlyStationXs[0])**2 + (y_2d - MonthlyStationYs[0])**2)
                    loc = dist == np.min(dist)
                    tloc = (MonthlyStationYears[:,0] == TS.year) * (MonthlyStationMonths[:,0] == TS.month)
                    
                    if not np.isnan(MonthlyStationAirT[tloc][0]):
                        Lapse_tmean_interp = Lapse_tmean_interp + (MonthlyStationAirT[tloc][0] - Lapse_tmean_interp[loc])
                
            else:
                Lapse_tmean_interp = np.array([])
            
            # from matplotlib import pyplot as plt
            # plt.imshow(Lapse_ppt_interp)
            # plt.colorbar()
            # plt.show()
            # print(Lapse_ppt_interp.shape == (0,))
            # sys.exit()
            
            # Lapse Rate Adjustment Parameters
            if not Lapse_ppt_interp.shape == (0,):
                sum_ppt = np.sum(ppt,axis=0)
                sum_ppt[sum_ppt == 0] = 1e-6
                ppt_mult = Lapse_ppt_interp / sum_ppt
            else:
                ppt_mult = np.ones((rows,cols))
                
            ppt_mult[np.isnan(ppt_mult)] = 1
            
            if not Lapse_tmean_interp.shape == (0,):
                airt_add = Lapse_tmean_interp - np.mean(airt,axis=0)
            else:
                airt_add = np.zeros((rows,cols))

            # from matplotlib import pyplot as plt
            # plt.imshow(airt[c,:,:])
            # plt.colorbar()
            # plt.show()
            # sys.exit()

            # Create NetCDF files for each day
            for d in range(DIM):
                yyyy = str(TS.year)
                mm = str(TS.month)
                if len(mm) < 2:
                    mm = '0' + mm
                dd = str(d+1)
                if len(dd) < 2:
                    dd = '0' + dd
                    
                OFName = pars['OFDir'] + '/' + yyyy + '/' + mm + '/' + dd + '.nc'
                if not os.path.exists(pars['OFDir'] + '/' + yyyy + '/' + mm):
                    os.makedirs(pars['OFDir'] + '/' + yyyy + '/' + mm)
               
                print('Writing ' + OFName)
                
                if os.path.exists(OFName):
                    os.remove(OFName)
                    
                with nc4.Dataset(OFName, 'w' , format='NETCDF4_CLASSIC') as ds:
                
                    # Initialize the dimensions of the dataset
                    if pars['OutputTimestep'] == 0:
                        dim_time = ds.createDimension('time', 24)
                    elif pars['OutputTimestep'] == 1:
                        dim_time = ds.createDimension('time', 1)
                        
                    dim_lat = ds.createDimension('Y', y_2d.shape[0])
                    dim_lon = ds.createDimension('X', x_2d.shape[1])

                    # Create the corresponding variables for the dimensions
                    time = ds.createVariable('time', np.float32, 'time')
                    Y = ds.createVariable('Y', np.float32, 'Y')
                    Y.axis  = ['Y']
                    Y.standard_name = ['northing']
                    X = ds.createVariable('X', np.float32, 'X')
                    X.axis = ['X']
                    X.standard_name = ['easting']
                    
                    # Fill with 1D arrays of x_2d/y_2d
                    if pars['OutputTimestep'] == 0:
                        time[:] = range(24)
                    elif pars['OutputTimestep'] == 1:
                        time[:] = 0
                        
                    Y[:] = np.flipud(y_2d[:,0])
                    X[:] = x_2d[0,:]

                    
                    # Create a coordinate reference system
                    crs = ds.createVariable('CRS', 'c')
                    crs.spatial_ref = wkt
                    
                    # Ready the Temperature data field
                    airt_nc = ds.createVariable('AirT', np.float32, ('time','Y','X'), zlib=True, least_significant_digit=pars['least_significant_digit'])
                    airt_nc.standard_name = ['Air Temperature']
                    airt_nc.units = ['degrees-C']
                    airt_nc.grid_mapping = 'CRS' # the crs variable name
                    airt_nc.grid_mapping_name = 'northing_easting'
                    
                    # Ready the Relative Humidity data field
                    rh_nc = ds.createVariable('RH', np.float32, ('time','Y','X'), zlib=True, least_significant_digit=pars['least_significant_digit'])
                    rh_nc.standard_name = ['Relative Humidity']
                    rh_nc.units = ['%']
                    rh_nc.grid_mapping = 'CRS' # the crs variable name
                    rh_nc.grid_mapping_name = 'northing_easting'
                    
                    # Ready the Pressure data field
                    pres_nc = ds.createVariable('Pres', np.float32, ('time','Y','X'), zlib=True, least_significant_digit=pars['least_significant_digit'])
                    pres_nc.standard_name = ['Pressure']
                    pres_nc.units = ['Pa']
                    pres_nc.grid_mapping = 'CRS' # the crs variable name
                    pres_nc.grid_mapping_name = 'northing_easting'
                    
                    # Ready the Wind Speed data field
                    windspeed_nc = ds.createVariable('WindSpeed', np.float32, ('time','Y','X'), zlib=True, least_significant_digit=pars['least_significant_digit'])
                    windspeed_nc.standard_name = ['Wind Speed']
                    windspeed_nc.units = ['m/s']
                    windspeed_nc.grid_mapping = 'CRS' # the crs variable name
                    windspeed_nc.grid_mapping_name = 'northing_easting'
                    
                    # Ready the Wind Direction data field
                    winddir_nc = ds.createVariable('WindDir', np.float32, ('time','Y','X'), zlib=True, least_significant_digit=pars['least_significant_digit'])
                    winddir_nc.standard_name = ['Wind Direction']
                    winddir_nc.units = ['Degrees']
                    winddir_nc.grid_mapping = 'CRS' # the crs variable name
                    winddir_nc.grid_mapping_name = 'northing_easting'
                    
                    # Ready the Incoming Solar data field
                    shortwave_nc = ds.createVariable('Shortwave', np.float32, ('time','Y','X'), zlib=True, least_significant_digit=pars['least_significant_digit'])
                    shortwave_nc.standard_name = ['Incoming Shortwave Radiation']
                    shortwave_nc.units = ['W/m^2']
                    shortwave_nc.grid_mapping = 'CRS' # the crs variable name
                    shortwave_nc.grid_mapping_name = 'northing_easting'
                    
                    # Ready the Incoming Longwave data field
                    longwave_nc = ds.createVariable('Longwave', np.float32, ('time','Y','X'), zlib=True, least_significant_digit=pars['least_significant_digit'])
                    longwave_nc.standard_name = ['Incoming Longwave Radiation']
                    longwave_nc.units = ['W/m^2']
                    longwave_nc.grid_mapping = 'CRS' # the crs variable name
                    longwave_nc.grid_mapping_name = 'northing_easting'
                    
                    # Ready the Precipitation data field
                    precip_nc = ds.createVariable('Precip', np.float32, ('time','Y','X'), zlib=True, least_significant_digit=pars['least_significant_digit'])
                    precip_nc.standard_name = ['Precipitation']
                    precip_nc.units = ['mm']
                    precip_nc.grid_mapping = 'CRS' # the crs variable name
                    precip_nc.grid_mapping_name = 'northing_easting'
                    
                    # Ready the Precipitation data field
                    rain_nc = ds.createVariable('Rain', np.float32, ('time','Y','X'), zlib=True, least_significant_digit=pars['least_significant_digit'])
                    rain_nc.standard_name = ['Rainfall']
                    rain_nc.units = ['mm']
                    rain_nc.grid_mapping = 'CRS' # the crs variable name
                    rain_nc.grid_mapping_name = 'northing_easting'
                    
                    # Ready the Precipitation data field
                    snow_nc = ds.createVariable('Snow', np.float32, ('time','Y','X'), zlib=True, least_significant_digit=pars['least_significant_digit'])
                    snow_nc.standard_name = ['Snowfall']
                    snow_nc.units = ['mm']
                    snow_nc.grid_mapping = 'CRS' # the crs variable name
                    snow_nc.grid_mapping_name = 'northing_easting'
                    
                    # Ready the PET data field
                    pet_nc = ds.createVariable('PET', np.float32, ('time','Y','X'), zlib=True, least_significant_digit=pars['least_significant_digit'])
                    pet_nc.standard_name = ['Potential Evaporation']
                    pet_nc.units = ['mm']
                    pet_nc.grid_mapping = 'CRS' # the crs variable name
                    pet_nc.grid_mapping_name = 'northing_easting'
                    
                    # Fill with values
                    if pars['OutputTimestep'] == 0:
                    
                        for i in range(24):
                            airt_nc[i,:,:] = airt[d*24+i,:,:] + airt_add
                            rh_nc[i,:,:] = rh[d*24+i,:,:]
                            pres_nc[i,:,:] = pres[d*24+i,:,:]
                            windspeed_nc[i,:,:] = windspeed[d*24+i,:,:]
                            winddir_nc[i,:,:] = winddir[d*24+i,:,:]
                            shortwave_nc[i,:,:] = dswrf[d*24+i,:,:]
                            longwave_nc[i,:,:] = dlwrf[d*24+i,:,:]
                            precip_nc[i,:,:] = ppt[d*24+i,:,:] * ppt_mult
                            rain_nc[i,:,:] = rain[d*24+i,:,:] * ppt_mult
                            snow_nc[i,:,:] = snow[d*24+i,:,:] * ppt_mult
                            pet_nc[i,:,:] = pet[d*24+i,:,:]
                            
                    elif pars['OutputTimestep'] == 1:
                    
                        # print(d)
                        # print(rain[d*24:(d+1)*24-1,:,:])
                        # sys.exit()
                    
                        airt_nc[0,:,:] = np.mean(airt[d*24:(d+1)*24-1,:,:], axis=0) + airt_add
                        rh_nc[0,:,:] = np.mean(rh[d*24:(d+1)*24-1,:,:], axis=0)
                        pres_nc[0,:,:] = np.mean(pres[d*24:(d+1)*24-1,:,:], axis=0)
                        windspeed_nc[0,:,:] = np.mean(windspeed[d*24:(d+1)*24-1,:,:], axis=0)
                        winddir_nc[0,:,:] = np.mean(winddir[d*24:(d+1)*24-1,:,:], axis=0)
                        shortwave_nc[0,:,:] = np.mean(dswrf[d*24:(d+1)*24-1,:,:], axis=0)
                        longwave_nc[0,:,:] = np.mean(dlwrf[d*24:(d+1)*24-1,:,:], axis=0)
                        precip_nc[0,:,:] = np.sum(ppt[d*24:(d+1)*24-1,:,:], axis=0) * ppt_mult
                        rain_nc[0,:,:] = np.sum(rain[d*24:(d+1)*24-1,:,:], axis=0) * ppt_mult
                        snow_nc[0,:,:] = np.sum(snow[d*24:(d+1)*24-1,:,:], axis=0) * ppt_mult
                        pet_nc[0,:,:] = np.sum(pet[d*24:(d+1)*24-1,:,:], axis=0)
    