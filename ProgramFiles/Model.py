import sys
import os
import subprocess
from osgeo import gdal, ogr, osr
from osgeo.gdalconst import *
import numpy as np
import tempfile
import copy
from scipy.io import savemat, loadmat
from scipy.special import expn
from datetime import datetime, date, timedelta
import netCDF4 as nc4
from scipy import interpolate
import itertools
import multiprocessing
import time
from scipy.signal import find_peaks
import csv
import time

# nodataval = -9999
dtype = 'float32'

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
    
    
def exec_cmd(cmd, Verbose):
    if Verbose:
        print('Executing command: ' + cmd)

        subprocess.call(cmd, shell=True)
    else:
        subprocess.call(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.STDOUT)
        
        
def daterange(start_date, end_date):
    for n in range(int((end_date - start_date).days)):
        yield start_date + timedelta(n)
        
# def daterange_hr(start_date, end_date):
    # start_date = datetime(start_date)
    # end_date = datetime(end_date)
    # for n in range(int((end_date - start_date).hours)):
        # yield start_date + timedelta(n)
        
# @profile        
def run_model(TileName, forcing_data, model_pars, program_pars):

    
    print('Running SnowPALM for ' + TileName)
    
    # Model Constants
    modelconst = {}
    modelconst['karman'] = 0.41  # Von karman constant
    modelconst['subheat'] = 2.85e6  # Latent heat of sublimation [J/kg]
    modelconst['fusheat'] = 3.34e5  # Latent heat of fusion [J/kg]
    modelconst['specheat_a'] = 1008  # Specific heat of air [J/kg-K]
    modelconst['specheat_w'] = 4181  # Specific heat of water [J/kg-K]
    modelconst['specheat_i'] = 2050  # Specific heat of ice [J/kg-K]
    modelconst['Rd'] = 287  # Dry gas constant [J kg-1 K-1]
    modelconst['g'] = 9.81  # Gravity at earth's surface [m/s2]
    modelconst['I0'] = 1388  # Solar constant [W/m2]
    modelconst['emiss_snow'] = 0.99  # Snow surface emmissivity [-]
    modelconst['sigma'] = 5.67E-8  # Stefan-Boltzmann constant [W/m2-k4]
    modelconst['M2MM'] = 1000  # Conversion factor between millimeters and meters [mm/m]
    if program_pars['ModelTimestep'] == 1:
        modelconst['TS'] = 86400  # Model Timestep [s]
    elif program_pars['ModelTimestep'] == 0:
        modelconst['TS'] = 3600  # Model Timestep [s]
        
    modelconst['DAY'] = 86400  # Conversion factor between seconds and days [s/day]
    modelconst['K'] = 273.15  # Conversion factor between celcius and kelvin
    modelconst['rhoi'] = 931  # density of ice   [kg/m3]
    modelconst['rhoa'] = 1.229  # density of air   [kg/m3]
    modelconst['rhow'] = 1000  # density of water [kg/m3]
    modelconst['P0'] = 101325  # Standard Sea level pressure [Pa]
    modelconst['L'] = 6.5E-3  # Standard Lapse Rate [K/m]
    modelconst['rhos'] = 1300  # density of soil   (kg/m3)
    modelconst['specheat_s'] = 1480  # specific heat of soil [J/kg-K]

    # Initialization

    #  Size of state (for simultaneous execution on multiple cells)
    sz = forcing_data['airt'][1, :].shape
    sz_3d = forcing_data['airt'].shape

    # Initialize snow states to zero
    state = {}

    state['swe'] = np.ones(sz) * model_pars['swe_i']  # SWE [mm]
    state['cansnowstor'] = np.ones(sz) * model_pars['cansnowstor_i']  # Canopy snow storage [mm]
    state['canrainstor'] = np.ones(sz) * model_pars['canrainstor_i']  # Canopy rain storage [mm]
    # state['swe_age_a'] = np.ones(sz) * model_pars['swe_age_a_i']  # Age of snowpack surface [day]
    state['albedosnow'] = np.ones(sz) * model_pars['albedosnow_i']  # Age of snowpack surface [day]
    Tm = np.ones(sz) * model_pars['Tm_i']  # Internal snowpack temperature [C]
    state['cc'] = Tm / ((np.maximum(1, state['swe']) / modelconst['M2MM']) * modelconst['rhow'] * modelconst['specheat_i'])  # Cold Content [J/m2]
    state['density'] = np.ones(sz) * model_pars['density_i']  # Snow Density [g/cm3]
    state['sm_stor'] = np.ones(sz) * model_pars['H'] * model_pars['sm_i']  # Amount of water in soil [mm]
    state['Q_soil'] = np.ones(sz) * model_pars['T_soil_i'] * ((state['sm_stor'] / 1000 * modelconst['specheat_w'] * modelconst['rhow']) + ((model_pars['H'] - state['sm_stor']) / 1000 * modelconst['specheat_s'] * modelconst['rhos']))  # Energy content of soil water
    state['ice_percent_soil'] = np.ones(sz) * model_pars['ice_percent_soil_i']  # Percent soil ice
    state['x_vadose'] = np.ones(sz) * model_pars['q_vadose_i'] / model_pars['coef_vadose']  # Water in Vadose Zone
    state['x_phreatic'] = np.ones(sz) * model_pars['q_phreatic_i'] / model_pars['coef_phreatic']  # Water in Phreatic Zone
    
    depth = state['swe'] / state['density']
    depth_p = depth

    sm_sat = model_pars['ssat'] * model_pars['H'] * np.ones(sz)  # Saturated soil water content
    sm_res = model_pars['sres'] * model_pars['H'] * np.ones(sz)
    cc_p = state['cc']  # Previous cold content
    # Tm = state['cc']/((np.maximum(1, state['swe']) / modelconst['M2MM']) * modelconst['rhow'] * modelconst['specheat_i'])

    # Initialize the model output variables based on the size of the forcing data
    model_output = {}
    model_output['swe'] = np.zeros(forcing_data['airt'].shape).astype(dtype)  # Snow Water Equivalent [mm]
    model_output['depth'] = np.zeros(forcing_data['airt'].shape).astype(dtype)  # Snow Depth [mm]
    model_output['density'] = np.zeros(forcing_data['airt'].shape).astype(dtype)  # Snow Density [g/cm3]
    model_output['rain_on_snow'] = np.zeros(forcing_data['airt'].shape).astype(dtype)  # Rain on Snow [mm/day]
    model_output['snowpack_sublimation'] = np.zeros(forcing_data['airt'].shape).astype(dtype)  # Sublimation (from snowpack) [mm/day]
    model_output['tfall'] = np.zeros(forcing_data['airt'].shape).astype(dtype)  # Rain throughfall (below canopy) [mm/day]
    model_output['tsfall'] = np.zeros(forcing_data['airt'].shape).astype(dtype)  # Snow throughfall (below canopy) [mm/day]
    model_output['snow_unload'] = np.zeros(forcing_data['airt'].shape).astype(dtype)  # Snow unloading (from canopy) [mm/day]
    model_output['melt_drip'] = np.zeros(forcing_data['airt'].shape).astype(dtype)  # Melt Drip (from canopy) [mm/day]
    model_output['canopy_sublimation'] = np.zeros(forcing_data['airt'].shape).astype(dtype)  # Sublimation (from canopy) [mm/day]
    model_output['canopy_snow_storage'] = np.zeros(forcing_data['airt'].shape).astype(dtype)  # Canopy Snow Storage [mm]
    model_output['canopy_evaporation'] = np.zeros(forcing_data['airt'].shape).astype(dtype)  # Evaporation (from canopy) [mm/day]
    model_output['drip'] = np.zeros(forcing_data['airt'].shape).astype(dtype)  # Evaporation (from canopy) [mm/day]
    model_output['canopy_rain_storage'] = np.zeros(forcing_data['airt'].shape).astype(dtype)  # Canopy Rain Storage [mm]
    model_output['melt'] = np.zeros(forcing_data['airt'].shape).astype(dtype)  # Snowmelt [mm/day]
    model_output['albedo'] = np.zeros(forcing_data['airt'].shape).astype(dtype)  # Surface albedo [-]
    model_output['Tm'] = np.zeros(forcing_data['airt'].shape).astype(dtype)  # Integrated snowpack temperature [C]
    model_output['Ts'] = np.zeros(forcing_data['airt'].shape).astype(dtype)  # Surface temperature [C]
    model_output['Qsd'] = np.zeros(forcing_data['airt'].shape).astype(dtype) # Incoming Shortwave Radiation (ground) [W/m2]
    model_output['Qld'] = np.zeros(forcing_data['airt'].shape).astype(dtype)  # Incoming Longwave Radiation (ground) [W/m2]
    model_output['Qse'] = np.zeros(forcing_data['airt'].shape).astype(dtype)  # Outgoing shortwave radiation (ground) [W/m2]
    model_output['Qle'] = np.zeros(forcing_data['airt'].shape).astype(dtype)  # Outgoing Longwave Radiation [W/m2]
    model_output['Qn'] = np.zeros(forcing_data['airt'].shape).astype(dtype)  # Net Radiation [W/m2]
    model_output['Qn_snow'] = np.zeros(forcing_data['airt'].shape).astype(dtype)  # Net Radiation over snowpack [W/m2]
    model_output['Qh'] = np.zeros(forcing_data['airt'].shape).astype(dtype)  # Sensible heat [W/m2]
    model_output['Qg'] = np.zeros(forcing_data['airt'].shape).astype(dtype)  # Ground heat [W/m2]
    model_output['Qe'] = np.zeros(forcing_data['airt'].shape).astype(dtype)  # Latent heat [W/m2]
    model_output['Qp'] = np.zeros(forcing_data['airt'].shape).astype(dtype)  # Heat from precip [W/m2]
    model_output['Qm'] = np.zeros(forcing_data['airt'].shape).astype(dtype)  # Melt heat [W/m2]
    model_output['Q'] = np.zeros(forcing_data['airt'].shape).astype(dtype)  # Cold Content [J/m2]
    model_output['T_soil'] = np.zeros(forcing_data['airt'].shape).astype(dtype)
    model_output['ice_percent_soil'] = np.zeros(forcing_data['airt'].shape).astype(dtype)
    model_output['ET'] = np.zeros(forcing_data['airt'].shape).astype(dtype)
    model_output['SMC'] = np.zeros(forcing_data['airt'].shape).astype(dtype)
    model_output['sm_stor'] = np.zeros(forcing_data['airt'].shape).astype(dtype)
    model_output['infil_runoff'] = np.zeros(forcing_data['airt'].shape).astype(dtype)
    model_output['sat_runoff'] = np.zeros(forcing_data['airt'].shape).astype(dtype)
    model_output['perc'] = np.zeros(forcing_data['airt'].shape).astype(dtype)
    model_output['caprise'] = np.zeros(forcing_data['airt'].shape).astype(dtype)
    model_output['infiltration'] = np.zeros(forcing_data['airt'].shape).astype(dtype)
    model_output['x_vadose'] = np.zeros(forcing_data['airt'].shape).astype(dtype)
    model_output['x_phreatic'] = np.zeros(forcing_data['airt'].shape).astype(dtype)
    model_output['q_vadose'] = np.zeros(forcing_data['airt'].shape).astype(dtype)
    model_output['q_phreatic'] = np.zeros(forcing_data['airt'].shape).astype(dtype)
    model_output['vadose_to_phreatic'] = np.zeros(forcing_data['airt'].shape).astype(dtype)
    
    NDays = forcing_data['airt'].shape[0]
    
    # st = time.time()
    # c = 0
    # print(forcing_data['airt'].shape)
    
    ## Main Time Loop
    for TS in range(NDays):
        # c = c+1
        # st = time.time()

        # Extract forcing data for a particular day
        airt = forcing_data['airt'][TS, :]              # Mean temperature [C]
        wind = forcing_data['wind'][TS, :]              # Wind speed [m/s]
        srad = forcing_data['srad'][TS, :]              # Solar radiation [W/m2]
        sfi = forcing_data['sfi'][TS, :]                # Solar radiation [W/m2]
        lrad = forcing_data['lrad'][TS, :]              # Incoming longwave radiation [W/m2]
        vapp = forcing_data['vapp'][TS, :]              # Vapor Pressure [pa]
        rainfall = forcing_data['rainfall'][TS, :]      # Rainfall [mm]
        snowfall = forcing_data['snowfall'][TS, :]      # Snowfall [mm]
        snowfall_0 = forcing_data['snowfall_0'][TS, :]  # Snowfall [mm]
        PET = forcing_data['PET'][TS, :]                # Potential Evaporation [mm]
        doy = forcing_data['doys'][TS]                  # Potential Evaporation [mm]
        rainfall[rainfall<0] = 0
        snowfall[snowfall<0] = 0
        snowfall_0[snowfall_0<0] = 0
        
        svapp = 0.6108 * np.exp(17.27 * airt / (237.3 + airt)) * 1000
        rh = vapp/svapp*100
        rh[rh > 100] = 100

        swe_p = state['swe']  # Previous SWE
        depth = state['swe'] / state['density']

        ## Albedo

        frac_summer = (np.sin(np.deg2rad(doy-85))+1)/2
        nosnowalbedo = model_pars['NoSnowAlbedo_winter']*(1-frac_summer)+model_pars['NoSnowAlbedo_summer']*frac_summer;
        
        snowfall_depth = snowfall / model_pars['density_min']
        snowfall_locs = snowfall_depth > 0
        factor = snowfall_depth / model_pars['Snowfall_factor']
        factor[factor > 1] = 1
        state['albedosnow'][snowfall_locs] = state['albedosnow'][snowfall_locs] * (1-factor[snowfall_locs]) + model_pars['MaxAlbedo'] * factor[snowfall_locs]
        state['albedosnow'][airt < 0] = state['albedosnow'][airt < 0] - model_pars['albedo_decay_cold'] * modelconst['TS'] / modelconst['DAY']
        state['albedosnow'][airt > 0] = state['albedosnow'][airt > 0] - model_pars['albedo_decay_warm'] * modelconst['TS'] / modelconst['DAY']
        state['albedosnow'][state['albedosnow'] < model_pars['minalbedo']] = model_pars['minalbedo']
        albedosnow = state['albedosnow'] ** (sfi ** model_pars['albedo_enh_red'])
        
        snowfrac = np.minimum(1, depth / (model_pars['groundveght'] * 1000))
        albedo = snowfrac * albedosnow + (1 - snowfrac) * nosnowalbedo
        
        ## Net Radiation

        # Net shortwave radiation
        Qsn = srad * (1 - albedo)

        # Incoming longwave radiation (given as forcing variable)
        Qli = lrad

        Ts_nosnow = airt + 0.0192 * (Qsn + Qli) - 0.0428 * rh - 4.1790
        Ts_snow = np.minimum(0, airt + 0.0258 * (Qsn + Qli) + 0.0648 * rh - 14.5601)
        Ts = Ts_snow * snowfrac + Ts_nosnow * (1 - snowfrac)

        # Computed based on snow temperature
        Qle = modelconst['emiss_snow'] * modelconst['sigma'] * (Ts + modelconst['K']) ** 4

        # Net Radiation
        Qn = Qsn + Qli - Qle

        ## Architectural resistance

        # Resistance for equilibrium conditions
        k0 = modelconst['karman'] ** 2 * wind / (np.log(model_pars['windlevel'] / model_pars['sroughness'])) ** 2

        # Richardson number (for stability correction)
        Ri = modelconst['g'] * (airt - Ts) * model_pars['windlevel'] / np.maximum(1E-14,(wind **2 * airt))
        ka = k0
        ka[Ri > 0] = ka[Ri > 0] / (1 + 10 * Ri[Ri > 0])
        ka[Ri < 0] = ka[Ri < 0] * (1 - 10 * Ri[Ri < 0])
        ka = k0 + model_pars['fstab'] * (ka - k0)

        ## Sensible heat flux

        # Estimate how air density changes with altitude by assuming a station pressure based on elevation
        pres = modelconst['P0'] * np.exp(-modelconst['g'] * model_pars['elevation'] / (modelconst['Rd'] * (airt + modelconst['K'] + modelconst['L'] * model_pars['elevation'])))
        rhoa = pres / (modelconst['Rd'] * (airt + modelconst['K']))

        Qh = ka * rhoa * modelconst['specheat_a'] * (airt - Ts) * model_pars['Ch']

        ## Latent heat flux and Sublimation

        # Saturated vapor pressure
        svapp = 0.6108 * np.exp(17.27 * Ts_nosnow / (237.3 + Ts_nosnow)) * 1000

        # Sublimation heat
        Qe = k0 * (modelconst['subheat'] * 0.622) / (modelconst['Rd'] * (airt + modelconst['K'])) * (vapp - svapp)
        Qe[Qe > 0] = 0  # Limit to mass losses

        # Convert to actual sublimation amount, later we will need to adjust if SWE is not enough
        sublimation_potential = -(Qe / (modelconst['subheat'] * modelconst['rhow'])) * modelconst['TS'] * modelconst['M2MM']

        # Canopy Snow Interception

        # Canopy Storage capacity
        cansnowstorcap = model_pars['C_S_cap_mult'] * model_pars['lai']  # model_pars['lai']: Leaf area index (mm/mm)

        # Snow that is caught in canopy
        
        L = 0.7 * (cansnowstorcap - state['cansnowstor']) * (1 - np.exp(-snowfall_0 / (cansnowstorcap + 1E-5)))
        L[np.isnan(L)] = 0  # Throughfall is snow that falls through canopy
        tsfall = snowfall_0 - L
        state['cansnowstor'] = state['cansnowstor'] + L
         
        # Snow Drip Rate
        melt_drip = np.maximum(0, model_pars['melt_drip_par'] * airt)
        # model_pars['melt_drip_par']: Melt Drip Rate (mm/day / deg-C above freezing
        
        # Snow Unloading from the canopy
        snow_unload = np.maximum(model_pars['snow_unload_par'] * state['cansnowstor'] * modelconst['TS'] / modelconst['DAY'], 0)  # Snow Unload Rate
        # model_pars['snow_unload_par']:
        
        # Canopy sublimation

        r = 5E-4
        a = 0.9
        C_e = 0.01 * (state['cansnowstor'] / (cansnowstorcap + 1E-6)) ** 0.4    # Calculate Canopy Sublimation
        C_e[np.isnan(C_e)] = 0
        m = modelconst['rhoi'] * 4/3 * np.pi * r ** 3                       # Mass of Ice Sphere (kg)
        rho_v = 0.622 * vapp / (287 * (airt + modelconst['K']))        # Water Vapor Density (kg/m3)
        S_p = np.pi * r ** 2 * (1-a) * srad                                 # Radiation absorbed by partical (W/m2)
        D = 2.06E-5 * ((airt + modelconst['K'])/modelconst['K']) ** 1.75 # Diffusivity of air (m2/s)
        nu = 1.3E-5                                                   # Kinematic viscosity of air (m2/s)
        a_flow = 0.9 * model_pars['lai']                               # Canopy flow index
        u_c = wind * np.exp(-a_flow * (1-0.6))                           # ventilation velocity
        Re = 2 * r * u_c/nu                                           # Reynolds number
        Sh = 1.79 + 0.606 * Re ** 0.5                                 # Sherwood number
        Nu = Sh                                                       # Nusset number
        M = 18.01E-3                                                  # Molecular weight of water(kg/mol)
        k_t = 0.024                                                   # Thermal conductivity of air (W/m2-K)
        R_const = 8314                                                # Universal gas constant (J/mol-K)
    
        omega = (1 / (k_t * (airt + modelconst['K']) * Nu)) * ((modelconst['subheat'] * M) / (R_const * (airt + modelconst['K'])) -1)        # Ventilation factor
        dmdt = (2*np.pi*r*((vapp/svapp)-1) - S_p * omega) / (modelconst['subheat'] * omega + 1 / (D * rho_v * Sh))
        psi_s = dmdt/m
        # Sublimation rate loss coefficient
        acsub = np.real(np.maximum(0,-C_e * state['cansnowstor'] * psi_s * modelconst['TS'])*model_pars['canopy_sub_mult'])
        acsub[np.isnan(acsub)] = 0

        # Figure out total ablation demand, and scale based on how much snow is
        # available (to avoid over-emptying of canopy snow storage)
        
        p_canopy_abl = acsub + melt_drip + snow_unload
        
        multiplier = state['cansnowstor'] / (np.maximum(1E-6,p_canopy_abl))
        multiplier[multiplier > 1] = 1
        melt_drip = melt_drip * multiplier
        snow_unload = snow_unload * multiplier
        acsub = acsub * multiplier

        # Revised canopy snow storage
        state['cansnowstor'] = np.maximum(0, state['cansnowstor'] - acsub - melt_drip - snow_unload)  # Subtract evaporated snow from the canopy

        # If canopy snow storage is exceeded (e.g. due to deposition), then unload
        snow_unload = snow_unload + np.maximum(0, state['cansnowstor'] - cansnowstorcap)
        
        # Canopy Rain Storage capacity
        canrainstorcap = model_pars['inter_cap_mult'] * model_pars['lai']  # model_pars['lai']: Leaf area index (mm/mm)
        L_r = 0.7 * (canrainstorcap - state['canrainstor']) * (1 - np.exp(-rainfall / (canrainstorcap + 1E-5)))
        tfall = rainfall - L_r
        state['canrainstor'] = state['canrainstor'] + L_r
        
        drip = model_pars['drip_par']
        canevap = model_pars['canevappar'] * PET
        
        p_canopy_abl_r = canevap + drip
        multiplier = state['canrainstor'] / (np.maximum(1E-6,p_canopy_abl_r))
        multiplier[multiplier > 1] = 1
        drip = drip * multiplier
        canevap = canevap * multiplier
        state['canrainstor'] = np.maximum(0, state['canrainstor'] - drip - canevap)
        drip = drip + np.maximum(0, state['canrainstor'] - canrainstorcap)
        # tfall = tfall + drip + melt_drip
        # tfall[np.isnan(tfall)] = 0
        # tfall[tfall < 0] = 0

        # Add all solid and liquid precipitation to SWE
        rain_on_snow = tfall + drip + melt_drip
        rain_on_snow[np.logical_and(state['swe'] == 0, snowfall == 0)] = 0
        state['swe'] = state['swe'] + tsfall + rain_on_snow + snow_unload

        # Heat from precip

        Qp_r = ((tfall + drip + melt_drip) / (modelconst['M2MM'] * modelconst['TS'])) * (modelconst['fusheat'] * modelconst['rhow'] + modelconst['specheat_w'] * modelconst['rhow'] * np.maximum(0, airt))
        Qp_s = ((tsfall + snow_unload) / (modelconst['M2MM'] * modelconst['TS'])) * (modelconst['specheat_i'] * modelconst['rhow'] * np.minimum(0, airt))
        Qp = Qp_s + Qp_r

        # Ground Heat
        Qg = model_pars['kappa_snow'] * (model_pars['tempdampdepth'] - Tm) / (model_pars['H'] / modelconst['M2MM'] + (swe_p / state['density']) / (2 * modelconst['M2MM']))

        # Adjust if not enough SWE
        sublimation_potential = sublimation_potential * model_pars['ground_sub_mult']
        sublimation = np.minimum(state['swe'], sublimation_potential)
        locs = np.logical_and(snowfall > 0 , sublimation > model_pars['max_sub_pct_when_snow']*snowfall)
        sublimation[locs] = model_pars['max_sub_pct_when_snow']*snowfall[locs]
        state['swe'] = state['swe'] - sublimation

        # Recompute sublimation heat and melt heat
        Qe = -sublimation * (modelconst['subheat'] * modelconst['rhow']) / (modelconst['TS'] * modelconst['M2MM'])
        
        # # Melt

        # Potential melt based on known energy inputs
        pdq = -np.maximum(0, state['cc'] + (Qn + Qe + Qh + Qp + Qg) * modelconst['TS'])
        melt_potential = -pdq / (modelconst['rhow'] * modelconst['fusheat']) * modelconst['M2MM']

        # Adjust if not enough SWE
        melt = np.minimum(state['swe'], melt_potential)
        locs = np.logical_and(snowfall > 0 , melt > model_pars['max_melt_pct_when_snow']*snowfall+rain_on_snow)
        melt[locs] = model_pars['max_melt_pct_when_snow']*snowfall[locs]+rain_on_snow[locs]
        state['swe'] = state['swe'] - melt

        # Recompute sublimation heat and melt heat
        Qm = (-melt / modelconst['M2MM']) * (modelconst['rhow'] * modelconst['fusheat']) / modelconst['TS']

        # Frozen soil model
        ice_soil_0 = state['ice_percent_soil'] * model_pars['H']
        T_soil = state['Q_soil'] / ((state['sm_stor'] / 1000 * modelconst['specheat_w'] * modelconst['rhow']) + ((model_pars['H'] - state['sm_stor']) / 1000 * modelconst['specheat_s'] * modelconst['rhos']))
        g_abv = model_pars['kappa_soil'] / (model_pars['H'] / 2 / 1000) * (Ts - T_soil) * modelconst['TS']
        g_blw = model_pars['kappa_soil'] / (model_pars['dampdepth'] - (model_pars['H'] / 2 / 1000)) * (model_pars['tempdampdepth'] - T_soil) * modelconst['TS']
        g_abv_snow = -Qg * modelconst['TS']
        g_abv[state['swe'] > 0] = 0
        g_abv_snow[state['swe'] <= 0] = 0
        g_abv = g_abv + g_abv_snow
        p_dQ = (g_abv + g_blw)
        gtlocs = state['Q_soil'] > 0
        ltlocs = state['Q_soil'] < 0
        Q_soil_gtlocs = np.maximum(0, state['Q_soil'] + p_dQ)
        Q_soil_ltlocs = np.minimum(0, state['Q_soil'] + p_dQ)
        Q_soil_gtlocs[gtlocs == 0] = 0
        Q_soil_ltlocs[ltlocs == 0] = 0
        Q_soil = Q_soil_gtlocs + Q_soil_ltlocs
        residual = state['Q_soil'] + p_dQ - Q_soil
        soil_melt = (residual / (modelconst['rhow'] * modelconst['fusheat'])) * 1000

        p_ice_soil = state['sm_stor']
        ice_soil_0 = ice_soil_0 - soil_melt
        ice_soil = np.maximum(0, np.minimum(p_ice_soil, ice_soil_0))
        residual = ice_soil - ice_soil_0
        Q_soil = Q_soil + residual * (modelconst['rhow'] * modelconst['fusheat']) / 1000

        state['Q_soil'] = Q_soil
        state['ice_percent_soil'] = ice_soil / (model_pars['H'])
        T_soil = state['Q_soil'] / ((state['sm_stor'] / 1000 * modelconst['specheat_w'] * modelconst['rhow']) + ((model_pars['H'] - state['sm_stor']) / 1000 * modelconst['specheat_s'] * modelconst['rhos']))
        
        # Snow Density

        # Reduce density based on new snow depth relative to old snow depth
        depth_p = swe_p / state['density']
        new_depth = np.maximum(1E-6, snowfall / model_pars['density_min'])
        # model_pars['density_min']: Density of fresh snowfall [g/cm3]

        new_frac = new_depth / (depth_p + new_depth)
        density_p = state['density']
        state['density'] = (1 - new_frac) * density_p + new_frac * model_pars['density_min']

        # Densify snowpack based on age, overburdin, and warm snowpacks
        state['density'] = state['density'] + ((model_pars['density_max'] - density_p) * model_pars['apar'] * modelconst['TS'] / modelconst['DAY'])
        state['density'] = state['density'] + ((model_pars['density_max'] - density_p) * model_pars['dpar'] * state['swe'] / 10 * modelconst['TS'] / modelconst['DAY'])
        state['density'] = state['density'] + ((model_pars['density_max'] - density_p) * model_pars['rpar'] * (Ts >= 0) * modelconst['TS'] / modelconst['DAY'])
        # model_pars['rpar']: Snow densfication rate due to liquid in snowpack [Fraction when isothermal snowpack]
        if len(model_pars['density_min']) > 1:
            state['density'][state['density'] > model_pars['density_max']] = model_pars['density_max'][state['density'] > model_pars['density_max']]
        else:
            state['density'][state['density'] > model_pars['density_max']] = model_pars['density_max']

        if len(model_pars['density_min']) > 1:
            state['density'][state['density'] < model_pars['density_min']] = model_pars['density_min'][state['density'] < model_pars['density_min']]
        else:
            state['density'][state['density'] < model_pars['density_min']] = model_pars['density_min']

        depth = state['swe'] / state['density']
        density = state['density'] * 1
        density[state['swe'] == 0] = np.nan

        # Clean up, prepare for next iteration, and fill output structure

        # Tm = (np.minimum(0, Ts * model_pars['k_avg'] + T_soil * (1 - model_pars['k_avg'])))
        # state['cc'] = Tm * (state['swe'] / modelconst['M2MM']) * modelconst['rhow'] * modelconst['specheat_i']
        # Tm[state['swe'] == 0] = 0
        
        # Isolate net radiation above snow in new variable
        Qn_snow = Qn * 1
        Qn_snow[state['swe'] == 0] = 0
        
        Tm_min = np.minimum(0,Ts)
        cc_min = Tm_min * (state['swe'] / modelconst['M2MM']) * modelconst['rhow'] * modelconst['specheat_i']
        cc_i = cc_p + (Qn_snow + Qh + Qe + Qp + Qm + Qg) * modelconst['TS']
        state['cc'] = np.minimum(0,np.maximum(cc_min,cc_i))
        Tm = state['cc'] / np.maximum(1E-6,((state['swe'] / modelconst['M2MM']) * modelconst['rhow'] * modelconst['specheat_i']))
        Tm[state['swe'] == 0] = 0

        
        # Make sure that when SWE is zero, heats are not reported
        state['cc'][state['swe'] == 0] = 0
        state['cc'][state['cc'] > 0] = 0
        Qe[state['swe'] == 0] = 0
        Qp[state['swe'] == 0] = 0
        Qm[state['swe'] == 0] = 0
        Qg[state['swe'] == 0] = 0
        Qh[state['swe'] == 0] = 0
        density[state['swe'] == 0] = 0

        # Compute energy imbalance caused by above acounting and add to sensible heat term
        imbal = ((state['cc'] - cc_p) - (Qn_snow + Qh + Qe + Qp + Qm + Qg) * modelconst['TS']) / modelconst['TS']
        Qh = Qh + imbal
        cc_p = state['cc']

        # Compute Infiltration excess runoff
        net_input = tfall + drip + melt_drip + melt - rain_on_snow
        infil_runoff = net_input * model_pars['max_infil_mult'] * (np.maximum(0, state['sm_stor'] - model_pars['sm_max_infil']) / (sm_sat - model_pars['sm_max_infil']))
        net_input = net_input - infil_runoff
        state['sm_stor'] = state['sm_stor'] + net_input

        # Compute actual ET
        et = PET * ((state['sm_stor'] / model_pars['H']) - model_pars['wp']) / (model_pars['cmc'] - model_pars['wp'])

        
        # Compute deep percolation
        # state['sm_stor'] = np.maximum(0, state['sm_stor'] - et)
        sat_runoff = np.maximum(0, state['sm_stor'] - sm_sat)
        # state['sm_stor'] = state['sm_stor'] - sat_runoff
        
        perc = np.minimum(state['sm_stor'] / 3, model_pars['k_soil'] * (np.maximum(0, (state['sm_stor']-sm_res) / (sm_sat-sm_res))) ** (2 * model_pars['b_soil'] + 3)) * modelconst['TS'] / modelconst['DAY']
        
        bw = 1-(state['sm_stor']-sm_res) / (sm_sat-sm_res)
        bw[bw < 0] = 0
        bw[bw > 1] = 1
        beta = 2 + 3/model_pars['b_soil']
        alpha = 1 + (3/2) / (beta -1);
        caprise = bw * model_pars['k_soil'] * alpha * (model_pars['psi_s'] / (model_pars['H']) ** beta ) * modelconst['TS'] / modelconst['DAY']
        locs = caprise > (sm_sat-state['sm_stor']-perc)
        caprise[locs] = sm_sat[locs]-state['sm_stor'][locs] - perc[locs]
        locs = caprise > (state['x_vadose'] + perc)
        caprise[locs] = state['x_vadose'][locs] + perc[locs]
        
        
        state['sm_stor'] = state['sm_stor'] - perc + caprise - et - sat_runoff
        # state['x_vadose'] = state['x_vadose'] + perc - caprise
        q_vadose = model_pars['coef_vadose'] * state['x_vadose'] * modelconst['TS'] / modelconst['DAY']
        state['x_vadose'] = state['x_vadose'] - q_vadose
        vadose_to_phreatic = model_pars['coef_vadose2phreatic'] * state['x_vadose'] * modelconst['TS'] / modelconst['DAY']
        state['x_vadose'] = state['x_vadose'] + perc - caprise - vadose_to_phreatic

        
        # state['x_phreatic'] = state['x_phreatic']
        q_phreatic = model_pars['coef_phreatic'] * state['x_phreatic'] * modelconst['TS'] / modelconst['DAY']
        state['x_phreatic'] = state['x_phreatic'] - q_phreatic + vadose_to_phreatic

        model_output['x_vadose'][TS, :] = state['x_vadose']
        model_output['x_phreatic'][TS, :] = state['x_phreatic']
        model_output['q_vadose'][TS, :] = q_vadose
        model_output['q_phreatic'][TS, :] = q_phreatic

        model_output['ET'][TS, :] = et
        model_output['SMC'][TS, :] = state['sm_stor'] / model_pars['H'] * 100
        model_output['sm_stor'][TS, :] = state['sm_stor']
        model_output['infil_runoff'][TS, :] = infil_runoff
        model_output['sat_runoff'][TS, :] = sat_runoff
        model_output['perc'][TS, :] = perc
        model_output['caprise'][TS, :] = caprise
        infiltration = net_input
        model_output['infiltration'][TS, :] = infiltration
        model_output['vadose_to_phreatic'][TS, :] = vadose_to_phreatic

        model_output['swe'][TS, :] = state['swe']  # Snow Water Equivalent [mm]
        model_output['depth'][TS, :] = depth  # Snow Depth [mm]
        model_output['density'][TS, :] = density  # Snow Density [g/cm3]
        model_output['rain_on_snow'][TS, :] = rain_on_snow - melt_drip  # Rain on Snow [mm/day], only consider rain contribution
        model_output['snowpack_sublimation'][TS, :] = sublimation  # Sublimation (from snowpack) [mm/day]
        model_output['tfall'][TS, :] = tfall  # Rain throughfall (below canopy) [mm/day]
        model_output['tsfall'][TS, :] = tsfall  # Snow throughfall (below canopy) [mm/day]
        model_output['snow_unload'][TS, :] = snow_unload  # Snow unloading (from canopy) [mm/day]
        model_output['melt_drip'][TS, :] = melt_drip  # Melt Drip (from canopy) [mm/day]
        model_output['canopy_sublimation'][TS, :] = acsub  # Sublimation (from canopy) [mm/day]
        model_output['canopy_evaporation'][TS, :] = canevap  # Evaporation (from canopy) [mm/day]
        model_output['drip'][TS, :] = drip  # Evaporation (from canopy) [mm/day]
        model_output['canopy_snow_storage'][TS, :] = state['cansnowstor']  # Canopy Snow Storage [mm]
        model_output['canopy_rain_storage'][TS, :] = state['canrainstor']  # Canopy Rain Storage [mm]
        model_output['melt'][TS, :] = melt  # Snowmelt [mm/day]
        model_output['albedo'][TS, :] = albedo  # Surface albedo [-]
        Tm_out = copy.deepcopy(Tm)
        Tm_out[state['swe'] == 0] = 0
        model_output['Tm'][TS, :] = Tm_out  # Integrated snowpack temperature [C] (0 if no snow)
        model_output['Ts'][TS, :] = Ts  # Surface temperature [C]'
        Qsd = srad
        Qld = lrad
        Qse = Qsd - Qsn
        model_output['Qsd'][TS, :] = Qsd  # Incoming Shortwave Radiation (ground) [W/m2]
        model_output['Qld'][TS,] = Qld    # Incoming Longwave Radiation (ground) [W/m2]
        model_output['Qse'][TS, :] = Qse  # Outgoing shortwave radiation (ground) [W/m2]
        model_output['Qle'][TS,] = Qle  # Outgoing Longwave Radiation (ground) [W/m2]
        model_output['Qn'][TS, :] = Qn  # Net Radiation [W/m2]
        model_output['Qn_snow'][TS, :] = Qn_snow  # Net Radiation over snowpack [W/m2]
        model_output['Qh'][TS, :] = Qh  # Sensible and ground heat [W/m2]
        model_output['Qg'][TS, :] = Qg  # Ground heat [W/m2]
        model_output['Qe'][TS, :] = Qe  # Latent heat [W/m2]
        model_output['Qp'][TS, :] = Qp  # Heat from precip [W/m2]
        model_output['Qm'][TS, :] = Qm  # Melt heat [W/m2]
        model_output['Q'][TS, :] = state['cc']  # Cold Content [J/m2]
        model_output['T_soil'][TS, :] = T_soil
        model_output['ice_percent_soil'][TS, :] = state['ice_percent_soil'] * 100
        
        # print(time.time()-st)
        # sys.exit()
        
    # print((time.time()-st)/c)

    return model_output


