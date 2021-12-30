# coding: utf-8
import argparse
from pathlib import Path, PurePosixPath

import numpy as np
from flask import Flask, Response, jsonify, request, send_from_directory
from PIL import Image

from indexer import ImagesIndexer
import requests

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
    return Response(INDEX.thumbnail(path), mimetype='image/jpeg')


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('images_path', type=str, help='Path to images folder')
    parser.add_argument('--rotation-invariant', help='Average embeddings of 4 rotations on image inputs', default=False, action='store_true')
    parser.add_argument('-p', '--port', type=int, help='Port to start server', default=5000)
    parser.add_argument('-s', '--host', type=str, help='Host to start server', default='0.0.0.0')
    parser.add_argument('--dev', help='Start in dev mode', default=False, action='store_true')

    args = parser.parse_args()

    images_path = Path(args.images_path)
    rotation_invariant = args.rotation_invariant

    INDEX = ImagesIndexer(images_path, do_rotate_images=rotation_invariant)

    # Add dev env
    if args.dev:
        print('Go to ./frontend folder and run: npm install && npm run dev')

        @app.route('/', methods=['GET', 'POST'])
        def _proxy(*args, **kwargs):
            resp = requests.request(
                method=request.method,
                url=request.url.replace(request.host_url, 'http//localhost:8000'),
                headers={key: value for (key, value) in request.headers if key != 'Host'},
                data=request.get_data(),
                cookies=request.cookies,
                allow_redirects=False)

            excluded_headers = ['content-encoding', 'content-length', 'transfer-encoding', 'connection']
            headers = [(name, value) for (name, value) in resp.raw.headers.items()
                    if name.lower() not in excluded_headers]

            response = Response(resp.content, resp.status_code, headers)
            return response



    app.run(host=args.host, port=args.port, debug=args.dev)
