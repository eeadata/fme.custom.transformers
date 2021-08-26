#===============================================================================
#
#  Name     : grass_plugin_raster_stats.py
#  
#  System   : FME Custom Transformer
#  
#  Language : Python
#  
#  Purpose  : GRASS r.stats program wrapper
# 
#        Copyright (c) 2015, Tracasa - ahuarte@tracasa.es. All rights reserved.
#
#   Redistribution and use of this sample code in source and binary forms, with 
#   or without modification, are permitted provided that the following 
#   conditions are met:
#   * Redistributions of source code must retain the above copyright notice, 
#     this list of conditions and the following disclaimer.
#   * Redistributions in binary form must reproduce the above copyright notice, 
#     this list of conditions and the following disclaimer in the documentation 
#     and/or other materials provided with the distribution.
#
#   THIS SAMPLE CODE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS 
#   "AS IS" AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED 
#   TO, THE IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR 
#   PURPOSE ARE DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT HOLDER OR 
#   CONTRIBUTORS BE LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, 
#   EXEMPLARY, OR CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT LIMITED TO, 
#   PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES; LOSS OF USE, DATA, OR PROFITS; 
#   OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND ON ANY THEORY OF LIABILITY, 
#   WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR 
#   OTHERWISE) ARISING IN ANY WAY OUT OF THE USE OF THIS SAMPLE CODE, EVEN IF 
#   ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.
# 
#===============================================================================
#
#  Note: 
#  This function returns the results of the GRASS r.stats program as string list.
#
#

import os
import fmeobjects

from grass_plugin_utils import GrassManager, S_OK, S_FAIL
from TransformerUtil import Transformer

#===============================================================================
# Class to perform the overall logic of the GrassRasterStats transformer.
#
class grass_plugin_raster_stats(Transformer):

    # The class constructor.
    def __init__(self, instanceName, paramMap):
        Transformer.__init__(self, instanceName, paramMap)
        self.logger = fmeobjects.FMELogFile()
        self.logger.logMessageString("Transformer initialized", fmeobjects.FME_INFORM)
        self.featureList = []
    
    # Takes a feature and processes it.
    def input(self, feature):
        fmetype = str(feature.getAttribute("fme_type"))
        
        # Saves the source raster-type features to process all when finalize the transformer.
        if fmetype == "fme_raster":            
            self.logger.logMessageString("Feature '" + str(feature.getAttribute("fme_basename")) + "' assigned to process", fmeobjects.FME_INFORM)
            self.featureList.append(feature)
        else:
            self.logger.logMessageString("Feature '" + str(feature.getAttribute("fme_basename")) + "' of type '" + fmetype + "' ignored", fmeobjects.FME_ERROR)
    
    # Finishing the current geoprocessing task.
    def close(self):
        statsText = ""
        statsList = []

        if len(self.featureList) == 0:
            self.logger.logMessageString("No features to process!", fmeobjects.FME_ERROR)
        else:
            self.logger.logMessageString(str(len(self.featureList)) + " raster[s] to process...", fmeobjects.FME_INFORM)
            i = 0
            
            # Create the helper manager to execute GRASS commands.
            grassManager = GrassManager(self.logger)
            grassDatabaseLocationPath = grassManager.initializeLocationFromFile(str(self.featureList[0].getAttribute('fme_dataset')))
            # Disable GRASS messages (GRASS_INFO_MESSAGE, GRASS_INFO_PERCENT, ...), disabled by default, enable when we want to show them for debug purposes.
            grassManager.showGrassMessages(False)
            #
            # Now we can use grass directly... or use methods of this GrassManager :-)
            # ... import grass.script as grass
            # ... grass.message('GRASS platform running!')
            # ... grass.run_command('r.xxx', flags='x', input=bla bla bla)
            
            # Convert the source RASTER files as GRASS raster objects.
            for feature in self.featureList:
                raster_name = grassManager.importFmeRasterFeatureAsGrassRasterObject(feature, True)
                if (len(raster_name) > 0): statsText += raster_name + ","
                i = i + 1
            
            # Remove last character of RASTER list.
            if (len(statsText) > 1): statsText = statsText[:-1]
            
            # Define a temp filename where we save the results of GRASS 'r.stats' program.
            result_log_file = os.path.join(grassDatabaseLocationPath, 'r.stats.csv')

            self.logger.logMessageString("Processing 'r.stats' with the source RASTER objects...", fmeobjects.FME_INFORM)
            #
            # https://grass.osgeo.org/grass70/manuals/r.stats.html
            #
            if (grassManager.runCommand('r.stats', flags='c', input=statsText, output=result_log_file) == S_OK):
                self.logger.logMessageString("The 'r.stats' program was successly processed!", fmeobjects.FME_INFORM)
                
                if os.path.exists(result_log_file):
                    with open(result_log_file, 'r') as file:
                        for line in file: statsList.append(line)
            else:
                self.logger.logMessageString("The 'r.stats' program failed!", fmeobjects.FME_ERROR)
                        
            # Release the manager (Optional, it is called automatically).
            grassManager = None
        
        # Send a new unique feature as result of the transformer.
        resultFeature = fmeobjects.FMEFeature()
        resultFeature.setAttribute("fme_type", "fme_no_geom")
        resultFeature.setAttribute("fme_dataset", "")
        resultFeature.setAttribute("fme_basename", "r.stats")
        resultFeature.setAttribute(self.paramMap()["OUTPUT_LIST_NAME"], statsList)
        self.pyoutput(resultFeature)
        
        self.logger.logMessageString("Transformer closed", fmeobjects.FME_INFORM)
        del(self.logger) # Needed to avoid "Not All FME sessions were destroyed"
    
