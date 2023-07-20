## README Data


### Data Sources

To obtain the processed data used in the analysis, the following data sources were used:

- CENED+2 dataset (https://www.dati.lombardia.it/Energia/Database-CENED-2-Certificazione-ENergetica-degli-E/bbky-sde5), open dataset regaring builidng Energy Performance Certificates (EPCs) for the Lombardy Region (Italy). For a description of the features, please see https://www.dati.lombardia.it/api/views/bbky-sde5/files/37c35b51-f538-4ebd-8b29-8d861f8e1e7b?download=true&filename=descrizione_campi_cened.pdf.
- Shape file with the Italian regions (download https://www.istat.it/it/archivio/222527)
- Shape file with the Italian municipalities (download https://www.istat.it/it/archivio/222527)
- Sentinel-2 Satellite images were downloaded form the openEO service (https://openeo.org/). For information about the collections and the processes available on the server, please visit https://hub.openeo.org/.
- Buildings geometry was obtained from Open Street Maps data using the OSMnx Python package (https://osmnx.readthedocs.io/en/stable/).
- Data ERA5 2m temperature was downloaded manually form the website (https://cds.climate.copernicus.eu/cdsapp#!/dataset/reanalysis-era5-single-levels?tab=overview).

After all the required preprocessing steps, the final dataset `data-analysis.csv` was obtained. 


### `data-analysis.csv`

The obtained dataset includes the information regarding the builidngs included in the analysis.  The dataset has the 26192 rows and 88 columns. Each row rapresents a single building and the following variables are provided:

- `YEAR_BUILD` - Factor variable indicating the building construction period (7 levels: `"Before 1945"`, `"1945 - 1969"`, `"1970 - 1979"`, `"1980 - 1989"`, `"1990 - 1999"`, `"2000 - 2010"`, and  `"After 2010"`);
- `ENER_CLASS` - Factor variable indicating the building EPC class (7 levels: `"A"`, `"B"`, `"C"`, `"D"`, `"E"`, `"F"`, and  `"G"`);
- `summer_temp` - Numeric variable indicating the temperature [in Celsius] in summer (`2021-08-14` at `10.00 am`);
- `winter_temp` - Numeric variable indicating the temperature [in Celsius] in winter (`2022-01-11` at `10.00 am`);

Information obtained by elaborating the two stellite images taken in summer (`2021-08-14`) and winter (`2022-01-11`) are provided in the remaining columns. All columns are numeric and are named aaccording to the following convention:

> `{image}_{band}_{statistic}`

Where

- `image` indicate the image to which values refer, one between `summer` and `winter`.
- `band` indicate the band to which values refer, one between `AOT`, `B02` ,`B03`, `B04`, `B05`, `B06`, `B07`, `B08`, `B11`, `B12`, `B8A`, `SCL`, `WVP`, and `CLOUD_MASK`. For the description of the different bands, see https://docs.sentinel-hub.com/api/latest/data/sentinel-2-l2a/.
- `statistic`indicate the summmary statistic to which values refer, one between `max`, `mean`, `min`.

