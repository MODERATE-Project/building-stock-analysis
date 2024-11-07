import tkinter as tk
from tkinter import Tk, Label, Entry, Button
from pathlib import Path
from PIL import Image, ImageTk
import os
import pandas as pd
import numpy as np
import shutil
import random


def label_images(image_folder, label_path: Path):
    """
    Open images in a folder using a Tkinter window, allow the user to label them, 
    and append the label to the file name.
    Labeled images are ignored.
    
    Args:
    image_folder (str): The directory where the images are stored.
    """
    def display_image(file_path: Path):
        """Display the image in the Tkinter window and get user input for the label."""
        image_array = np.load(file_path)
        img = np.moveaxis(image_array, 0, -1) 
        img = Image.fromarray(img.astype('uint8'))

        img.thumbnail((800, 800))  # Resize the image to fit in the window
        
        # Update the image in the window
        img_tk = ImageTk.PhotoImage(img)
        
        # Keep the image reference to avoid garbage collection
        img_label.config(image=img_tk)
        img_label.image = img_tk  # Keeping a reference to avoid it being collected
        
        # Update the filename label
        filename_label.config(text=file_path.name)

        # Clear and focus on the input field
        label_entry.delete(0, 'end')  # Clear any previous input
        label_entry.focus()

        # Update the window
        root.update_idletasks()
        img.close()

    def save_label():
        """Save the label and rename the file."""
        label = label_entry.get().strip().lower()

        if label in ["0", "1"]:
            # Generate the new file name with the label
            new_file_name = f"{current_file.name.replace('.npy','')}_{label}.npy"
            new_file_path = image_folder / "labeled" / new_file_name

            # Rename the file (overwrite the original image)
            shutil.copy(current_file, new_file_path)
            print(f"Image {current_file} labeled as '{label}' and renamed to {new_file_name}")

            # Move to the next image
            next_image()
        else:
            error_label.config(text="Invalid input. Please type '1='yes or '0'=no.", fg="red")

    def next_image():
        """Load the next image."""
        nonlocal current_file

        try:
            current_file = next(files_iter)  # Get the next image file
            display_image(current_file)
        except StopIteration:
            print("No more images to label.")
            root.quit()

    # Get the list of PNG files that are not already labeled
    if label_path.exists():
        labels = pd.read_csv(label_path, sep=";")
        identified_ids = list(labels["osmid"].values)
    else:
        identified_ids = []
    files = [f for f in (image_folder).iterdir() if f.name.endswith(".npy") and not ("_0.npy" in f.name or "_1.npy" in f.name)]
    labeled_ids = [f.name.replace(".npy", "").replace("building_", "")[:-2] for f in (image_folder/"labeled").iterdir() if f.name.endswith(".npy")]
    # drop the ids from the csv file in case the images have been moved or deleted and the info is just stored in the csv file:
    files_2 = [f for f in files if f.name.replace(".npy", "").replace("building_", "") not in identified_ids]
    files_3 = [f for f in files_2 if f.name.replace(".npy", "").replace("building_", "") not in labeled_ids]
    random.shuffle(files_3)  
    files_iter = iter(files_3)

    # Set up Tkinter window
    root = Tk()
    root.title("Image Labeling")

    # Set up the layout
    img_label = Label(root)
    img_label.pack()

    filename_label = Label(root, text="")
    filename_label.pack()

    label_entry = Entry(root)
    label_entry.pack()

    submit_button = Button(root, text="Submit", command=save_label)
    submit_button.pack()

    error_label = Label(root, text="")
    error_label.pack()

    # Start labeling the first image
    current_file = None
    next_image()

    # Start the Tkinter event loop
    root.mainloop()


def create_csv_with_labels(folder: Path, label_file: Path):

    files = [f.name for f in folder.iterdir() if f.name.endswith("_0.npy") or f.name.endswith("_1.npy")]
    id_dict = {}
    for f in files:
        osmid = f.replace("building_", "").replace("_0.npy", "").replace("_1.npy", "")
        pv_bool =  f.split("_")[-1].replace(".npy","")
        if pv_bool == "0":
            has_pv = "no"
        elif  pv_bool == "1":
            has_pv = "yes"
        else:
            assert "wrong pv bool in image name"
        id_dict[osmid] = has_pv
    df = pd.DataFrame.from_dict(id_dict, orient="index").reset_index().rename(columns={"index": "osmid", 0: "has_pv"})

    if label_file.exists():
        label_df = pd.read_csv(label_file, sep=";")  # read the file with labels that were already saved
        df_sum = pd.concat([label_df, df], axis=0)
        # df_sum.drop_duplicates(inplace=True)
    else:
        df_sum = df
    
    df_sum.drop_duplicates(inplace=True)  # drop duplicates in case this function is called multiple times with the same data
    df_sum.to_csv(label_file, sep=";", index=False)
    print(f"saved {label_file}")


