# CLIP-Search: Find Similar Images with OpenAI CLIP

Discover and explore similar images using the power of OpenAI CLIP with CLIP-Search. This demo project leverages the capabilities of OpenAI CLIP to provide a seamless and intuitive image search experience.

![Animated screenshot](clip-search.gif)

## Install

Getting started with CLIP-Search is easy. Simply follow these steps to install:

```bash
git clone --recursive https://github.com/brunodoamaral/clip-search.git
cd clip-search

python3 -m venv clip-env
clip-env/bin/pip3 install -r requirements.txt

clip-env/bin/python3 app.py /path/to/my/pictures
````

However, we strongly recommend installing with conda for a smoother experience:

```bash
git clone --recursive https://github.com/brunodoamaral/clip-search.git
cd clip-search

conda env create -n clip-env -f environment.yml
conda activate clip-env

python app.py /path/to/my/pictures
```

Once installed, simply open your browser and navigate to: http://localhost:5000/index.html

## Features:

### Drag and drop images

CLIP-Search allows you to search for similar images using text queries or by dragging and dropping one or more pictures into the search input. The tool intelligently "averages" the semantic features of the images to provide accurate and relevant search results.

### More/less like this

Refine your search with the "More Like This" and "Less Like This" buttons. These buttons provide hints to the search algorithm about the type of images you are looking for. When you click on any of these buttons, the corresponding image will be hidden from the search results, allowing you to curate and fine-tune your image search experience.
