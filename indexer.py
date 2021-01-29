# coding: utf-8
import sys

sys.path.append("./CLIP/")
import json
import os
from itertools import chain
from pathlib import Path

import clip
import numpy as np
import torch
from PIL import Image
from torch.utils.data import DataLoader, Dataset
from torchvision.utils import save_image
from torchvision.transforms import CenterCrop, Compose, Normalize, Resize, ToTensor
from tqdm import tqdm

EXTENSIONS_LIST = ["*.jpg", "*.png", "*.jpeg"]

class ImagesDataset(Dataset):
    def __init__(self, images_path, images_files, preprocess, input_resolution):
        super().__init__()
        self.images_files = images_files
        self.preprocess = preprocess
        self.empty_image = torch.zeros(3, input_resolution, input_resolution)
        self.images_path = images_path

    def __len__(self):
        return len(self.images_files)

    def __getitem__(self, index):
        raw_fname = self.images_files[index]
        fname = self.images_path / raw_fname

        try:
            image = self.preprocess(Image.open(fname))
        except:
            image = self.empty_image

        return image, str(raw_fname)


def to_rgb(image):
    return image.convert("RGB")


class ThumbnailsAppender():
    def __init__(self, thumbnail):
        self.thumbnail = thumbnail
        self.thumb_file_path = self.thumbnail.thumb_file_path
        self.thumb_index_file_path = self.thumbnail.thumb_index_file_path

    def __enter__(self):
        self.thumb_file = open(self.thumb_file_path, 'w')
        self.thumb_index_file = open(self.thumb_index_file_path, 'w')
        self.begin_last_file = 0
        self.last_file_name = None

        # Start dictionary
        self.thumb_index_file.write('{')

        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self._write_last_file()
        self.thumb_index_file.write('}')

        self.thumb_file.close()
        self.thumb_index_file.close()

    def _write_last_file(self):
        if self.last_file_name is not None:
            if self.begin_last_file > 0:
                self.thumb_index_file.write(',')

            end_last_file = self.thumb_file.tell()
            self.thumb_index_file.write(f'"{self.last_file_name}":[{self.begin_last_file}, {end_last_file}]')

            self.begin_last_file = end_last_file

    def append(self, fname):
        # Write to index
        self._write_last_file()

        self.last_file_name = fname

        return self.thumb_file


class Thumbnails():
    def __init__(self, root_path):
        self.root_path = root_path
        self.thumb_file_path = root_path / 'thumbs.data'
        self.thumb_index_file_path = root_path / 'thumbs.index'

    def appender(self):
        return ThumbnailsAppender(self)

    def _load(self):
        if not hasattr(self, 'thumb_index'):
            with open(self.thumb_index_file_path, 'r') as f:
                self.thumb_index = json.load(f)

            self.thumb_data = np.memmap(self.thumb_file_path, np.uint8, mode='r')

    def thumbnail(self, fname):
        self._load()

        begin, end = self.thumb_index.get(fname, [0, 0])

        return self.thumb_data[begin:end].tobytes()


