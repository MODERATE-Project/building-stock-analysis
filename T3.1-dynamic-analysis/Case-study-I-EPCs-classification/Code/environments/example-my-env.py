#==================================#
#====    Configuration file    ====#
#==================================#

from pathlib import Path
import os

class Object(object):
    pass

# Create object to store all env variables
my_env = Object()

# execute the code from the root of the project
my_env.SRCDIR = Path.cwd()


#----    Geocoding    ----#

# geocoding keys (both keys are free, but google service requires a credit card)
my_env.BINGKEY='yourKeyHere'
my_env.GOOGLEKEY='yourKeyHere'

#----    data folders    ----#

my_env.DATADIR = my_env.SRCDIR / 'data'

my_env.RAWDIR = my_env.DATADIR / 'raw'
my_env.EXTERNALDIR = my_env.DATADIR / 'external'

my_env.INTERIMDIR = my_env.DATADIR / 'interim'
my_env.CONVERTEDDIR = my_env.INTERIMDIR / 'converted'

my_env.PROCESSEDDIR = my_env.DATADIR / 'processed'

# data/
#   |--  raw/
#   |--  external/
#   |--  interim/
#   |       |--  converted/
#   |--  processed/


#----    Inputs/Outputs    ----#

#-- 01-cened_filtering.py

my_env.CENEDTABLE = my_env.RAWDIR / 'cened_data_edifici.csv'
my_env.CENEDOUTPUT = my_env.INTERIMDIR / 'cened_data_filtered.csv'


#-- 02-cened_geocoding.py

my_env.CENEDGOOD = 'cened_good.csv'
my_env.CENEDBAD = 'cened_bad.csv'
my_env.CENEDGEOCODED = my_env.INTERIMDIR / 'cened_geocoded.csv'
my_env.CENEDGEOCODEDSHAPE = my_env.INTERIMDIR / 'cened_geocoded.shp'

my_env.GEOREGION = my_env.EXTERNALDIR / 'Reg01012022_g_WGS84.shp'
my_env.GEOMUNICIPALITY = my_env.EXTERNALDIR / 'Com01012022_g_WGS84.shp'


#--  03-cened_processing.py

my_env.CENEDPROCESSED = my_env.INTERIMDIR / 'cened_processed.csv'
my_env.CENEDPROCESSEDSHAPE = my_env.INTERIMDIR / 'cened_processed.shp'


#--  04-openeo_download.py

my_env.OPENEODIR = my_env.INTERIMDIR / 'openeo'
my_env.BACKEND_SERVER = "https://openeo.eurac.edu"
my_env.CLIENT_ID = "Eurac_EDP_Keycloak"
my_env.COLLECTION_ID = "S2_L2A_ALPS"

my_env.S2EURAC = my_env.INTERIMDIR / 'S2_eurac.shp'


#--  05-osm_meteo_download.py

my_env.ERA5WINTER_IMPORT = my_env.EXTERNALDIR / 'data-meteo-winter.grib'
my_env.ERA5SUMMER_IMPORT = my_env.EXTERNALDIR / 'data-meteo-summer.grib'

my_env.OSMBUILDINGS = my_env.INTERIMDIR / 'osm_buildings.geojson'
my_env.ERA5TEMPERATURE = my_env.INTERIMDIR / 'era5-temperature.geojson'


#--  06-data_processing.py

my_env.DATAANALYSIS = my_env.PROCESSEDDIR / 'data_analysis.csv'

#====