def solar_zenith(lat_deg, day_of_year, hour_local_solar):

    # Ensure dimensions
    lat_deg = np.asarray(lat_deg)[None, :]          # (1, nspace)
    day_of_year = np.asarray(day_of_year)[:, None] # (ntime, 1)
    hour_local_solar = np.asarray(hour_local_solar)[:, None]

    # Convert latitude to radians
    lat = np.radians(lat_deg)

    # Solar declination
    decl = np.radians(
        23.44 * np.sin(2 * np.pi * (day_of_year - 81) / 365)
    )

    # Hour angle
    hour_angle = np.radians(
        15 * (hour_local_solar - 12)
    )

    # Cosine of solar zenith angle
    cosz = (
        np.sin(lat) * np.sin(decl)
        + np.cos(lat) * np.cos(decl) * np.cos(hour_angle)
    )

    cosz = np.clip(cosz, -1, 1)

    # Zenith angle
    sza = np.degrees(np.arccos(cosz))

    return sza
    
def get_forcing_data(TileName, ForcingFName, IndexFName, model_pars, program_pars):

    print('Getting Forcing Data for ' + TileName)
    
    # Model Constants
    modelconst = {}
    modelconst['emiss_c'] = 0.97  # Canopy emmissivity [-]
    
    doys = []
    hours = []
    if program_pars['ModelTimestep'] == 1:
        for TS in daterange(program_pars['StartDate'], program_pars['EndDate'] + timedelta(days=1)):
            doys.append(TS.timetuple().tm_yday)
            hours.append(12)
    elif program_pars['ModelTimestep'] == 0:
        for TS in daterange(program_pars['StartDate'], program_pars['EndDate'] + timedelta(days=1)):
            for h in range(24):
               doys.append(TS.timetuple().tm_yday) 
               hours.append(h)
               
    doys = np.array(doys)
    hours = np.array(hours)
    
    ds = nc4.Dataset(ForcingFName)
    AirT = ds['AirT'][:].astype(dtype)
    RH = ds['RH'][:].astype(dtype)
    Pres = ds['Pres'][:].astype(dtype)
    WindSpeed = ds['WindSpeed'][:].astype(dtype)
    WindDir = ds['WindDir'][:].astype(dtype)
    Shortwave = ds['Shortwave'][:].astype(dtype)
    Longwave = ds['Longwave'][:].astype(dtype)
    Precip = ds['Precip'][:].astype(dtype)
    Rain = ds['Rain'][:].astype(dtype)
    Snow = ds['Snow'][:].astype(dtype)
    PET = ds['PET'][:].astype(dtype)
    ds = None
    
    ds = nc4.Dataset(IndexFName)
    Lat = ds['Lat'][:].astype(dtype)
    LAI = ds['LAI'][:].astype(dtype)
    Elev = ds['Elev'][:].astype(dtype)
    Skyview = ds['Skyview'][:].astype(dtype)
    LWI = ds['LWI'][:].astype(dtype)
    SFI_Direct_UnderCanopy = ds['SFI_Direct_UnderCanopy'][:].astype(dtype)
    SFI_Diffuse_UnderCanopy = ds['SFI_Diffuse_UnderCanopy'][:].astype(dtype)
    SFI_Direct_NoVeg = ds['SFI_Direct_NoVeg'][:].astype(dtype)
    SFI_Diffuse_NoVeg = ds['SFI_Diffuse_NoVeg'][:].astype(dtype)
    SnowfallIndex_WithVeg = ds['SnowfallIndex_WithVeg'][:].astype(dtype)
    SnowfallIndex_NoVeg = ds['SnowfallIndex_NoVeg'][:].astype(dtype)
    ds = None
    
    # SFI_Direct_UnderCanopy = SFI_Direct_UnderCanopy ** 3
    
    AirT = AirT + model_pars['airt_adj']
    RH = np.minimum(RH * model_pars['rh_mult'],100)
    
    nt, nd = AirT.shape
    
    esat = 0.6108 * np.exp(17.27 * AirT / (237.3 + AirT)) * 1000    # Saturated vapor pressure (Pa)
    vapp = esat * (RH/100)
    
    # Partition Rainfall and Snowfall
    # Use a rainfall threshold (smooth function from T+1 to T-1)
    dh = 1
    rainthresh_tmax = model_pars['RainThresh'] + model_pars['RainThresh_dh']/2
    rainthresh_tmin = model_pars['RainThresh'] - model_pars['RainThresh_dh']/2
    dx = rainthresh_tmax - rainthresh_tmin
    T = AirT
    # rainthresh_tmax = np.tile(rainthresh_tmax,[nt,1])
    # rainthresh_tmin = np.tile(rainthresh_tmin,[nt,1])
    f_s = 1 - ((dh/dx) * (T-rainthresh_tmin) - (dh * np.sin((2*np.pi/dx) * (T-rainthresh_tmin))) / (2*np.pi))
    f_s[f_s < 0] = 0
    f_s[f_s > 1] = 1

    Rain_filled = Precip * (1-f_s)  # daily rainfall amount (mm of water) 
    Snow_filled = Precip * f_s      # daily snowfall amount (mm of water) 

    Rain[np.isnan(Rain)] = Rain_filled[np.isnan(Rain)]
    Snow[np.isnan(Snow)] = Snow_filled[np.isnan(Snow)]

    snow_mult = np.tile(model_pars['snow_mult'],[nt,1])
    Snow_0 = Snow * snow_mult
    
    # snowfall_wind_trans = np.tile(model_pars['snowfall_wind_trans'],[nt,1])
    # snowfall_wind_exp = np.tile(model_pars['snowfall_wind_exp'],[nt,1])
    Snow = Snow * ((1-model_pars['snowfall_wind_trans']) * SnowfallIndex_WithVeg + model_pars['snowfall_wind_trans'] * SnowfallIndex_NoVeg) ** model_pars['snowfall_wind_exp']

    # Apply the snowfall multiplier if specified
    
    Snow = Snow * snow_mult

    # Apply multiplier to shortwave radiation if specified
    
    srad_mult = np.minimum(model_pars['srad_mult_summer'], np.tile(np.reshape((np.sin(np.deg2rad(doys-85))+1)/2, [nt, 1]), [1, nd]) * (model_pars['srad_mult_summer'] - model_pars['srad_mult_winter']) + model_pars['srad_mult_winter'])
    Shortwave = Shortwave * srad_mult
    
    # Apply multiplier to longwave radiation if specified
    lrad_mult = np.minimum(model_pars['lrad_mult_summer'], np.tile(np.reshape((np.sin(np.deg2rad(doys-85))+1)/2, [nt, 1]), [1, nd]) * (model_pars['lrad_mult_summer'] - model_pars['lrad_mult_winter']) + model_pars['lrad_mult_winter'])
    Longwave = Longwave * lrad_mult
        
    # Apply the PET multiplier if specified
    PET = PET * model_pars['PET_Mult']
    
    # Potential solar radiation and solar forcing index
    
    CF = np.zeros(Shortwave.shape)
    import time
    start = time.time()
    for i in range(nd):
        x = Shortwave[:, 0]
        if program_pars['ModelTimestep'] == 0:
            peaks, _ = find_peaks(x, distance=360)
            PotentialShortwave_max = np.interp(range(nt), peaks, x[peaks])
            peaks, _ = find_peaks(x)
            PotentialShortwave_actual = np.interp(range(nt), peaks, x[peaks])
            CF[:,i] = PotentialShortwave_actual/PotentialShortwave_max
        elif program_pars['ModelTimestep'] == 1:
            peaks, _ = find_peaks(x, distance=15)
            PotentialShortwave_max = np.interp(range(nt), peaks, x[peaks])
            CF[:,i] = Shortwave[:,i]/PotentialShortwave_max
            
    CF[CF > 1] = 1
    Diffuse_fr = model_pars['diffuse_fr_0'] + (1 - CF) * (1-model_pars['diffuse_fr_0'])
    DiffuseShortwave = Shortwave * Diffuse_fr
    DirectShortwave = Shortwave * (1-Diffuse_fr)
    
    Longwave_UnderCanopy = np.zeros(Longwave.shape) * np.nan
    DiffuseShortwave_UnderCanopy = np.zeros(Shortwave.shape) * np.nan
    DirectShortwave_UnderCanopy = np.zeros(Shortwave.shape) * np.nan
    
    zenith = np.minimum(90,solar_zenith(Lat, doys.T, hours.T))
    b = 0.5
    G = 0.5
    Kb = np.maximum(1E-8,G/np.cos(np.deg2rad(zenith)))
    LAImax = model_pars['LF_trans']
    k = np.sqrt(1-b)
    shortwave_trans_direct = np.exp(-k*Kb*LAImax)
    
    DirectShortwave_UnderCanopy = (1-shortwave_trans_direct) * SFI_Direct_UnderCanopy * DirectShortwave + shortwave_trans_direct * SFI_Direct_NoVeg * DirectShortwave
    
    GLF = G*LAImax
    Tau_d = (1-k*GLF)*np.exp(-k*GLF) + ((k*GLF)**2)*expn(1,k*GLF)
    
    Tc = AirT
    Longwave_UnderCanopy = Skyview * Longwave + (1-Skyview) * (((1-Tau_d) * modelconst['emiss_c'] * 5.67E-8 * (Tc+273.15) ** 4) + Tau_d * Longwave)
    Longwave_UnderCanopy = Longwave_UnderCanopy + LWI * Shortwave * model_pars['lwi_par']

    DiffuseShortwave_UnderCanopy = (1-Tau_d) * SFI_Diffuse_UnderCanopy * DiffuseShortwave + Tau_d * SFI_Diffuse_NoVeg * DiffuseShortwave
   
    
    # from matplotlib import pyplot as plt
    # print(Tau_d)
    # plt.plot(shortwave_trans_direct[:,0])
    # plt.show()
    # sys.exit()
    

    ## Put data in output structure
    forcing_data = {}
    forcing_data['airt'] = np.array(AirT).astype(dtype)
    forcing_data['wind'] = np.array(WindSpeed).astype(dtype)
    forcing_data['srad'] = np.array(DirectShortwave_UnderCanopy + DiffuseShortwave_UnderCanopy).astype(dtype)
    forcing_data['srad_0'] = np.array(Shortwave).astype(dtype)
    forcing_data['sfi'] = np.array((DirectShortwave_UnderCanopy + DiffuseShortwave_UnderCanopy)/Shortwave).astype(dtype)
    forcing_data['lrad'] = np.array(Longwave_UnderCanopy).astype(dtype)
    forcing_data['lrad_0'] = np.array(Longwave).astype(dtype)
    forcing_data['vapp'] = np.array(vapp).astype(dtype)
    forcing_data['rh'] = np.array(RH).astype(dtype)
    forcing_data['rainfall'] = np.array(Rain).astype(dtype)
    forcing_data['snowfall'] = np.array(Snow).astype(dtype)
    forcing_data['snowfall_0'] = np.array(Snow_0).astype(dtype)
    forcing_data['PET'] = np.array(PET).astype(dtype)
    forcing_data['doys'] = doys
    
    # print(sys.getsizeof(forcing_data['lrad']))
    # print(Shortwave.shape)
    # import matplotlib.pyplot as plt
    # plt.plot(ds['SnowfallIndex_WithVeg'],linewidth=0.25)
    # plt.show()
   
    model_pars['lai'] = np.array(LAI)
    model_pars['elevation'] = np.array(Elev)
    
    # if program_pars['ModelTimestep'] == 1:
        # TS_vec = daterange(program_pars['StartDate'],program_pars['EndDate']+timedelta(days=1))
    # elif program_pars['ModelTimestep'] == 0:
        # TS_vec = daterange_hr(program_pars['StartDate'],program_pars['EndDate']+timedelta(days=1))
    
    return forcing_data, model_pars


