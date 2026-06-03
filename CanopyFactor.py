def get_trans():

    # Reduces that importance of canopy cover at lower levels of cover for LAI, SVF, and SFI maps (to account for unrealistically high
    # bias in canopy cover and canopy height for trees with low canopy cover (for example, burned trees still look fairly dense in a lidar
    # scene and they still have a significant height).  This has two affects: under trees, (1-Transmittance) is multiplied by vertical 
    # quantities like LAI to get an adjusted LAI.  Next to trees, the shading effects from canopies in different veg cover categories are 
    # reduced for sparse canopies.  For example, if there are dense trees nearby, shading is strong, like having shading from curtains draped 
    # across the canopy.  If the nearby trees are sparse, shading is diffuse.  If there is dense canopy behind the sparse canopy, the effects 
    # from the denser trees will dominate.
    VegCoverCategories = [[80, 100], [60, 80], [40, 60], [20, 40], [0, 20]] 
    Transmittances = [0, 0.75, 0.9, 0.95, 0.99]                             
    
    return VegCoverCategories,Transmittances