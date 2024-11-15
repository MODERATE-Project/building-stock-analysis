import numpy as np
import torch
from pathlib import Path
import random

from typing import Optional, List, Tuple

from .utils import normalize
from .transforms import no_change, horizontal_flip, vertical_flip, colour_jitter


class ClassifierDataset:

    def __init__(self,
                 processed_folder: Path,
                 normalize: bool = True, 
                 transform_images: bool = False,
                 device: torch.device = torch.device('cuda:0' if
                                                     torch.cuda.is_available() else 'cpu'),
                 mask: Optional[List[bool]] = None,
                 labeled: bool = True,
                 train: bool = True,
                 ) -> None:

        self.device = device
        self.normalize = normalize
        self.transform_images = transform_images
        if labeled and train:
            solar_files = list((processed_folder.parent / 'solar/org').glob("*.npy"))
            empty_files = list((processed_folder.parent / 'empty/org').glob("*.npy"))
            self.y = torch.as_tensor([1 for _ in solar_files] + [0 for _ in empty_files],
                                 device=self.device).float()
            self.x_files = solar_files + empty_files
        elif labeled and not train:
            solar_files = list((processed_folder.parent / 'solar/val').glob("*.npy"))
            empty_files = list((processed_folder.parent / 'empty/val').glob("*.npy"))
            self.y = torch.as_tensor([1 for _ in solar_files] + [0 for _ in empty_files],
                                 device=self.device).float()
            self.x_files = solar_files + empty_files
        else:
            files = list((processed_folder).glob("*.npy"))
            self.x_files = files
            self.y = torch.as_tensor([2 for _ in files], device=self.device).float()



        if mask is not None:
            self.add_mask(mask)

    def add_mask(self, mask: List[bool]) -> None:
        """Add a mask to the data
        """
        assert len(mask) == len(self.x_files), \
            f"Mask is the wrong size! Expected {len(self.x_files)}, got {len(mask)}"
        self.y = torch.as_tensor(self.y.cpu().numpy()[mask], device=self.device)
        self.x_files = [x for include, x in zip(mask, self.x_files) if include]

    def __len__(self) -> int:
        return self.y.shape[0]

    def _transform_images(self, image: np.ndarray) -> np.ndarray:
        transforms = [
            no_change,
            horizontal_flip,
            vertical_flip,
            colour_jitter,
        ]
        chosen_function = random.choice(transforms)
        return chosen_function(image)

    def __getitem__(self, index: int) -> Tuple[torch.Tensor, torch.Tensor]:
        y = self.y[index]
        x = np.load(self.x_files[index])
        if self.transform_images: x = self._transform_images(x)
        if self.normalize: x = normalize(x)
        return torch.as_tensor(x.copy(), device=self.device).float(), y
