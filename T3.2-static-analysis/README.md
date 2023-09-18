# Task 3.2 - Bottom-up approach: Static building stock analysis

In this directory, data regarding the Building stock for the EU27 (reference year 2020) are provided.

This activity is part of the Horizon EU project MODERATE (https://moderate-project.eu/).



## Directory Structure

The directory is structured as follow:

- `data /` directory collecting all data
	- `HEU MODERATE Building Stock Data_Sources.csv` data in the long format with all details and data source 
	- `HEU MODERATE Building Stock Data.xlsx` data in the wide format (separate sheet for each country

### Columns Abbreviation Legend

#### Building Sector Information

- `country_num` country code number
- `country_code` country abbreviation
- `country` country name 
- `sector` building sector
- `subsector` building subsector
- `bage` building construction period

#### Building Sector Characteristics

- `area_Mm2` constructed area [million square meters]
- `area_heated_Mm2` heated area [million square meters]
- `area_cooled_Mm2` cooled area [million square meters]
- `build_M` number of buildings [million]
- `dwellings_M` number of dwellings [million]
- `owner_occupied_M` number of owner occupied dwellings [million]
- `private_rented_M` number of private dwellings [million]
- `social_housing_M` number of social housing dwellings [million]
- `occupied_M` number of occupied dwellings [million]
- `vacant_M` number of vacant dwellings [million]
- `secondary_M` number of secondary dwellings [million]
- `floor` number of floors [unit]
- `volume_surface_ratio_m` volume to surface ratio [meters]
- `vertical_area_m2` vertical area [square meters]
- `ground_m2`  ground area [square meters]
- `surface_windows_m2` window surface [square meters]
- `u_roof_W_m2K` roof u-values [W/m²K]
- `u_walls_W_m2K` walls u-values [W/m²K]
- `u_windows_W_m2K` windows u-values [W/m²K]
- `u_floor_W_m2K` floors u-values [W/m²K]

#### Construction  Materials and Methodology

- `walls_material_*` wall construction materials (e.g., brick, concrete, wood, and other)	
- `walls_methodology_*` wall construction methodology (e.g., solid wall, solid wall with insulation,  cavity wall, cavity wall with insulation, honeycomb bricks hollow blocks wall, honeycomb bricks hollow blocks wall with insulation, and other)
- `windows_material_*` window construction materials (e.g., wood, synthetic PVC, and aluminium)	
- `windows_methodology_*` window construction methodology (e.g., single glazing, double glazing, double glazing with low-e, triple glazing, and triple glazing with low-e)
- `roof_material_*` roof construction materials (e.g., wood, concrete, and concrete plus bricks)
- `roof_methodology_* ` roof construction methodology (e.g., tilted roof, tilted roof with insulation, flat roof, and flat roof with insulation)
- `floor_material_*` floor construction materials (e.g., wood, concrete, concrete plus bricks, and other)
- `floor_methodology_*` floor construction methodology (e.g., concrete slab, concrete slab with insulation, wooden floor rafters boards, wooden floor rafters boards, and other)

#### H&C Systems 

- `SH_*` space heating system (e.g., individual, central, district heating, boiler non-condensing, boiler condensing, combined, stove, electric heating, heat pump, fossil fuels solid, fossil fuels liquid, fossil fuels gas, electricity, and biomass)	
- `SC_*` space cooling system (e.g., no space cooling, space cooling)
- `DHW_*` domestic hot water (e.g., individual, central, district heating, boiler non-condensing,boiler condensing,	combined, solar collectors, heat pump, fossil fuels solid, fossil fuels liquid, fossil fuels gas, electricity, and biomass)

#### Energy Indicators

- `ued_sh_kWh_m2` useful energy demand for space heating [kWh/m2]
- `ued_sc_kWh_m2` useful energy demand for space cooling [kWh/m2]
- `ued_dhw_kWh_m2` useful energy demand for domestic hot water [kWh/m2]
- `tot_ued_sh_dhw_TWh` total useful energy demand for space heating and domestic hot water [TWh]
- `tot_ued_sc_TWh` total useful energy demand for space cooling [TWh]
- `fec_sh_kWh_m2` final energy consumption for space heating [kWh/m2]
- `fec_sc_kWh_m2` final energy consumption for space cooling [kWh/m2]
- `fec_dhw_kWh_m2` final energy consumption for domestic hot water [kWh/m2]
- `tot_fec_sh_dhw_TWh` total final energy consumption for space heating and domestic hot water [TWh]
- `tot_fec_sc_TWh` total final energy consumption for space cooling [TWh]


## How to Cite

> Simon Pezzutto, Dario Bottino, Arif Farahi Mohammad, and Eric  Wilczynski . Deliverable 32: Static building stock analysis. Moderate Project. 2023 https://moderate-project.eu/  

<br>

```
@techreport{pezzuttoModerateProjectD32023,
    title = {Deliverable 3.2: {{Static}} Building Stock Analysis. {{Moderate Project}}.},
    author = {Pezzutto, S and Bottino, Dario and Farahi Mohammad, Arif and Wilczynski, Eric},
    year = {2023}
}
```