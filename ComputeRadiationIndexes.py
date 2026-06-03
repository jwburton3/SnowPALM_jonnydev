import sys
import shutil
import os
sys.path.insert(1, 'ProgramFiles')
import GIS
import Indexes
pars = {}

############################### Parameters ################################

# General Parameters

pars['Verbose'] = True                          # Verbose output
pars['OverwriteGISMaps'] = False                # Overwrite GIS (Skyview and Potential Solar) Files?
pars['OverwriteSVFMaps'] = False                 # Overwrite Potential Solar Files?
pars['OverwriteSFIMaps'] = True                # Overwrite Below Canopy SFI Files?
pars['OverwriteLWIMaps'] = False                # Overwrite Longwave Enhancement Files?
pars['CreatePyramids'] = False                  # Create pyramids for faster display
# pars['SagaGISLoc'] = r'C:\saga-8.2.0_x64'       # Location of Saga GIS Executable    
pars['SagaGISLoc'] = os.path.dirname(
    shutil.which('saga_cmd')
)        # Location of Saga GIS Executable                

# Skyview factor parameters (see https://saga-gis.sourceforge.io/saga_tool_doc/2.2.0/ta_lighting_3.html)

pars['RADIUS'] = 200                 	# Maximum Search Radius [m]
pars['METHOD'] = 0                      # Method (0: multi scale, 1: sectors)
pars['NDIRS'] = 36                      # Number of sectors
pars['DLEVEL'] = 3                      # Multi scale factor

pars['SVFInterpUnderTreesFactor'] = 0.5     	                       	# Interpolate SVF under trees (rather than treating trees as curtain)
pars['SVFResizeFactor'] = 1                                     # Filter applied to enlarge LWI enhancement zones

# Potential solar radiation parameters (see https://saga-gis.sourceforge.io/saga_tool_doc/2.2.2/ta_lighting_2.html)

pars['Solar_output_step'] = 1                                   # 0: hourly solar maps 1: daily solar maps
pars['Solar_hour_step'] = 0.25                                  # Time step for SFI calculation [h]
pars['Solar_Months'] = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12]  # Months to compute SFI for
pars['Solar_Days'] = [1]                                        # Days in Months to compute SFI for
pars['ConstantLatitude'] = True                                 # Set this to True to speed up processing for small areas
pars['SOLARCONST'] = 1367                                       # Solar Constant [W / m2]
pars['LOCALSVF'] = 1                                            # Use Local skyview Factor (0: False, 1: True)
pars['SHADOW'] = 1                                              # Shadow type (0: slim, 1: fat, 2: none)
pars['METHOD'] = 2                                              # 0: Height of Atmosphere and Vapour Pressure
                                                                # 1: Air Pressure, Water and Dust Content
                                                                # 2: Lumped Atmospheric Transmittance
                                                                # 3: Hofierka and Suri
# The following parameters are only used as applicable
pars['ATMOSPHERE'] = 12000                                      # Height of Atmosphere [m]
pars['PRESSURE'] = 1013                                         # Barometric Pressure [mbar]
pars['WATER'] = 1.68                                            # Water Content [cm]
pars['DUST'] = 100                                              # Dust [ppm]
pars['LUMPED'] = 70                                             # Lumped atmospheric transmittance [percent]

pars['SFIInterpUnderTreesFactor'] = 1     	                    # 0: Areas under dense canopy -> no skyview, 1: Areas under trees have diffuse skyview based on surroundings
pars['SFIResizeFactor'] = 1                                     # Filter applied to enlarge LWI enhancement zones

# LWI parameters

pars['LWIHeightRed'] = 25                   # Maximum height of canopy where additional longwave enhancement is observed [m]
pars['LWIResizeFactor'] = 7                 # Filter applied to enlarge LWI enhancement zones

###########################################################################

# Get Canopy transmittance estimates
import CanopyFactor
pars['VegCoverCategories'], pars['Transmittances'] = CanopyFactor.get_trans()

# Define input and output directories
pars['GISDir'] = os.getcwd() + '/Preprocess/GIS'                                # GIS Directory
pars['IndexDir'] = os.getcwd() + '/Preprocess/Indexes'                          # Index Directory    

if __name__ == '__main__':

    # Compute Saga GIS Skyview and Potential Solar maps for different canopy cover classes
    if pars['OverwriteGISMaps']:
        pars['Overwrite'] = True
    else:
        pars['Overwrite'] = False
    GIS.GetSkyViewMaps(pars)
    GIS.GetPotentialSolarMaps(pars)

    # Compute SVF Index Maps
    if pars['OverwriteSVFMaps']:
        pars['Overwrite'] = True
    else:
        pars['Overwrite'] = False
    Indexes.GetBelowCanopySkyviewFactor(pars)
    
    # Compute SFI Index Maps
    if pars['OverwriteSFIMaps']:
        pars['Overwrite'] = True
    else:
        pars['Overwrite'] = False
    Indexes.GetBelowCanopySFIMaps(pars)

    # Compute LWI Index Maps
    if pars['OverwriteLWIMaps']:
        pars['Overwrite'] = True
    else:
        pars['Overwrite'] = False
    Indexes.GetLongwaveEnhancementMaps(pars)