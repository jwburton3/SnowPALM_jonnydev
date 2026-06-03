Prior to running SnowPALM, the spatial inputs to the model need to be created.  These include
maps of canopy cover (closure; Cover.tif), canopy height (VegHT.tif), and a bare earth DTM 
(DTM.tif).  These maps can have any projection and format, but must be readable using GDAL.  
Note that SnowPALM has the ability to reproject and clip the input rasters, so they just need 
to cover at least model domain (or largest domain, in case multiple subdomains are set up).