import sys
import os
sys.path.insert(1, 'ProgramFiles')
import GIS
import Indexes
pars = {}

############################### Parameters ################################

# General Parameters

pars['Verbose'] = False                                 # Verbose output
pars['OverwriteGISMaps'] = False                        # Overwrite GIS Maps?
pars['OverwriteLAIMap'] = False                          # Overwrite LAI Maps?
pars['CreatePyramids'] = False                          # Create pyramids for faster display 

# GIS File locations and extent

from pathlib import Path

# Elevation raster to get data from
pars['DTM_File'] = 'InputData/SpatialData/DTM.tif'
# Canopy height raster to get data from
pars['VegHT_File'] = 'InputData/SpatialData/VegHT.tif'
# Canopy cover raster to get data from
pars['VegCover_File'] = 'InputData/SpatialData/Cover.tif'
# Cutline file to clip out shape (will only be used if pars['Cutline_File'] is not an empty string)
pars['Cutline_File'] = ''

pars['NSWE'] = [3754797, 3754187, 642165, 643000]       # Spatial Extents
pars['UseOriginalPixels'] = True                    # Force model boundaries to accomodate existing  pixels

# The following parameters are only used if UseOriginalPixels is set to False (otherwise all input files need to have the desired SRS and align with each other)
pars['Target_SRS'] = 'EPSG:31966'                       # Spatial Reference System (Proj4)
pars['CellSize'] = 1                                    # Model Cell Size
pars['CellSize_LowRes'] = 30                            # Low resolution cell size (for interpolation of forcing data)
pars['Resample'] = 'average'                            # Resampling Method (near(default) bilinear, cubic, cubicspline, lanczos, 
                                                        # average, rms, mode, max, min, med, Q1, Q3, sum)
# LAI Parameters
pars['LAIResizeFactor'] = 1                         # Filter applied to soften the edges of the LAI map (1 = none; higher numbers = more softening)
# LAI= f_c * pars['LAI_ref'] * (VegHT / pars['H_ref']) ** pars['LAI_exp']
# The following are default parameters, but can be adjusted as needed
pars['LAI_ref'] = 6                                 # Reference LAI
pars['H_ref'] = 30                                  # Reference Canopy Height
pars['LAI_exp'] = 0.5                               # Exponent applied to Canopy Height Adjustment

###########################################################################

# Get Canopy transmittance estimates
import CanopyFactor
pars['VegCoverCategories'], pars['Transmittances'] = CanopyFactor.get_trans()

# Define input and output directories
pars['GISDir'] = os.getcwd() + '/Preprocess/GIS'                                # GIS Directory
pars['IndexDir'] = os.getcwd() + '/Preprocess/Indexes'                          # Index Directory   

if __name__ == '__main__':

    # Subset spatial maps for the model domain
    if pars['OverwriteGISMaps']:
        pars['Overwrite'] = True
    else:
        pars['Overwrite'] = False
    GIS.GetSpatialData(pars)
    
    # Create Leaf Area Index Map
    if pars['OverwriteLAIMap']:
        pars['Overwrite'] = True
    else:
        pars['Overwrite'] = False
    Indexes.GetVerticalLAI(pars)