def shift_numpy_files_into_empty_and_solar_folders(numpy_folder: Path, label_file: Path):
    # numpy files are saved in image folder parent and are shifted in the correct folders here:
    empty_folder = numpy_folder / "empty/org"  
    solar_folder = numpy_folder / "solar/org"
    empty_folder.mkdir(exist_ok=True, parents=True)
    solar_folder.mkdir(exist_ok=True, parents=True)
    
    # iterate through labeled folder:
    labeled_folder = numpy_folder / "processed" / "labeled"
    for file in [f for f in labeled_folder.iterdir() if f.is_file()]:
        label = file.name.split("_")[-1].replace(".npy", "")
        if label == "0":
            if not (empty_folder / file.name).exists(): # dont copy twice in case it was copied before
                file.rename(empty_folder / file.name)
        else:
            if not (solar_folder / file.name).exists():
                file.rename(solar_folder / file.name)
    print(f"moved labeled files from {labeled_folder} to empty {empty_folder} and solar folder {solar_folder}")
        
    # in case some files in the labeled folder are not there but we have the labels in the Labels File:
    # labels = pd.read_csv(label_file, sep=";")
    # for i, row in labels.iterrows():
    #     file = numpy_folder / "processed" / f'building_{row["osmid"]}.npy'
    #     label = row["has_pv"]
    #     if label == "no":
    #         if not (empty_folder / file.name).exists(): # dont copy twice in case it was copied before
    #             shutil.copy(file, empty_folder / file.name)
    #     else:
    #         if not (solar_folder / file.name).exists():
    #             shutil.copy(file, solar_folder / file.name)


    
    # emtly = [f for f in empty_folder.iterdir() if f.name.endswith("_0.npy")]
    # empty_n = [f for f in empty_folder.iterdir() if f.name.endswith(".npy") and not f.name.endswith("_0.npy")]
    # total = empty_n + emtly

    # solar_ = [f for f in solar_folder.iterdir() if f.name.endswith("_1.npy")]
    # solar = [f for f in solar_folder.iterdir() if f.name.endswith(".npy") and not f.name.endswith("_1.npy")]
    # total_solar = solar + solar_
    # ls = []
    # for  file in total_solar:
    #     if file.name.endswith("_1.npy"):
    #         name = file.name.replace("_1.npy", ".npy")
    #         if name in ls:
    #             file.unlink()
    #             print(f"deleted {file}")
    #         else:
    #             ls.append(name)
    #     else:
    #         ls.append(file.name)
    

            
        


def main():
    # preped_image_folder = Path(__file__).parent / "solar-panel-classifier" / "new_data" / "processed"
    # label_file = Path(__file__).parent / "OSM_IDs_labeled.csv"

    preped_image_folder = Path(r"X:\projects4\workspace_philippm\building-stock-analysis\T3.1-dynamic-analysis\Case-study-II-III-PV-analysis\solar-panel-classifier\new_data\processed")
    label_file = Path(r"X:\projects4\workspace_philippm\building-stock-analysis\T3.1-dynamic-analysis\Case-study-II-III-PV-analysis") / "OSM_IDs_labeled.csv"

    if not preped_image_folder.exists():
        preped_image_folder.mkdir(parents=True)
    if not (preped_image_folder / "labeled").exists():   
        (preped_image_folder / "labeled").mkdir(parents=True)

    # create csv file before and after to make sure the labeles from the previous run, if aborted are updated
    create_csv_with_labels(preped_image_folder / "labeled", label_file)
    label_images(preped_image_folder, label_file)
    create_csv_with_labels(preped_image_folder / "labeled", label_file)

    shift_numpy_files_into_empty_and_solar_folders(numpy_folder=preped_image_folder.parent, label_file=label_file)


if __name__ == "__main__":
    main()


    

