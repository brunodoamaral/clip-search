# CLIP-Search

Your private semantic search. No cloud needed!

## Install

The easiest way to install is as follow:

```bash
git clone https://github.com/brunodoamaral/clip-search.git
cd clip-search
pip install -r requirements.txt
python app.py /path/to/my/pictures
````

But it is strongly advised to instal using conda:

```bash
conda create -n env-clip numpy pip pytorch torchvision -c pytorch -c main
conda activate env-clip
pip install -r requirements.txt
python app.py /path/to/my/pictures
```

Then point your browser to: http://localhost:5000/index.html

## Usage

The basic usage is to search by text. But you can drag one of more pictures to the search
input in order to find similar images. It will "average" the semantics of all images before
searching.

### More/less like this

Use these buttoms to give a hint to the search of which kind of images are you searching
for. Notice that once you click any of these buttoms, the image will be hidden from results.