def output_nc(TileName, FName, forcing_data, model_output, program_pars):

    nt, nd = forcing_data['airt'].shape
    print('Writing ' + FName)
      
    if not os.path.exists(os.path.dirname(FName)):
        os.makedirs(os.path.dirname(FName))
        
    if os.path.exists(FName):
        os.remove(FName)
        
    forcing_list = ['airt', 'wind', 'srad_0', 'lrad_0', 'vapp', 'rh', 'rainfall', 'snowfall_0', 'PET']
    NCData = []
    for OutVar in program_pars['OutVars']:
        NCRow = []
        NCRow.append(OutVar[0])
        NCRow.append(OutVar[1])
        NCRow.append(OutVar[2])
        if OutVar[1] in forcing_list:
            NCRow.append(forcing_data[OutVar[1]])
        else:
            NCRow.append(model_output[OutVar[1]])
            
        NCData.append(NCRow)
      
    with nc4.Dataset(FName, 'w' , format='NETCDF4_CLASSIC') as ds:
        
        # Initialize the dimensions of the dataset
        dim_time = ds.createDimension('time', nt)
        dim_ndata = ds.createDimension('X', nd)
            
        for Data in NCData:
            varlongname = Data[0]
            varname = Data[1]
            unit = Data[2]
            data = Data[3]
            nc_var = ds.createVariable(varname, np.float32, ('time','X'), zlib=True, least_significant_digit=program_pars['least_significant_digit'])
            nc_var.standard_name = [varlongname]
            nc_var.units = [unit]
            nc_var[:] = data


