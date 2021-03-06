import os, sys, inspect
import argparse
import time
import logging as log
from socket import timeout as TimeoutError
from socket import error as SocketError
import http
from ssl import CertificateError

import urllib
from urllib.parse import urlparse, urlencode, urlunparse
from urllib.request import urlopen
from imagenet.conf.apikeys import imagenet_username, imagenet_accesskey

# add parent dir to system dir
CURR_DIR = os.path.dirname(os.path.abspath(inspect.getfile(inspect.currentframe())))
ROOT_DIR = os.path.dirname(CURR_DIR)
sys.path.insert(0, ROOT_DIR)


class DownloadError(Exception):
    def __init__(self, message=""):
        self.message = message


class ImagenetDownloader(object):

    def __init__(self,
                 path,
                 timeout=10,
                 retry=2,
                 sleep=0.8,
                 input_encoding=None,
                 synset_wnids_url=None,
                 synset_maps_url=None,
                 synset_original_url=None,
                 verbose=True,):

        self.path = path
        self._input_encoding = input_encoding
        if synset_wnids_url is None:
            synset_wnids_url = "http://www.image-net.org/api/text/imagenet.synset.obtain_synset_list"
        self._synset_wnids_url = synset_wnids_url
        if synset_maps_url is None:
            synset_maps_url = "http://image-net.org/archive/words.txt"
        self._synset_maps_url = synset_maps_url
        if synset_original_url is None:
            synset_original_url = "http://www.image-net.org/download/synset"
        self._synset_original_url = synset_original_url

        self.timeout = timeout
        self.retry = retry
        self.sleep = sleep

        self.verbose = verbose
        if self.verbose:
            log.basicConfig(format="%(levelname)s: %(message)s", level=log.DEBUG)
        else:
            log.basicConfig(format="%(levelname)s: %(message)s")
        # self.verboseprint = print if self.verbose else lambda *a, **k: None

        self.get_wnid_list()
        self.get_wnid_maps()

    def get_wnids(self, filename=None, release="latest", src="stanford"):
        if not self.path:
            os.mkdir(os.path.join(self.path))
        else:
            log.info(f"Appending over to {self.path}. The out path already exists!")

        if filename is None:
            filename = os.path.join(CURR_DIR, "data", "int", "synset_list.txt")

        with open(filename, "rb") as f:
            cnt = 0
            while True:
                line = f.readline()
                cnt += 1
                if line.strip():
                    wnid = str(line.decode().strip())
                    self.get_wnid(wnid=wnid, release=release, src=src)
                if not line:
                    break

    def get_wnid(self, wnid, release="latest", src="stanford"):

        params = dict(
            wnid=wnid,
            username=imagenet_username,
            accesskey=imagenet_accesskey,
            release=release,
            src=src
        )
        filename = os.path.join(self.path, wnid + ".tar")

        if not os.path.isfile(filename):
            log.info(f"Downloading WNDI '{wnid}'..")
            url = self.build_url(self._synset_original_url + "?", params_extra=params)
            content = self.download_wnid(url)

            with open(filename, "wb") as f:
                f.write(content)
        else:
            log.info(f"Skipping WNID '{wnid}'. The tar file already exists!")
        return filename

    def download_wnid(self, url):
        count = 0
        while True:
            try:
                f = urllib.request.urlopen(url, timeout=self.timeout)
                if f is None:
                    raise DownloadError('Cannot open URL' + url)
                content = f.read()
                f.close()
                break
            except (urllib.error.HTTPError, http.client.HTTPException, CertificateError) as e:
                count += 1
                if count > self.retry:
                    raise DownloadError()
            except (urllib.error.URLError, TimeoutError, SocketError, IOError) as e:
                count += 1
                if count > self.retry:
                    raise DownloadError()
                time.sleep(self.sleep)
        return content

    def get_wnid_list(self):

        filename = os.path.join("imagenet", "data", "int", "synset_list.txt")
        if not os.path.isfile(filename):
            log.info("Downloading WNID list")
            response = urlopen(self._synset_wnids_url)
            with open(filename, 'wb') as f:
                for line in response:
                    if line.strip():
                        f.write(line)

    def get_wnid_maps(self):

        filename = os.path.join("imagenet", "data", "int", "synset_maps.txt")
        if not os.path.isfile(filename):
            log.info("Downloading WNID mapping list...")
            response = urlopen(self._synset_maps_url)
            with open(filename, 'wb') as f:
                for line in response:
                    if line.strip():
                        f.write(line)

    def build_url(self, url, components=None, params_extra=None):
        (scheme, netloc, path, params, query, fragment) = urlparse(url)
        if components:
            # filter components with None values
            c = [component for component in components if component]
            if not path.endswith("/"):
                path += "/"
            path += "/".join(c)

        if params_extra and len(params_extra)>0:
            query_extra = self._encode_params(params_extra)
            if query:
                query += query_extra
            else:
                query = query_extra

        return urlunparse((scheme, netloc, path, params, query, fragment))

    def _encode_params(self, params):

        if params is None:
            return None
        else:
            return urlencode(dict([(key, self._encode(value))
                                   for key, value in list(params.items()) if value is not None]))

    def _encode(self, value):
        if self._input_encoding:
            return str(value, self._input_encoding).encode("utf-8")
        else:
            return str(value).encode("utf-8")


def main(**args):
    imgnet_downloader = ImagenetDownloader(**args)
    imgnet_downloader.get_wnids()


if __name__ == '__main__':

    p = argparse.ArgumentParser()

    p.add_argument('--path',
                   "-p",
                   type=str,
                   default=os.path.join(CURR_DIR, "data", "ext", "imagenet"),
                   help='Output directory')
    p.add_argument('--timeout',
                   '-t',
                   type=float,
                   default=1000,
                   help='Timeout per request in seconds')
    p.add_argument('--retry',
                   '-r',
                   type=int,
                   default=0,
                   help='Max count of retry for each request')
    p.add_argument('--sleep',
                   '-s',
                   type=float,
                   default=0,
                   help='Sleep after download each image in second')
    p.add_argument('--synset_wnids_url',
                   '-w',
                   type=str,
                   default="http://www.image-net.org/api/text/imagenet.synset.obtain_synset_list",
                   help='TBA')
    p.add_argument('--synset_maps_url',
                   '-m',
                   type=str,
                   default="http://image-net.org/archive/words.txt",
                   help='TBA')
    p.add_argument('--synset_original_url',
                   '-o',
                   type=str,
                   default="http://www.image-net.org/download/synset",
                   help='TBA')
    p.add_argument('--verbose',
                   '-v',
                   default=True,
                   action='store_true',
                   help='Enable verbose messages')

    args = p.parse_args()

    main(path=args.path,
         timeout=args.timeout,
         retry=args.retry,
         sleep=args.sleep,
         synset_wnids_url=args.synset_wnids_url,
         synset_maps_url=args.synset_maps_url,
         synset_original_url=args.synset_original_url,
         verbose=args.verbose)
