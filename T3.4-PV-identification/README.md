# Advancement of Case Study III - Analysis Photovoltaic Distribution
The previously developed code could not be scaled up, therefore a new approach to identify PV images from Aerial Imagery was taken. As a case study the region of Valencia was analyzed as a whole. The image classifier used is described within the `README` of `solar-panel-classifier` and can be downloaded and retrained freely. 

## Data preparation
For the case study presented, data was downloaded in `tif` format for the regions [Valencia](https://descargas.icv.gva.es) and [Bolzano](https://mapview.civis.bz.it). To create images for the image classifier following workflow needs to be appllied:


1) train the model as described in `\solar-panel-classifier\README.md`. 
   
2) download the areal images where building rooftops should be classified. The resolution should be 25x25 cm. Save those `.tif` files under `\solar-panel-classifier\new_data\input_tifs`.
   
3) open `prepare_data.py` and define `labeling` as `True` or `False` and run the script. If set to True, the images of rooftops will be provided 1 by 1 using tkinter and the user needs to input 1 or 0 if there is PV visible on the roof. (1=PV visible, 0=no PV visible). If the labelling process is interrupted the labelled files will be sorted into training and validation folders and saved in a csv file. Labelling can be restarted at any time without having to re-label the already labelled images. Setting `labeling` to False just generates the images of the building polygons within each `.tif` file. Labelling can also be done independent of this pipeline. If this is done the labeled numpy files should be saved under `\solar-panel-classifier\new_data\processed\labeled` under the same name with an extension `_0.npy` or `_1.npy` to implicate if they contain a PV or not (0=no, 1=yes). By running `shift_numpy_files_into_empty_and_solar_folders` from the `label_images.py` the files will be sorted into the training and validation folder performing a 80/20 split.
   
4) use `\solar-panel-classifier\run.py` to classify new data and re-train the existing model. If `labeled` is set to `True` then the model will be validated using the labelled data. If set to `False` the classifier will label all data without performing a validation. As an output `Classifier_Results.csv` will be generated within the folder `\solar-panel-classifier\new_data`, containing the OSM ID of each building and the prediction value (0 and 1) if the respective building is equipped with a PV system.

