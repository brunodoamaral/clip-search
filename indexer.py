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
from thumbs import Thumbnails
from threading import Thread
from queue import Queue 

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

class FileAppenderThread(Thread):
    def __init__(self, q:Queue, appender):
        super().__init__()
        self.q = q
        self.appender = appender

    def run(self):
        while True:
            image, fname = self.q.get()
            if image is None:
                break
            save_image(image, self.appender.append(fname), format='JPEG')

class ImagesIndexer:
    def __init__(self, images_path, do_rotate_images=False):
        self.images_path = Path(images_path)
        self.rotations = [0, 1, 2, 3] if do_rotate_images else [0]
        assert (
            images_path.exists()
        ), f"Image folder {images_path.resolve().absolute()} does not exist"

        self.index_base_path = images_path / ".index"
        self.index_path = self.index_base_path / ("index-rotation.npy" if do_rotate_images else "index.npy")
        self.images_files_path = self.index_base_path / "files.json"
        self.thumbs = Thumbnails(self.index_base_path)

        self.index_base_path.mkdir(exist_ok=True)

        print("Listing files...")
        self.images_files = sorted(
            map(str, chain(*map(self._rglob_extension, EXTENSIONS_LIST)))
        )
        print("{} images found".format(len(self.images_files)))

        # CLIP
        self.device = "cuda" if torch.cuda.is_available() else "cpu"
        print(f"Torch will use self.device: {self.device}")

        print("Loading CLIP model...")
        self.model, _ = clip.load("ViT-B/32", device=self.device, jit=False)
        # self.model, preprocess = clip.load("RN50", device=self.device)

        self.model.eval()

        self.input_resolution = self.model.visual.input_resolution
        self.output_dim = self.model.encode_image(
            torch.zeros(1, 3, self.input_resolution, self.input_resolution, device=self.device)
        ).shape[1]
        self.context_length = self.model.context_length

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
                ds, batch_size=32, shuffle=False, num_workers=os.cpu_count() // 4
            )

            print("Building index with CLIP. It may take a while...")
            self.index = []

            with self.thumbs.appender() as appender:
                q_thread = Queue(256)
                file_appender_thread = FileAppenderThread(q_thread, appender)
                file_appender_thread.start()

                for images, fnames in tqdm(dl, file=sys.stdout, bar_format="{l_bar}{bar}{r_bar}"):
                    # Images are not normalized yet. Save thumbnails
                    for image, fname in zip(images, fnames):
                        q_thread.put((image, fname))

                    # Normalize images before input
                    images = self.normalize_image(images).to(self.device)
                    with torch.no_grad():
                        emb_images = torch.stack([
                            self.model.encode_image(
                                torch.rot90(images, rotation, [-2, -1])
                            )
                            for rotation in self.rotations
                        ], 0).mean(0).cpu().float().numpy()
                    self.index.append(emb_images)

                # Signal thread to finish
                q_thread.put((None, None))
                file_appender_thread.join()

            # Save results
            self.index = np.concatenate(self.index)
            self.index /= np.linalg.norm(self.index, axis=-1, keepdims=True)
            np.save(self.index_path, self.index)

            with open(self.images_files_path, "w") as f:
                json.dump(self.images_files, f)

    def _rglob_extension(self, extension):
        for fname in chain.from_iterable([self.images_path.rglob(extension), self.images_path.rglob(extension.upper())]):
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
        image = self.normalize_image(self.preprocess_image(img)).to(self.device)

        # Apply rotation
        images_rot = torch.stack([
            torch.rot90(image, rotation, [-2, -1])
            for rotation in self.rotations
        ], 0)

        with torch.no_grad():
            image_features = self.model.encode_image(images_rot).float().mean(0)

        if normalize:
            image_features /= image_features.norm(dim=-1, keepdim=True)

        return image_features.cpu().numpy()

    def thumbnail(self, fname):
        return self.thumbs.thumbnail(fname)