def output_csv(TileName, FDir, forcing_data, model_output, ForcingFName, IndexFName, program_pars):
    
    # ds = nc4.Dataset(ForcingFName)
    # AirT = ds['AirT'][:]
    # RH = ds['RH'][:]
    # Pres = ds['Pres'][:]
    # WindSpeed = ds['WindSpeed'][:]
    # WindDir = ds['WindDir'][:]
    # Shortwave = ds['Shortwave'][:]
    # Longwave = ds['Longwave'][:]
    # Precip = ds['Precip'][:]
    # Rain = ds['Rain'][:]
    # Snow = ds['Snow'][:]
    # PET = ds['PET'][:]
    # ds = None
    
    # ds = nc4.Dataset(IndexFName)
    # LAI = ds['LAI'][:]
    # Elev = ds['Elev'][:]
    # Skyview = ds['Skyview'][:]
    # LWI = ds['LWI'][:]
    # SFI_Direct_UnderCanopy = ds['SFI_Direct_UnderCanopy'][:]
    # SFI_Diffuse_UnderCanopy = ds['SFI_Diffuse_UnderCanopy'][:]
    # SFI_Direct_NoVeg = ds['SFI_Direct_NoVeg'][:]
    # SFI_Diffuse_NoVeg = ds['SFI_Diffuse_NoVeg'][:]
    # SnowfallIndex_WithVeg = ds['SnowfallIndex_WithVeg'][:]
    # SnowfallIndex_NoVeg = ds['SnowfallIndex_NoVeg'][:]
    # ds = None
    
    a = loadmat(program_pars['ModelDir'] + '/' + 'ModelInfo.mat',simplify_cells=True)
    POIs = a['POIs']
    
    nt, nd = forcing_data['airt'].shape
    print('Writing ' + FDir)
      
    if not os.path.exists(FDir):
        os.makedirs(FDir)
   
    forcing_list = ['airt', 'wind', 'srad_0', 'lrad_0', 'vapp', 'rh', 'rainfall', 'snowfall_0', 'PET']
    CSVData = []
    for OutVar in program_pars['OutVars']:
        CSVRow = []
        CSVRow.append(OutVar[0])
        CSVRow.append(OutVar[2])
        if OutVar[1] in forcing_list:
            CSVRow.append(forcing_data[OutVar[1]])
        else:
            CSVRow.append(model_output[OutVar[1]])
            
        CSVData.append(CSVRow)
    
    POIGrid = ReadRaster(program_pars['ModelDir'] + '/' + 'POIs.tif', program_pars['Verbose'])
    Locs = POIGrid >= 0
    POIGrid = POIGrid[Locs]
        
    if isinstance(POIs, dict):
        POIs = [POIs]
    
    p = 0
    for POI in POIs:
        FLocs = POIGrid == p
        OFName = FDir + '/' + POI['Name'] + '.csv'
        with open(OFName, 'w',newline='') as csvfile:
            writer = csv.writer(csvfile, delimiter=',')
            header = ['Year', 'Month', 'Day', 'Hour']
            units = ['', '', '', '']
            for Data in CSVData:
                header.append(Data[0])
                units.append(Data[1])
            writer.writerow(header)
            writer.writerow(units)
            
            data = np.zeros([nt,len(CSVData)+4])
            
            dates = daterange(program_pars['StartDate'], program_pars['EndDate']+timedelta(days=1))
            if program_pars['ModelTimestep'] == 1:
                t = 0
                for date in dates:
                    data[t,0] = date.year
                    data[t,1] = date.month
                    data[t,2] = date.day
                    data[t,3] = 0
                    t = t+1
             
            elif program_pars['ModelTimestep'] == 0:
                t = 0
                for date in dates:
                    for h in range(0, 24):
                        data[t,0] = date.year
                        data[t,1] = date.month
                        data[t,2] = date.day
                        data[t,3] = h
                        t = t+1
                
            c = 4
            for Data in CSVData:
                all_data_ = Data[2]
                if len(all_data_.shape) == 2:
                    data_ = all_data_[:,FLocs]
                elif len(all_data_.shape) == 1:
                    data_ = np.tile(all_data_[FLocs],[nt,1])
                    
                if data_.ndim == 1:
                    data[:,c] = data_
                else:
                    data[:,c] = np.mean(data_,axis=1)
                c = c+1    
                
            for t in range(nt):
                data_ = data[t,:]
                writer.writerow(data_)
        
        p = p+1
        

