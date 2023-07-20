# Moderate

## Description / Target
Predict year energy performance certificates (EPCs) of buildings by using only satellite data from Sentinel 2 - Lombardy case study.

## Installation and prerequisites
The file <b>moderate_requirements.txt</b> contains the Python3 libraries to be installed in order to run the code in the repository. Creating a separate environment through a tool like conda is strongly suggested.

### Environment

Environment variables are managed using the extension `py_config_env` (https://git@github.com/aaronestrada/py-config-env.git). This extension allows loading configuration files containing variables in a Python script, to then access to them via a configuration dictionary.

An object `my_env` is defined containing all the environmental variables as methods. To get a variable value, use `my_env.NAME_VAR`. See `environments/example-my-env.py` for the definition of my_env and available environmental variables. 

Please be aware that `environments/example-my-env.py` should be renamed to `environments/my-env.py` for the code to work properly. 

### Geocoding API

To use Bing and Google geocoding services, it is important to activate the respective keys (which should be personal) and to insert them as environment variables in the `environments/my-env.py` file. Limits and policies of the geocoding services are highlighted as comments in `analysis/02-cened_geocoding.py`.

### Data Directory Structure
The project tries to follow the data directory structure outlined at https://kedro.readthedocs.io/en/stable/faq/faq.html#what-is-data-engineering-convention.

```
data/
   |--  raw/        <- The original, immutable data
   |--  external/   <- Data from third party sources
   |--  interim/    <- Transformed intermediate data
   |--  processed/  <- The final datasets for modeling
```

## Usage
For ease of use, the code used for the analysis is divided into different scripts. All scripts are collected in the `analysis/` directory and named with a numeric prefix indicating the expected order of execution. In particular, scripts are organized in order according to the following pipeline:

> Install the project as a package to allow solving issue in importing custom modules by running
> ```
> $ pip install -e .
> ```
> https://stackoverflow.com/a/56806766/12481476

### 1. cened_filtering.py

**DESCRIPTION:** CENED certificates which do not refer to buildings with a surface of at least 100mq are filtered out. Data is further filtered by removing buildings without address or number and without year of construction. Data points go from more than a million to around 70k. 

**INPUT:** 

- CENED+2 dataset (https://www.dati.lombardia.it/Energia/Database-CENED-2-Certificazione-ENergetica-degli-E/bbky-sde5) renamed as `cened_data_edifici.csv` and assumed to be within the `data/raw/` directory. Please refer to https://www.dati.lombardia.it/api/views/bbky-sde5/files/37c35b51-f538-4ebd-8b29-8d861f8e1e7b?download=true&filename=descrizione_campi_cened.pdf (accessible from the same page of the dataset) for a description of the features.

**OUTPUT:** 

- saved as `data/interim/cened_data_filtered.csv` (CENED data which refer only to buildings with a surface >= 100mq).


### 2. cened_geocoding.py

**DESCRIPTION:** CENED addresses are geocoded. The address of buildings is geocoded using three different providers (Open Street Maps, Bing, Google), checking that each geocoding has been converted to rooftop level and within the administrative borders of the respective region and municipality. Buildings which do not satisfy these requirements or are in a Region/municipality that is not found in the list of ISTAT's Italian Regions/municipalities, are first converted using Google geocoding service (if geocoded using Open Street Maps or Bing) and then dropped, if geocoding results are still not satisfactory. Finally, a plot shows on a map the dataset's processed buildings in this refined version of the CENED dataset.

**INPUT:**

- output dataset of the previous script `data/interim/cened_data_filtered.csv` 
- shape file with the Italian regions `data/external/Reg01012022_g_WGS84.shp` (download https://www.istat.it/it/archivio/222527)
- shape file with the Italian municipalities `data/external/Com01012022_g_WGS84.shp` (download https://www.istat.it/it/archivio/222527)

**OUTPUT:**

- saved as `data/interim/cened_geocoded.csv` and `.shp` (geocoded CENED addresses which refer only to buildings with a surface >= 100mq, whose geocoding is precise up to rooftop level and within respective Region/municipality).

**DATA LOSS:**  Starting from ~70k data rows, correctly geocoded data are ~61K. Data loss due to the presence of buildings with no rooftop geolocalization (~7K) or outside of the respective Region/municipality (~1K).


### 3. cened_processing.py

**DESCRIPTION:** Geocoded CENED certificates are further filtered.

Data is filtered by removing buildings which were subject to important rebuilding or energy performance requalification (these could decrease correlation between year and APE). Only features which are considered to be useful for interpretation of the results of AI models are kept. Moreover, the labels year of construction and energy classes are merged in representative categories.  Finally, a plot shows on a map the dataset's processed buildings in this refined version of the CENED dataset.

**INPUT:**

- output dataset of the `01-cened_filtering.py` script `data/interim/cened_data_filtered.csv` 
- output geocoded data of the previous script `data/interim/cened_geocoded.shp` 
- shape file with the Italian regions `data/external/Reg01012022_g_WGS84.shp` (download https://www.istat.it/it/archivio/222527)

**OUTPUT:**

- saved as `data/interim/cened_processed.csv` and `.shp` (geocoded CENED addresses containing only possibly useful features).

**DATA LOSS:** Starting from ~61k data rows, correctly geocoded data are ~52K. Data loss due to removing buildings which were subject to important rebuilding or energy performance requalification (~9K).


### 4. openeo_download.py

**DESCRIPTION:** Download of Sentinel 2 images by using the openEO service (https://openeo.org/) through EURAC's server. 

For information about the collections and the processes available on the server, please visit https://hub.openeo.org/.

The script computes the size of Lombardy through the respective shapefile and how many tails should be downloaded in order to cover the region. Only tails that contain at least one builidng are considered. Currently, each raster is 20x20km and weights approximately 120mb while containing 14 bands. Note that tails larger than 500mb will cause EURAC's openEO service to fail due to some memory error. Unfortunately, EURAC's server has some issues and, if the download of a raster fails, it just shows a generic error without explaining what went wrong.

First, we download cloud mask time series from `2021-06-01` to `2022-09-01` for all tails (saved in `data/interim/openeo/cloud-mask`), to evalaute which are the best dates to select images. We selected dates considering availability of images and low cloud presence. For summer and winter condition we selected respectively `2021-08-14` and `2022-01-11`.

The script automatically tries to download all tails for winter and summer images saved in `data/interim/openeo/winter`) and `data/interim/openeo/summer` respectively. in case of failure, the script tries up to 3 times to download missing tails. When the script ends, manually check whether all tails are available (72 tails). 

Directories where tails are saved are named according to parent geometry name and the tail id name. Tail name is given according to its position in the grid starting from the top left corner (row, column). The temporal extent of the image, and the date-time value at the download are also indicated in the directory name. Resulting name is of type `tail_{id_parent}_{id_name}_openeo_{start_date}_{end_date}_now_{download_date_time}` e.g., `tail_S2_eurac_5x2_openeo_2021-08-13_2021-08-15_now_2022-11-11_h11_m53_s13` is the tail in the 5th row, 2nd column obtained using data from 2021-08-13 to 2021-08-13, that was downloaded the 2022-11-11 at h11:m53:s13.

Example grid indexes (3x3):

|       |       |        |
|:-----:|:-----:|:------:|
| (0,0) | (0,1) | (0, 3) |
| (1,0) | (1,1) | (1, 3) |
| (2,0) | (2,1) | (2, 3) |


**INPUT:** 

- Output dataset of the previous script`data/interim/cened_processed.csv` and `.shp` (geocoded CENED addresses containing only possibly useful features).
- shape file with the Italian regions `data/external/Reg01012022_g_WGS84.shp` (download https://www.istat.it/it/archivio/222527)
- GeoJSON file with the Sentinel-2 tails `data/external/S2_tiles.geojson` 

**OUTPUT:** 

- Shapefile with the Sentinel-2 tails cropped to lombardy `data/interim/S2_eurac.shp`
- Cloud mask timeserires are saved ad `.json` files in `data/interim/openeo/cloud-mask/`.
- Winter images are saved as `.tiff` files in `data/interim/openeo/winter`.
- Summer images are saved as `.tiff` files in `data/interim/openeo/summer`.

Each tail has it own subfolder named according to parent geometry name and the tail id name. Tail name is given according to its position in the grid starting from the top left corner (row, column). The temporal extent of the image, and the date-time value at the download are also indicated in the directory name. Resulting name is of type `tail_{id_parent}_{id_name}_openeo_{start_date}_{end_date}_now_{download_date_time}` e.g., `tail_S2_eurac_5x2_openeo_2021-08-13_2021-08-15_now_2022-11-11_h11_m53_s13` is the tail in the 5th row, 2nd column obtained using data from 2021-08-13 to 2021-08-13, that was downloaded the 2022-11-11 at h11:m53:s13.

**DATA LOSS:** Part of the lombardy (bottom) is not covered by Sentinel 2 tails available from the EURAC server `S2_L2A_ALPS` (see https://maps.eurac.edu/layers/saocompute:geonode:EURAC_S2_RGB_10m_alps_last). Thus, 2944 buildings are not covered.


### 5. osm_meteo_download.py

**DESCRIPTION:** Download of OSM buildings shapefiles and temperature data. 

Given the list of point geocoded buildings, we retrieve the buildings geometry from Open Street Maps data. For each builiding point, the nearest geometry (within 100m) is selected. If no building is within 100m, empty geom is returned.

Data ERA5 2m temperature is downloaded manually form the website (https://cds.climate.copernicus.eu/cdsapp#!/dataset/reanalysis-era5-single-levels?tab=overview). Following data is considered:

- Winter. date-time `time 10 hrs:from 202201110000`
- Summer. date-time `time 10 hrs:from 202108140000`

Data is imported and shaped into geopandas with tail polygons covering the area.

**INPUT:** 

- Output dataset of the previous script `data/interim/cened_processed.csv` and `.shp` (geocoded CENED addresses containing only possibly useful features).
- shape file with the Italian regions `data/external/Reg01012022_g_WGS84.shp` (download https://www.istat.it/it/archivio/222527)
- Shapefile with the Sentinel-2 tails cropped to lombardy `data/interim/S2_eurac.shp`
- ERA5 winter data `data/external/data-meteo-winter.grib`
- ERA5 summer data `data/external/data-meteo-summer.grib`

**OUTPUT:** 

- GeoJson file with building geoms `data/interim/osm_buildings.geojson`. Available columns are `COD_APE` indicating the building id, `id_tail` indicating the tail id containing the building, and `geometry`. If no building was within 100m, empty geom is returned.
- GeoJson file with ERA5 winter and summer temperature data `data/interim/era5-temperature.geojson`. Available columns are `temp-winter` and `temp-summer` indicating the temperature in Celsius, and `geometry`.

### 6. openeo_processing.py

**DESCRIPTION:** Get the dataframe used in the analysis.

Add temperature data (winter and summer) to each building. Get summary statistics (count, min, mean, and max) of the pixels of each respective building for each band of satellite data. Finally, data gets filtered due to the presence of empty values, shadow, or clouds.

Final dataset ready for the analysis is saved.

**INPUT:** 

- Output dataset of the previous script `data/interim/cened_processed.csv` and `.shp` (geocoded CENED addresses containing only possibly useful features).
- Shapefile with the Sentinel-2 tails cropped to lombardy `data/interim/S2_eurac.shp`.
- GeoJson file with building geoms `data/interim/osm_buildings.geojson`.
- GeoJson file with ERA5 winter and summer temperature data `data/interim/era5-temperature.geojson`.

**OUTPUT:** 

- CSV file with the final dataset ready for the analysis `data/processed/data_analysis.csv`. 


**DATA LOSS:** Remove around 20,000 observations due to not available images, certification after image date, empty geometries, not correct geocoding (building geometry distant more than 50m  from the point), and buildings smaller than 100m2. Remove around 700 observations due to clouds or shadows in the satellite image. Final data includes around 26,000 observations.


### 7. models_application.py

DESCRIPTION: Apply some machine learning models after properly encoding labels, splitting data in training/test sets, normalizing features. 

Models tried: Gaussian Naive Bayes Classifier, Gradient Boosting Classifier, Random Forest Classifier, and XGB classifier. Confusion matrices together with precision and recall are computed for each class.

INPUT: 

- CSV file with the final dataset ready for the analysis `data/processed/data_analysis.csv`. 

## Authors and acknowledgment
Manuel Dalcastagnè (manuel.dalcastagne@eurac.edu -> manuel.dalcastagne@gmail.com) contributed to the project until the 11th of September, 2022. 

## LICENSE

<a rel="license" href="http://creativecommons.org/licenses/by/4.0/"><img alt="Creative Commons License" style="border-width:0" src="https://i.creativecommons.org/l/by/4.0/88x31.png" /></a><br />This
work is licensed under a
<a rel="license" href="http://creativecommons.org/licenses/by/4.0/">Creative
Commons Attribution 4.0 International License</a>.
