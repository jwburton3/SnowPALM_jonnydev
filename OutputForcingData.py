import sys
import os
import netCDF4 as nc4
from datetime import timedelta
from dateutil.parser import parse
import numpy as np
import csv
from osgeo import gdal, osr, ogr
from scipy.interpolate import RegularGridInterpolator


# ----------------- PARAMETERS -----------------
pars = {}
pars['StartDate'] = sys.argv[1]
pars['EndDate'] = sys.argv[2]
pars['StationName'] = sys.argv[3]
pars['Latitude'] = float(sys.argv[4])
pars['Longitude'] = float(sys.argv[5])
pars['ForcingSetName'] = sys.argv[6]

pars['ElevFile'] = 'Preprocess/GIS/DTM_small.tif'
pars['ForcingDir'] = 'Preprocess/Forcing/' + pars['ForcingSetName']
pars['OutputDir'] = 'Output/Forcing_csv'


# ----------------- FUNCTIONS -----------------
def daterange(start_date, end_date):
    for n in range((end_date - start_date).days):
        yield start_date + timedelta(n)


def build_interpolator(x, y, data):
    return RegularGridInterpolator(
        (y, x),
        np.flipud(data),
        method='linear',
        bounds_error=False,
        fill_value=np.nan
    )


def interp_all_vars(interp_dict, pt):
    return {k: f(pt) for k, f in interp_dict.items()}


# ----------------- MAIN -----------------
if __name__ == '__main__':

    StartDate = parse(pars['StartDate']).date()
    EndDate = parse(pars['EndDate']).date()

    # --- Load elevation grid ---
    ds = gdal.Open(pars['ElevFile'])
    print(pars['ElevFile'])

    geotransform = ds.GetGeoTransform()
    outSpatialRef = osr.SpatialReference(wkt=ds.GetProjection())

    Elev_grid = ds.GetRasterBand(1).ReadAsArray().astype(float)
    ds = None

    # --- Coordinate transform ---
    inSpatialRef = osr.SpatialReference()
    inSpatialRef.ImportFromEPSG(4326)

    coordTrans = osr.CoordinateTransformation(inSpatialRef, outSpatialRef)

    point = ogr.Geometry(ogr.wkbPoint)
    point.AddPoint(pars['Latitude'], pars['Longitude'])
    point.Transform(coordTrans)

    xi, yi = point.GetX(), point.GetY()
    pt = (yi, xi)

    # --- Storage ---
    data_out = []

    var_names = [
        'Precip', 'Rain', 'Snow', 'AirT', 'Pres', 'RH',
        'WindSpeed', 'WindDir', 'Shortwave', 'Longwave', 'PET'
    ]

    # --- Loop over dates ---
    for TS in daterange(StartDate, EndDate + timedelta(days=1)):

        yyyy = f"{TS.year:04d}"
        mm = f"{TS.month:02d}"
        dd = f"{TS.day:02d}"

        ifname = f"{pars['ForcingDir']}/{yyyy}/{mm}/{dd}.nc"
        print('Reading ' + ifname)

        ds = nc4.Dataset(ifname)

        x = ds['X'][:]
        y = np.flipud(ds['Y'][:])

        # Load all variables into dict
        vars_data = {v: ds[v][:] for v in var_names}

        nt = vars_data['AirT'].shape[0]

        for i in range(nt):

            row = {
                'Year': TS.year,
                'Month': TS.month,
                'Day': TS.day,
                'Hour': i if nt == 24 else np.nan
            }

            # Build interpolators for this timestep
            interps = {
                v: build_interpolator(x, y, vars_data[v][i, :, :])
                for v in var_names
            }

            # Interpolate all variables at once
            vals = interp_all_vars(interps, pt)

            # Map names to output keys
            row.update({
                'Precip': vals['Precip'],
                'Rain': vals['Rain'],
                'Snow': vals['Snow'],
                'AirT': vals['AirT'],
                'Pres': vals['Pres'],
                'RH': vals['RH'],
                'Wind': vals['WindSpeed'],
                'WindAngle': vals['WindDir'],
                'DSWRF': vals['Shortwave'],
                'DLWRF': vals['Longwave'],
                'PET': vals['PET']
            })

            data_out.append(row)

        ds = None

    # --- Elevation interpolation ---
    elev_interp = RegularGridInterpolator(
        (y, x),
        np.flipud(Elev_grid),
        bounds_error=False,
        fill_value=np.nan
    )
    Elev = elev_interp(pt)

    # --- Output ---
    if not os.path.exists(pars['OutputDir']):
        os.makedirs(pars['OutputDir'])

    OFName = f"{pars['OutputDir']}/{pars['StationName']} ({pars['ForcingSetName']}).csv"
    print('Writing ' + OFName)

    header = [
        'Year', 'Month', 'Day', 'Hour',
        'Precip', 'Rain', 'Snow', 'AirT',
        'Pres', 'RH', 'Wind', 'WindAngle',
        'DSWRF', 'DLWRF', 'PET'
    ]

    units = [
        '', '', '', '',
        'mm', 'mm', 'mm', 'C',
        'Pa', 'pct', 'm/s', 'degrees',
        'W/m2', 'W/m2', 'mm'
    ]

    with open(OFName, 'w', newline='') as csvfile:
        writer = csv.writer(csvfile)

        writer.writerow([
            pars['StationName'],
            pars['Latitude'],
            pars['Longitude'],
            int(Elev)
        ])

        writer.writerow(header)
        writer.writerow(units)

        for row in data_out:
            writer.writerow([row[h] for h in header])