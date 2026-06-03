import sys
import os
sys.path.insert(1, 'ProgramFiles')
from datetime import date
import Initialize
import Model
import ModelPars
model_pars = ModelPars.model_pars
program_pars = {}

# Simulation Parameters

program_pars['SimulationName'] = sys.argv[1]            # Name of simulation
program_pars['Verbose'] = False                         # Verbose Output
program_pars['ReinitializeModel'] = False               # Reinitialize Model? (Causes everything for a particular simulation to be overwritten)
program_pars['OverwriteForcing'] = False                # Overwrite preprocessing forcing files?
program_pars['OverwriteIndexes'] = False                # Overwrite preprocessing index files?

program_pars['NProcesses'] = 4                         # Maximum Number of processes used for multiprocessing
program_pars['CreatePyramids'] = False

if program_pars['SimulationName'] == 'EntireArea':

    program_pars['ForcingSetName'] = 'DailyStationData'             # Name of forcing dataset to use as model input
    program_pars['ModelTimestep'] = 1                               # 0: Hourly, 1: Daily
    program_pars['UseHourlySFIFiles'] = False                       # Use hourly solar forcing files (only for hourly model)
    program_pars['StartDate'] = date(2018, 10, 1)                   # Simulation Start Date
    program_pars['EndDate'] = date(2019, 5, 31)                     # Simulation End Date
    program_pars['SimulationType'] = 0                              # 0: Entire Area, 1: Subset Area, 2: POIs only
    program_pars['MaxChunkSize'] = 25000                            # Maximum size (in pixels) of each model chunk 
    program_pars['UseWindModel'] = True                             # Use Wind Model

elif program_pars['SimulationName'] == 'SnowtographyArea':

    program_pars['ForcingSetName'] = 'DailyStationData'             # Name of forcing dataset to use as model input
    program_pars['ModelTimestep'] = 1                               # 0: Hourly, 1: Daily
    program_pars['UseHourlySFIFiles'] = False                       # Use hourly solar forcing files (only for hourly model)
    program_pars['StartDate'] = date(2018, 10, 1)                   # Simulation Start Date
    program_pars['EndDate'] = date(2019, 5, 31)                     # Simulation End Date
    program_pars['SimulationType'] = 1                              # 0: Entire Area, 1: Subset Area, 2: POIs only
    program_pars['NSWE'] = [3754645, 3754575, 642475, 642535]       # Spatial Extents of Subset Area - Northing and Easting in UTM projection
    program_pars['MaxChunkSize'] = 1000                             # Maximum size (in pixels) of each model chunk 
    program_pars['UseWindModel'] = True                             # Use Wind Model
    

elif program_pars['SimulationName'] == 'POIs':

    program_pars['ForcingSetName'] = 'DailyStationData'             # Name of forcing dataset to use as model input
    program_pars['ModelTimestep'] = 1                               # 0: Hourly, 1: Daily
    program_pars['UseHourlySFIFiles'] = False                       # Use hourly solar forcing files (only for hourly model)
    program_pars['StartDate'] = date(2018, 10, 1)                   # Simulation Start Date
    program_pars['EndDate'] = date(2019, 5, 31)                     # Simulation End Date
    program_pars['SimulationType'] = 2                              # 0: Entire Area, 1: Subset Area, 2: POIs only
    program_pars['POIDir'] = 'InputData/POIs'                       # POI directory
    program_pars['UseWindModel'] = True                             # Use Wind Model
  
elif program_pars['SimulationName'] == 'POIs_HourlyNLDAS':

    program_pars['ForcingSetName'] = 'HourlyNLDASData'              # Name of forcing dataset to use as model input
    program_pars['ModelTimestep'] = 0                               # 0: Hourly, 1: Daily
    program_pars['UseHourlySFIFiles'] = False                       # Use hourly solar forcing files (only for hourly model)
    program_pars['StartDate'] = date(2018, 10, 1)                   # Simulation Start Date
    program_pars['EndDate'] = date(2019, 5, 31)                     # Simulation End Date
    program_pars['SimulationType'] = 2                              # 0: Entire Area, 1: Subset Area, 2: POIs only
    program_pars['POIDir'] = 'InputData/POIs'                       # POI directory
    program_pars['UseWindModel'] = True                             # Use Wind Model
 