def distribute_parameters(TileName, model_pars, program_pars, rows, cols, Locs, te, tr):
   
    for model_par in model_pars:
        key = str(model_par);
        val = model_pars[str(model_par)]
        
        if isinstance(val, str):
        
            tmp_dir = tempfile.TemporaryDirectory()
            ifname = model_pars[key]
            ofname = tmp_dir.name + '/tmp_index.tif'
            print('Clipping data from ' + ifname + ' as parameter ' + key + ' for ' + TileName)
            cmd = 'gdalwarp -overwrite -te ' + te + ' -tr ' + tr + ' "' + ifname + '" "' + ofname + '"'
            exec_cmd(cmd, program_pars['Verbose'])
            model_pars[key] = ReadRaster(ofname, program_pars['Verbose'])[Locs].astype(dtype)
            os.remove(ofname)
            
        else:
            model_pars[key] = np.array([val]).flatten().astype(dtype)

    return model_pars

def run_tile(Tile, c, program_pars, model_pars):
    
    if program_pars['ModelTimestep'] == 0:
        nt = ((program_pars['EndDate'] - program_pars['StartDate']).days + 1) * 24
    elif program_pars['ModelTimestep'] == 1:
        nt = (program_pars['EndDate'] - program_pars['StartDate']).days + 1 
        
    Locs = Tile['mask'].astype(bool)
    nd = np.sum(Locs)
    ForcingFName = program_pars['ModelDir'] + '/Tile' + str(c) + '/Forcing.nc'
    IndexFName = program_pars['ModelDir'] + '/Tile' + str(c) + '/Indexes.nc'
    ModelOutputFName = program_pars['ModelDir'] + '/Tile' + str(c) + '/ModelOutput.nc'
    rows = int(Tile['rows'])
    cols = int(Tile['cols'])

    te = str(Tile['ulx']) + ' ' + str(Tile['lry']) + ' ' + str(Tile['lrx']) + ' ' + str(Tile['uly'])
    tr = str(Tile['pixelWidth']) + ' ' + str(Tile['pixelHeight']) 
    
    #print(ModelOutputFName)
    if not os.path.exists(ModelOutputFName) or program_pars['OverwriteModelOutput'] == True:
        if os.path.exists(ForcingFName):
            model_pars = distribute_parameters('Tile ' + str(c), model_pars, program_pars, rows, cols, Locs, te, tr)
            forcing_data, model_pars = get_forcing_data('Tile ' + str(c), ForcingFName, IndexFName, model_pars, program_pars)
            model_output = run_model('Tile ' + str(c), forcing_data, model_pars, program_pars)
            
            output_nc('Tile ' + str(c), ModelOutputFName, forcing_data, model_output, program_pars)


