
import json
import mmap

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
        print('Loading thumbs...')
        if not hasattr(self, 'thumb_index'):
            with open(self.thumb_index_file_path, 'r') as f:
                self.thumb_index = json.load(f)

            self.thumb_f = open(self.thumb_file_path, 'r')
            self.thumb_data = mmap.mmap(self.thumb_f.fileno(), 0, prot=mmap.PROT_READ)

    def thumbnail(self, fname):
        self._load()

        begin, end = self.thumb_index.get(fname, [0, 0])

        return self.thumb_data[begin:end]
