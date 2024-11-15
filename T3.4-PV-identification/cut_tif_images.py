import rasterio
from rasterio.mask import mask
import numpy as np
import pandas as pd
from pathlib import Path
import osmnx as ox
import os
import rasterio
from PIL import Image
from shapely.geometry import box
from concurrent.futures import ThreadPoolExecutor, as_completed
import json
import tqdm


max_cpu_count = int(os.cpu_count() * 0.75)  # leave room for other processes
CPU_COUNT = max(1, max_cpu_count)  # ensure 1 core at least
OSM_IDS = []  # global variable to save the IDs to not save them twice in case the tifs overlap
OSM_IDS_BELOW_45 = []


def add_building_coordinates_to_json(df_filtered: pd.DataFrame) -> None:
    """This function creates and saves a json file which contains the coordinates of every uilding downloaded from OSM and used in the analysis."""
    # calculate lan and long and save them together with the osm id:
    d = df_filtered.set_index("osmid").geometry.to_crs(epsg=32630) # UTM Zone 30N
    centroids_projected = d.centroid
    centroids = centroids_projected.to_crs(epsg=4326)

    d = d.reset_index().set_index("osmid")
    d.loc[:, "lat,lon"] = (centroids.y.astype(str) + "," + centroids.x.astype(str))
    d.drop(columns="geometry", inplace=True)

    dictionary = d.to_dict()["lat,lon"]
    # load existing dict:
    path_2_dict = Path(__file__).parent / "results" / "OSM_IDs_lat_lon.json"
    if path_2_dict.exists():
        with open(path_2_dict, "r") as f:
            file = json.load(f)
    else:
        file = {}
        (Path(__file__).parent / "results").mkdir(exist_ok=True)
    
    len_0 = len(file)
    len_dict = len(dictionary)
    file.update(dictionary)
    # check if keys have been overwritten
    if len_0 + len_dict != len(file):
        assert "Dict keys have been overwritten! OMS ID was not unique or a building appeared in 2 different tif files."
    # save updated json
    with open(path_2_dict, "w") as f:
        json.dump(file, f)
    print("updated json file")


def download_osm_building_shapes(source: str) -> pd.DataFrame:
    """ downloads all building shapes that are within the bounds of the source"""
    print(f"downloading osm data for {Path(source.name).name}...")
    bounds = source.bounds
    polygon = box(bounds.left, bounds.bottom, bounds.right, bounds.top)
    polygon_wgs84 = ox.projection.project_geometry(polygon, crs=source.crs, to_crs='EPSG:4326')[0]
    try:
        buildings = ox.features_from_polygon(polygon=polygon_wgs84, tags={"building": True})
    except ox._errors.InsufficientResponseError:
        print(f"no building data found for {Path(source.name).name}")
        return pd.DataFrame()
    
    areas = buildings.to_crs(epsg=3857).area
    columns_2_keep = ["geometry", "building", ]
    df = buildings.loc[:, columns_2_keep]
    df["area"] = areas
    # save the IDs that are excluded because they are smaller than 45m^2 to know later how many were excluded in total
    df_below_45 = df.loc[df["area"] <= 45, :].copy().reset_index()
    ids_not_used_below_45 = list(set(list(df_below_45["osmid"])) - set(OSM_IDS_BELOW_45))
    OSM_IDS_BELOW_45.extend(ids_not_used_below_45)

    df_filtered = df.loc[df["area"] > 45, :].copy().reset_index()
    # filter out the IDS that have already been saved because the tifs are overlapping:
    ids_not_used = list(set(list(df_filtered["osmid"])) - set(OSM_IDS))
    df_id_filtered = df_filtered[df_filtered["osmid"].isin(ids_not_used)].copy()
    print(f"{len(df_filtered) - len(ids_not_used)} ids are already in the dataset and are skipped")
    OSM_IDS.extend(ids_not_used)

    # save the building coordinates:
    add_building_coordinates_to_json(df_id_filtered)

    # df_filtered.to_file(Path(__file__).parent / "solar-panel-classifier" / "new_data" / f'{Path(source.name).name.replace(".tif", "")}.gpkg', driver="GPKG")
    return df_filtered


