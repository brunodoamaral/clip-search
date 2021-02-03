# coding: utf-8
import json
import numpy as np
from tqdm import tqdm
from pathlib import Path, PurePosixPath
import re
from flask import Flask, request, url_for, jsonify, redirect, Response, send_from_directory
from PIL import Image
from itertools import chain
from torch.utils.data import Dataset, DataLoader
from torchvision.transforms import Compose, Resize, CenterCrop, ToTensor, Normalize
import os
import argparse
from indexer import ImagesIndexer

IMAGES_PREFIX_URL = PurePosixPath('/images')
THUMBS_PREFIX_URL = PurePosixPath('/thumb')
MAX_TOP_N = 100
ROUND_NUM = 1_000_000

############ Helper functions ############

def round_float(x):
    # TODO: make round num work
    return float(x) # round(x * ROUND_NUM) / ROUND_NUM)


def emb_to_list(emb):
    if emb.ndim == 2:
        assert emb.shape[0] == 1, 'Multidimension embedding: ' + str(emb.shape)
        emb = emb[0]

    return list(map(round_float, emb))

################ Flask app ###############

app = Flask(
    __name__,
        static_url_path='/', 
        static_folder='./frontend/public/'
)

@app.route('/hello', methods=['GET', 'POST'])
def ping():
    return 'pong'


@app.route('/get-embedding', methods=['POST', 'GET'])
def get_embedding():
    results = {}

    if request.method == 'POST':
        uploaded_files = request.files.getlist("fileToUpload[]")
        for file in uploaded_files:
            emb = INDEX.encode_image(Image.open(file.stream))
            results[file.filename] = emb_to_list(emb)
        results['_mean_'] = emb_to_list(np.mean(list(results.values()), 0))
    else:
        if 'prompt' in request.args:
            emb = INDEX.encode_prompt(request.args['prompt'])
            results = emb_to_list(emb)
        
        elif 'src_image' in request.args:
            src_image = Path(request.args['src_image']).relative_to(IMAGES_PREFIX_URL)

            if '..' not in str(src_image):
                path_image = images_path / src_image
                if path_image.exists():
                    emb = INDEX.encode_image(Image.open(path_image))
                    results = emb_to_list(emb)

    return jsonify(results)


@app.route('/search', methods=['POST'])
def do_the_magic():
    # Read request objects
    params = request.get_json()
    top_n = params.get('num-results', '100')
    top_n = min(MAX_TOP_N, int(top_n))
    
    query = np.array(params['query'], dtype=np.float32)[np.newaxis]
    query_excludes = set(params.get('query_excludes', []))
                
    similarity, query_result, query_fnames = INDEX.search(query, top_n + len(query_excludes))
    similarity = similarity[0]
    query_result = query_result[0]
    query_fnames = query_fnames[0]
    
    pre_result_dict = [
        {
            'fname': str(IMAGES_PREFIX_URL / f),
            'thumb': str(THUMBS_PREFIX_URL / f)
        }
        for f in query_fnames
    ]
    
    result_dict = []
    for result, sim in zip(pre_result_dict, similarity):
        if result['fname'] not in query_excludes:
            result['similarity'] = float(sim)
            result_dict.append(result)
            
        # Limit results
        if len(result_dict) == top_n:
            break
    
    return jsonify(result_dict)


@app.route(str(IMAGES_PREFIX_URL / '<path:path>'))
def send_image(path):
    return send_from_directory(images_path, path)


@app.route(str(THUMBS_PREFIX_URL / '<path:path>'))
def send_thumb(path):
    return  Response(INDEX.thumbnail(path), mimetype='image/jpeg')


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('images_path', type=str, help='Path to images folder')
    parser.add_argument('-p', '--port', type=int, help='Port to start server', default=5000)
    parser.add_argument('-s', '--host', type=str, help='Host to start server', default='0.0.0.0')
    parser.add_argument('--debug', help='Host to start server', default=False, action='store_true')

    args = parser.parse_args()

    images_path = Path(args.images_path)

    INDEX = ImagesIndexer(images_path)

    app.run(host=args.host, port=args.port, debug=args.debug)