class ImagesIndexer:
    def __init__(self, images_path):
        self.images_path = Path(images_path)
        assert (
            images_path.exists()
        ), f"Image folder {images_path.resolve().absolute()} does not exist"

        self.index_base_path = images_path / ".index"
        self.index_path = self.index_base_path / "index.npy"
        self.images_files_path = self.index_base_path / "files.json"
        self.thumbs = Thumbnails(self.index_base_path)


        print("Listing files...")
        self.images_files = sorted(
            map(str, chain(*map(self._rglob_extension, EXTENSIONS_LIST)))
        )
        print("{} images found".format(len(self.images_files)))

        # CLIP
        self.device = "cuda" if torch.cuda.is_available() else "cpu"
        print(f"Torch will use self.device: {self.device}")

        print("Loading CLIP model...")
        self.model, _ = clip.load("ViT-B/32", device=self.device)
        # self.model, preprocess = clip.load("RN50", device=self.device)

        self.model.eval()

        self.input_resolution = self.model.input_resolution.item()
        self.output_dim = self.model.encode_image(
            torch.zeros(1, 3, self.input_resolution, self.input_resolution)
        ).shape[1]
        self.context_length = self.model.context_length.item()

        self.preprocess_image = Compose(
            [
                Resize(self.input_resolution, interpolation=Image.BICUBIC),
                CenterCrop(self.input_resolution),
                to_rgb,
                ToTensor(),
            ]
        )

        self.normalize_image = Compose(
            [
                Normalize(
                    (0.48145466, 0.4578275, 0.40821073),
                    (0.26862954, 0.26130258, 0.27577711),
                ),
            ]
        )

        self.index = None

        # Try to load from cache
        if self.index_path.exists() and self.images_files_path.exists():
            # Load images paths used to build the index
            with open(self.images_files_path) as f:
                images_files_on_index = json.load(f)

            # Compare previous list with current one
            if len(images_files_on_index) == len(self.images_files) and all(
                str(f1) == str(f2)
                for f1, f2 in zip(images_files_on_index, self.images_files)
            ):
                print(f"Loading index from cache: {self.index_path}")
                self.index = np.load(self.index_path)
            else:
                print(
                    "Images used in previous index had changed. Will generate a new one."
                )

        if self.index is None:
            # Build index
            ds = ImagesDataset(
                images_path, self.images_files, self.preprocess_image, self.input_resolution
            )
            dl = DataLoader(
                ds, batch_size=64, shuffle=False, num_workers=os.cpu_count()
            )

            print("Building index with CLIP. It may take a while...")
            self.index = []

            with self.thumbs.appender() as appender:
                for images, fnames in tqdm(dl, file=sys.stdout, bar_format="{l_bar}{bar}{r_bar}"):
                    # Images are not normalized yet. Save thumbnails
                    for image, fname in zip(images, fnames):
                        save_image(image, appender.append(fname), format='JPEG')

                    # Normalize images before input
                    images = self.normalize_image(images)
                    with torch.no_grad():
                        emb_images = self.model.encode_image(images)
                        emb_images = emb_images.cpu().float().numpy()
                    self.index.append(emb_images)

            # Save results
            self.index_base_path.mkdir(exist_ok=True)
            self.index = np.concatenate(self.index)
            self.index /= np.linalg.norm(self.index, axis=-1, keepdims=True)
            np.save(self.index_path, self.index)

            with open(self.images_files_path, "w") as f:
                json.dump(self.images_files, f)

    def _rglob_extension(self, extension):
        for fname in self.images_path.rglob(extension):
            yield fname.relative_to(self.images_path)


    def search(self, query, top_n):
        # Normalize query
        query = query / np.linalg.norm(query, axis=-1, keepdims=True)

        unsorted_similarity = (self.index @ query.T).T

        # Take top_n unsorted indexes (but fast method!)
        unsorted_query_result = np.argpartition(unsorted_similarity, -top_n, axis=-1)[
            :, -top_n:
        ][:, ::-1]

        # Sort only top_n results
        query_result = np.take(
            unsorted_query_result,
            np.argsort(np.take(unsorted_similarity, unsorted_query_result), axis=-1)[
                :, ::-1
            ],
        )

        similarity = unsorted_similarity.take(query_result)
        query_fnames = [[self.images_files[i] for i in result] for result in query_result]

        return similarity, query_result, query_fnames

    def encode_prompt(self, prompt, normalize=False):
        text = clip.tokenize([prompt]).to(self.device)
        with torch.no_grad():
            emb_text = self.model.encode_text(text).float()

            if normalize:
                emb_text /= emb_text.norm(dim=-1, keepdim=True)

        return emb_text.cpu().numpy()

    def encode_image(self, img, normalize=False):
        image = self.normalize_image(self.preprocess_image(img)).unsqueeze(0).to(self.device)

        with torch.no_grad():
            image_features = self.model.encode_image(image).float()

        if normalize:
            image_features /= image_features.norm(dim=-1, keepdim=True)

        return image_features.cpu().numpy()

    def thumbnail(self, fname):
        return self.thumbs.thumbnail(fname)