def cut_tif(processed_folder, building, src, orig_file, imsize, save_png):
    """ cuts avery building polygon as image from the tif file, resizes it and saves it as numpy file"""
    # Mask the image using the building polygon
    image_path = processed_folder / f"building_{building.osmid}.npy"
    if image_path.exists():
        return None

    try:
        out_image, out_transform = mask(src, [building["geometry"]], crop=True)
    except Exception as e:
        print(f"building {building.osmid} out of bounds. {e}")
        return None
    
    # Calculate bounds for a 224x224 window around the centroid
    # centroid = building["geometry"].centroid
    bounds = building['geometry'].bounds
    min_px, min_py = src.index(bounds[0], bounds[1])  # minx, miny
    max_px, max_py = src.index(bounds[2], bounds[3]) 
    # if min and max are change - swap them
    if min_px > max_px:
        min_px, max_px = max_px, min_px

    if min_py > max_py:
        min_py, max_py = max_py, min_py

    # Ensure the pixel coordinates are within image bounds
    px_min = max(0, min_px)
    px_max = min(orig_file.shape[1], max_px)
    py_min = max(0, min_py)
    py_max = min(orig_file.shape[2], max_py)
    
    clipped_orgfile = orig_file[:3, int(px_min):int(px_max), int(py_min):int(py_max)]  # CAREFUL, this is writte for RGBI images, cutting the infrared part

    # Convert to PIL Image, resize, then convert back to NumPy array
    img = np.moveaxis(clipped_orgfile, 0, -1)  # Rearrange (bands, x, y) to (x, y, bands)
    img = Image.fromarray(img.astype('uint8'))  # Convert to unsigned 8-bit integer format
    img_resized = img.resize((imsize, imsize), Image.LANCZOS)
    clipped_orgfile = np.moveaxis(np.array(img_resized), -1, 0) 
    
    np.save(processed_folder / f'building_{building.osmid}.npy', clipped_orgfile)

    # to check the images:
    if save_png:
        img_resized.save(processed_folder/ "unlabelled" / f"building_{building.osmid}.png")


def cut_tif_into_building_photos(buildings, src, imsize: int, save_png: bool):
    # create folders:
    processed_folder = Path(__file__).parent / "solar-panel-classifier" / "new_data" / "processed" 
    processed_folder.mkdir(parents=True, exist_ok=True)

    # cut out the buildings from the photos:
    orig_file = src.read()

    print("cutting rooftop pics out of tif...")
    with ThreadPoolExecutor(max_workers=CPU_COUNT) as executor:   
        cut_tasks = [executor.submit(cut_tif, processed_folder, building, src, orig_file, imsize, save_png) for _, building in buildings.iterrows()]
        for future in as_completed(cut_tasks):
            future.result() 
        

def is_black(file_path: Path):
    try:
        img_array = np.load(file_path)
        
        # Check if all the pixels are black
        if np.all(img_array == 0):
            # If the image is black, delete it
            os.remove(file_path)
            png_path = file_path.parent / "unlabelled" / file_path.name.replace(".npy", ".png") # also delete corresponding png file if exists
            if png_path.exists():
                os.remove(png_path)
                
            print(f"Removed black image: {file_path.name}")

    except Exception as e:
        print(f"Error processing {file_path.name}: {e}")


def remove_black_images(image_folder: Path):
    """
    This function checks each image in the folder and removes the black images.
    
    Args:
    image_folder (str): Path to the folder containing the images.
    """
    # Get all PNG files in the folder
    files = [f for f in image_folder.iterdir() if f.name.endswith('.npy')]
    with ThreadPoolExecutor(max_workers=CPU_COUNT) as executor:       
        remove_tasks = [executor.submit(is_black, file_path) for file_path in files]
        for future in as_completed(remove_tasks):
            future.result()


def main(save_png: bool=False):
    tif_folder = Path(__file__).parent / "solar-panel-classifier" / "new_data" / "input_tifs"
    input_tifs =  [f for f in tif_folder.iterdir() if f.suffix == ".tif"]

    for file in tqdm.tqdm(input_tifs):
        src = rasterio.open(file)
        buildings = download_osm_building_shapes(src)
        if buildings.empty:
            continue
        buildings.reset_index(inplace=True)

        if src.crs != buildings.crs:
            buildings = buildings.to_crs(src.crs)
        cut_tif_into_building_photos(buildings=buildings, src=src, imsize=224, save_png=save_png)

    # some images are just black, remove them
    remove_black_images(image_folder=Path(__file__).parent / "solar-panel-classifier" / "new_data" /"processed")

    print(f"{len(OSM_IDS_BELOW_45)} building shapes excluded because their ground are is below 45m^2")  


if __name__ =="__main__":
    main(save_png=False)







