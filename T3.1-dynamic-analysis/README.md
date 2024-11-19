# Task 3.1 - Top-down approach: Dynamic building stock analysis

This directory collects the data assembled in *“Task 3.1 - Top-down approach: Dynamic building stock analysis”*.

The scope of Task 3.1 is to explore opportunities for combining dynamic data coming from satellite and/or sensors in buildings to obtain information on the status of the building stock both in terms of characteristics and energy consumption.

Task 3.1 is formed my three case studies:

- **Case Study I: EPCs Classification form Satellite Images.** We proposed a method for automatically classifying building energy performance certificates based on the analysis of satellite images.
- **Case Study II: Photovoltaic Data Extraction from Aerial Imagery.** We presented an approach based on aerial images to detect installed photovoltaic panels and estimate the installed photovoltaic capacity on rooftops in urban areas. This study has been partly enhanced (classification of PV panels) to make it scalable which is described in D3.4 if the project. A detailed description and the code is provided in `Case-study-II-III-PV-analysis`.
- **Case Study III: Analysis Photovoltaic Distribution in Relation to Urban Morphology from Aerial Imagery.** We investigated the relationship between urban residential and industrial areas with respect to presence of PV installations. 


### Directory Structure

The directory is structured as follow:

- `Case-study-I-EPCs-classification/` directory collecting the code and results of case study I.
- `Case-study-II-III-PV-analysis/` directory collecting the code and results of case study II and III.

### How to Cite

> Fabio Giussani, Claudio Zandonella Callegher, Simon Pezzutto, and Eric  Wilczynski.Deliverable 3.1: Dynamic building stock analysis. Moderate Project. 2023 https:/moderate-project.eu/  

<br>

```
@techreport{pezzuttoModerateProjectD32023,
    title = {Deliverable 3.1: {{Dynamic}} Building Stock Analysis. {{Moderate Project}}.},
    author = {Giussani, Fabio and Zandonella Callegher, Claudio and Pezzutto, Simon and Wilczynski, Eric},
    year = {2023}
}
```

PV classification:
> Philipp Mascherbauer ... .Deliverable 3.4: Comparison of dynamic and static data/information of Europe's building stock. Moderate Project. 2023 https:/moderate-project.eu/

```
@techreport{MXXX;,
    title = {Deliverable 3.4: Comparison of dynamic and static data/information of Europe's building stock. {{Moderate Project}}.},
    author = {Philipp Mascherbauer},
    year = {2024}
}

```


Packages to install

`rasterio`
`pandas`
`osmnx`
`tqdm`
`numpy`
`torch`
`seaborn`
`scikit-learn`
`pillow`
`torchvision`

