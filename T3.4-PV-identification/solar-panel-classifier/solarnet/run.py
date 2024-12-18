import torch
from torch.utils.data import DataLoader

import numpy as np
from pathlib import Path
from tqdm import tqdm
from PIL import Image
import pandas as pd

from solarnet.preprocessing import MaskMaker, ImageSplitter
from solarnet.datasets import ClassifierDataset, SegmenterDataset, make_masks
from solarnet.models import Classifier, Segmenter, train_classifier, train_segmenter
import matplotlib.pyplot as plt
from sklearn.metrics import roc_curve, auc, confusion_matrix
import seaborn as sns


def plot_roc_curve(y_true, y_scores):
    """
    Plot the ROC curve for a binary classifier.
    
    Parameters:
    - y_true: array-like of shape (n_samples,)
      True binary labels (0 or 1).
    - y_scores: array-like of shape (n_samples,)
      Predicted scores or probabilities for the positive class (1).
    """
    fpr, tpr, _ = roc_curve(y_true, y_scores)
    roc_auc = auc(fpr, tpr)

    plt.figure()
    plt.plot(fpr, tpr, label=f"ROC curve (area = {roc_auc:.2f})")
    plt.plot([0, 1], [0, 1], "k--", label="Random Guess")
    plt.xlim([0.0, 1.0])
    plt.ylim([0.0, 1.05])
    plt.xlabel("False Positive Rate")
    plt.ylabel("True Positive Rate")
    plt.title("Receiver Operating Characteristic (ROC) Curve")
    plt.legend(loc="lower right")
    save_path = Path(__file__).parent.parent.parent / "results"  # T3.4-PV-identification
    save_path.mkdir(exist_ok=True)
    plt.savefig(save_path / "ROC.png")
    plt.close()

def plot_confusion_matrix(y_true, y_pred):
    """
    Plot the confusion matrix for a binary classifier.
    
    Parameters:
    - y_true: array-like of shape (n_samples,)
      True binary labels (0 or 1).
    - y_pred: array-like of shape (n_samples,)
      Predicted binary labels (0 or 1).
    """
    cm = confusion_matrix(y_true, y_pred)
    sns.heatmap(cm, annot=True, fmt="d", cmap="Blues", cbar=False)
    plt.xlabel("Predicted Label")
    plt.ylabel("True Label")
    plt.title("Confusion Matrix")
    save_path = Path(__file__).parent.parent.parent / "results"  # T3.4-PV-identification
    save_path.mkdir(exist_ok=True)    
    plt.savefig(save_path / "Confusion_Matrix.png")
    plt.close()



