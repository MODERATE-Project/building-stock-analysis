# Case Study II and III

In *“Case Study II: Photovoltaic Data Extraction from Aerial Imagery”*, we presented an approach based on aerial images to detect installed photovoltaic panels and estimate the installed photovoltaic capacity on rooftops in urban areas.

In *“Case Study III: Analysis Photovoltaic Distribution in Relation to Urban Morphology from Aerial Imagery”*, we investigated the relationship between urban residential and industrial areas with respect to presence of PV installations. 

## Data Sources

To obtain the processed data used in the analysis, the following data sources were used:

- The aerial imagery used in this project is freely available as open data and has been retrieved from the portal of IDEV [Infraestructura Valenciana de Dades Espacials](https://geocataleg.gva.es/#/search?uuid=spaicv0202_2022CVAL0025&lang=spa). 

    The imagery consists of orthophotos in natural color (red, green, and blue - RGB) and false infrared color (IRG) covering the extent of the Comunidad Valenciana at a resolution of 25 centimeters per pixel. The images are based on a RGBI digital photogrammetric flight and were taken from 08/05/2022 to 11/06/2022. The data was downloaded in the form of six 1:5.000 sheets in a TIFF format which were then patched as a unique image in a GIS environment.  

- Bottom-up data on photovoltaic installations in Crevillent have been provided by Enercoop, the energy cooperative managing the electricity network of the town. The data was in the form of a list of 98 addresses with photovoltaic installations as of 2022 and the relative installed inverter capacity expressed in Watts. 

Data have been elaborated as described in *“Deliverable 3.1: Dynamic Building Stock Analysis”*. 
The obtained final dataset used in the analysis is `MODERATE-D3.1-Dataset2_3.csv`.

## Data Description

`v1.0_Data_T3.1_Dynamicanalysis_PVanalysis.csv` is the output of the study containing information regarding rooftop photovoltaic presence in Crevillent, Spain. The dataset includes the following columns:

- `id_building`. Factor variable indicating the id number of each detected building.
- `h`. Numerical variable indicating the height [m] of each specific building.
- `Roof area`.  Numerical variable indicating the roof area [m2] of each specific building.
- `municipio`. Binomial variable where 1 indicates the presence of the building within the municipality.
- `id_landuse`. Factor variable indicating the id number of the area of Crevillent in which the building is located.
- `Name`. Factor variable indicating the name of the area of Crevillent in which the building is located.
- `Land Use`. Factor variable indicating the whether the land use of the area of Crevillent in wh`ich the building is located is industrial or residential.
- `Id_pv`. Factor variable indicating the id number of the PV installation.
- `pv_area_m2`. Numerical variable indicating the surface area [m2] of each specific pv installation.
- `pv_presence`. Binomial variable indicating the presence of pv installations.


> Missing values were indicated by `999`.


# Advancement of Case Study III - Analysis Photovoltaic Distribution
The previously developed code could not be scaled up, therefore a new approach to identify PV images from Aerial Imagery was taken. As a case study the region of Valencia was analyzed as a whole. The image classifier used is described within the `README` of `solar-panel-classifier` and can be downloaded and retrained freely. 

2 additional scripts are added to this repository which make it possible to reproduce the workflow presented in D3.4. 

## Data preparation
For the case study presented, data was downloaded in `tif` format for the regions [Valencia](https://descargas.icv.gva.es) and [Bolzano](https://mapview.civis.bz.it). To create images for the image classifier following workflow needs to be appllied:


1) train the model as described in `\solar-panel-classifier\README.md`. 
2) download the areal images where building rooftops should be classified. The resolution should be 25x25 cm. Save those `.tif` files under `\solar-panel-classifier\new_data\input_tifs`.
3) open `prepare_data.py` and define `labeling` as `True` or `False` and run the script. If set to True, the images of rooftops will be provided 1 by 1 using tkinter and the user needs to input 1 or 0 if there is PV visible on the roof. (1=PV visible, 0=no PV visible). Setting `labeling` to False just generates the images of the building polygons within each `.tif` file.
4) use `\solar-panel-classifier\run.py` to classify new data. Make sure to set `labeled` according to the `labeling` parameter of the previous point. As an output `Classifier_Results.csv` will be generated within the folder `\solar-panel-classifier\new_data`, containing the OSM ID of each building and the prediction value (0 and 1) if the respective building is equipped with a PV system.



