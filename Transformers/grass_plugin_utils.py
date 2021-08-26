#===============================================================================
#
#  Name     : grass_plugin_utils.py
#  
#  System   : FME Custom Transformer
#  
#  Language : Python
#  
#  Purpose  : GRASS platform helper functions
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

import os
import sys
import subprocess
import shutil
import binascii
import tempfile
import random
import fmeobjects

from weakref import WeakValueDictionary

# Define some WIN32-style function result codes.
S_OK = 0
S_FAIL = -1

#===============================================================================
#
# Class to manage the GRASS framework.
class GrassManager(object):
    # Enables auto-dispose capabilities (Automatic Garbage Collector - del method calling).
    __instances = WeakValueDictionary()

    # The GrassManager class constructor.
    def __init__(self, logger):
        self.__instances[id(self)] = self
        self.__grass7bin = ""
        self.__gisbase = ""
        self.__gisdb = ""
        self.__location_path = ""
        self.__location = ""
        self.__mapset = "PERMANENT"
        self.__showGrassMessages = False
        self.logger = logger

    # Releases the resources of the object (Remove the temporary batch location from disk).
    def __del__(self):
        shutil.rmtree(self.__location_path, ignore_errors=True)
        self.logger.logMessageString('GrassManager cleaned!', fmeobjects.FME_INFORM)

    # Normalize the specified filepath when it contains special characters.
    def __normalizePath(self, path):
        if (sys.platform.startswith('win') and path.find('"') == -1 and path.find(' ') != -1):
            path = '"' + path + '"'
        
        return path
    
    # Initializes the environment of the GRASS platform.
    def __initializeEnvironment(self):
        #if str(os.getenv('GRASS_PYTHON')) == 'python':
        #    return

        self.logger.logMessageString('Initializing GRASS platform...', fmeobjects.FME_INFORM)
        
        # Define the LOCATION environment to run a new GRASS instance.
        #
        self.__gisbase = os.path.join(os.path.dirname(os.path.realpath(__file__)), 'grass_plugin_core')
        self.__gisdb = os.path.join(tempfile.gettempdir(), 'grassdata')
        os.environ["GISBASE"] = self.__gisbase
        os.environ["GISDBASE"] = self.__gisdb
        
        try:
            os.stat (self.__gisdb)
        except:
            os.mkdir(self.__gisdb)
        
        self.logger.logMessageString("GISBASE: " + self.__gisbase, fmeobjects.FME_INFORM)
        self.logger.logMessageString("GISDB: " + self.__gisdb, fmeobjects.FME_INFORM)
        
        pythonhome = os.path.join(self.__gisbase, 'Python27')
        pythonpath = os.path.join(self.__gisbase, 'etc', 'python')
        if (pythonpath not in sys.path): sys.path.append(pythonpath)

        if sys.platform.startswith('win'):
            self.__grass7bin = self.__normalizePath(os.path.join(self.__gisbase, 'grassStart.bat'))
        else:
            OSError('Platform not configured.')
        
        # Define the ENV-PATH variables to initialize GRASS platform.
        #
        os.environ["GRASS_CONFIG_DIR"] = self.__gisdb
        # self.logger.logMessageString("GRASS_CONFIG_DIR: " + os.getenv("GRASS_CONFIG_DIR"), fmeobjects.FME_INFORM)
        os.environ["GRASS_PYTHON"] = 'python'
        # self.logger.logMessageString("GRASS_PYTHON: " + os.getenv("GRASS_PYTHON"), fmeobjects.FME_INFORM)
        
        os.environ["PYTHONHOME"] = pythonhome
        # self.logger.logMessageString("PYTHONHOME: " + str(os.getenv("PYTHONHOME")), fmeobjects.FME_INFORM)
        os.environ["PYTHONPATH"] = pythonpath
        # self.logger.logMessageString("PYTHONPATH: " + str(os.getenv("PYTHONPATH")), fmeobjects.FME_INFORM)
        
        os.environ["GDAL_ROOT_PATH"] = os.path.join(self.__gisbase, 'extrabin')
        # self.logger.logMessageString("GDAL_ROOT_PATH: " + str(os.getenv("GDAL_ROOT_PATH")), fmeobjects.FME_INFORM)
        os.environ["GDAL_DRIVER_PATH"] = os.path.join(self.__gisbase, 'extrabin', 'plugins')
        # self.logger.logMessageString("GDAL_DRIVER_PATH: " + str(os.getenv("GDAL_DRIVER_PATH")), fmeobjects.FME_INFORM)
        os.environ["LD_LIBRARY_PATH"] = os.path.join(self.__gisbase, 'lib')
        # self.logger.logMessageString("LD_LIBRARY_PATH: " + str(os.getenv("LD_LIBRARY_PATH")), fmeobjects.FME_INFORM)
        
        os.environ["GRASS_PROJSHARE"] = os.path.join(self.__gisbase, 'share', 'proj')
        # self.logger.logMessageString("GRASS_PROJSHARE: " + str(os.getenv("GRASS_PROJSHARE")), fmeobjects.FME_INFORM)
        os.environ["GDAL_DATA"] = os.path.join(self.__gisbase, 'share', 'gdal')
        # self.logger.logMessageString("GDAL_DATA: " + str(os.getenv("GDAL_DATA")), fmeobjects.FME_INFORM)
        os.environ["GEOTIFF_CSV"] = os.path.join(self.__gisbase, 'share', 'epsg_csv')
        # self.logger.logMessageString("GEOTIFF_CSV: " + str(os.getenv("GEOTIFF_CSV")), fmeobjects.FME_INFORM)
        os.environ["PROJ_LIB"] = os.path.join(self.__gisbase, 'share', 'proj')
        # self.logger.logMessageString("PROJ_LIB: " + str(os.getenv("PROJ_LIB")), fmeobjects.FME_INFORM)
        
        # Define the MAIN PATH variable.
        #
        path = os.getenv("PATH")
        path = pythonhome + ";" + path
        path = pythonpath + ";" + path
        path = os.path.join(self.__gisbase, 'msys', 'bin;', path)
        path = os.path.join(self.__gisbase, 'extrabin;', path)
        path = os.path.join(self.__gisbase, 'extralib;', path)
        path = os.path.join(self.__gisbase, 'scripts;', path)
        path = os.path.join(self.__gisbase, 'etc;', path)
        path = os.path.join(self.__gisbase, 'lib;', path)
        path = os.path.join(self.__gisbase, 'bin;', path)
        os.environ["PATH"] = path
        # self.logger.logMessageString("PATH: " + os.getenv("PATH"), fmeobjects.FME_INFORM)

        os.environ['LANG'] = 'en_US'
        os.environ['LOCALE'] = 'C'
    
    # Returns a new valid GRASS location path.
    def __createLocationPath(self):
        self.__initializeEnvironment()
        
        # location/mapset: use random names for batch jobs
        string_length = 16
        self.__location = binascii.hexlify(os.urandom(string_length))
        self.__location_path = os.path.join(self.__gisdb, self.__location)
        
        try:
            os.stat (self.__gisdb)
        except:
            os.mkdir(self.__gisdb)
        
        self.logger.logMessageString("LOCATION_PATH: " + self.__location_path, fmeobjects.FME_INFORM)
        return self.__location_path

    # Initializes a new GRASS location from the specified start CMD.
    def __initializeLocationFromStartCmd(self, startCmd):

        # Create new location (we assume that grass7bin is in the PATH):
        # https://grasswiki.osgeo.org/wiki/Working_with_GRASS_without_starting_it_explicitly#Python:_GRASS_GIS_7_without_existing_location_using_metadata_only
        #
        p = subprocess.Popen(startCmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        out, err = p.communicate()
        
        if p.returncode != S_OK:
            self.logger.logMessageString('ERROR: %s' % err, fmeobjects.FME_ERROR)
            self.logger.logMessageString('ERROR: Cannot generate location (%s)' % startCmd, fmeobjects.FME_ERROR)
            sys.exit(-1)
        
        # Launch session!
        import grass.script as grass
        import grass.script.setup as gsetup
        gsetup.init(self.__gisbase, self.__gisdb, self.__location, self.__mapset)
        grass.message('GRASS platform running!')
        
        return self.__location_path

    # Initializes a new GRASS location from the specified EPSG code.
    def initializeLocationFromEPSG(self, epsg):
        self.logger.logMessageString("Creating a new temporal GRASS location with EPSG: " + epsg, fmeobjects.FME_INFORM)
        self.__createLocationPath()

        # Create new location from a EPSG code.
        startcmd = self.__grass7bin + ' -c epsg:' + epsg + ' -e ' + self.__normalizePath(self.__location_path)
        return self.__initializeLocationFromStartCmd(startcmd)
        
    # Initializes a new GRASS location from the specified vector/raster file.
    def initializeLocationFromFile(self, file):
        self.logger.logMessageString("Creating a new temporal GRASS location from file: " + file, fmeobjects.FME_INFORM)
        self.__createLocationPath()

        # Create new location from a SHAPE or GeoTIFF file.
        startcmd = self.__grass7bin + ' -c ' + self.__normalizePath(file) + ' -e ' + self.__normalizePath(self.__location_path)
        return self.__initializeLocationFromStartCmd(startcmd)
        
    # Shows/Hides in the FME LOG manager the notified GRASS messages.
    def showGrassMessages(self, showGrassMessages):
        self.__showGrassMessages = showGrassMessages

    # Run a GRASS command using the specified parameters.
    def runCommand(self, *args, **kwargs):
        try:
            import grass.script as grass
            
            if (self.__showGrassMessages == True):             
                env = os.environ.copy()
                env['GRASS_MESSAGE_FORMAT'] = 'gui'                
                p = grass.pipe_command(env = env, *args, **kwargs)
                p.wait()
                return p.returncode
            else:
                p = grass.pipe_command(quiet = True, *args, **kwargs)
                p.wait()
                return p.returncode
        
        except:
            err_info = sys.exc_info()
            self.logger.logMessageString("ERROR processing '" + str(*args) + "' errtype=" + str(err_info[0]) + " errtrace=" + str(err_info[2]), fmeobjects.FME_ERROR)
            return S_FAIL
    
    # Convert the specified FME raster feature to a new GRASS raster object.
    def importFmeRasterFeatureAsGrassRasterObject(self, feature, updateRegion):            
        dataset_name = str(feature.getAttribute('fme_dataset'))
        raster_name = 'temp_raster_' + str(random.randint(10000, 20000))
        
        self.logger.logMessageString("Importing " + dataset_name + "...", fmeobjects.FME_INFORM)
        #
        # https://grass.osgeo.org/grass70/manuals/r.in.gdal.html
        #
        if (self.runCommand('r.in.gdal', flags='e', input=dataset_name, output=raster_name) != S_OK):
            return ""
        #
        # https://grass.osgeo.org/grass70/manuals/g.region.html
        #
        if updateRegion:
            if (self.runCommand('g.region', flags='d', raster=raster_name) != S_OK):
                return ""
        
        return raster_name
