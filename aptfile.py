try:
    from urllib2 import urlopen
except:
    from urllib.request import urlopen
import zlib
from io import BytesIO


def combine_with_slash(*itr):
    res = []
    for i in itr:
        res.append(i)
        if i[-1] != '/':
            res.append('/')
    del res[-1]
    return ''.join(res)


def parse_sources_list(stream, arch='amd64', ignore_stuff=True):
    urls = []
    for line in stream:
        line = line.decode()
        line = line.lstrip().rstrip()
        if not line.startswith('deb '):
            continue
        line = [x for x in line.split(' ') if x]
        # This stuff are not needed for package name resolving usually
        if ignore_stuff and ('updates' in line[2] or 'security' in line[2]):
            continue
        # For ubuntu
        url = combine_with_slash(line[1], 'dists', line[2], 'Contents-' + arch + '.gz')
        urls.append(url)
        # For debian
        url = combine_with_slash(line[1], 'dists', line[2], line[3], 'Contents-' + arch + '.gz')
        urls.append(url)
    return sorted(set(urls))


def get_contents_data(url):
    response = urlopen(url).read()
    dec = zlib.decompressobj(32 + zlib.MAX_WBITS)
    return dec.decompress(response)


def update(input_stream, output_stream=None, ignore_stuff=True):
    urls = parse_sources_list(input_stream, ignore_stuff=ignore_stuff)
    should_close = False if output_stream else True
    output_stream = output_stream or open('cache.db', 'wb')
    try:
        for url in urls:
            print(url)
            try:
                data = get_contents_data(url)
            except Exception as e:
                print(e)
                continue
            if data:
                output_stream.write(data)
    finally:
        if should_close:
            output_stream.close()


def find_packages(filenames, input_stream=None):
    fixed_filenames = set()
    for filename in set(filenames):
        if not isinstance(filename, bytes):
            filename = filename.encode()
        fixed_filenames.add(filename[1:])
        fixed_filenames.add(filename[1:] + b'/')

    packages = set()
    conflicts = set()
    should_close = False if input_stream else True
    input_stream = input_stream or open('cache.db', 'rb')
    try:
        for line in input_stream:
            data = line.rsplit(b' ', 1)
            filename = data[0].rstrip()
            as_dir = filename.rsplit(b'/', 1)[0]
            # TODO maybe remove last / in filename input ?
            if filename in fixed_filenames or as_dir in fixed_filenames:
                packagesname = data[1][:-1]
                packagesname = packagesname.split(b',')
                packagesname = [x.rsplit(b'/', 1)[1].decode() for x in packagesname]
                packagesname.sort()
                packagesname = tuple(packagesname)
                if len(packagesname) > 1:
                    conflicts.add(packagesname)
                packages.update(packagesname)
        return packages, conflicts
    finally:
        if should_close:
            input_stream.close()


if __name__ == "__main__":
    import sys

    if len(sys.argv) == 1:
        sys.stderr.write('Usage: %s update [sources.list file or - or empty for stdin]\n\n' % sys.argv[0])
        sys.stderr.write('Parse the sources.list repositories for indexing.\n\n')
        sys.stderr.write('Usage: %s find [file names to search or - or empty for stdin]\n\n' % sys.argv[0])
        sys.stderr.write('Search the indexed database for packages containing the filename.\n\n')
        sys.exit(1)
    if sys.argv[1] == 'update':
        if len(sys.argv) == 2 or sys.argv[2] == '-':
            update(sys.stdin)
        else:
            with open(sys.argv[2], 'rt') as f:
                update(sys.stdin)
    elif sys.argv[1] == 'find':
        if len(sys.argv) == 2 or sys.argv[2] == '-':
            files = [x[:-1] for x in sys.stdin]
        else:
            files = sys.argv[2:]
        for package in find_packages(files)[0]:
            print(package)