# Output Variables
#                            Variable Name                      Short Name (in code)    Units
program_pars['OutVars'] = [ ['Air Temperature',                 'airt',                 'C',            ],
                            ['Wind Speed',                      'wind',                 'm/s'           ],
                            ['Shortwave Radiation',             'srad_0',               'W/m2'          ],
                            ['Longwave Radiation',              'lrad_0',               'W/m2'          ],
                            ['Vapor Pressure',                  'vapp',                 'Pa'            ],
                            ['Relative Humidity',               'rh',                   '%'             ],
                            ['Rainfall',                        'rainfall',             'mm/timestep'   ],
                            ['Snowfall',                        'snowfall_0',           'mm/timestep'   ],
                            ['Potential Evapotranspiration',    'PET',                  'mm/timestep'   ],  # End of forcing Variables
                            ['Snow Water Equivalent',           'swe',                  'mm'            ],
                            ['Snow Depth',                      'depth',                'W/m2'          ],
                            ['Snow Density',                    'density',              'W/m2'          ],
                            ['Rain on Snow',                    'rain_on_snow',         'mm/timestep'   ],
                            ['Snowpack Sublimation',            'snowpack_sublimation', 'mm/timestep'   ],
                            ['Snow Melt',                       'melt',                 'mm/timestep'   ],
                            ['Snow throughfall',                'tsfall',               'mm/timestep'   ],
                            ['Canopy Snow Sublimation',         'canopy_sublimation',   'mm/timestep'   ],
                            ['Snow Unload from Canopy',         'snow_unload',          'mm/timestep'   ],
                            ['Melt Drip from Canopy',           'melt_drip',            'mm/timestep'   ],
                            ['Canopy Snow Storage',             'canopy_snow_storage',  'mm'            ],
                            ['Rain throughfall',                'tfall',                'mm/timestep'   ],
                            ['Canopy Evaporation',              'canopy_evaporation',   'mm'            ],
                            ['Canopy Drip',                     'drip',                 'mm'            ],
                            ['Canopy Rain Storage',             'canopy_rain_storage',  'mm'            ],
                            ['Albedo',                          'albedo',               '-'             ],
                            ['Surface Temperature',             'Ts',                   'C'             ],
                            ['Snowpack Temperature',            'Tm',                   'C'             ],
                            ['Cold Content',                    'Q',                    'J/m2'          ],
                            ['Incoming Shortwave (Ground)',     'Qsd',                 'W/m2'          ],
                            ['Incoming Longwave (Ground)',      'Qld',                 'W/m2'          ],
                            ['Outgoing Shortwave (Ground)',     'Qse',                  'W/m2'          ],
                            ['Outgoing Longwave (Ground)',      'Qle',                  'W/m2'          ],
                            ['Net Radiation',                   'Qn',                   'W/m2'          ],
                            ['Net Radiation over Snowpack',     'Qn_snow',              'W/m2'          ],
                            ['Sensible Heat Flux',              'Qh',                   'W/m2'          ],
                            ['Ground Heat Flux',                'Qg',                   'W/m2'          ],
                            ['Latent Heat Flux (sublimation)',  'Qe',                   'W/m2'          ],
                            ['Precipitation Heat Flux',         'Qp',                   'W/m2'          ],
                            ['Melt Heat Flux',                  'Qm',                   'W/m2'          ],
                            ['Surface Layer Soil Temperature',  'T_soil',               'C'             ],
                            ['Surface Layer Soil Ice Content',  'ice_percent_soil',     '%'             ],
                            ['Soil Moisture Content',           'SMC',                  '%'             ],
                            ['Soil Moisture Storage',           'sm_stor',              'mm'            ],
                            ['Infiltration',                    'infiltration',         'mm/timestep'   ],
                            ['Infiltration Excess Runoff',      'infil_runoff',         'mm/timestep'   ],
                            ['Saturation Excess Runoff',        'sat_runoff',           'mm/timestep'   ],
                            ['Actual Evapotranspiration',       'ET',                   'mm/timestep'   ],
                            ['Percolation',                     'perc',                 'mm/timestep'   ],
                            ['Capillary Rise',                  'caprise',              'mm/timestep'   ],
                            ['Vadose Zone Water Storage',       'x_vadose',             'mm'            ],
                            ['Vadose to Phreatic Zone Flux',    'vadose_to_phreatic',   'mm'            ],
                            ['Phreatic Zone Water Storage',     'x_phreatic',           'mm'            ],
                            ['Discharge from Vadose Zone',      'q_vadose',             'mm/timestep'   ],
                            ['Discharge from Phreatic Zone',    'q_phreatic',           'mm/timestep'   ]]
                                                
# Additional Parameters (probably no change)

program_pars['POIForcingInterpMethod'] = 0                                          # Forcing Interpolation for POIs (doesn't affect the results)
                                                                                    # 0: Default (Better for smaller number of POIs), 1: May be better when many POI grids or for small domains
program_pars['GISDir'] = 'Preprocess/GIS'                                           # Directory with preprocessed GIS data
program_pars['IndexDir'] = 'Preprocess/Indexes'                                     # Directory with preprocessed subcanopy indexes
program_pars['ForcingDir'] = 'Preprocess/Forcing/' + program_pars['ForcingSetName'] # Directory with forcing data (clipped at for main model domain)
program_pars['ModelDir'] = 'Model/' + program_pars['SimulationName']                # Directory where model files are saved
program_pars['OutputDir'] = 'Output/' + program_pars['SimulationName']              # Directory where output files are saved
program_pars['least_significant_digit'] = 3                                         # Smallest decimal place in unpacked data that is a reliable value

## Call function to RunModel
if __name__ == '__main__':
    Initialize.Initialize(program_pars)
    Initialize.InterpForcingData(program_pars)
    Initialize.InterpIndexes(program_pars)
    Model.run(program_pars,model_pars)
    