def run(program_pars, model_pars):

    if 'OverwriteModelOutput' not in program_pars:
        program_pars['OverwriteModelOutput'] = True

    if program_pars['SimulationType'] == 0 or program_pars['SimulationType'] == 1:
    
        a = loadmat(program_pars['ModelDir'] + '/' + 'ModelInfo.mat',simplify_cells=True)
        Tiles = a['Tiles']
        
        pool = multiprocessing.Pool(processes=min(program_pars['NProcesses'], len(Tiles)))
        pool.starmap(run_tile, zip(Tiles, range(len(Tiles)), itertools.repeat(program_pars), itertools.repeat(model_pars)))
        pool.close() 
        pool.join()
        
    elif program_pars['SimulationType'] == 2:
    
        a = loadmat(program_pars['ModelDir'] + '/' + 'ModelInfo.mat',squeeze_me=True)
        Subdomain = a['Subdomain']
        POIGrid = ReadRaster(program_pars['ModelDir'] + '/' + 'POIs.tif', program_pars['Verbose'])
        Locs = POIGrid >= 0
        
        if program_pars['ModelTimestep'] == 0:
            nt = ((program_pars['EndDate'] - program_pars['StartDate']).days + 1) * 24
        elif program_pars['ModelTimestep'] == 1:
            nt = (program_pars['EndDate'] - program_pars['StartDate']).days + 1
        
        nd = np.sum(Locs)
        ForcingFName = program_pars['ModelDir'] + '/' + 'Forcing.nc'
        IndexFName = program_pars['ModelDir'] + '/' + 'Indexes.nc'
        ModelOutputFName = program_pars['ModelDir'] + '/' + 'ModelOutput.nc'
        ModelCSVFDir = program_pars['OutputDir']
        ModelInfoFName = program_pars['ModelDir'] + '/' + 'ModelInfo.mat'
        rows = int(Subdomain['rows'])
        cols = int(Subdomain['cols'])
        
        te = str(Subdomain['ulx']) + ' ' + str(Subdomain['lry']) + ' ' + str(Subdomain['lrx']) + ' ' + str(Subdomain['uly'])
        tr = str(Subdomain['pixelWidth']) + ' ' + str(Subdomain['pixelHeight']) 
        
        model_pars = distribute_parameters('POIs', model_pars, program_pars, rows, cols, Locs, te, tr)
        forcing_data, model_pars = get_forcing_data('POIs', ForcingFName, IndexFName, model_pars, program_pars)
        model_output = run_model('POIs', forcing_data, model_pars, program_pars)
        
        output_nc('POIs', ModelOutputFName, forcing_data, model_output, program_pars)
        output_csv('POIs', ModelCSVFDir, forcing_data, model_output, ForcingFName, IndexFName, program_pars)
        
        
        # from matplotlib import pyplot as plt
        # plt.plot(model_output['swe'])
        # plt.show()