class RunTask:

    @staticmethod
    def make_masks(data_folder=Path(__file__).parent.parent / "data"):
        """Saves masks for each .tif image in the raw dataset. Masks are saved
        in  <org_folder>_mask/<org_filename>.npy where <org_folder> should be the
        city name, as defined in `data/README.md`.

        Parameters
        ----------
        data_folder: pathlib.Path
            Path of the data folder, which should be set up as described in `data/README.md`
        """
        mask_maker = MaskMaker(data_folder=data_folder)
        mask_maker.process()

    @staticmethod
    def split_images(data_folder=Path(__file__).parent.parent / "data", imsize=224, empty_ratio=2):
        """Generates images (and their corresponding masks) of height = width = imsize
        for input into the models.

        Parameters
        ----------
        data_folder: pathlib.Path
            Path of the data folder, which should be set up as described in `data/README.md`
        imsize: int, default: 224
            The size of the images to be generated
        empty_ratio: int, default: 2
            The ratio of images without solar panels to images with solar panels.
            Because images without solar panels are randomly sampled with limited
            patience, having this number slightly > 1 yields a roughly 1:1 ratio.
        """
        splitter = ImageSplitter(data_folder=data_folder)
        splitter.process(imsize=imsize, empty_ratio=empty_ratio)

    @staticmethod
    def train_classifier(max_epochs=100, 
                         warmup=2, 
                         patience=5, 
                         val_size=0.1,
                         test_size=0.1, 
                         data_folder=Path(__file__).parent.parent / "data",
                         device=torch.device('cuda:0' if torch.cuda.is_available() else 'cpu',),
                         retrain: bool = False
                         ):
        """Train the classifier

        Parameters
        ----------
        max_epochs: int, default: 100
            The maximum number of epochs to train for
        warmup: int, default: 2
            The number of epochs for which only the final layers (not from the ResNet base)
            should be trained
        patience: int, default: 5
            The number of epochs to keep training without an improvement in performance on the
            validation set before early stopping
        val_size: float < 1, default: 0.1
            The ratio of the entire dataset to use for the validation set
        test_size: float < 1, default: 0.1
            The ratio of the entire dataset to use for the test set
        data_folder: pathlib.Path
            Path of the data folder, which should be set up as described in `data/README.md`
        device: torch.device, default: cuda if available, else cpu
            The device to train the models on
        """

        model_dir = data_folder / 'models'
        model_path = model_dir / 'classifier.model'

        model = Classifier()
        if retrain:
            model.load_state_dict(torch.load(model_path, map_location=device))
            model_name = "classifier_retrained.model"
        else:
            model_name = "classifier.model"
        
        if device.type != 'cpu': model = model.cuda()

        if retrain:
            processed_folder = Path(__file__).parent.parent / "new_data" / "processed"
        else:
            processed_folder = data_folder / 'processed'
        dataset = ClassifierDataset(processed_folder=processed_folder, transform_images=True)

        # make a train and val set
        train_mask, val_mask, test_mask = make_masks(len(dataset), val_size, test_size)

        dataset.add_mask(train_mask)
        train_dataloader = DataLoader(dataset, batch_size=64, shuffle=True)
        val_dataloader = DataLoader(ClassifierDataset(mask=val_mask,
                                                      processed_folder=processed_folder,
                                                      transform_images=False),
                                    batch_size=64, shuffle=True)
        test_dataloader = DataLoader(ClassifierDataset(mask=test_mask,
                                                       processed_folder=processed_folder,
                                                       transform_images=False),
                                     batch_size=64)

        train_classifier(model, train_dataloader, val_dataloader, max_epochs=max_epochs,
                         warmup=warmup, patience=patience)


        if not model_dir.exists(): model_dir.mkdir()
        torch.save(model.state_dict(), model_dir / model_name)

        # save predictions for analysis
        print("Generating test results")
        preds, true = [], []
        with torch.no_grad():
            for test_x, test_y in tqdm(test_dataloader):
                test_preds = model(test_x)
                preds.append(test_preds.squeeze(1).cpu().numpy())
                true.append(test_y.cpu().numpy())

        np.save(model_dir / f'{model_name.split(".")[0]}_preds.npy', np.concatenate(preds))
        np.save(model_dir / f'{model_name.split(".")[0]}_true.npy', np.concatenate(true))      

    @staticmethod
    def train_segmenter(max_epochs=100, val_size=0.1, test_size=0.1, warmup=2,
                        patience=5, data_folder=Path(__file__).parent.parent / "data", use_classifier=True,
                        device=torch.device('cuda:0' if torch.cuda.is_available() else 'cpu')):
        """Train the segmentation model

        Parameters
        ----------
        max_epochs: int, default: 100
            The maximum number of epochs to train for
        warmup: int, default: 2
            The number of epochs for which only the final layers (not from the ResNet base)
            should be trained
        patience: int, default: 5
            The number of epochs to keep training without an improvement in performance on the
            validation set before early stopping
        val_size: float < 1, default: 0.1
            The ratio of the entire dataset to use for the validation set
        test_size: float < 1, default: 0.1
            The ratio of the entire dataset to use for the test set
        data_folder: pathlib.Path
            Path of the data folder, which should be set up as described in `data/README.md`
        use_classifier: boolean, default: True
            Whether to use the pretrained classifier (saved in data/models/classifier.model by the
            train_classifier step) as the weights for the downsampling step of the segmentation
            model
        device: torch.device, default: cuda if available, else cpu
            The device to train the models on
        """
        model = Segmenter()
        if device.type != 'cpu': model = model.cuda()

        model_dir = data_folder / 'models'
        if use_classifier:
            classifier_sd = torch.load(model_dir / 'classifier.model')
            model.load_base(classifier_sd)
        processed_folder = data_folder / 'processed'
        dataset = SegmenterDataset(processed_folder=processed_folder)
        train_mask, val_mask, test_mask = make_masks(len(dataset), val_size, test_size)

        dataset.add_mask(train_mask)
        train_dataloader = DataLoader(dataset, batch_size=64, shuffle=True)
        val_dataloader = DataLoader(SegmenterDataset(mask=val_mask,
                                                     processed_folder=processed_folder,
                                                     transform_images=False),
                                    batch_size=64, shuffle=True)
        test_dataloader = DataLoader(SegmenterDataset(mask=test_mask,
                                                      processed_folder=processed_folder,
                                                      transform_images=False),
                                     batch_size=64)

        train_segmenter(model, train_dataloader, val_dataloader, max_epochs=max_epochs,
                        warmup=warmup, patience=patience)

        if not model_dir.exists(): model_dir.mkdir()
        torch.save(model.state_dict(), model_dir / 'segmenter.model')

        print("Generating test results")
        images, preds, true = [], [], []
        with torch.no_grad():
            for test_x, test_y in tqdm(test_dataloader):
                test_preds = model(test_x)
                images.append(test_x.cpu().numpy())
                preds.append(test_preds.squeeze(1).cpu().numpy())
                true.append(test_y.cpu().numpy())

        np.save(model_dir / 'segmenter_images.npy', np.concatenate(images))
        np.save(model_dir / 'segmenter_preds.npy', np.concatenate(preds))
        np.save(model_dir / 'segmenter_true.npy', np.concatenate(true))

    def train_both(self, c_max_epochs=100, c_warmup=2, c_patience=5, c_val_size=0.1,
                   c_test_size=0.1, s_max_epochs=100, s_warmup=2, s_patience=5,
                   s_val_size=0.1, s_test_size=0.1, data_folder=Path(__file__).parent.parent / "data",
                   device=torch.device('cuda:0' if torch.cuda.is_available() else 'cpu')):
        """Train the classifier, and use it to train the segmentation model.
        """
        self.train_classifier(max_epochs=c_max_epochs, val_size=c_val_size, test_size=c_test_size,
                              warmup=c_warmup, patience=c_patience, data_folder=data_folder,
                              device=device)
        self.train_segmenter(max_epochs=s_max_epochs, val_size=s_val_size, test_size=s_test_size,
                             warmup=s_warmup, patience=s_patience, use_classifier=True,
                             data_folder=data_folder, device=device)


    @staticmethod
    def classify_new_data(data_folder=Path(__file__).parent.parent / "new_data", 
                        device=torch.device('cuda:0' if torch.cuda.is_available() else 'cpu'),
                        retrained: bool=False,
                        labeled: bool = True,
                        ):
        """Predict on new data using the trained classifier model

        Parameters
        ----------
        data_folder: pathlib.Path
            Path of the folder containing the trained models (classifier or segmenter)
        new_data_folder: pathlib.Path
            Path of the folder containing the new images to predict on
        device: torch.device, default: cuda if available, else cpu
            The device to perform predictions on
        retrained: bool, default False, If the model was retrained with new data, saved and should be used
        labeled: bool, default True, If the data was labelled the labels will be used to check model accuracy
        train: bool, default False, The validation for accuracy is done based on data in different val folders, data that the model hasnt seen yet. If train=True 
        the same data which it was retrained on will be used in the ClassifierDataset. If the model has not been retrained, it doesnt matter
        """
        def save_as_png(target_folder: Path, file_path: Path):
            """saves the file under 'file_path' in the target folder as png """
            np_array = np.load(file_path)
            img = np.moveaxis(np_array, 0, -1) 
            img = Image.fromarray(img.astype('uint8'))
            img.save(target_folder / file_path.name.replace(".npy", ".png"))
        

        new_data_folder = data_folder / "processed"

        # Load the new data 
        classifier_dataset = ClassifierDataset(processed_folder=new_data_folder, labeled=labeled, train=False)

        new_dataloader = DataLoader(classifier_dataset, batch_size=64, shuffle=False)
        
        # Load the appropriate model based on the model_type parameter
        model_dir = Path(__file__).parent.parent / "data" / 'models'
        model = Classifier()
        if retrained:
            model_path = model_dir / 'classifier_retrained.model'
        else:
            model_path = model_dir / 'classifier.model'

        # Load the model's state_dict
        model.load_state_dict(torch.load(model_path, map_location=device))
        model.eval()  # Set model to evaluation mode
        
        if device.type != 'cpu': model = model.cuda()
        
        print("Generating test results")
        preds, true = [], []
        with torch.no_grad():
            for test_x, test_y in tqdm(new_dataloader):
                test_preds = model(test_x)
                preds.append(test_preds.squeeze(1).cpu().numpy().round())
                true.append(test_y.cpu().numpy())

        # real_labels = classifier_dataset.y.cpu().numpy()
        predicted = np.concatenate(preds)
        
        # Save predictions for analysis
        np.save(model_dir / f'{model_path.name.split(".")[0]}_new_preds.npy', predicted)
        building_ids = [f'{f.name.replace(".npy", "")}' for f in classifier_dataset.x_files]
        # save the predictions to a csv file:
        df = pd.DataFrame({
            'OSM_ID': building_ids,    
            'prediction': predicted   
        })
        (data_folder.parent.parent / "results").mkdir(exist_ok=True)
        df.to_csv(data_folder.parent.parent / "results" / "Classifier_Results.csv", index=False, sep=";")

        
        if labeled:
            # save the wrongly identified etc in folders so they can be examined:
            not_identified_folder = new_data_folder.parent / "not_identified"
            wrongly_identified_folder = new_data_folder.parent / "wrong_identified"
            not_identified_folder.mkdir(exist_ok=True)
            wrongly_identified_folder.mkdir(exist_ok=True)
            # delete old images
            [f.unlink() for f in not_identified_folder.iterdir()]
            [f.unlink() for f in wrongly_identified_folder.iterdir()]

            true_labels = np.concatenate(true)  # true labels and real label
            comparison = true_labels == predicted
            print(f"identified {np.round(np.sum(comparison) / len(true_labels) * 100, 2)}% of roofs correctly")

            not_identified = 0
            wrong_indentified = 0
            for i, label in enumerate(true_labels):
                if label == 1 and predicted[i] == 0:
                    not_identified += 1
                    save_as_png(not_identified_folder, classifier_dataset.x_files[i])
                if label == 0 and predicted[i] == 1:
                    wrong_indentified += 1
                    save_as_png(wrongly_identified_folder, classifier_dataset.x_files[i])

            print(f"False negative: {np.round(not_identified / true_labels.sum() * 100, 2)} % ({not_identified}) of all PVs ({true_labels.sum()}) were not identified")
            print(f"False positive: {np.round(wrong_indentified / (len(predicted)-true_labels.sum()) * 100, 2)}%  ({wrong_indentified}) of all buildings without PV ({len(predicted)-true_labels.sum()}) were identified wrongly of having PV")
            np.save(model_dir / f'{model_path.name.split(".")[0]}_new_true.npy', np.concatenate(true))

            plot_roc_curve(y_true=true_labels, y_scores=predicted)
            plot_confusion_matrix(y_true=true_labels, y_pred=predicted)




    @staticmethod
    def segment_new_data(data_folder=Path(__file__).parent.parent / "new_data",
                         device=torch.device('cuda:0' if torch.cuda.is_available() else 'cpu')):
              
        """Predict on new data using the trained segmenter model

        Parameters
        ----------
        data_folder: pathlib.Path
            Path of the folder containing the trained models (segmenter)
        new_data_folder: pathlib.Path
            Path of the folder containing the new images to predict on
        device: torch.device, default: cuda if available, else cpu
            The device to perform predictions on
        """

        new_data_folder = data_folder / "processed"

        segmenter_dataset = SegmenterDataset(processed_folder=new_data_folder, transform_images=False)
        new_dataloader = DataLoader(segmenter_dataset, batch_size=64)
        
        # Load the appropriate model based on the model_type parameter
        model_dir = Path("data") / 'models'
        model_type = "Segmenter"
        model = Segmenter()
        model_path = model_dir / 'segmenter.model'

        # Load the model's state_dict
        model.load_state_dict(torch.load(model_path, map_location=device))
        model.eval()  # Set model to evaluation mode
        
        if device.type != 'cpu': model = model.cuda()
            
        print("Generating test results")
        images, preds, true = [], [], []
        # we dont have masks for these pictures to evaluate the model but the images with the predicted areas will be saved for 
        # later manual inspection
        with torch.no_grad():
            for test_x, _ in tqdm(new_dataloader):
                test_preds = model(test_x)
                images.append(test_x.cpu().numpy())
                preds.append(test_preds.cpu().numpy())

        identified_folder = Path(__file__).parent.parent / "new_data" / "identified"
        identified_folder.mkdir(exist_ok=True)

        # all_images = np.concatenate(images)
        # all_images = (all_images * 255).astype('uint8')  # Scale to [0, 255] and convert to uint8
        # rearanged_imgs = [np.moveaxis(i, 0, -1) for i in all_images]  # Rearrange (bands, x, y) to (x, y, bands)
        # new_images = [Image.fromarray(img.astype('uint8')) for img in rearanged_imgs]  # Convert to unsigned 8-bit integer format

        # predicted masks of the PV
        pred_images = np.concatenate(preds)
        all_preds = (pred_images * 255).astype('uint8')  
        mask_rgb = [np.repeat(i, 3, axis=0) for i in all_preds]
        rearanged_preds= [np.moveaxis(i, 0, -1) for i in mask_rgb]  # Rearrange (bands, x, y) to (x, y, bands)
        new_preds = [Image.fromarray(img.astype('uint8')) for img in rearanged_preds]  # Convert to unsigned 8-bit integer format

        for i, img in enumerate(new_preds):
            imgg = Image.fromarray(np.moveaxis(np.load(segmenter_dataset.org_solar_files[i]), 0, -1))
            # put images side by side to be able to check performance manually
            new_img = Image.new('RGB', (224*2, 224))
            new_img.paste(imgg, (0, 0))  # Paste image1 at the left
            new_img.paste(img, (224, 0))
            new_img.save(identified_folder / f'predicted_{segmenter_dataset.org_solar_files[i].name.replace("npy", "png")}')



        # Save predictions for analysis
        np.save(model_dir / f'{model_type}_new_preds.npy', np.concatenate(preds))
        np.save(model_dir / f'{model_type}_new_true.npy', np.concatenate(true))
        torch.cuda.empty_cache()
        print(f"Predictions saved in {model_dir}")