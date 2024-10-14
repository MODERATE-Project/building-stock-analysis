import tkinter as tk
from tkinter import Tk, Label, Entry, Button
from pathlib import Path
from PIL import Image, ImageTk
import os
import pandas as pd


def label_images(image_folder, label_path: Path):
    """
    Open images in a folder using a Tkinter window, allow the user to label them, 
    and append the label to the file name.
    Labeled images are ignored.
    
    Args:
    image_folder (str): The directory where the images are stored.
    """
    def display_image(file_path, file_name):
        """Display the image in the Tkinter window and get user input for the label."""
        img = Image.open(file_path)
        img.thumbnail((600, 600))  # Resize the image to fit in the window
        
        # Update the image in the window
        img_tk = ImageTk.PhotoImage(img)
        
        # Keep the image reference to avoid garbage collection
        img_label.config(image=img_tk)
        img_label.image = img_tk  # Keeping a reference to avoid it being collected
        
        # Update the filename label
        filename_label.config(text=file_name)

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
            new_file_name = f"{current_file.replace('.png','')}_{label}.png"
            new_file_path = image_folder / new_file_name

            # Rename the file (overwrite the original image)
            os.rename(current_file_path, new_file_path)
            print(f"Image {current_file} labeled as '{label}' and renamed to {new_file_name}")

            # Move to the next image
            next_image()
        else:
            error_label.config(text="Invalid input. Please type '1='yes or '0'=no.", fg="red")

    def next_image():
        """Load the next image."""
        nonlocal current_file, current_file_path

        try:
            current_file = next(files_iter)  # Get the next image file
            current_file_path =image_folder / current_file
            display_image(current_file_path, current_file)
        except StopIteration:
            print("No more images to label.")
            root.quit()

    # Get the list of PNG files that are not already labeled
    if label_path.exists():
        labels = pd.read_csv(label_file, sep=";")
        identified_ids = list(labels["osmid"].values)
    else:
        identified_ids = []
    files = [f for f in image_folder.iterdir() if f.name.endswith(".png") and not ("_0.png" in f.name or "_1.png" in f.name)]
    # drop the ids from the csv file in case the images have been moved or deleted and the info is just stored in the csv file:
    files_2 = [f for f in files if f.name.split("_")[1] not in identified_ids]
    files_iter = iter(files_2)

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
    current_file_path = None
    next_image()

    # Start the Tkinter event loop
    root.mainloop()


def create_csv_with_labels(folder: Path, label_file: Path):

    
    files = [f.name for f in folder.iterdir()]
    id_dict = {}
    for f in files:
        osmid = f.split("_")[1]
        pv_bool =  f.split("_")[2].replace(".png","")
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
        df_sum.drop_duplicates(inplace=True)
    else:
        df_sum = df
    
    df_sum.to_csv(label_file, sep=";", index=False)


def shift_numpy_files_into_empty_and_solar_folders(image_folder: Path, label_file: Path):
    # numpy files are saved in image folder parent and are shifted in the correct folders here:
    empty_folder = image_folder.parent / "empty/org"  
    solar_folder = image_folder.parent / "solar/org"
    empty_folder.mkdir(exist_ok=True, parents=True)
    solar_folder.mkdir(exist_ok=True, parents=True)
    
    labels = pd.read_csv(label_file, sep=";")
    for file in [f for f in image_folder.iterdir()]:
        osmid = file.name.split(".")[0].replace("building_", "")
        label = labels.loc[labels["osmid"]==int(osmid), "has_pv"].iloc[0]
        if label == "no":
            file.rename(empty_folder / file.name)
        else:
            file.rename(solar_folder / file.name)
        


if __name__ == "__main__":
    preped_image_folder = Path(__file__).parent / "data"/ "processed" / "unlabelled"
    label_file = Path(__file__).parent / "data" / "OSM_IDs_with_has_pv.csv"

    if not preped_image_folder.exists():
        preped_image_folder.mkdir(parents=True)

    label_images(preped_image_folder, label_file)
    create_csv_with_labels(preped_image_folder, label_file)

    shift_numpy_files_into_empty_and_solar_folders(preped_image_folder, label_file)

    # clean out the images and numpy files that have been labelled at an earlier stage and thus are not copied to the folders:
    

